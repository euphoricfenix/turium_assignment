"""SQLite connection handling and schema setup."""

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager

from app.config import get_settings

SCHEMA = """
CREATE TABLE IF NOT EXISTS items (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    source_type TEXT    NOT NULL CHECK (source_type IN ('note', 'url')),
    source_url  TEXT,
    title       TEXT    NOT NULL,
    raw_content TEXT    NOT NULL,
    created_at  TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS chunks (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    item_id      INTEGER NOT NULL REFERENCES items(id) ON DELETE CASCADE,
    chunk_index  INTEGER NOT NULL,
    heading_path TEXT    NOT NULL DEFAULT '',
    text         TEXT    NOT NULL,
    embedding    BLOB    NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_chunks_item_id ON chunks(item_id);
"""


@contextmanager
def connect() -> Iterator[sqlite3.Connection]:
    """Open a connection, commit on success, roll back on failure.

    ponytail: synchronous sqlite3 inside async handlers. Local reads are
    sub-millisecond at this scale; move to aiosqlite or Postgres when the
    database stops being a single file on the same machine.
    """
    settings = get_settings()
    settings.database_path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(settings.database_path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    try:
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def init_database() -> None:
    with connect() as connection:
        connection.executescript(SCHEMA)
