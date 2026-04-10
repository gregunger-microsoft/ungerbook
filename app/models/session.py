from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Session:
    id: str
    topic: str
    created_at: str
    personality_ids: list[str]
    ended_at: Optional[str] = None
