import logging
import uuid
from datetime import datetime, timezone

from openai import AsyncAzureOpenAI

from app.config import AppConfig
from app.models.memory import Memory
from app.models.message import Message
from app.models.personality import Personality
from app.repositories.base import MemoryRepositoryBase, MessageRepositoryBase

logger = logging.getLogger(__name__)


class MemoryService:
    def __init__(
        self,
        config: AppConfig,
        memory_repo: MemoryRepositoryBase,
        message_repo: MessageRepositoryBase,
        client: AsyncAzureOpenAI,
    ) -> None:
        self._config = config
        self._memory_repo = memory_repo
        self._message_repo = message_repo
        self._client = client
        self._interval = config.memory_summarization_interval
        self._message_counts: dict[str, int] = {}

    def reset_counts(self) -> None:
        self._message_counts.clear()

    def get_count(self, personality_id: str) -> int:
        return self._message_counts.get(personality_id, 0)

    async def on_message(self, session_id: str, active_personality_ids: list[str], topic: str, personalities: dict[str, Personality]) -> None:
        for pid in active_personality_ids:
            self._message_counts[pid] = self._message_counts.get(pid, 0) + 1
            if self._message_counts[pid] >= self._interval:
                await self._update_memory(pid, session_id, topic, personalities.get(pid))
                self._message_counts[pid] = 0

    async def get_memory_text(self, personality_id: str) -> str:
        memory = await self._memory_repo.get_by_personality(personality_id)
        if memory is None:
            return ""
        return memory.memory_text

    async def _update_memory(self, personality_id: str, session_id: str, topic: str, personality: Personality | None) -> None:
        if personality is None:
            return

        existing = await self._memory_repo.get_by_personality(personality_id)
        existing_text = existing.memory_text if existing else "No previous memories."

        recent_messages = await self._message_repo.get_by_session(session_id, limit=self._interval * 2)
        conversation_text = "\n".join(
            f"[{m.sender_name}]: {m.content}" for m in recent_messages
        )

        prompt = (
            f"You are {personality.name}, a {personality.role}.\n"
            f"Topic being discussed: {topic}\n\n"
            f"Your previous memory:\n{existing_text}\n\n"
            f"Recent conversation:\n{conversation_text}\n\n"
            f"Update your memory with any new important facts, opinions, relationships, decisions, "
            f"or context from this conversation. Keep the memory concise (under 500 words). "
            f"Preserve important details from your previous memory. "
            f"Write in first person as notes to yourself."
        )

        try:
            response = await self._client.chat.completions.create(
                model=self._config.azure_openai_deployment,
                messages=[
                    {"role": "system", "content": f"You are a memory summarizer for {personality.name}."},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.3,
                max_completion_tokens=600,
            )

            new_memory_text = response.choices[0].message.content.strip()
            now = datetime.now(timezone.utc).isoformat()

            memory = Memory(
                id=existing.id if existing else str(uuid.uuid4()),
                personality_id=personality_id,
                memory_text=new_memory_text,
                last_updated=now,
            )
            await self._memory_repo.upsert(memory)
            logger.info(f"Updated memory for {personality.name}")

        except Exception as e:
            logger.error(f"Failed to update memory for {personality.name}: {e}")
