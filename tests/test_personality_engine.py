import pytest

from app.models.message import Message
from app.models.personality import Personality
from app.services.personality_engine import PersonalityEngine, RelevanceResult


@pytest.fixture
def sample_personality():
    return Personality(
        id="cyber_security",
        name="Alex Sentinel",
        role="Cyber-Security Specialist",
        avatar_color="#e74c3c",
        expertise_domain="Application security, threat modeling",
        communication_style="Cautious, direct",
        system_prompt="You are Alex Sentinel, a seasoned Cyber-Security Specialist.",
    )


class TestPersonalityEngine:
    def test_build_system_prompt_no_memory(self, test_config, sample_personality):
        engine = PersonalityEngine(test_config, client=None)
        prompt = engine.build_system_prompt(sample_personality, "AI Safety")

        assert "Alex Sentinel" in prompt
        assert "AI Safety" in prompt
        assert "past conversations" not in prompt

    def test_build_system_prompt_with_memory(self, test_config, sample_personality):
        engine = PersonalityEngine(test_config, client=None)
        prompt = engine.build_system_prompt(
            sample_personality, "AI Safety", memory_text="Previously discussed OWASP."
        )

        assert "Previously discussed OWASP" in prompt
        assert "past conversations" in prompt

    def test_build_context_messages_structure(self, test_config, sample_personality):
        engine = PersonalityEngine(test_config, client=None)
        messages = [
            Message(id="1", session_id="s1", sender_id="human", sender_name="You", content="Hello", timestamp="T1"),
            Message(id="2", session_id="s1", sender_id="cyber_security", sender_name="Alex Sentinel", content="Hi!", timestamp="T2"),
            Message(id="3", session_id="s1", sender_id="cloud_architect", sender_name="Jordan", content="Hey", timestamp="T3"),
        ]

        context = engine.build_context_messages(sample_personality, "Topic", messages)

        assert context[0]["role"] == "system"
        assert context[1]["role"] == "user"
        assert "[You]" in context[1]["content"]
        assert context[2]["role"] == "assistant"
        assert context[2]["content"] == "Hi!"
        assert context[3]["role"] == "user"
        assert "[Jordan]" in context[3]["content"]

    def test_build_context_messages_with_memory(self, test_config, sample_personality):
        engine = PersonalityEngine(test_config, client=None)
        context = engine.build_context_messages(
            sample_personality, "Topic", [], memory_text="I remember things."
        )

        assert "I remember things" in context[0]["content"]

    def test_context_respects_message_order(self, test_config, sample_personality):
        engine = PersonalityEngine(test_config, client=None)
        messages = [
            Message(id=str(i), session_id="s1", sender_id="human", sender_name="You", content=f"Msg {i}", timestamp=f"T{i}")
            for i in range(5)
        ]

        context = engine.build_context_messages(sample_personality, "Topic", messages)
        # 1 system + 5 user messages
        assert len(context) == 6
        assert context[1]["content"] == "[You]: Msg 0"
        assert context[5]["content"] == "[You]: Msg 4"
