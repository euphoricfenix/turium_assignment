# AI Knowledge Inbox

Save notes or URLs, then ask questions answered only from what you saved, with
the source chunks cited back.

- Backend: FastAPI, SQLite, OpenAI embeddings and chat, CrewAI for URL extraction
- Frontend: React, Vite, Tailwind, shadcn/ui, two tabs (Inbox, Chat)
- Environment: uv for Python, npm for the frontend

## Setup

Requires [uv](https://docs.astral.sh/uv/) and Node 18 or newer. uv installs
Python 3.12 itself; CrewAI does not support 3.13 or later.

```bash
# Backend, on http://localhost:8000
cd backend
cp .env.example .env          # then set a real OPENAI_API_KEY
uv sync
uv run uvicorn app.main:app --reload --port 8000

# Frontend, on http://localhost:5173
cd frontend
cp .env.example .env          # only if the backend is not on :8000
npm install
npm run dev

# Tests: chunking, retrieval ranking, citations, history. Offline, no API key.
cd backend && uv run pytest
```

API docs at http://localhost:8000/docs

### Docker

One image, built from the root `Dockerfile`: it compiles the frontend and serves
it from the API, so there is one port, no CORS and nothing to configure.

```bash
cp backend/.env.example backend/.env     # then set OPENAI_API_KEY
docker build -t knowledge-inbox .
docker run -p 8000:8000 --env-file backend/.env -v inbox:/data knowledge-inbox
```

Open http://localhost:8000

The named volume keeps SQLite outside the container, so saved items survive a
restart. The process runs as a non-root user and honours `PORT` if something
assigns one. The frontend is built with an empty `VITE_API_BASE_URL`, so it calls
its own origin with relative paths, and `STATIC_DIR` is what switches the static
mount on. Both are unset in local development, where Vite serves the frontend.

The two services can also run separately, each with its own Dockerfile beside its
code, which is closer to the development layout:

```bash
docker compose up --build                # frontend :5173, backend :8000
```

There `VITE_API_BASE_URL` is a build argument rather than a runtime variable,
because Vite inlines it at build time, and it has to be an address the browser
can reach, which is why compose passes `http://localhost:8000` and not the
`backend` service name.

The image is 1.8 GB, of which roughly 430 MB is CrewAI's transitive tree:
pyarrow, lancedb, kubernetes, onnxruntime and chromadb bindings, pulled in for
agent memory features this app never uses. Dropping CrewAI for a plain fetch
would cut it by about a quarter.

## API

### POST /ingest

```bash
curl -X POST http://localhost:8000/ingest -H 'Content-Type: application/json' \
  -d '{"source_type": "note", "content": "# Chunking\n\nOverlap keeps sentences whole."}'

curl -X POST http://localhost:8000/ingest -H 'Content-Type: application/json' \
  -d '{"source_type": "url", "content": "https://example.com/article"}'
```

`201` with `{"id": 1, "source_type": "note", "title": "Chunking", "chunk_count": 1}`

### GET /items

```bash
curl http://localhost:8000/items
```

`200` with a newest-first list of `{id, source_type, source_url, title, preview,
chunk_count, created_at}`.

### POST /query

```bash
curl -X POST http://localhost:8000/query -H 'Content-Type: application/json' \
  -d '{"question": "Why use overlap when chunking?", "top_k": 4}'

# A follow up: history is optional, capped at ten turns
curl -X POST http://localhost:8000/query -H 'Content-Type: application/json' \
  -d '{"question": "What did he build?",
       "history": [{"role": "user", "text": "Who is Viraj Virk?"},
                   {"role": "assistant", "text": "A CS graduate building AI products."}]}'
```

`200` with:

```json
{
  "answer": "Overlap keeps sentences from being cut at a chunk boundary [1].",
  "sources": [
    {
      "citation": 1,
      "item_id": 1,
      "title": "Chunking",
      "source_url": null,
      "heading_path": "Overlap",
      "snippet": "Overlap keeps sentences whole.",
      "score": 0.8123
    }
  ]
}
```

### Status codes

| Code | Meaning |
| --- | --- |
| 201 | Item ingested |
| 200 | Items listed, or question answered |
| 404 | Question asked but nothing saved yet |
| 422 | Payload failed validation, or a URL yielded no readable content |
| 500 | Misconfigured, for example a rejected API key |
| 502 | The AI provider could not be reached |

## Project structure

```
backend/
  app/
    config.py            Settings from environment or .env
    database.py          SQLite connection and schema
    schemas.py           Request and response models
    routes.py            /ingest, /items, /query
    main.py              App, logging, CORS, error handlers
    services/
      extractor.py       CrewAI crew: URL to markdown
      chunker.py         Heading aware chunking, titles, plain text
      embeddings.py      Embedding calls
      openai_client.py   Shared OpenAI client
      vector_store.py    Persistence and cosine search
      rag.py             Retrieve, prompt, cite, history
  tests/test_core.py     Offline checks, no API key needed
frontend/
  src/
    api/client.js        Single fetch wrapper
    hooks/               useItems, useIngest, useAsk
    components/
      ui/                shadcn primitives
      IngestForm.jsx     Note or URL
      ItemList.jsx       Three most recent, show all toggle
      ChatPanel.jsx      Question, transcript, Clear
      AnswerCard.jsx     Answer with collapsed sources
    App.jsx              Tab shell
```

Two tables: `items(id, source_type, source_url, title, raw_content, created_at)`
and `chunks(id, item_id, chunk_index, heading_path, text, embedding BLOB)`.

## Design decisions

### Chunking

Split on markdown headings first, then window any section over 1000 characters
with 150 of overlap, breaking on a paragraph or word boundary. A heading is the
document's own statement of where a topic ends, which beats a fixed character
count, and it gives every chunk a heading path so a citation reads
"Article > Setup" rather than "chunk 7". Overlap exists because a claim
straddling a boundary is otherwise retrievable from neither side.

The item title and heading path are also prepended to the text before embedding,
while the stored chunk stays clean for citation. Embedding the body alone loses
whatever appears only in a heading, which is where names live: a chunk under
"Hi, I'm Viraj Virk" that never repeats the name could not be retrieved by
asking who that is. That fix moved the top score for the question from 0.24 on
an unrelated document to 0.46 on the right one.

Not done: semantic or recursive chunking. Both need an evaluation set to prove
they win, and there is none here.

### Vector store

SQLite holds embeddings as float32 blobs; search loads them and scores with one
numpy matrix multiply. Exact nearest neighbour, no index to build, no extra
service. Scoring measured at 2 ms for 1000 chunks, 11 ms for 5000 and 89 ms for
50000, which is numpy alone and excludes the SQLite read that dominates at the
top end. A vector database at this size would be infrastructure without a
workload.

### URL extraction through CrewAI

A plain fetch with readability extraction handles most pages and is the first
thing the crew tries. The crew exists for the rest: blocked clients, or bodies
rendered in JavaScript, where the agent searches DuckDuckGo for the same
document and extracts a readable copy instead.

The tradeoff is real. Crew output passes through an LLM told to copy tool output
verbatim, and that instruction is a prompt, not a guarantee. Measured on a 15.5k
character Wikipedia article the output was 99.93 percent identical, losing 21
characters. Small, not zero. Since retrieved text is quoted back as a citation, a
production version would return the deterministic extraction directly and let
the agent only choose which URL to fetch.

### Citations

Markers are parsed out of the answer, so the response carries only the sources
used, each keeping the number the answer cited it by. Filtering without carrying
the number leaves an answer citing [4] beside a list starting at [1].

An answer with no markers is ambiguous: either nothing relevant was retrieved, or
the model omitted them. The top score decides, against `RELEVANCE_FLOOR`,
default 0.30. Above it the chunks were relevant and are returned anyway, so a
forgotten marker costs nothing. Below it nothing is returned, because listing
unrelated chunks beside "the inbox does not cover this" reads as evidence for an
answer never given. The floor comes from the observed spread:

| Question | Top four scores |
| --- | --- |
| What are the major components of Avni? | 0.674, 0.666, 0.647, 0.598 |
| Why does chunking use overlap? | 0.590, 0.464, 0.378, 0.314 |
| What is the capital city of Brazil? | 0.086, 0.076, 0.074, 0.062 |

### Conversation history

`/query` stays stateless. The client sends the turns it wants considered, capped
at six by the frontend and ten by the schema, and nothing is kept between
requests. The transcript in the Chat tab is that history, so Clear drops the
context by construction rather than by remembering to.

History has to reach retrieval, not just the answer call: "What did he build?"
embeds to nothing useful, so the previous question is prepended before embedding.
That took the same follow up from zero sources to four scoring 0.507 to 0.450.
Earlier answers have their citation markers stripped first, since an old [1]
refers to that turn's numbering.

Retrieval prepends the last question rather than paying for a second LLM call to
rewrite the follow up standalone. That covers the pronoun case for free; a topic
switch mid conversation drags the vector toward the earlier subject, and a
rewrite call is the upgrade if that bites.

### Titles and display text

A title is the first markdown heading. For fetched pages that is often noisy
("Chunking - Wikipedia") or too vague to identify in a list ("Introduction"), so
the site suffix is dropped and a short title is qualified with its host:
"Introduction (docs.astral.sh)". The suffix rule is a regex, not a registry, so
it can cut a real trailing clause. Acceptable in a list showing the URL below.

Previews and snippets are stripped of markdown before display, since the answer
renders as plain text and raw `**` would show up literally. The stored chunk
keeps its markdown, which is signal for the model and what retrieval matched on.

### Interface

Two tabs: saving and reading the inbox is a different activity from
interrogating it. The item list shows three most recent with a toggle for the
rest, because the list is context, not the task. Citation markers render as
numbered pills, and the sources sit behind one collapsed row per answer showing
the count and numbers cited, opening to all of them together. Inline snippets
pushed the answer off screen, and a snippet is wanted only when checking a claim.
The chat input is a shadcn input group: send button bottom right, Enter to send,
Shift with Enter for a newline.

## What breaks at scale

- **Full table scan per query.** Every embedding is loaded and scored, so cost
  grows linearly: 2 ms of scoring at 1000 chunks, 89 ms at 50000, plus reading
  every blob out of SQLite on each request. Fix: sqlite-vec locally, or Postgres
  with pgvector once there is more than one user.
- **Synchronous SQLite in async handlers.** Sub-millisecond locally, but the
  single writer lock becomes the bottleneck under real concurrency.
- **Ingestion runs in the request.** Fetch, LLM pass, chunk and embed all finish
  before the response, so a slow page holds a connection for tens of seconds.
  Fix: 202 with an item id, and a queue.
- **Re-embedding is unbounded.** Changing the embedding model, or what is fed to
  it, invalidates every stored vector, and nothing records which model or input
  format produced which row. Fix: store both per chunk and migrate in background.
- **No deduplication.** The same URL ingested twice is stored twice and both
  copies compete for retrieval slots.

## What would change for production

- Authentication and per-user scoping; the schema has no owner column.
- Background ingestion with retries and visible per-item status.
- Postgres with pgvector, and hybrid retrieval so exact terms and names are not
  lost to embedding similarity alone.
- Deterministic extraction in the content path, keeping the LLM out of it.
- Request ids threaded through logs, traces on embedding and LLM calls.
- Rate limiting and a spend cap; OpenAI calls are currently unbounded per request.
- An evaluation set of question and expected-source pairs, so chunking, the
  relevance floor and retrieval changes can be measured instead of guessed at.

## Known limitations

- Single user, no authentication, by design.
- Append only. No delete or edit endpoint.
- URL ingestion caps at 20000 characters of markdown per page.
- Nothing falls back to the open web at query time.
- The chat transcript lives in the browser tab and is gone on reload, taking the
  history with it. Nothing is persisted per conversation.
- Titles are derived at ingestion, so items saved before a change to the title
  rules keep the old title.
- The relevance floor is one hand-tuned threshold, validated on a small corpus.
- Follow up retrieval prepends rather than rewrites, so a mid conversation topic
  switch can pull retrieval toward the earlier subject.
