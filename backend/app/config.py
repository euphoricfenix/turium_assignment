"""Application settings, loaded from the environment or backend/.env."""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=BACKEND_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    openai_api_key: str = ""
    chat_model: str = "gpt-4o-mini"
    embedding_model: str = "text-embedding-3-small"

    database_path: Path = BACKEND_DIR / "data" / "knowledge_inbox.db"

    chunk_size: int = 1000
    chunk_overlap: int = 150
    default_top_k: int = 4
    # Cosine score below which retrieved chunks are treated as unrelated to the
    # question. Observed: 0.60 to 0.67 for good matches, under 0.09 for an
    # unrelated question.
    relevance_floor: float = 0.30

    fetch_timeout_seconds: float = 20.0
    max_markdown_chars: int = 20000

    cors_origins: list[str] = ["http://localhost:5173"]
    log_level: str = "INFO"


@lru_cache
def get_settings() -> Settings:
    return Settings()
