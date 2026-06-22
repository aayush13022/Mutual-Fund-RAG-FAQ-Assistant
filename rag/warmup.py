"""Pre-load models and clients so the first chat request is fast."""

from __future__ import annotations

import logging

from config.settings import Settings, get_settings
from ingestion.embedder import embed_query, get_embedding_provider
from rag.llm import get_llm_provider
from storage.vector_store import get_vector_store

logger = logging.getLogger(__name__)


def warmup_rag_stack(settings: Settings | None = None) -> None:
    """Load embedding models, vector store, and LLM client.

    Failures are logged but never raised: a warmup error must not crash the
    API process (which on memory-constrained hosts would cause a restart loop).
    The components load lazily on first request if warmup does not finish.
    """
    cfg = settings or get_settings()

    try:
        get_vector_store()

        if cfg.embeddings.provider == "bge":
            for model_key in ("small", "large"):
                embed_query("warmup", model_key=model_key, settings=cfg)
            logger.info("BGE embedding models warmed up")
        elif cfg.embeddings.provider == "openai":
            embed_query("warmup", model_key="openai", settings=cfg)
            logger.info("OpenAI embedding client warmed up")
        else:
            get_embedding_provider(cfg)
            logger.info("Embedding provider warmed up")

        get_llm_provider(cfg.llm.provider)
        logger.info("LLM provider warmed up")
    except Exception:
        logger.exception("RAG warmup failed; components will load lazily on first request")
