import json
import os

import aiosqlite


async def init_database(db_path: str) -> None:
    os.makedirs(os.path.dirname(db_path), exist_ok=True)

    async with aiosqlite.connect(db_path) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                id TEXT PRIMARY KEY,
                topic TEXT NOT NULL,
                created_at TEXT NOT NULL,
                ended_at TEXT,
                personality_ids TEXT NOT NULL
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id TEXT PRIMARY KEY,
                session_id TEXT NOT NULL,
                sender_id TEXT NOT NULL,
                sender_name TEXT NOT NULL,
                content TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                FOREIGN KEY (session_id) REFERENCES sessions(id)
            )
        """)
        await db.execute("""
            CREATE INDEX IF NOT EXISTS idx_messages_session
            ON messages(session_id, timestamp)
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS memories (
                id TEXT PRIMARY KEY,
                personality_id TEXT NOT NULL UNIQUE,
                memory_text TEXT NOT NULL,
                last_updated TEXT NOT NULL
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS guestbook (
                id TEXT PRIMARY KEY,
                email TEXT NOT NULL,
                activation_code TEXT NOT NULL UNIQUE,
                created_at TEXT NOT NULL,
                activated_at TEXT,
                expires_at TEXT NOT NULL,
                is_active INTEGER NOT NULL DEFAULT 0,
                tokens_used INTEGER NOT NULL DEFAULT 0,
                max_tokens INTEGER NOT NULL DEFAULT 100000
            )
        """)
        await db.execute("""
            CREATE INDEX IF NOT EXISTS idx_guestbook_code
            ON guestbook(activation_code)
        """)
        await db.execute("""
            CREATE INDEX IF NOT EXISTS idx_guestbook_email
            ON guestbook(email, created_at)
        """)
        await db.commit()
