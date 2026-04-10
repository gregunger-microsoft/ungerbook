import pytest

from app.models.message import Message


class TestMessageRepository:
    @pytest.mark.asyncio
    async def test_create_and_get_by_session(self, message_repo, session_repo):
        from app.models.session import Session

        session = Session(id="s1", topic="T", created_at="2025-01-01T00:00:00Z", personality_ids=["a"])
        await session_repo.create(session)

        msg1 = Message(id="m1", session_id="s1", sender_id="human", sender_name="You", content="Hello", timestamp="2025-01-01T00:00:01Z")
        msg2 = Message(id="m2", session_id="s1", sender_id="cyber_security", sender_name="Alex", content="Hi there", timestamp="2025-01-01T00:00:02Z")

        await message_repo.create(msg1)
        await message_repo.create(msg2)

        results = await message_repo.get_by_session("s1")
        assert len(results) == 2
        assert results[0].id == "m1"
        assert results[1].id == "m2"

    @pytest.mark.asyncio
    async def test_get_by_session_with_limit(self, message_repo, session_repo):
        from app.models.session import Session

        session = Session(id="s2", topic="T", created_at="2025-01-01T00:00:00Z", personality_ids=["a"])
        await session_repo.create(session)

        for i in range(10):
            msg = Message(
                id=f"m{i}",
                session_id="s2",
                sender_id="human",
                sender_name="You",
                content=f"Message {i}",
                timestamp=f"2025-01-01T00:00:{i:02d}Z",
            )
            await message_repo.create(msg)

        results = await message_repo.get_by_session("s2", limit=3)
        assert len(results) == 3
        # Should be the last 3 messages in chronological order
        assert results[0].content == "Message 7"
        assert results[1].content == "Message 8"
        assert results[2].content == "Message 9"

    @pytest.mark.asyncio
    async def test_count_by_session(self, message_repo, session_repo):
        from app.models.session import Session

        session = Session(id="s3", topic="T", created_at="2025-01-01T00:00:00Z", personality_ids=["a"])
        await session_repo.create(session)

        for i in range(5):
            msg = Message(id=f"c{i}", session_id="s3", sender_id="human", sender_name="You", content=f"Msg {i}", timestamp=f"2025-01-01T00:00:{i:02d}Z")
            await message_repo.create(msg)

        count = await message_repo.count_by_session("s3")
        assert count == 5

    @pytest.mark.asyncio
    async def test_get_by_nonexistent_session(self, message_repo):
        results = await message_repo.get_by_session("nonexistent")
        assert results == []

    @pytest.mark.asyncio
    async def test_count_nonexistent_session(self, message_repo):
        count = await message_repo.count_by_session("nonexistent")
        assert count == 0
