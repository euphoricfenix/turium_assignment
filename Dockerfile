# Single image: the built frontend is served by the API, so there is one
# service, one domain and no CORS. Hosts that look for a Dockerfile at the
# repository root find this one with no configuration.

FROM node:22-alpine AS web
WORKDIR /web
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
# Empty base URL means the client calls its own origin with relative paths.
ENV VITE_API_BASE_URL=""
RUN npm run build

FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PYTHONUNBUFFERED=1
WORKDIR /app

COPY backend/pyproject.toml backend/uv.lock ./
RUN uv sync --locked --no-install-project --no-dev

COPY backend/app ./app
RUN uv sync --locked --no-dev
COPY --from=web /web/dist ./static

ENV PATH="/app/.venv/bin:$PATH" \
    DATABASE_PATH=/data/knowledge_inbox.db \
    STATIC_DIR=/app/static

RUN useradd --create-home --uid 1000 app && mkdir -p /data && chown app:app /data
USER app
VOLUME /data

EXPOSE 8000
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
