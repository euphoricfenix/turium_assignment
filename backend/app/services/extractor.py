"""URL to markdown, driven by a small CrewAI crew.

A direct fetch handles most pages, so the crew exists for the cases it does
not: pages that block plain HTTP clients or render their body in JavaScript.
There the agent falls back to a DuckDuckGo search for the same document and
extracts a readable copy instead. The agent is told to pass tool output
through verbatim rather than summarise it, because retrieved chunks are
quoted back to the user as citations.
"""

import logging
from typing import Any

import httpx
import trafilatura
from crewai import LLM, Agent, Crew, Task
from crewai.tools import tool

from app.config import get_settings

logger = logging.getLogger(__name__)

NO_CONTENT = "NO_CONTENT"
USER_AGENT = "Mozilla/5.0 (compatible; KnowledgeInbox/0.1; +https://example.com/bot)"
SEARCH_RESULT_LIMIT = 5


@tool("fetch_url_as_markdown")
def fetch_url_as_markdown(url: str) -> str:
    """Download a web page and return its readable content as markdown.

    Returns an empty string when the page cannot be fetched or holds no
    readable text.
    """
    settings = get_settings()
    try:
        response = httpx.get(
            url,
            timeout=settings.fetch_timeout_seconds,
            follow_redirects=True,
            headers={"User-Agent": USER_AGENT},
        )
        response.raise_for_status()
    except httpx.HTTPError as error:
        logger.warning("event=fetch_failed url=%s error=%s", url, error)
        return ""

    body = trafilatura.extract(
        response.text,
        output_format="markdown",
        include_comments=False,
        include_tables=True,
    )
    if not body:
        logger.warning("event=extract_empty url=%s", url)
        return ""

    # The page title becomes an H1 so it shows up as the item title and as the
    # first segment of every chunk's heading path. trafilatura's own
    # with_metadata option emits YAML front matter instead, which is not markdown.
    metadata = trafilatura.extract_metadata(response.text)
    title = (metadata.title or "").strip() if metadata else ""
    markdown = f"# {title}\n\n{body}" if title else body
    return markdown[: settings.max_markdown_chars]


@tool("search_web")
def search_web(query: str) -> str:
    """Search the web with DuckDuckGo.

    Returns the top results as a markdown list of title, URL and snippet, so
    another URL holding the same document can be fetched instead.
    """
    from ddgs import DDGS

    try:
        results: list[dict[str, Any]] = DDGS().text(query, max_results=SEARCH_RESULT_LIMIT)
    except Exception as error:  # ddgs raises library specific errors and rate limits
        logger.warning("event=search_failed query=%s error=%s", query, error)
        return ""

    logger.info("event=searched query=%s results=%d", query, len(results))
    return "\n".join(
        f"- [{result.get('title', 'untitled')}]({result.get('href', '')}) - {result.get('body', '')}"
        for result in results
    )


def _build_crew() -> Crew:
    settings = get_settings()
    extractor = Agent(
        role="Web content extractor",
        goal="Return the readable content of a web page as clean markdown.",
        backstory=(
            "You collect source documents for a knowledge base. You copy what the page says "
            "and never invent, summarise or reword it."
        ),
        tools=[fetch_url_as_markdown, search_web],
        llm=LLM(model=f"openai/{settings.chat_model}", api_key=settings.openai_api_key),
        max_iter=4,
        verbose=False,
    )
    task = Task(
        description=(
            "Extract the readable content of {url} as markdown.\n"
            "1. Call fetch_url_as_markdown with that exact URL.\n"
            "2. If it returns an empty string, call search_web with the URL or its likely title, "
            "choose the result most likely to hold the same document, and fetch that URL instead.\n"
            f"3. If no readable content can be retrieved, return exactly {NO_CONTENT}."
        ),
        expected_output=(
            "The markdown returned by the tool, copied verbatim: no commentary, no summary, "
            f"no added headings. Or the single token {NO_CONTENT}."
        ),
        agent=extractor,
    )
    return Crew(agents=[extractor], tasks=[task], verbose=False)


async def extract_url_markdown(url: str) -> str:
    """Run the crew and return markdown, or an empty string when nothing was readable."""
    settings = get_settings()
    result = await _build_crew().kickoff_async(inputs={"url": url})
    markdown = str(result).strip()
    if not markdown or markdown == NO_CONTENT:
        logger.warning("event=extraction_empty url=%s", url)
        return ""
    logger.info("event=extracted url=%s characters=%d", url, len(markdown))
    return markdown[: settings.max_markdown_chars]
