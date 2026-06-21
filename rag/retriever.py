"""Tiered hybrid retrieval over the Phase 2 vector store."""

from __future__ import annotations

import logging
from dataclasses import replace

from config.settings import Settings, get_settings
from ingestion.embedder import embed_query
from ingestion.models import SearchResult
from rag.models import RetrievedChunk
from rag.scheme_detector import detect_scheme
from rag.section_detector import detect_section_hint
from storage.vector_store import VectorStore, get_vector_store

logger = logging.getLogger(__name__)

FALLBACK_MIN_CANDIDATES = 3


def model_key_for_section(section_type: str | None, settings: Settings) -> str:
    if settings.embeddings.provider == "openai":
        return "openai"
    if section_type:
        mapped = settings.embeddings.section_model_map.get(section_type)
        if mapped in {"small", "large"}:
            return mapped
    return "large"


def other_model_key(model_key: str) -> str:
    return "small" if model_key == "large" else "large"


def apply_section_boost(
    candidates: list[SearchResult],
    section_hint: str | None,
    settings: Settings | None = None,
) -> list[SearchResult]:
    """Re-rank candidates by adding configured boost when section_type matches hint."""
    if not section_hint or not candidates:
        return candidates

    cfg = settings or get_settings()
    boost_weight = cfg.retrieval.section_boost.get(section_hint, 0.0)
    if boost_weight <= 0:
        return candidates

    boosted: list[SearchResult] = []
    for candidate in candidates:
        score = candidate.score
        if candidate.section_type == section_hint:
            score = min(1.0, score + boost_weight)
        boosted.append(replace(candidate, score=score))

    boosted.sort(key=lambda item: item.score, reverse=True)
    return boosted


def _to_retrieved(result: SearchResult, *, tier: str) -> RetrievedChunk:
    return RetrievedChunk(
        chunk_id=result.chunk_id,
        text=result.text,
        source_url=result.source_url,
        scheme_name=result.scheme_name,
        section_type=result.section_type,
        score=result.score,
        embedding_model_key=result.embedding_model_key,
        retrieval_tier=tier,
    )


def _apply_threshold(results: list[RetrievedChunk], settings: Settings) -> list[RetrievedChunk]:
    threshold = settings.retrieval.similarity_threshold
    metadata_hits = [item for item in results if item.retrieval_tier == "metadata"]
    if metadata_hits:
        return metadata_hits

    passed = [item for item in results if item.score >= threshold]
    return passed


def _dedupe_candidates(candidates: list[SearchResult]) -> list[SearchResult]:
    best_by_id: dict[str, SearchResult] = {}
    for candidate in candidates:
        existing = best_by_id.get(candidate.chunk_id)
        if existing is None or candidate.score > existing.score:
            best_by_id[candidate.chunk_id] = candidate
    return sorted(best_by_id.values(), key=lambda item: item.score, reverse=True)


def _tier1_metadata_retrieve(
    query: str,
    scheme: str,
    section: str,
    settings: Settings,
    vector_store: VectorStore,
) -> list[RetrievedChunk]:
    _ = query
    model_key = model_key_for_section(section, settings)
    hits = vector_store.fetch_by_metadata(
        scheme_name=scheme,
        section_type=section,
        model_key=model_key,
    )
    return [_to_retrieved(hit, tier="metadata") for hit in hits]


def _semantic_retrieve(
    query: str,
    scheme: str | None,
    section: str | None,
    settings: Settings,
    vector_store: VectorStore,
) -> list[SearchResult]:
    candidate_k = settings.retrieval.candidate_k
    provider = settings.embeddings.provider

    if provider == "openai":
        embedding = embed_query(query, model_key="openai", settings=settings)
        return vector_store.search(
            embedding,
            model_key="openai",
            top_k=candidate_k,
            scheme_filter=scheme,
        )

    if section:
        primary_key = model_key_for_section(section, settings)
        embedding = embed_query(query, model_key=primary_key, settings=settings)
        candidates = vector_store.search(
            embedding,
            model_key=primary_key,
            top_k=candidate_k,
            scheme_filter=scheme,
        )
        if len(candidates) < FALLBACK_MIN_CANDIDATES:
            fallback_key = other_model_key(primary_key)
            fallback_embedding = embed_query(query, model_key=fallback_key, settings=settings)
            candidates.extend(
                vector_store.search(
                    fallback_embedding,
                    model_key=fallback_key,
                    top_k=candidate_k,
                    scheme_filter=scheme,
                )
            )
        return _dedupe_candidates(candidates)

    embeddings = {
        key: embed_query(query, model_key=key, settings=settings)
        for key in vector_store.model_keys_for_provider()
    }
    return vector_store.search_all(
        embeddings,
        top_k=candidate_k,
        scheme_filter=scheme,
    )


def retrieve(
    query: str,
    top_k: int | None = None,
    *,
    settings: Settings | None = None,
    vector_store: VectorStore | None = None,
) -> list[RetrievedChunk]:
    """Retrieve ranked chunks for a user query using tiered hybrid routing."""
    cfg = settings or get_settings()
    store = vector_store or get_vector_store()
    limit = top_k or cfg.retrieval.top_k

    scheme = detect_scheme(query, cfg)
    section = detect_section_hint(query, cfg)

    if scheme and section:
        metadata_hits = _tier1_metadata_retrieve(query, scheme, section, cfg, store)
        if metadata_hits:
            return _apply_threshold(metadata_hits, cfg)[:limit]

    candidates = _semantic_retrieve(query, scheme, section, cfg, store)
    boosted = apply_section_boost(candidates, section, cfg)
    retrieved = [_to_retrieved(hit, tier="semantic") for hit in boosted]
    return _apply_threshold(retrieved, cfg)[:limit]
