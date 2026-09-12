"""Offline checks for the logic that has no business being wrong: chunking,
similarity search and citation parsing. No network, no OpenAI key needed.
"""

import os
import tempfile
from pathlib import Path

os.environ["DATABASE_PATH"] = str(Path(tempfile.mkdtemp()) / "test.db")

import numpy as np  # noqa: E402

from app.database import init_database  # noqa: E402
from app.services.chunker import (  # noqa: E402
    Chunk,
    chunk_markdown,
    derive_title,
    embedding_text,
    plain_text,
)
from app.schemas import Turn  # noqa: E402
from app.services.rag import (  # noqa: E402
    _cited_sources,
    _history_messages,
    _retrieval_query,
)
from app.services.vector_store import count_chunks, list_items, save_item, search  # noqa: E402

MARKDOWN = """# Guide

Intro paragraph.

## Setup

Run the installer.

### Windows

Use the msi.
"""


def test_chunks_carry_their_heading_path():
    chunks = chunk_markdown(MARKDOWN, chunk_size=1000, chunk_overlap=100)
    paths = [chunk.heading_path for chunk in chunks]
    assert paths == ["Guide", "Guide > Setup", "Guide > Setup > Windows"]
    assert [chunk.index for chunk in chunks] == [0, 1, 2]


def test_long_section_is_windowed_with_overlap():
    body = "# Title\n\n" + " ".join(f"word{index}" for index in range(600))
    chunks = chunk_markdown(body, chunk_size=500, chunk_overlap=100)
    assert len(chunks) > 1
    assert all(len(chunk.text) <= 500 for chunk in chunks)
    assert chunks[0].text.split()[-1] in chunks[1].text


def test_derive_title_prefers_the_first_heading():
    assert derive_title(MARKDOWN, fallback="none") == "Guide"
    assert derive_title("plain text note", fallback="none") == "plain text note"
    assert derive_title("", fallback="Untitled note") == "Untitled note"


def test_url_titles_lose_the_site_suffix_and_gain_a_host_when_vague():
    wikipedia = "# Retrieval-augmented generation - Wikipedia\n\nbody"
    assert (
        derive_title(wikipedia, fallback="url", source_url="https://en.wikipedia.org/wiki/RAG")
        == "Retrieval-augmented generation"
    )

    # Too vague to identify in a list, so name where it came from.
    assert (
        derive_title("# Introduction\n\nbody", fallback="url", source_url="https://docs.astral.sh/uv/")
        == "Introduction (docs.astral.sh)"
    )

    # A long descriptive title is left alone, suffix pattern or not.
    descriptive = "# uv - An extremely fast Python package manager\n\nbody"
    assert derive_title(descriptive, fallback="url", source_url="https://docs.astral.sh/uv/") == (
        "uv - An extremely fast Python package manager"
    )

    # Notes are never touched.
    assert derive_title("# Chunking notes\n\nbody", fallback="note") == "Chunking notes"


def test_plain_text_unwraps_markdown_without_eating_identifiers():
    source = (
        "# Heading\n\n**Four components:** 1. **Field App** with `offline` mode.\n"
        "- See [the docs](https://example.com) for *details* on source_type and a_b_c.\n"
        "> A quote."
    )
    assert plain_text(source) == (
        "Heading Four components: 1. Field App with offline mode. "
        "See the docs for details on source_type and a_b_c. A quote."
    )


def test_embedding_text_carries_heading_context():
    chunk = Chunk(index=0, heading_path="Profile > About", text="Fresh CS grad building AI products.")
    assert embedding_text("Viraj Virk", chunk) == (
        "Viraj Virk > Profile > About\n\nFresh CS grad building AI products."
    )

    # A heading that already starts with the title is not repeated.
    same = Chunk(index=0, heading_path="Viraj Virk", text="body")
    assert embedding_text("Viraj Virk", same) == "Viraj Virk\n\nbody"


def test_search_ranks_the_nearest_chunk_first():
    init_database()
    chunks = [
        Chunk(index=0, heading_path="A", text="cats purr"),
        Chunk(index=1, heading_path="B", text="engines roar"),
    ]
    embeddings = np.array([[1.0, 0.0], [0.0, 1.0]], dtype=np.float32)
    item_id = save_item("note", None, "Animals", "cats purr", chunks, embeddings)

    results = search(np.array([0.9, 0.1], dtype=np.float32), top_k=2)
    assert [result["text"] for result in results] == ["cats purr", "engines roar"]
    assert results[0]["score"] > results[1]["score"]
    assert results[0]["item_id"] == item_id

    assert count_chunks() == 2
    assert list_items()[0]["chunk_count"] == 2


FLOOR = 0.30


def matches(top_score=0.7):
    return [
        {"title": "one", "heading_path": "one > Background", "score": top_score},
        {"title": "two", "heading_path": "two", "score": 0.5},
        {"title": "three", "heading_path": "", "score": 0.4},
    ]


def test_retrieval_query_resolves_a_follow_up_against_the_last_question():
    history = [
        Turn(role="user", text="Who is Viraj Virk?"),
        Turn(role="assistant", text="A computer science graduate [1]."),
    ]
    # "he" is meaningless to an embedding on its own.
    assert _retrieval_query("What did he build?", history) == (
        "Who is Viraj Virk?\nWhat did he build?"
    )

    # First question of a conversation is already self contained.
    assert _retrieval_query("Who is Viraj Virk?", []) == "Who is Viraj Virk?"


def test_history_messages_drop_stale_citation_markers():
    history = [
        Turn(role="user", text="Who is Viraj Virk? [1]"),
        Turn(role="assistant", text="A CS graduate [1], building AI products [2]."),
    ]
    messages = _history_messages(history)

    # An earlier answer's [1] points at that turn's chunks, not this turn's.
    assert messages[1] == {"role": "assistant", "content": "A CS graduate , building AI products ."}
    # The user's own words are passed through untouched.
    assert messages[0] == {"role": "user", "content": "Who is Viraj Virk? [1]"}


def test_cited_sources_keeps_the_number_the_answer_used():
    selected = _cited_sources("As shown in [2] and [3].", matches(), FLOOR)
    assert [source["citation"] for source in selected] == [2, 3]
    assert [source["title"] for source in selected] == ["two", "three"]

    # An answer citing [3] must not be shown a list that starts at [1]
    # holding a different chunk.
    assert _cited_sources("See [3] only.", matches(), FLOOR)[0]["citation"] == 3


def test_cited_sources_drops_a_heading_that_repeats_the_title():
    assert _cited_sources("See [1].", matches(), FLOOR)[0]["heading_path"] == "Background"
    assert _cited_sources("See [2].", matches(), FLOOR)[0]["heading_path"] == ""

    # Including when the title carries a site suffix the heading does not.
    suffixed = [{"title": "one - Wikipedia", "heading_path": "one > Background", "score": 0.7}]
    assert _cited_sources("See [1].", suffixed, FLOOR)[0]["heading_path"] == "Background"


def test_missing_citation_markers_fall_back_on_relevance():
    # Relevant chunks, model forgot the markers: keep the sources.
    relevant = _cited_sources("Avni has four components.", matches(top_score=0.67), FLOOR)
    assert [source["citation"] for source in relevant] == [1, 2, 3]

    # Nothing relevant retrieved: no sources to show beside a non answer.
    assert _cited_sources("That is not in the saved items.", matches(top_score=0.2), FLOOR) == []

    # The floor itself counts as relevant.
    assert len(_cited_sources("No markers here.", matches(top_score=FLOOR), FLOOR)) == 3
