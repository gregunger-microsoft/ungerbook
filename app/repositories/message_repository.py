from typing import Optional

import aiosqlite

from app.models.message import Message
from app.repositories.base import MessageRepositoryBase


class MessageRepository(MessageRepositoryBase):
    def __init__(self, db_path: str) -> None:
        self._db_path = db_path

    async def create(self, message: Message) -> None:
        async with aiosqlite.connect(self._db_path) as db:
            await db.execute(
                "INSERT INTO messages (id, session_id, sender_id, sender_name, content, timestamp) VALUES (?, ?, ?, ?, ?, ?)",
                (
                    message.id,
                    message.session_id,
                    message.sender_id,
                    message.sender_name,
                    message.content,
                    message.timestamp,
                ),
            )
            await db.commit()

    async def get_by_session(self, session_id: str, limit: Optional[int] = None) -> list[Message]:
        async with aiosqlite.connect(self._db_path) as db:
            db.row_factory = aiosqlite.Row
            if limit is not None:
                query = """
                    SELECT * FROM (
                        SELECT * FROM messages WHERE session_id = ? ORDER BY timestamp DESC LIMIT ?
                    ) sub ORDER BY timestamp ASC
                """
                params = (session_id, limit)
            else:
                query = "SELECT * FROM messages WHERE session_id = ? ORDER BY timestamp ASC"
                params = (session_id,)

            async with db.execute(query, params) as cursor:
                rows = await cursor.fetchall()
                return [
                    Message(
                        id=row["id"],
                        session_id=row["session_id"],
                        sender_id=row["sender_id"],
                        sender_name=row["sender_name"],
                        content=row["content"],
                        timestamp=row["timestamp"],
                    )
                    for row in rows
                ]

    async def count_by_session(self, session_id: str) -> int:
        async with aiosqlite.connect(self._db_path) as db:
            async with db.execute(
                "SELECT COUNT(*) FROM messages WHERE session_id = ?", (session_id,)
            ) as cursor:
                row = await cursor.fetchone()
                return row[0]
