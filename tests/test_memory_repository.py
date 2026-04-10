import pytest

from app.models.memory import Memory


class TestMemoryRepository:
    @pytest.mark.asyncio
    async def test_upsert_and_get(self, memory_repo):
        memory = Memory(
            id="mem-1",
            personality_id="cyber_security",
            memory_text="I remember discussing threat models.",
            last_updated="2025-01-01T00:00:00Z",
        )
        await memory_repo.upsert(memory)

        result = await memory_repo.get_by_personality("cyber_security")
        assert result is not None
        assert result.personality_id == "cyber_security"
        assert result.memory_text == "I remember discussing threat models."

    @pytest.mark.asyncio
    async def test_upsert_updates_existing(self, memory_repo):
        m1 = Memory(id="mem-1", personality_id="cyber_security", memory_text="First memory", last_updated="2025-01-01T00:00:00Z")
        await memory_repo.upsert(m1)

        m2 = Memory(id="mem-2", personality_id="cyber_security", memory_text="Updated memory", last_updated="2025-01-02T00:00:00Z")
        await memory_repo.upsert(m2)

        result = await memory_repo.get_by_personality("cyber_security")
        assert result.memory_text == "Updated memory"
        assert result.last_updated == "2025-01-02T00:00:00Z"

    @pytest.mark.asyncio
    async def test_get_nonexistent_returns_none(self, memory_repo):
        result = await memory_repo.get_by_personality("nonexistent")
        assert result is None

    @pytest.mark.asyncio
    async def test_delete_by_personality(self, memory_repo):
        memory = Memory(id="mem-d", personality_id="operations", memory_text="Ops memory", last_updated="2025-01-01T00:00:00Z")
        await memory_repo.upsert(memory)

        await memory_repo.delete_by_personality("operations")
        result = await memory_repo.get_by_personality("operations")
        assert result is None

    @pytest.mark.asyncio
    async def test_delete_nonexistent_no_error(self, memory_repo):
        await memory_repo.delete_by_personality("nonexistent")

    @pytest.mark.asyncio
    async def test_multiple_personalities(self, memory_repo):
        m1 = Memory(id="m1", personality_id="cyber_security", memory_text="Cyber mem", last_updated="2025-01-01T00:00:00Z")
        m2 = Memory(id="m2", personality_id="cloud_architect", memory_text="Cloud mem", last_updated="2025-01-01T00:00:00Z")

        await memory_repo.upsert(m1)
        await memory_repo.upsert(m2)

        r1 = await memory_repo.get_by_personality("cyber_security")
        r2 = await memory_repo.get_by_personality("cloud_architect")

        assert r1.memory_text == "Cyber mem"
        assert r2.memory_text == "Cloud mem"
