from abc import ABC, abstractmethod
from typing import Optional

from app.models.session import Session
from app.models.message import Message
from app.models.memory import Memory


class SessionRepositoryBase(ABC):
    @abstractmethod
    async def create(self, session: Session) -> None:
        ...

    @abstractmethod
    async def get_by_id(self, session_id: str) -> Optional[Session]:
        ...

    @abstractmethod
    async def list_all(self) -> list[Session]:
        ...

    @abstractmethod
    async def update_ended_at(self, session_id: str, ended_at: str) -> None:
        ...

    @abstractmethod
    async def delete(self, session_id: str) -> None:
        ...


class MessageRepositoryBase(ABC):
    @abstractmethod
    async def create(self, message: Message) -> None:
        ...

    @abstractmethod
    async def get_by_session(self, session_id: str, limit: Optional[int] = None) -> list[Message]:
        ...

    @abstractmethod
    async def count_by_session(self, session_id: str) -> int:
        ...


class MemoryRepositoryBase(ABC):
    @abstractmethod
    async def upsert(self, memory: Memory) -> None:
        ...

    @abstractmethod
    async def get_by_personality(self, personality_id: str) -> Optional[Memory]:
        ...

    @abstractmethod
    async def delete_by_personality(self, personality_id: str) -> None:
        ...
