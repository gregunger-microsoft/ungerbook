from dataclasses import dataclass
from dotenv import dotenv_values


@dataclass(frozen=True)
class AppConfig:
    azure_openai_endpoint: str
    azure_openai_deployment: str
    azure_openai_api_version: str
    azure_openai_api_key: str
    conversation_mode: str
    ai_response_delay_seconds: int
    max_ai_responses_per_round: int
    max_context_messages: int
    enable_streaming: bool
    memory_summarization_interval: int
    database_path: str
    personalities_file: str
    session_export_dir: str
    smtp_host: str
    smtp_port: int
    smtp_username: str
    smtp_password: str
    smtp_from_email: str
    app_base_url: str


_REQUIRED_KEYS = [
    "AZURE_OPENAI_ENDPOINT",
    "AZURE_OPENAI_DEPLOYMENT",
    "AZURE_OPENAI_API_VERSION",
    "AZURE_OPENAI_API_KEY",
    "CONVERSATION_MODE",
    "AI_RESPONSE_DELAY_SECONDS",
    "MAX_AI_RESPONSES_PER_ROUND",
    "MAX_CONTEXT_MESSAGES",
    "ENABLE_STREAMING",
    "MEMORY_SUMMARIZATION_INTERVAL",
    "DATABASE_PATH",
    "PERSONALITIES_FILE",
    "SESSION_EXPORT_DIR",
    "SMTP_HOST",
    "SMTP_PORT",
    "SMTP_USERNAME",
    "SMTP_PASSWORD",
    "SMTP_FROM_EMAIL",
    "APP_BASE_URL",
]


def load_config(env_path: str = ".env") -> AppConfig:
    values = dotenv_values(env_path)

    for key in _REQUIRED_KEYS:
        if key not in values or not values[key] or not values[key].strip():
            raise ValueError(
                f"Missing or blank .env setting: '{key}'. "
                f"All required settings must be present and non-empty in {env_path}"
            )

    conversation_mode = values["CONVERSATION_MODE"].strip().lower()
    if conversation_mode not in ("autonomous", "round_robin"):
        raise ValueError(
            f"Invalid CONVERSATION_MODE: '{conversation_mode}'. Must be 'autonomous' or 'round_robin'."
        )

    enable_streaming = values["ENABLE_STREAMING"].strip().lower()
    if enable_streaming not in ("true", "false"):
        raise ValueError(
            f"Invalid ENABLE_STREAMING: '{enable_streaming}'. Must be 'true' or 'false'."
        )

    return AppConfig(
        azure_openai_endpoint=values["AZURE_OPENAI_ENDPOINT"].strip(),
        azure_openai_deployment=values["AZURE_OPENAI_DEPLOYMENT"].strip(),
        azure_openai_api_version=values["AZURE_OPENAI_API_VERSION"].strip(),
        azure_openai_api_key=values["AZURE_OPENAI_API_KEY"].strip(),
        conversation_mode=conversation_mode,
        ai_response_delay_seconds=int(values["AI_RESPONSE_DELAY_SECONDS"].strip()),
        max_ai_responses_per_round=int(values["MAX_AI_RESPONSES_PER_ROUND"].strip()),
        max_context_messages=int(values["MAX_CONTEXT_MESSAGES"].strip()),
        enable_streaming=(enable_streaming == "true"),
        memory_summarization_interval=int(values["MEMORY_SUMMARIZATION_INTERVAL"].strip()),
        database_path=values["DATABASE_PATH"].strip(),
        personalities_file=values["PERSONALITIES_FILE"].strip(),
        session_export_dir=values["SESSION_EXPORT_DIR"].strip(),
        smtp_host=values["SMTP_HOST"].strip(),
        smtp_port=int(values["SMTP_PORT"].strip()),
        smtp_username=values["SMTP_USERNAME"].strip(),
        smtp_password=values["SMTP_PASSWORD"].strip(),
        smtp_from_email=values["SMTP_FROM_EMAIL"].strip(),
        app_base_url=values["APP_BASE_URL"].strip().rstrip("/"),
    )
