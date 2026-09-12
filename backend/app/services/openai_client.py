"""Single shared OpenAI client."""

from functools import lru_cache

from openai import AsyncOpenAI

from app.config import get_settings


@lru_cache
def get_openai_client() -> AsyncOpenAI:
    settings = get_settings()
    if not settings.openai_api_key:
        raise RuntimeError("OPENAI_API_KEY is not set, see backend/.env.example")
    return AsyncOpenAI(api_key=settings.openai_api_key)
