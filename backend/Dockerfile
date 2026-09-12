FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Dependencies first, so a source edit does not rebuild the whole tree.
COPY pyproject.toml uv.lock ./
RUN uv sync --locked --no-install-project --no-dev

COPY app ./app
RUN uv sync --locked --no-dev

ENV PATH="/app/.venv/bin:$PATH"

# SQLite lives on a mounted volume, so the image itself stays stateless and a
# redeploy does not wipe saved items.
ENV DATABASE_PATH=/data/knowledge_inbox.db
RUN useradd --create-home --uid 1000 app && mkdir -p /data && chown app:app /data
USER app
VOLUME /data

EXPOSE 8000
# Hosts inject PORT; fall back to 8000 when run locally.
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
