import pytest

from app.config import load_config


class TestConfigValidation:
    def test_load_valid_config(self, test_env_path):
        config = load_config(test_env_path)
        assert config.azure_openai_endpoint == "https://test.openai.azure.com/"
        assert config.azure_openai_deployment == "test-model"
        assert config.conversation_mode == "autonomous"
        assert config.ai_response_delay_seconds == 0
        assert config.max_ai_responses_per_round == 5
        assert config.max_context_messages == 50
        assert config.enable_streaming is False
        assert config.memory_summarization_interval == 10

    def test_missing_key_raises_error(self, test_dir):
        env_file = test_dir / ".env"
        env_file.write_text("AZURE_OPENAI_ENDPOINT=https://test.openai.azure.com/\n")
        with pytest.raises(ValueError, match="Missing or blank .env setting"):
            load_config(str(env_file))

    def test_blank_value_raises_error(self, test_dir, test_db_path):
        env_content = (
            f"AZURE_OPENAI_ENDPOINT=\n"
            f"AZURE_OPENAI_DEPLOYMENT=test-model\n"
            f"AZURE_OPENAI_API_VERSION=2025-04-01-preview\n"
            f"AZURE_OPENAI_API_KEY=test-key\n"
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
        with pytest.raises(ValueError, match="AZURE_OPENAI_ENDPOINT"):
            load_config(str(env_file))

    def test_invalid_conversation_mode_raises_error(self, test_dir, test_db_path):
        env_content = (
            f"AZURE_OPENAI_ENDPOINT=https://test.openai.azure.com/\n"
            f"AZURE_OPENAI_DEPLOYMENT=test-model\n"
            f"AZURE_OPENAI_API_VERSION=2025-04-01-preview\n"
            f"AZURE_OPENAI_API_KEY=test-key\n"
            f"CONVERSATION_MODE=invalid_mode\n"
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
        with pytest.raises(ValueError, match="Invalid CONVERSATION_MODE"):
            load_config(str(env_file))

    def test_invalid_streaming_raises_error(self, test_dir, test_db_path):
        env_content = (
            f"AZURE_OPENAI_ENDPOINT=https://test.openai.azure.com/\n"
            f"AZURE_OPENAI_DEPLOYMENT=test-model\n"
            f"AZURE_OPENAI_API_VERSION=2025-04-01-preview\n"
            f"AZURE_OPENAI_API_KEY=test-key\n"
            f"CONVERSATION_MODE=autonomous\n"
            f"AI_RESPONSE_DELAY_SECONDS=0\n"
            f"MAX_AI_RESPONSES_PER_ROUND=5\n"
            f"MAX_CONTEXT_MESSAGES=50\n"
            f"ENABLE_STREAMING=maybe\n"
            f"MEMORY_SUMMARIZATION_INTERVAL=10\n"
            f"DATABASE_PATH={test_db_path}\n"
            f"PERSONALITIES_FILE=personalities.json\n"
            f"SESSION_EXPORT_DIR={test_dir}/sessions\n"
        )
        env_file = test_dir / ".env"
        env_file.write_text(env_content)
        with pytest.raises(ValueError, match="Invalid ENABLE_STREAMING"):
            load_config(str(env_file))

    def test_round_robin_mode(self, test_dir, test_db_path):
        env_content = (
            f"AZURE_OPENAI_ENDPOINT=https://test.openai.azure.com/\n"
            f"AZURE_OPENAI_DEPLOYMENT=test-model\n"
            f"AZURE_OPENAI_API_VERSION=2025-04-01-preview\n"
            f"AZURE_OPENAI_API_KEY=test-key\n"
            f"CONVERSATION_MODE=round_robin\n"
            f"AI_RESPONSE_DELAY_SECONDS=0\n"
            f"MAX_AI_RESPONSES_PER_ROUND=5\n"
            f"MAX_CONTEXT_MESSAGES=50\n"
            f"ENABLE_STREAMING=true\n"
            f"MEMORY_SUMMARIZATION_INTERVAL=10\n"
            f"DATABASE_PATH={test_db_path}\n"
            f"PERSONALITIES_FILE=personalities.json\n"
            f"SESSION_EXPORT_DIR={test_dir}/sessions\n"
        )
        env_file = test_dir / ".env"
        env_file.write_text(env_content)
        config = load_config(str(env_file))
        assert config.conversation_mode == "round_robin"
        assert config.enable_streaming is True

    def test_nonexistent_env_file_raises_error(self):
        with pytest.raises(ValueError, match="Missing or blank .env setting"):
            load_config("/nonexistent/path/.env")
