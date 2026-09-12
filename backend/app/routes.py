"""HTTP endpoints: ingest content, list items, ask questions."""

import logging

from fastapi import APIRouter, HTTPException, status

from app.config import get_settings
from app.schemas import (
    IngestRequest,
    IngestResponse,
    ItemSummary,
    QueryRequest,
    QueryResponse,
)
from app.services.chunker import chunk_markdown, derive_title, embedding_text
from app.services.embeddings import embed_texts
from app.services.extractor import extract_url_markdown
from app.services.rag import answer_question
from app.services.vector_store import count_chunks, list_items, save_item

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/ingest", response_model=IngestResponse, status_code=status.HTTP_201_CREATED)
async def ingest(payload: IngestRequest) -> IngestResponse:
    settings = get_settings()

    if payload.source_type == "url":
        source_url = payload.content
        markdown = await extract_url_markdown(source_url)
        if not markdown:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"No readable content could be extracted from {source_url}",
            )
        title = derive_title(markdown, fallback=source_url, source_url=source_url)
    else:
        source_url = None
        markdown = payload.content
        title = derive_title(markdown, fallback="Untitled note")

    chunks = chunk_markdown(markdown, settings.chunk_size, settings.chunk_overlap)
    if not chunks:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Content held no indexable text",
        )

    embeddings = await embed_texts([embedding_text(title, chunk) for chunk in chunks])
    item_id = save_item(
        source_type=payload.source_type,
        source_url=source_url,
        title=title,
        raw_content=markdown,
        chunks=chunks,
        embeddings=embeddings,
    )
    logger.info(
        "event=ingested item_id=%d source_type=%s chunks=%d",
        item_id,
        payload.source_type,
        len(chunks),
    )
    return IngestResponse(
        id=item_id,
        source_type=payload.source_type,
        title=title,
        chunk_count=len(chunks),
    )


@router.get("/items", response_model=list[ItemSummary])
async def items() -> list[ItemSummary]:
    return [ItemSummary(**row) for row in list_items()]


@router.post("/query", response_model=QueryResponse)
async def query(payload: QueryRequest) -> QueryResponse:
    settings = get_settings()
    if count_chunks() == 0:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Nothing has been saved yet, add a note or a URL first",
        )

    answer, sources = await answer_question(
        payload.question,
        payload.top_k or settings.default_top_k,
        payload.history,
    )
    return QueryResponse(answer=answer, sources=sources)
