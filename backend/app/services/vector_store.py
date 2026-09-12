"""Item and chunk persistence, plus cosine similarity search."""

import logging

import numpy as np

from app.database import connect
from app.services.chunker import Chunk, plain_text

logger = logging.getLogger(__name__)
SNIPPET_LENGTH = 320
PREVIEW_LENGTH = 200
# Read extra before stripping markdown, so the trimmed preview still fills out.
PREVIEW_SOURCE_LENGTH = PREVIEW_LENGTH * 3


def save_item(
    source_type: str,
    source_url: str | None,
    title: str,
    raw_content: str,
    chunks: list[Chunk],
    embeddings: np.ndarray,
) -> int:
    with connect() as connection:
        cursor = connection.execute(
            "INSERT INTO items (source_type, source_url, title, raw_content) VALUES (?, ?, ?, ?)",
            (source_type, source_url, title, raw_content),
        )
        item_id = int(cursor.lastrowid)
        connection.executemany(
            "INSERT INTO chunks (item_id, chunk_index, heading_path, text, embedding)"
            " VALUES (?, ?, ?, ?, ?)",
            [
                (item_id, chunk.index, chunk.heading_path, chunk.text, embedding.astype(np.float32).tobytes())
                for chunk, embedding in zip(chunks, embeddings, strict=True)
            ],
        )
    return item_id


def list_items() -> list[dict]:
    with connect() as connection:
        rows = connection.execute(
            f"""
            SELECT i.id,
                   i.source_type,
                   i.source_url,
                   i.title,
                   i.created_at,
                   substr(i.raw_content, 1, {PREVIEW_SOURCE_LENGTH}) AS preview,
                   COUNT(c.id) AS chunk_count
            FROM items i
            LEFT JOIN chunks c ON c.item_id = i.id
            GROUP BY i.id
            ORDER BY i.id DESC
            """
        ).fetchall()
    return [
        {**dict(row), "preview": plain_text(row["preview"])[:PREVIEW_LENGTH]} for row in rows
    ]


def count_chunks() -> int:
    with connect() as connection:
        return int(connection.execute("SELECT COUNT(*) FROM chunks").fetchone()[0])


def search(query_embedding: np.ndarray, top_k: int) -> list[dict]:
    """Return the top_k most similar chunks, each with its parent item.

    ponytail: loads every embedding and scores it in numpy. Exact, no index to
    maintain, and fast enough for a single-user inbox. Past roughly 50k chunks
    move to sqlite-vec or pgvector.
    """
    with connect() as connection:
        rows = connection.execute(
            """
            SELECT c.item_id, c.heading_path, c.text, c.embedding, i.title, i.source_url
            FROM chunks c
            JOIN items i ON i.id = c.item_id
            """
        ).fetchall()
    if not rows:
        return []

    matrix = np.vstack([np.frombuffer(row["embedding"], dtype=np.float32) for row in rows])
    scores = matrix @ query_embedding / (
        np.linalg.norm(matrix, axis=1) * np.linalg.norm(query_embedding) + 1e-10
    )
    ranked = np.argsort(scores)[::-1][:top_k]
    logger.info("event=search chunks=%d top_k=%d", len(rows), top_k)
    return [
        {
            "item_id": rows[index]["item_id"],
            "title": rows[index]["title"],
            "source_url": rows[index]["source_url"],
            "heading_path": rows[index]["heading_path"],
            "text": rows[index]["text"],
            "snippet": plain_text(rows[index]["text"])[:SNIPPET_LENGTH],
            "score": round(float(scores[index]), 4),
        }
        for index in ranked
    ]
