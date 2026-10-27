"""Cấu hình tập trung — đọc từ biến môi trường / .env. Không hardcode secret."""

from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Database
    database_url: str = "postgresql://lawvn:lawvn-dev@localhost:5432/lawvn"

    # LLM chung
    llm_provider: str = "auto"

    # Gemini (OpenAI-compatible)
    gemini_base_url: str = "https://generativelanguage.googleapis.com/v1beta/openai/"
    gemini_model: str = "gemini-3.5-flash"
    gemini_model_lite: str = "gemini-3.1-flash-lite"

    # Claude
    anthropic_api_key: str | None = None
    anthropic_model: str = "claude-opus-5-5"

    # FPT (tùy chọn)
    fpt_base_url: str = "https://mkp-api.fptcloud.com"
    fpt_api_key: str | None = None
    fpt_model: str = "gpt-oss-20b"

    # Embedding
    embedder: str = "hashing"
    embed_dim: int = 1024

    # Rerank
    rerank_enabled: bool = False
    rerank_model: str = "BAAI/bge-reranker-v2-m3"

    # Observability
    langfuse_enabled: bool = False
    langfuse_host: str = "http://localhost:3001"
    langfuse_public_key: str | None = None
    langfuse_secret_key: str | None = None

    @property
    def gemini_keys(self) -> list[str]:
        """Gom GEMINI_API_KEY_1..10 từ môi trường, bỏ ô trống."""
        import os

        keys = []
        for i in range(1, 11):
            v = os.getenv(f"GEMINI_API_KEY_{i}", "").strip()
            if v:
                keys.append(v)
        # Cho phép cả GEMINI_API_KEY đơn lẻ.
        single = os.getenv("GEMINI_API_KEY", "").strip()
        if single:
            keys.append(single)
        return keys

    @property
    def sqlalchemy_url(self) -> str:
        """SQLAlchemy cần driver rõ ràng (psycopg3)."""
        url = self.database_url
        if url.startswith("postgresql://"):
            return url.replace("postgresql://", "postgresql+psycopg://", 1)
        return url


@lru_cache
def get_settings() -> Settings:
    return Settings()
