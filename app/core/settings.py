from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    hermes_env: str = "development"
    ai_base_url: str = "http://127.0.0.1:20128/v1"
    ai_api_key: str | None = None
    ai_model: str | None = None
    supabase_url: str | None = None
    supabase_secret_key: str | None = None


settings = Settings()
