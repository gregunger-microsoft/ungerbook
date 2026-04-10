from dataclasses import dataclass


@dataclass
class Memory:
    id: str
    personality_id: str
    memory_text: str
    last_updated: str
