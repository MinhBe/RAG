from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[2]

# USD per 1M tokens (input, output). Source: Anthropic pricing, checked 2026-10.
MODEL_PRICES: dict[str, tuple[float, float]] = {
    "claude-opus-5-5": (4.00, 20.00),
    "claude-sonnet-5-5": (2.00, 10.00),
    "claude-haiku-5-5": (0.10, 0.50),
}


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # "auto" uses Anthropic when ANTHROPIC_API_KEY is set, otherwise the offline extractive LLM.
    llm_provider: str = "auto"
    anthropic_api_key: str | None = None
    llm_model: str = "claude-opus-5-5"
    llm_effort: str = "low"
    llm_max_tokens: int = 8000

    # "hashing" needs no download; "bge-m3" needs requirements-ml.txt (sentence-transformers).
    embedder: str = "hashing"
    data_dir: Path = REPO_ROOT / "data" / "policies"

    top_k: int = 5
    candidates: int = 20
    rrf_k: int = 60
    # Below this dense similarity, with no keyword overlap, we answer "not found".
    min_dense_score: float = 0.12

    cors_origins: list[str] = ["http://localhost:3000"]


@lru_cache
def get_settings() -> Settings:
    return Settings()
