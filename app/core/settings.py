from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    hermes_env: str = "development"
    ai_base_url: str = "http://127.0.0.1:20128/v1"
    ai_api_key: str | None = None
    ai_model: str | None = None
    ai_timeout_seconds: float = 45.0
    ai_retry_count: int = 1
    hermes_a_llm_enabled: bool = False
    hermes_omh_hooks_enabled: bool = False
    hermes_omh_evidence_enabled: bool = False
    hermes_omh_state_dir: str = ".omh/state"
    hermes_omh_events_path: str = ".omh/events/hooks.jsonl"
    supabase_url: str | None = None
    supabase_secret_key: str | None = None
    telegram_bot_token: str | None = None
    telegram_swain_bot_token: str | None = None
    telegram_shen_bot_token: str | None = None
    telegram_garen_bot_token: str | None = None
    telegram_kayn_bot_token: str | None = None
    telegram_allowed_chat_id: str | None = None
    telegram_bot_usernames: str = (
        "Swain_SubAgent_bot,Shen_SubAgent_bot,Garen_SubAgent_bot,Kayn_SubAgent_bot,Taric_SubAgent_bot,Xinzhao_SubAgent_bot"
    )


settings = Settings()
