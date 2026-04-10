import pytest

from app.services.memory_service import MemoryService
from app.models.memory import Memory


class TestMemoryService:
    @pytest.mark.asyncio
    async def test_initial_count_is_zero(self, test_config, memory_repo, message_repo):
        service = MemoryService(test_config, memory_repo, message_repo, client=None)
        assert service.get_count("cyber_security") == 0

    @pytest.mark.asyncio
    async def test_get_memory_text_empty(self, test_config, memory_repo, message_repo):
        service = MemoryService(test_config, memory_repo, message_repo, client=None)
        text = await service.get_memory_text("nonexistent")
        assert text == ""

    @pytest.mark.asyncio
    async def test_get_memory_text_existing(self, test_config, memory_repo, message_repo):
        mem = Memory(id="m1", personality_id="cyber_security", memory_text="I recall threats.", last_updated="2025-01-01T00:00:00Z")
        await memory_repo.upsert(mem)

        service = MemoryService(test_config, memory_repo, message_repo, client=None)
        text = await service.get_memory_text("cyber_security")
        assert text == "I recall threats."

    @pytest.mark.asyncio
    async def test_reset_counts(self, test_config, memory_repo, message_repo):
        service = MemoryService(test_config, memory_repo, message_repo, client=None)
        service._message_counts["cyber_security"] = 5
        service._message_counts["cloud_architect"] = 3

        service.reset_counts()
        assert service.get_count("cyber_security") == 0
        assert service.get_count("cloud_architect") == 0

    @pytest.mark.asyncio
    async def test_count_increments_per_personality(self, test_config, memory_repo, message_repo):
        # Use a high interval so _update_memory is never triggered (it requires a real LLM client)
        config = test_config
        service = MemoryService(config, memory_repo, message_repo, client=None)
        service._interval = 999

        await service.on_message("s1", ["cyber_security", "cloud_architect"], "Topic", {})
        assert service.get_count("cyber_security") == 1
        assert service.get_count("cloud_architect") == 1

        await service.on_message("s1", ["cyber_security"], "Topic", {})
        assert service.get_count("cyber_security") == 2
        assert service.get_count("cloud_architect") == 1
