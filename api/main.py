"""FastAPI application entrypoint."""

import logging
import os
import threading
from contextlib import asynccontextmanager

from config.settings import configure_logging, get_settings

configure_logging()

from fastapi import FastAPI  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402

from api.routes.chat import router as chat_router  # noqa: E402
from api.routes.corpus import router as corpus_router  # noqa: E402
from api.routes.ingest import router as ingest_router  # noqa: E402
from rag.warmup import warmup_rag_stack  # noqa: E402

logger = logging.getLogger(__name__)

settings = get_settings()

DEFAULT_ALLOWED_ORIGINS = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
]


def _allowed_origins() -> list[str]:
    """Combine local defaults with any production origins from CORS_ORIGINS."""
    origins = list(DEFAULT_ALLOWED_ORIGINS)
    extra = os.getenv("CORS_ORIGINS", "")
    for origin in extra.split(","):
        cleaned = origin.strip().rstrip("/")
        if cleaned and cleaned not in origins:
            origins.append(cleaned)
    return origins


def _on_railway() -> bool:
    return bool(os.getenv("RAILWAY_ENVIRONMENT") or os.getenv("RAILWAY_SERVICE_ID"))


def _warmup_enabled() -> bool:
    explicit = os.getenv("WARMUP_ON_STARTUP")
    if explicit is not None:
        return explicit.lower() in {"1", "true", "yes"}
    # Default off on Railway: loading BGE models in the background still OOMs
    # small instances and triggers restart loops.
    if _on_railway():
        return False
    return True


@asynccontextmanager
async def lifespan(_: FastAPI):
    # Warm up in a background thread so the server reaches "startup complete"
    # immediately. Blocking here loads heavy BGE models before the health check
    # can pass, which causes restart loops on memory/timeout-constrained hosts.
    if _warmup_enabled():
        threading.Thread(
            target=warmup_rag_stack,
            args=(settings,),
            name="rag-warmup",
            daemon=True,
        ).start()
        logger.info("RAG warmup started in background")
    elif _on_railway():
        logger.info(
            "RAG warmup disabled on Railway (set WARMUP_ON_STARTUP=true to enable); "
            "BGE_KEEP_SINGLE_MODEL=%s",
            os.getenv("BGE_KEEP_SINGLE_MODEL", "auto-on-railway"),
        )
    else:
        logger.info("RAG warmup disabled (WARMUP_ON_STARTUP=false); loading lazily")
    yield


app = FastAPI(
    title="Mutual Fund FAQ Assistant",
    description="Facts-only RAG assistant for HDFC mutual fund schemes.",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(chat_router)
app.include_router(corpus_router)
app.include_router(ingest_router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/")
def root() -> dict[str, str]:
    return {
        "service": "mutual-fund-faq-assistant",
        "status": "ok",
        "amc": settings.amc,
        "sources": str(len(settings.sources)),
    }
