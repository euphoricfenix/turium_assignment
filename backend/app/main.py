"""FastAPI application: logging, CORS, error handling, routes."""

import logging
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from openai import AuthenticationError, OpenAIError

from app.config import get_settings
from app.database import init_database
from app.routes import router

settings = get_settings()
logging.basicConfig(
    level=settings.log_level,
    format="%(asctime)s level=%(levelname)s logger=%(name)s %(message)s",
)
logger = logging.getLogger("app")


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_database()
    logger.info("event=startup database=%s", settings.database_path)
    yield


app = FastAPI(title="AI Knowledge Inbox", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


@app.middleware("http")
async def log_request(request: Request, call_next):
    started = time.perf_counter()
    response = await call_next(request)
    logger.info(
        "event=request method=%s path=%s status=%d duration_ms=%.1f",
        request.method,
        request.url.path,
        response.status_code,
        (time.perf_counter() - started) * 1000,
    )
    return response


@app.exception_handler(AuthenticationError)
async def handle_authentication_error(request: Request, error: AuthenticationError) -> JSONResponse:
    logger.error("event=openai_auth_failed path=%s error=%s", request.url.path, error)
    return JSONResponse(
        status_code=500,
        content={"detail": "OpenAI rejected the API key, check OPENAI_API_KEY in backend/.env"},
    )


@app.exception_handler(OpenAIError)
async def handle_openai_error(request: Request, error: OpenAIError) -> JSONResponse:
    logger.error("event=openai_error path=%s error=%s", request.url.path, error)
    return JSONResponse(
        status_code=502,
        content={"detail": "The AI provider could not be reached, try again shortly"},
    )


@app.exception_handler(RuntimeError)
async def handle_runtime_error(request: Request, error: RuntimeError) -> JSONResponse:
    logger.error("event=misconfigured path=%s error=%s", request.url.path, error)
    return JSONResponse(status_code=500, content={"detail": str(error)})


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


app.include_router(router)
