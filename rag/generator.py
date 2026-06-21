"""RAG answer generation: retrieve context, call Groq LLM, post-process response."""

from __future__ import annotations

import logging

from config.settings import Settings, get_settings
from rag.llm import LLMProvider, get_llm_provider
from rag.models import RAGResponse
from rag.postprocessor import build_rag_response, retrieval_miss_response
from rag.prompts import SYSTEM_PROMPT, build_context_block, build_user_prompt
from rag.retriever import retrieve
from storage.metadata_store import MetadataStore

logger = logging.getLogger(__name__)


def _last_updated_from_sources(settings: Settings) -> str | None:
    metadata = MetadataStore(settings=settings)
    return metadata.get_last_updated_from_sources()


def answer(
    query: str,
    *,
    settings: Settings | None = None,
    llm: LLMProvider | None = None,
) -> RAGResponse:
    """Retrieve chunks, generate a grounded answer, and return the response envelope."""
    cfg = settings or get_settings()
    last_updated = _last_updated_from_sources(cfg)

    try:
        chunks = retrieve(query, settings=cfg)
    except Exception:
        logger.exception("Retrieval failed for query: %s", query)
        return retrieval_miss_response(last_updated_from_sources=last_updated, settings=cfg)

    if not chunks:
        logger.info("Retrieval miss for query: %s", query)
        return retrieval_miss_response(last_updated_from_sources=last_updated, settings=cfg)

    provider = llm or get_llm_provider(cfg.llm.provider)
    context = build_context_block(chunks)
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": build_user_prompt(context, query)},
    ]

    try:
        draft = provider.chat(messages)
    except Exception:
        logger.exception("LLM generation failed for query: %s", query)
        raise

    return build_rag_response(
        draft,
        top_chunk=chunks[0],
        last_updated_from_sources=last_updated,
    )
