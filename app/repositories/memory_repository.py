from typing import Optional

import aiosqlite

from app.models.memory import Memory
from app.repositories.base import MemoryRepositoryBase


class MemoryRepository(MemoryRepositoryBase):
    def __init__(self, db_path: str) -> None:
        self._db_path = db_path

    async def upsert(self, memory: Memory) -> None:
        async with aiosqlite.connect(self._db_path) as db:
            await db.execute(
                """INSERT INTO memories (id, personality_id, memory_text, last_updated)
                   VALUES (?, ?, ?, ?)
                   ON CONFLICT(personality_id) DO UPDATE SET
                       memory_text = excluded.memory_text,
                       last_updated = excluded.last_updated""",
                (memory.id, memory.personality_id, memory.memory_text, memory.last_updated),
            )
            await db.commit()

    async def get_by_personality(self, personality_id: str) -> Optional[Memory]:
        async with aiosqlite.connect(self._db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT * FROM memories WHERE personality_id = ?", (personality_id,)
            ) as cursor:
                row = await cursor.fetchone()
                if row is None:
                    return None
                return Memory(
                    id=row["id"],
                    personality_id=row["personality_id"],
                    memory_text=row["memory_text"],
                    last_updated=row["last_updated"],
                )

    async def delete_by_personality(self, personality_id: str) -> None:
        async with aiosqlite.connect(self._db_path) as db:
            await db.execute("DELETE FROM memories WHERE personality_id = ?", (personality_id,))
            await db.commit()
