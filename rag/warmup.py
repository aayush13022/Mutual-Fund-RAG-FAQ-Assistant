"""Pre-load models and clients so the first chat request is fast."""

from __future__ import annotations

import logging
import os

from config.settings import Settings, get_settings
from ingestion.embedder import embed_query, get_embedding_provider
from rag.llm import get_llm_provider
from storage.vector_store import get_vector_store

logger = logging.getLogger(__name__)


def _warmup_embedding_model_keys(provider: str) -> tuple[str, ...]:
    raw = os.getenv("WARMUP_EMBEDDING_MODELS", "").strip()
    if raw:
        return tuple(key.strip() for key in raw.split(",") if key.strip())
    if provider == "bge":
        return ("small",)
    if provider == "openai":
        return ("openai",)
    return ()


def warmup_rag_stack(settings: Settings | None = None) -> None:
    """Load embedding models, vector store, and LLM client.

    Failures are logged but never raised: a warmup error must not crash the
    API process (which on memory-constrained hosts would cause a restart loop).
    The components load lazily on first request if warmup does not finish.
    """
    cfg = settings or get_settings()

    try:
        get_vector_store()

        model_keys = _warmup_embedding_model_keys(cfg.embeddings.provider)
        if model_keys:
            for model_key in model_keys:
                embed_query("warmup", model_key=model_key, settings=cfg)
            logger.info("Embedding models warmed up: %s", ", ".join(model_keys))
        else:
            logger.info("Embedding warmup skipped; models load lazily on first request")

        get_llm_provider(cfg.llm.provider)
        logger.info("LLM provider warmed up")
    except Exception:
        logger.exception("RAG warmup failed; components will load lazily on first request")
