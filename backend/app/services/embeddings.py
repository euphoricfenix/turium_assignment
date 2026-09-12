"""Embedding generation."""

import logging

import numpy as np

from app.config import get_settings
from app.services.openai_client import get_openai_client

logger = logging.getLogger(__name__)


async def embed_texts(texts: list[str]) -> np.ndarray:
    """Embed many texts in one request. Returns a (len(texts), dimensions) matrix."""
    settings = get_settings()
    response = await get_openai_client().embeddings.create(
        model=settings.embedding_model,
        input=texts,
    )
    logger.info("event=embedded count=%d model=%s", len(texts), settings.embedding_model)
    return np.array([item.embedding for item in response.data], dtype=np.float32)


async def embed_query(question: str) -> np.ndarray:
    matrix = await embed_texts([question])
    return matrix[0]
