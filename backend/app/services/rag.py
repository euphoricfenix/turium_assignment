"""Retrieval augmented answering: retrieve, prompt, return cited sources."""

import logging
import re

from app.config import get_settings
from app.schemas import Turn
from app.services.embeddings import embed_query
from app.services.openai_client import get_openai_client
from app.services.vector_store import search

logger = logging.getLogger(__name__)

CITATION_PATTERN = re.compile(r"\[(\d+)\]")

# The answer is rendered as plain text, so markdown would show up as literal
# asterisks and hashes on screen.
SYSTEM_PROMPT = (
    "You answer questions using only the numbered context provided. "
    "Cite the context you use inline as [1], [2] and so on. "
    "If the context does not contain the answer, say so plainly instead of guessing. "
    "Write plain prose only. Do not use any markdown formatting: no asterisks for "
    "bold or italics, no headings, no bullet or numbered lists."
)


async def answer_question(
    question: str,
    top_k: int,
    history: list[Turn] | None = None,
) -> tuple[str, list[dict]]:
    history = history or []
    query_embedding = await embed_query(_retrieval_query(question, history))
    matches = search(query_embedding, top_k)
    if not matches:
        return "", []

    settings = get_settings()
    response = await get_openai_client().chat.completions.create(
        model=settings.chat_model,
        temperature=0,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            *_history_messages(history),
            {"role": "user", "content": _build_prompt(question, matches)},
        ],
    )
    answer = (response.choices[0].message.content or "").strip()
    sources = _cited_sources(answer, matches, settings.relevance_floor)
    logger.info(
        "event=answered question_characters=%d history_turns=%d retrieved=%d cited=%d",
        len(question),
        len(history),
        len(matches),
        len(sources),
    )
    return answer, sources


def _retrieval_query(question: str, history: list[Turn]) -> str:
    """What gets embedded for retrieval, which must stand on its own.

    "What did he build?" embeds to nothing useful, so the previous question is
    prepended to resolve the reference.

    ponytail: prepends the last user turn rather than paying for a second LLM
    call to rewrite the question. Handles the common pronoun follow up; a topic
    switch mid conversation drags the vector toward the old subject. Swap in a
    rewrite call if that shows up in practice.
    """
    previous = [turn.text for turn in history if turn.role == "user"]
    return f"{previous[-1]}\n{question}" if previous else question


def _history_messages(history: list[Turn]) -> list[dict]:
    """Earlier turns as chat messages, with stale citation markers removed.

    An earlier answer's [1] refers to that turn's numbering, not this one's.
    Leaving the markers in invites the model to reuse a number that now points
    at a different chunk.
    """
    return [
        {
            "role": turn.role,
            "content": CITATION_PATTERN.sub("", turn.text).strip()
            if turn.role == "assistant"
            else turn.text,
        }
        for turn in history
    ]


def _build_prompt(question: str, matches: list[dict]) -> str:
    blocks = []
    for number, match in enumerate(matches, start=1):
        label = match["title"]
        section = _section_path(match)
        if section:
            label = f"{label} > {section}"
        blocks.append(f"[{number}] {label}\n{match['text']}")
    context = "\n\n".join(blocks)
    return f"Context:\n{context}\n\nQuestion: {question}"


def _section_path(match: dict) -> str:
    """Drop a leading heading that only repeats the item title."""
    segments = [segment for segment in match["heading_path"].split(" > ") if segment]
    # startswith, not equality: page titles often carry a site suffix, as in
    # "Chunking - Wikipedia" over a leading "Chunking" heading.
    if segments and match["title"].startswith(segments[0]):
        segments = segments[1:]
    return " > ".join(segments)


def _cited_sources(answer: str, matches: list[dict], relevance_floor: float) -> list[dict]:
    """Resolve the sources to return alongside an answer.

    The citation number has to travel with the source, or filtering to the
    cited subset leaves an answer citing [4] beside a list starting at [1].

    An answer with no citation markers is ambiguous: either retrieval found
    nothing worth citing, or the model simply omitted the markers. The top
    score separates the two. Above the floor the chunks were relevant, so they
    are returned and a forgotten marker does not cost the user their sources.
    Below it, nothing is returned, because listing unrelated chunks beside an
    answer that says the inbox does not cover the question would read as
    evidence for an answer that was never given.
    """
    numbered = [
        {**match, "citation": number, "heading_path": _section_path(match)}
        for number, match in enumerate(matches, start=1)
    ]
    cited = {int(number) for number in CITATION_PATTERN.findall(answer)}
    selected = [source for source in numbered if source["citation"] in cited]
    if selected:
        return selected

    # matches arrive ranked, so the first is the best score available.
    if numbered and numbered[0]["score"] >= relevance_floor:
        logger.info("event=citations_missing top_score=%s", numbered[0]["score"])
        return numbered
    return []
