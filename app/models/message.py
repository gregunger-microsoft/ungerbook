from dataclasses import dataclass


@dataclass
class Message:
    id: str
    session_id: str
    sender_id: str
    sender_name: str
    content: str
    timestamp: str
