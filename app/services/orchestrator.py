import asyncio
import json
import logging
import os
import random
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Callable, Awaitable, Optional

from app.config import AppConfig
from app.models.message import Message
from app.models.personality import Personality
from app.models.session import Session
from app.repositories.base import SessionRepositoryBase, MessageRepositoryBase
from app.services.memory_service import MemoryService
from app.services.personality_engine import PersonalityEngine, RelevanceResult

logger = logging.getLogger(__name__)

MessageCallback = Callable[[dict], Awaitable[None]]


@dataclass
class ConversationState:
    session: Optional[Session] = None
    personalities: dict[str, Personality] = field(default_factory=dict)
    muted: set[str] = field(default_factory=set)
    last_speaker_id: Optional[str] = None
    is_processing: bool = False
    is_paused: bool = False


class ConversationStrategy(ABC):
    @abstractmethod
    async def process_message(
        self,
        new_message: Message,
        state: ConversationState,
        engine: PersonalityEngine,
        memory_service: MemoryService,
        message_repo: MessageRepositoryBase,
        config: AppConfig,
        send_callback: MessageCallback,
    ) -> None:
        ...


class AutonomousStrategy(ConversationStrategy):
    async def process_message(
        self,
        new_message: Message,
        state: ConversationState,
        engine: PersonalityEngine,
        memory_service: MemoryService,
        message_repo: MessageRepositoryBase,
        config: AppConfig,
        send_callback: MessageCallback,
    ) -> None:
        eligible = get_eligible_personalities(state, new_message.sender_id)
        if not eligible:
            return

        recent = await message_repo.get_by_session(
            state.session.id, limit=config.max_context_messages
        )

        relevance_tasks = []
        for pid in eligible:
            p = state.personalities[pid]
            mem = await memory_service.get_memory_text(pid)
            relevance_tasks.append(
                engine.check_relevance(p, state.session.topic, recent, new_message, mem)
            )

        results = await asyncio.gather(*relevance_tasks, return_exceptions=True)

        want_to_respond: list[RelevanceResult] = []
        for r in results:
            if isinstance(r, Exception):
                logger.error(f"Relevance check exception: {r}")
            elif isinstance(r, RelevanceResult):
                logger.info(f"Relevance result: {r.personality_id} -> respond={r.should_respond}, urgency={r.urgency}")
                if r.should_respond:
                    want_to_respond.append(r)

        logger.info(f"Personalities wanting to respond: {len(want_to_respond)} / {len(eligible)}")
        queue = order_response_queue(want_to_respond, state.last_speaker_id)
        queue = apply_anti_flood(queue, config.max_ai_responses_per_round)

        await send_callback({"type": "thinking", "personality_ids": [r.personality_id for r in queue]})

        for result in queue:
            if state.is_paused:
                break

            pid = result.personality_id
            p = state.personalities[pid]
            mem = await memory_service.get_memory_text(pid)

            refreshed = await message_repo.get_by_session(
                state.session.id, limit=config.max_context_messages
            )

            if config.enable_streaming:
                chunks = []
                msg_id = str(uuid.uuid4())
                now = datetime.now(timezone.utc).isoformat()

                await send_callback({
                    "type": "stream_start",
                    "sender_id": pid,
                    "sender_name": p.name,
                    "avatar_color": p.avatar_color,
                    "msg_id": msg_id,
                })

                async for chunk in engine.generate_response_stream(p, state.session.topic, refreshed, mem):
                    chunks.append(chunk)
                    await send_callback({"type": "stream_chunk", "msg_id": msg_id, "content": chunk})

                full_content = "".join(chunks)
                await send_callback({"type": "stream_end", "msg_id": msg_id})
            else:
                full_content = await engine.generate_response(p, state.session.topic, refreshed, mem)
                now = datetime.now(timezone.utc).isoformat()
                msg_id = str(uuid.uuid4())

            ai_msg = Message(
                id=msg_id,
                session_id=state.session.id,
                sender_id=pid,
                sender_name=p.name,
                content=full_content,
                timestamp=now,
            )
            await message_repo.create(ai_msg)
            state.last_speaker_id = pid

            if not config.enable_streaming:
                await send_callback({
                    "type": "message",
                    "sender_id": pid,
                    "sender_name": p.name,
                    "role": p.role,
                    "content": full_content,
                    "avatar_color": p.avatar_color,
                    "timestamp": now,
                })

            await memory_service.on_message(
                state.session.id,
                list(state.personalities.keys()),
                state.session.topic,
                state.personalities,
            )

            if config.ai_response_delay_seconds > 0 and result != queue[-1]:
                await asyncio.sleep(config.ai_response_delay_seconds)


class RoundRobinStrategy(ConversationStrategy):
    async def process_message(
        self,
        new_message: Message,
        state: ConversationState,
        engine: PersonalityEngine,
        memory_service: MemoryService,
        message_repo: MessageRepositoryBase,
        config: AppConfig,
        send_callback: MessageCallback,
    ) -> None:
        eligible = get_eligible_personalities(state, new_message.sender_id)
        if not eligible:
            return

        recent = await message_repo.get_by_session(
            state.session.id, limit=config.max_context_messages
        )

        for pid in eligible:
            p = state.personalities[pid]
            mem = await memory_service.get_memory_text(pid)

            relevance = await engine.check_relevance(p, state.session.topic, recent, new_message, mem)
            if not relevance.should_respond:
                continue

            refreshed = await message_repo.get_by_session(
                state.session.id, limit=config.max_context_messages
            )
            full_content = await engine.generate_response(p, state.session.topic, refreshed, mem)
            now = datetime.now(timezone.utc).isoformat()
            msg_id = str(uuid.uuid4())

            ai_msg = Message(
                id=msg_id,
                session_id=state.session.id,
                sender_id=pid,
                sender_name=p.name,
                content=full_content,
                timestamp=now,
            )
            await message_repo.create(ai_msg)
            state.last_speaker_id = pid

            await send_callback({
                "type": "message",
                "sender_id": pid,
                "sender_name": p.name,
                "role": p.role,
                "content": full_content,
                "avatar_color": p.avatar_color,
                "timestamp": now,
            })

            await memory_service.on_message(
                state.session.id,
                list(state.personalities.keys()),
                state.session.topic,
                state.personalities,
            )

            if config.ai_response_delay_seconds > 0:
                await asyncio.sleep(config.ai_response_delay_seconds)


def get_eligible_personalities(state: ConversationState, last_sender_id: str) -> list[str]:
    return [
        pid for pid in state.personalities
        if pid not in state.muted and pid != last_sender_id
    ]


def order_response_queue(
    results: list[RelevanceResult],
    last_speaker_id: Optional[str] = None,
) -> list[RelevanceResult]:
    def sort_key(r: RelevanceResult) -> tuple:
        recency_penalty = 0 if r.personality_id != last_speaker_id else 100
        jitter = random.uniform(0, 0.5)
        return (-r.urgency + recency_penalty, -jitter)

    return sorted(results, key=sort_key)


def apply_anti_flood(queue: list[RelevanceResult], max_responses: int) -> list[RelevanceResult]:
    return queue[:max_responses]


class Orchestrator:
    def __init__(
        self,
        config: AppConfig,
        engine: PersonalityEngine,
        memory_service: MemoryService,
        session_repo: SessionRepositoryBase,
        message_repo: MessageRepositoryBase,
        all_personalities: dict[str, Personality],
    ) -> None:
        self._config = config
        self._engine = engine
        self._memory_service = memory_service
        self._session_repo = session_repo
        self._message_repo = message_repo
        self._all_personalities = all_personalities
        self._state = ConversationState()
        self._send_callback: Optional[MessageCallback] = None

        if config.conversation_mode == "autonomous":
            self._strategy: ConversationStrategy = AutonomousStrategy()
        else:
            self._strategy = RoundRobinStrategy()

    @property
    def state(self) -> ConversationState:
        return self._state

    def set_send_callback(self, callback: MessageCallback) -> None:
        self._send_callback = callback

    def pause(self) -> None:
        self._state.is_paused = True

    def resume(self) -> None:
        self._state.is_paused = False

    async def start_session(self, topic: str, personality_ids: list[str]) -> Session:
        now = datetime.now(timezone.utc).isoformat()
        session = Session(
            id=str(uuid.uuid4()),
            topic=topic,
            created_at=now,
            personality_ids=personality_ids,
        )
        await self._session_repo.create(session)

        self._state.session = session
        self._state.personalities = {
            pid: self._all_personalities[pid]
            for pid in personality_ids
            if pid in self._all_personalities
        }
        self._state.muted.clear()
        self._state.last_speaker_id = None
        self._state.is_processing = False
        self._state.is_paused = False
        self._memory_service.reset_counts()

        return session

    async def end_session(self) -> None:
        if self._state.session is None:
            return

        now = datetime.now(timezone.utc).isoformat()
        await self._session_repo.update_ended_at(self._state.session.id, now)
        await self._export_session(self._state.session.id)

        self._state.session = None
        self._state.personalities.clear()
        self._state.muted.clear()
        self._state.is_processing = False
        self._memory_service.reset_counts()

    async def handle_human_message(self, content: str) -> None:
        if self._state.session is None or self._send_callback is None:
            return

        if self._state.is_processing:
            return

        self._state.is_processing = True
        try:
            now = datetime.now(timezone.utc).isoformat()
            msg = Message(
                id=str(uuid.uuid4()),
                session_id=self._state.session.id,
                sender_id="human",
                sender_name="You",
                content=content,
                timestamp=now,
            )
            await self._message_repo.create(msg)
            self._state.last_speaker_id = "human"

            await self._send_callback({
                "type": "message",
                "sender_id": "human",
                "sender_name": "You",
                "role": "Human",
                "content": content,
                "avatar_color": "#7f8c8d",
                "timestamp": now,
            })

            await self._memory_service.on_message(
                self._state.session.id,
                list(self._state.personalities.keys()),
                self._state.session.topic,
                self._state.personalities,
            )

            if not self._state.is_paused:
                await self._strategy.process_message(
                    msg,
                    self._state,
                    self._engine,
                    self._memory_service,
                    self._message_repo,
                    self._config,
                    self._send_callback,
                )
        finally:
            self._state.is_processing = False

    def mute_personality(self, personality_id: str) -> None:
        self._state.muted.add(personality_id)

    def unmute_personality(self, personality_id: str) -> None:
        self._state.muted.discard(personality_id)

    async def _export_session(self, session_id: str) -> None:
        session = await self._session_repo.get_by_id(session_id)
        messages = await self._message_repo.get_by_session(session_id)

        export = {
            "session": {
                "id": session.id,
                "topic": session.topic,
                "created_at": session.created_at,
                "ended_at": session.ended_at,
                "personality_ids": session.personality_ids,
            },
            "messages": [
                {
                    "id": m.id,
                    "sender_id": m.sender_id,
                    "sender_name": m.sender_name,
                    "content": m.content,
                    "timestamp": m.timestamp,
                }
                for m in messages
            ],
        }

        export_dir = self._config.session_export_dir
        os.makedirs(export_dir, exist_ok=True)
        filepath = os.path.join(export_dir, f"{session_id}.json")
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(export, f, indent=2, ensure_ascii=False)
        logger.info(f"Exported session {session_id} to {filepath}")
