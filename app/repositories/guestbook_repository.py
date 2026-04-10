import uuid
import secrets
import string
from datetime import datetime, timezone, timedelta
from dataclasses import dataclass
from typing import Optional

import aiosqlite


@dataclass
class GuestbookEntry:
    id: str
    email: str
    activation_code: str
    created_at: str
    activated_at: Optional[str]
    expires_at: str
    is_active: bool
    tokens_used: int = 0
    max_tokens: int = 100000


class GuestbookRepository:
    def __init__(self, db_path: str) -> None:
        self._db_path = db_path

    def _generate_code(self) -> str:
        chars = string.ascii_uppercase + string.digits
        return "".join(secrets.choice(chars) for _ in range(6))

    async def register(self, email: str, max_tokens: int = 100000) -> GuestbookEntry:
        now = datetime.now(timezone.utc)
        expires = now + timedelta(hours=1)
        entry = GuestbookEntry(
            id=str(uuid.uuid4()),
            email=email.strip().lower(),
            activation_code=self._generate_code(),
            created_at=now.isoformat(),
            activated_at=None,
            expires_at=expires.isoformat(),
            is_active=False,
            tokens_used=0,
            max_tokens=max_tokens,
        )
        async with aiosqlite.connect(self._db_path) as db:
            await db.execute(
                """INSERT INTO guestbook (id, email, activation_code, created_at, activated_at, expires_at, is_active, tokens_used, max_tokens)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (entry.id, entry.email, entry.activation_code, entry.created_at, entry.activated_at, entry.expires_at, 0, 0, max_tokens),
            )
            await db.commit()
        return entry

    async def activate(self, code: str) -> Optional[GuestbookEntry]:
        now = datetime.now(timezone.utc)
        async with aiosqlite.connect(self._db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT * FROM guestbook WHERE activation_code = ?", (code.strip().upper(),)
            )
            row = await cursor.fetchone()
            if not row:
                return None

            expires_at = datetime.fromisoformat(row["expires_at"])
            if now > expires_at:
                return None

            activated_at = now.isoformat()
            await db.execute(
                "UPDATE guestbook SET is_active = 1, activated_at = ? WHERE id = ?",
                (activated_at, row["id"]),
            )
            await db.commit()

            return GuestbookEntry(
                id=row["id"],
                email=row["email"],
                activation_code=row["activation_code"],
                created_at=row["created_at"],
                activated_at=activated_at,
                expires_at=row["expires_at"],
                is_active=True,
                tokens_used=row["tokens_used"] if "tokens_used" in row.keys() else 0,
                max_tokens=row["max_tokens"] if "max_tokens" in row.keys() else 100000,
            )

    async def validate_code(self, code: str) -> bool:
        now = datetime.now(timezone.utc)
        async with aiosqlite.connect(self._db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT * FROM guestbook WHERE activation_code = ? AND is_active = 1", (code,)
            )
            row = await cursor.fetchone()
            if not row:
                return False
            expires_at = datetime.fromisoformat(row["expires_at"])
            if now > expires_at:
                return False
            tokens_used = row["tokens_used"] if "tokens_used" in row.keys() else 0
            max_tokens = row["max_tokens"] if "max_tokens" in row.keys() else 100000
            return tokens_used < max_tokens

    async def increment_tokens(self, code: str, tokens: int) -> Optional[GuestbookEntry]:
        async with aiosqlite.connect(self._db_path) as db:
            db.row_factory = aiosqlite.Row
            await db.execute(
                "UPDATE guestbook SET tokens_used = tokens_used + ? WHERE activation_code = ? AND is_active = 1",
                (tokens, code),
            )
            await db.commit()
            cursor = await db.execute(
                "SELECT * FROM guestbook WHERE activation_code = ?", (code,)
            )
            row = await cursor.fetchone()
            if not row:
                return None
            return GuestbookEntry(
                id=row["id"],
                email=row["email"],
                activation_code=row["activation_code"],
                created_at=row["created_at"],
                activated_at=row["activated_at"],
                expires_at=row["expires_at"],
                is_active=bool(row["is_active"]),
                tokens_used=row["tokens_used"],
                max_tokens=row["max_tokens"],
            )

    async def list_all(self) -> list[GuestbookEntry]:
        async with aiosqlite.connect(self._db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute("SELECT * FROM guestbook ORDER BY created_at DESC")
            rows = await cursor.fetchall()
            return [
                GuestbookEntry(
                    id=r["id"],
                    email=r["email"],
                    activation_code=r["activation_code"],
                    created_at=r["created_at"],
                    activated_at=r["activated_at"],
                    expires_at=r["expires_at"],
                    is_active=bool(r["is_active"]),
                    tokens_used=r["tokens_used"] if "tokens_used" in r.keys() else 0,
                    max_tokens=r["max_tokens"] if "max_tokens" in r.keys() else 100000,
                )
                for r in rows
            ]
