"""Markdown-aware chunking.

Text is split on markdown headings first, so a chunk rarely spans two topics
and every chunk can cite the section it came from. Sections longer than the
chunk size are then windowed with overlap, breaking on paragraph or word
boundaries so sentences stay intact.
"""

import re
from dataclasses import dataclass
from urllib.parse import urlparse

HEADING_PATTERN = re.compile(r"^(#{1,6})\s+(.+)$")
# "Some Article - Wikipedia", "Docs | Vendor", "Post – Blog"
# ponytail: a regex, not a registry of site names. It will also strip a real
# trailing clause ("How to X - a guide"), which is acceptable in a list that
# shows the source URL underneath. Swap in the og:site_name meta tag if it bites.
SITE_SUFFIX_PATTERN = re.compile(r"\s+[-|\u2013\u2014]\s+[^-|\u2013\u2014]{1,40}$")
MAX_TITLE_LENGTH = 120
# Below this, a title like "Introduction" says nothing on its own.
VAGUE_TITLE_LENGTH = 25


@dataclass(frozen=True)
class Chunk:
    index: int
    heading_path: str
    text: str


def chunk_markdown(markdown: str, chunk_size: int, chunk_overlap: int) -> list[Chunk]:
    if chunk_overlap >= chunk_size:
        raise ValueError("chunk_overlap must be smaller than chunk_size")

    chunks: list[Chunk] = []
    for heading_path, body in _split_on_headings(markdown):
        for piece in _window(body, chunk_size, chunk_overlap):
            chunks.append(Chunk(index=len(chunks), heading_path=heading_path, text=piece))
    return chunks


def embedding_text(title: str, chunk: Chunk) -> str:
    """The string that gets embedded: heading context prepended to the chunk.

    Embedding the chunk body alone loses whatever appears only in a heading,
    and a heading is exactly where a name or a section topic lives. A chunk
    under "Hi, I'm Viraj Virk" that never repeats the name in its body could
    not be retrieved by asking who that is. The stored chunk text stays clean,
    because it is what gets quoted back as a citation.
    """
    prefix = title
    if chunk.heading_path and not title.startswith(chunk.heading_path):
        prefix = f"{title} > {chunk.heading_path}"
    return f"{prefix}\n\n{chunk.text}" if prefix else chunk.text


def derive_title(markdown: str, fallback: str, source_url: str | None = None) -> str:
    """Use the first markdown heading as the title, else the first non-empty line.

    For a page fetched from a URL the raw heading is often either noisy
    ("Chunking - Wikipedia") or too vague to identify in a list
    ("Introduction"), so the site suffix is dropped and a vague title is
    qualified with the host it came from.
    """
    title = fallback
    for line in markdown.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        heading = HEADING_PATTERN.match(stripped)
        title = heading.group(2).strip() if heading else stripped
        break

    if source_url:
        without_suffix = SITE_SUFFIX_PATTERN.sub("", title).strip()
        if len(without_suffix) >= 3:
            title = without_suffix
        host = urlparse(source_url).netloc.removeprefix("www.")
        if host and len(title) < VAGUE_TITLE_LENGTH and host not in title:
            title = f"{title} ({host})"

    return title[:MAX_TITLE_LENGTH]


# Markdown syntax to unwrap when text is shown to a reader rather than fed to
# the model. Bold and italic markers require non-word neighbours so that
# snake_case identifiers survive.
MARKDOWN_SYNTAX = [
    (re.compile(r"`{1,3}([^`]*)`{1,3}"), r"\1"),
    (re.compile(r"!?\[([^\]]*)\]\([^)]*\)"), r"\1"),
    (re.compile(r"(?<!\w)(\*\*|__)(?=\S)(.+?)(?<=\S)\1(?!\w)"), r"\2"),
    (re.compile(r"(?<!\w)([*_])(?=\S)(.+?)(?<=\S)\1(?!\w)"), r"\2"),
    (re.compile(r"^\s{0,3}#{1,6}\s*", re.MULTILINE), ""),
    (re.compile(r"^\s{0,3}[-*+]\s+", re.MULTILINE), ""),
    (re.compile(r"^\s{0,3}>\s?", re.MULTILINE), ""),
]


def plain_text(markdown: str) -> str:
    """Unwrap markdown syntax for display, collapsing whitespace to one line.

    Only for previews and snippets. The stored chunk keeps its markdown,
    because headings and emphasis are signal for the model and the chunk text
    is what retrieval matched on.
    """
    text = markdown
    for pattern, replacement in MARKDOWN_SYNTAX:
        text = pattern.sub(replacement, text)
    return re.sub(r"\s+", " ", text).strip()


def _split_on_headings(markdown: str) -> list[tuple[str, str]]:
    """Return (heading path, body) pairs, the path being "Parent > Child"."""
    sections: list[tuple[str, str]] = []
    headings: list[str] = []
    body: list[str] = []

    def flush() -> None:
        text = "\n".join(body).strip()
        if text:
            sections.append((" > ".join(headings), text))
        body.clear()

    for line in markdown.splitlines():
        heading = HEADING_PATTERN.match(line.strip())
        if heading:
            flush()
            level = len(heading.group(1))
            headings[level - 1 :] = [heading.group(2).strip()]
        else:
            body.append(line)
    flush()
    return sections


def _window(text: str, chunk_size: int, chunk_overlap: int) -> list[str]:
    if len(text) <= chunk_size:
        return [text]

    pieces: list[str] = []
    start = 0
    while start < len(text):
        end = min(start + chunk_size, len(text))
        if end < len(text):
            boundary = text.rfind("\n\n", start + chunk_overlap, end)
            if boundary == -1:
                boundary = text.rfind(" ", start + chunk_overlap, end)
            if boundary != -1:
                end = boundary
        piece = text[start:end].strip()
        if piece:
            pieces.append(piece)
        if end >= len(text):
            break
        start = max(end - chunk_overlap, start + 1)
    return pieces
