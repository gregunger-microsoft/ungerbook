import json
import logging
from dataclasses import dataclass
from typing import AsyncIterator, Optional

from openai import AsyncAzureOpenAI

from app.config import AppConfig
from app.models.message import Message
from app.models.personality import Personality

logger = logging.getLogger(__name__)


@dataclass
class RelevanceResult:
    personality_id: str
    should_respond: bool
    reason: str
    urgency: int


class PersonalityEngine:
    def __init__(self, config: AppConfig, client: AsyncAzureOpenAI) -> None:
        self._config = config
        self._client = client
        self._deployment = config.azure_openai_deployment

    def build_system_prompt(self, personality: Personality, topic: str, memory_text: Optional[str] = None) -> str:
        parts = [personality.system_prompt]
        parts.append(f"\nThe current discussion topic is: {topic}")
        if memory_text:
            parts.append(f"\nYour memory from past conversations:\n{memory_text}")
        parts.append(
            "\nCRITICAL RULES FOR THIS GROUP DISCUSSION:"
            "\n1. You are ONE voice in a multi-expert panel. Other experts will also respond."
            "\n2. NEVER repeat, rephrase, or summarize points already made by others in this conversation."
            "\n3. If someone already covered a topic, skip it entirely and focus on what ONLY YOU can add."
            f"\n4. Lead with YOUR unique perspective as a {personality.role}. Use your specific expertise: {personality.expertise_domain}."
            "\n5. If you agree with a prior point, say so briefly (one sentence) then add NEW information."
            "\n6. Keep responses under 150 words. Be concise and punchy."
            "\n7. Do not use bullet-point lists that look like every other response. Use your natural voice."
            "\n8. Do not prefix your response with your name."
            "\n9. Do not break character."
        )
        return "\n".join(parts)

    def build_context_messages(
        self,
        personality: Personality,
        topic: str,
        recent_messages: list[Message],
        memory_text: Optional[str] = None,
    ) -> list[dict]:
        system_prompt = self.build_system_prompt(personality, topic, memory_text)
        messages = [{"role": "system", "content": system_prompt}]

        for msg in recent_messages:
            if msg.sender_id == personality.id:
                messages.append({"role": "assistant", "content": msg.content})
            else:
                messages.append({"role": "user", "content": f"[{msg.sender_name}]: {msg.content}"})

        return messages

    async def check_relevance(
        self,
        personality: Personality,
        topic: str,
        recent_messages: list[Message],
        new_message: Message,
        memory_text: Optional[str] = None,
    ) -> RelevanceResult:
        conversation_text = "\n".join(
            f"[{m.sender_name}]: {m.content}" for m in recent_messages[-10:]
        )

        system_content = (
            f"You are {personality.name}, a {personality.role}. "
            f"Expertise: {personality.expertise_domain}. "
            f"Style: {personality.communication_style}."
        )
        if memory_text:
            system_content += f"\n\nYour memory from past conversations:\n{memory_text}"

        user_content = (
            f"Topic: {topic}\n\n"
            f"Recent conversation:\n{conversation_text}\n\n"
            f"A new message was just posted by [{new_message.sender_name}]: {new_message.content}\n\n"
            f"You are in a group discussion. If this is early in the conversation or a direct question "
            f"related to your expertise, you should almost always respond. "
            f"Do you have something valuable to add from your perspective as a {personality.role}? "
            f'Respond with ONLY a JSON object (no markdown, no code fences): '
            f'{{"should_respond": true, "reason": "one sentence", "urgency": 1-10}}'
        )

        try:
            response = await self._client.chat.completions.create(
                model=self._deployment,
                messages=[
                    {"role": "system", "content": system_content},
                    {"role": "user", "content": user_content},
                ],
                temperature=0.3,
                max_completion_tokens=100,
            )

            raw = response.choices[0].message.content.strip()
            logger.debug(f"Relevance raw response from {personality.name}: {raw}")
            # Strip markdown code fence if present
            if raw.startswith("```"):
                lines = raw.split("\n")
                raw = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])

            parsed = json.loads(raw)
            result = RelevanceResult(
                personality_id=personality.id,
                should_respond=bool(parsed.get("should_respond", False)),
                reason=str(parsed.get("reason", "")),
                urgency=int(parsed.get("urgency", 5)),
            )
            logger.info(f"Relevance for {personality.name}: respond={result.should_respond}, urgency={result.urgency}, reason={result.reason}")
            return result

        except (json.JSONDecodeError, KeyError, TypeError) as e:
            logger.warning(f"Relevance check parse error for {personality.name}: {e}")
            return RelevanceResult(
                personality_id=personality.id,
                should_respond=False,
                reason="Failed to parse relevance response",
                urgency=0,
            )
        except Exception as e:
            logger.error(f"Relevance check error for {personality.name}: {e}")
            return RelevanceResult(
                personality_id=personality.id,
                should_respond=False,
                reason=f"Error: {e}",
                urgency=0,
            )

    async def generate_response(
        self,
        personality: Personality,
        topic: str,
        recent_messages: list[Message],
        memory_text: Optional[str] = None,
    ) -> str:
        context = self.build_context_messages(personality, topic, recent_messages, memory_text)

        response = await self._client.chat.completions.create(
            model=self._deployment,
            messages=context,
            temperature=0.8,
            max_completion_tokens=500,
        )

        return response.choices[0].message.content.strip()

    async def generate_response_stream(
        self,
        personality: Personality,
        topic: str,
        recent_messages: list[Message],
        memory_text: Optional[str] = None,
    ) -> AsyncIterator[str]:
        context = self.build_context_messages(personality, topic, recent_messages, memory_text)

        stream = await self._client.chat.completions.create(
            model=self._deployment,
            messages=context,
            temperature=0.8,
            max_completion_tokens=500,
            stream=True,
        )

        async for chunk in stream:
            if chunk.choices and chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content
