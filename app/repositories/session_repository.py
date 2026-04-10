import json
from typing import Optional

import aiosqlite

from app.models.session import Session
from app.repositories.base import SessionRepositoryBase


class SessionRepository(SessionRepositoryBase):
    def __init__(self, db_path: str) -> None:
        self._db_path = db_path

    async def create(self, session: Session) -> None:
        async with aiosqlite.connect(self._db_path) as db:
            await db.execute(
                "INSERT INTO sessions (id, topic, created_at, ended_at, personality_ids) VALUES (?, ?, ?, ?, ?)",
                (
                    session.id,
                    session.topic,
                    session.created_at,
                    session.ended_at,
                    json.dumps(session.personality_ids),
                ),
            )
            await db.commit()

    async def get_by_id(self, session_id: str) -> Optional[Session]:
        async with aiosqlite.connect(self._db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("SELECT * FROM sessions WHERE id = ?", (session_id,)) as cursor:
                row = await cursor.fetchone()
                if row is None:
                    return None
                return Session(
                    id=row["id"],
                    topic=row["topic"],
                    created_at=row["created_at"],
                    ended_at=row["ended_at"],
                    personality_ids=json.loads(row["personality_ids"]),
                )

    async def list_all(self) -> list[Session]:
        async with aiosqlite.connect(self._db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("SELECT * FROM sessions ORDER BY created_at DESC") as cursor:
                rows = await cursor.fetchall()
                return [
                    Session(
                        id=row["id"],
                        topic=row["topic"],
                        created_at=row["created_at"],
                        ended_at=row["ended_at"],
                        personality_ids=json.loads(row["personality_ids"]),
                    )
                    for row in rows
                ]

    async def update_ended_at(self, session_id: str, ended_at: str) -> None:
        async with aiosqlite.connect(self._db_path) as db:
            await db.execute(
                "UPDATE sessions SET ended_at = ? WHERE id = ?",
                (ended_at, session_id),
            )
            await db.commit()

    async def delete(self, session_id: str) -> None:
        async with aiosqlite.connect(self._db_path) as db:
            await db.execute("DELETE FROM messages WHERE session_id = ?", (session_id,))
            await db.execute("DELETE FROM sessions WHERE id = ?", (session_id,))
            await db.commit()
