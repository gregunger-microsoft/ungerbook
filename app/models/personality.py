from dataclasses import dataclass


@dataclass
class Personality:
    id: str
    name: str
    role: str
    avatar_color: str
    expertise_domain: str
    communication_style: str
    system_prompt: str
