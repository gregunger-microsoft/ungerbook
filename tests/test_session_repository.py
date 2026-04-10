import pytest

from app.models.session import Session


class TestSessionRepository:
    @pytest.mark.asyncio
    async def test_create_and_get_by_id(self, session_repo):
        session = Session(
            id="sess-001",
            topic="AI Safety",
            created_at="2025-01-01T00:00:00Z",
            personality_ids=["cyber_security", "legal_ai"],
        )
        await session_repo.create(session)

        result = await session_repo.get_by_id("sess-001")
        assert result is not None
        assert result.id == "sess-001"
        assert result.topic == "AI Safety"
        assert result.personality_ids == ["cyber_security", "legal_ai"]
        assert result.ended_at is None

    @pytest.mark.asyncio
    async def test_get_nonexistent_returns_none(self, session_repo):
        result = await session_repo.get_by_id("nonexistent")
        assert result is None

    @pytest.mark.asyncio
    async def test_list_all_returns_ordered_by_created_at_desc(self, session_repo):
        s1 = Session(id="s1", topic="Topic A", created_at="2025-01-01T00:00:00Z", personality_ids=["a"])
        s2 = Session(id="s2", topic="Topic B", created_at="2025-01-02T00:00:00Z", personality_ids=["b"])
        s3 = Session(id="s3", topic="Topic C", created_at="2025-01-03T00:00:00Z", personality_ids=["c"])

        await session_repo.create(s1)
        await session_repo.create(s2)
        await session_repo.create(s3)

        results = await session_repo.list_all()
        assert len(results) == 3
        assert results[0].id == "s3"
        assert results[1].id == "s2"
        assert results[2].id == "s1"

    @pytest.mark.asyncio
    async def test_update_ended_at(self, session_repo):
        session = Session(
            id="sess-end",
            topic="Ending test",
            created_at="2025-01-01T00:00:00Z",
            personality_ids=["ops"],
        )
        await session_repo.create(session)
        await session_repo.update_ended_at("sess-end", "2025-01-01T01:00:00Z")

        result = await session_repo.get_by_id("sess-end")
        assert result.ended_at == "2025-01-01T01:00:00Z"

    @pytest.mark.asyncio
    async def test_list_all_empty(self, session_repo):
        results = await session_repo.list_all()
        assert results == []
