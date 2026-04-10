import json
import os

import pytest
import pytest_asyncio

from app.config import load_config
from app.models.personality import Personality
from app.repositories.db import init_database
from app.repositories.session_repository import SessionRepository
from app.repositories.message_repository import MessageRepository
from app.repositories.memory_repository import MemoryRepository


@pytest.fixture
def test_dir(tmp_path):
    return tmp_path


@pytest.fixture
def test_db_path(test_dir):
    db_path = str(test_dir / "test_moltbook.db")
    return db_path


@pytest.fixture
def test_env_path(test_dir, test_db_path):
    env_content = (
        f"AZURE_OPENAI_ENDPOINT=https://test.openai.azure.com/\n"
        f"AZURE_OPENAI_DEPLOYMENT=test-model\n"
        f"AZURE_OPENAI_API_VERSION=2025-04-01-preview\n"
        f"AZURE_OPENAI_API_KEY=test-key-for-unit-tests\n"
        f"CONVERSATION_MODE=autonomous\n"
        f"AI_RESPONSE_DELAY_SECONDS=0\n"
        f"MAX_AI_RESPONSES_PER_ROUND=5\n"
        f"MAX_CONTEXT_MESSAGES=50\n"
        f"ENABLE_STREAMING=false\n"
        f"MEMORY_SUMMARIZATION_INTERVAL=10\n"
        f"DATABASE_PATH={test_db_path}\n"
        f"PERSONALITIES_FILE=personalities.json\n"
        f"SESSION_EXPORT_DIR={test_dir}/sessions\n"
    )
    env_file = test_dir / ".env"
    env_file.write_text(env_content)
    return str(env_file)


@pytest.fixture
def test_config(test_env_path):
    return load_config(test_env_path)


@pytest_asyncio.fixture
async def initialized_db(test_db_path):
    await init_database(test_db_path)
    return test_db_path


@pytest_asyncio.fixture
async def session_repo(initialized_db):
    return SessionRepository(initialized_db)


@pytest_asyncio.fixture
async def message_repo(initialized_db):
    return MessageRepository(initialized_db)


@pytest_asyncio.fixture
async def memory_repo(initialized_db):
    return MemoryRepository(initialized_db)


@pytest.fixture
def sample_personalities() -> dict[str, Personality]:
    with open("personalities.json", "r", encoding="utf-8") as f:
        raw = json.load(f)
    return {
        p["id"]: Personality(
            id=p["id"],
            name=p["name"],
            role=p["role"],
            avatar_color=p["avatar_color"],
            expertise_domain=p["expertise_domain"],
            communication_style=p["communication_style"],
            system_prompt=p["system_prompt"],
        )
        for p in raw
    }
