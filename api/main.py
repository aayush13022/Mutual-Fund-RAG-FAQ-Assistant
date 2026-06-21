"""FastAPI application entrypoint."""

from contextlib import asynccontextmanager

from config.settings import configure_logging, get_settings

configure_logging()

from fastapi import FastAPI  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402

from api.routes.chat import router as chat_router  # noqa: E402
from api.routes.corpus import router as corpus_router  # noqa: E402
from api.routes.ingest import router as ingest_router  # noqa: E402
from rag.warmup import warmup_rag_stack  # noqa: E402

settings = get_settings()


@asynccontextmanager
async def lifespan(_: FastAPI):
    warmup_rag_stack(settings)
    yield


app = FastAPI(
    title="Mutual Fund FAQ Assistant",
    description="Facts-only RAG assistant for HDFC mutual fund schemes.",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
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
