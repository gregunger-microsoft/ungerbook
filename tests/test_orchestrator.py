import pytest

from app.models.personality import Personality
from app.services.orchestrator import (
    ConversationState,
    get_eligible_personalities,
    order_response_queue,
    apply_anti_flood,
    AutonomousStrategy,
    RoundRobinStrategy,
    Orchestrator,
)
from app.services.personality_engine import RelevanceResult


def _make_personalities(*ids):
    return {
        pid: Personality(
            id=pid, name=f"Name-{pid}", role="Role", avatar_color="#000",
            expertise_domain="test", communication_style="test", system_prompt="test",
        )
        for pid in ids
    }


class TestGetEligiblePersonalities:
    def test_excludes_muted(self):
        state = ConversationState()
        state.personalities = _make_personalities("a", "b", "c")
        state.muted = {"b"}
        result = get_eligible_personalities(state, "human")
        assert set(result) == {"a", "c"}

    def test_excludes_last_speaker(self):
        state = ConversationState()
        state.personalities = _make_personalities("a", "b", "c")
        result = get_eligible_personalities(state, "a")
        assert "a" not in result
        assert set(result) == {"b", "c"}

    def test_excludes_both_muted_and_last_speaker(self):
        state = ConversationState()
        state.personalities = _make_personalities("a", "b", "c")
        state.muted = {"c"}
        result = get_eligible_personalities(state, "a")
        assert result == ["b"]

    def test_all_muted(self):
        state = ConversationState()
        state.personalities = _make_personalities("a", "b")
        state.muted = {"a", "b"}
        result = get_eligible_personalities(state, "human")
        assert result == []

    def test_empty_personalities(self):
        state = ConversationState()
        result = get_eligible_personalities(state, "human")
        assert result == []


class TestOrderResponseQueue:
    def test_orders_by_urgency_descending(self):
        results = [
            RelevanceResult(personality_id="a", should_respond=True, reason="r", urgency=3),
            RelevanceResult(personality_id="b", should_respond=True, reason="r", urgency=8),
            RelevanceResult(personality_id="c", should_respond=True, reason="r", urgency=5),
        ]
        ordered = order_response_queue(results)
        # Higher urgency first (lower sort key)
        assert ordered[0].personality_id == "b"
        assert ordered[1].personality_id == "c"
        assert ordered[2].personality_id == "a"

    def test_last_speaker_penalized(self):
        results = [
            RelevanceResult(personality_id="a", should_respond=True, reason="r", urgency=10),
            RelevanceResult(personality_id="b", should_respond=True, reason="r", urgency=5),
        ]
        ordered = order_response_queue(results, last_speaker_id="a")
        # 'a' has urgency 10 but penalty of -100 pushes it to back
        assert ordered[0].personality_id == "b"
        assert ordered[1].personality_id == "a"

    def test_empty_queue(self):
        assert order_response_queue([]) == []

    def test_single_item(self):
        results = [RelevanceResult(personality_id="a", should_respond=True, reason="r", urgency=5)]
        ordered = order_response_queue(results)
        assert len(ordered) == 1
        assert ordered[0].personality_id == "a"


class TestApplyAntiFlood:
    def test_limits_to_max(self):
        results = [
            RelevanceResult(personality_id=f"p{i}", should_respond=True, reason="r", urgency=5)
            for i in range(10)
        ]
        limited = apply_anti_flood(results, 3)
        assert len(limited) == 3

    def test_under_limit_returns_all(self):
        results = [
            RelevanceResult(personality_id="a", should_respond=True, reason="r", urgency=5),
            RelevanceResult(personality_id="b", should_respond=True, reason="r", urgency=5),
        ]
        limited = apply_anti_flood(results, 5)
        assert len(limited) == 2

    def test_zero_limit(self):
        results = [
            RelevanceResult(personality_id="a", should_respond=True, reason="r", urgency=5),
        ]
        limited = apply_anti_flood(results, 0)
        assert len(limited) == 0

    def test_empty_queue(self):
        assert apply_anti_flood([], 5) == []


class TestOrchestrator:
    @pytest.mark.asyncio
    async def test_start_session(self, test_config, session_repo, message_repo, memory_repo, sample_personalities):
        from app.services.memory_service import MemoryService

        mem_service = MemoryService(test_config, memory_repo, message_repo, client=None)
        engine = None  # Not needed for start_session

        orch = Orchestrator(test_config, engine, mem_service, session_repo, message_repo, sample_personalities)
        session = await orch.start_session("Test topic", ["cyber_security", "cloud_architect"])

        assert session.topic == "Test topic"
        assert "cyber_security" in session.personality_ids
        assert orch.state.session is not None
        assert len(orch.state.personalities) == 2

    @pytest.mark.asyncio
    async def test_end_session_exports(self, test_config, session_repo, message_repo, memory_repo, sample_personalities):
        from app.services.memory_service import MemoryService
        import os

        mem_service = MemoryService(test_config, memory_repo, message_repo, client=None)
        orch = Orchestrator(test_config, None, mem_service, session_repo, message_repo, sample_personalities)

        session = await orch.start_session("Export test", ["cyber_security"])
        session_id = session.id

        os.makedirs(test_config.session_export_dir, exist_ok=True)
        await orch.end_session()

        assert orch.state.session is None
        export_path = os.path.join(test_config.session_export_dir, f"{session_id}.json")
        assert os.path.exists(export_path)

    @pytest.mark.asyncio
    async def test_mute_unmute(self, test_config, session_repo, message_repo, memory_repo, sample_personalities):
        from app.services.memory_service import MemoryService

        mem_service = MemoryService(test_config, memory_repo, message_repo, client=None)
        orch = Orchestrator(test_config, None, mem_service, session_repo, message_repo, sample_personalities)

        await orch.start_session("Mute test", ["cyber_security", "cloud_architect"])

        orch.mute_personality("cyber_security")
        assert "cyber_security" in orch.state.muted

        eligible = get_eligible_personalities(orch.state, "human")
        assert "cyber_security" not in eligible
        assert "cloud_architect" in eligible

        orch.unmute_personality("cyber_security")
        assert "cyber_security" not in orch.state.muted

    @pytest.mark.asyncio
    async def test_strategy_selection_autonomous(self, test_config, session_repo, message_repo, memory_repo, sample_personalities):
        from app.services.memory_service import MemoryService

        mem_service = MemoryService(test_config, memory_repo, message_repo, client=None)
        orch = Orchestrator(test_config, None, mem_service, session_repo, message_repo, sample_personalities)
        assert isinstance(orch._strategy, AutonomousStrategy)

    @pytest.mark.asyncio
    async def test_handle_message_without_session_does_nothing(self, test_config, session_repo, message_repo, memory_repo, sample_personalities):
        from app.services.memory_service import MemoryService

        mem_service = MemoryService(test_config, memory_repo, message_repo, client=None)
        orch = Orchestrator(test_config, None, mem_service, session_repo, message_repo, sample_personalities)
        orch.set_send_callback(lambda d: None)

        # Should not raise even without an active session
        await orch.handle_human_message("Hello")
