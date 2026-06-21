"""Index embedded chunks into ChromaDB with blue/green corpus versioning."""

from __future__ import annotations

import logging
import uuid
from datetime import datetime

from config.settings import Settings, get_settings
from ingestion.embedder import embed_chunks, get_embedding_provider
from ingestion.models import Chunk, IngestionResult, IngestionStatus, SourceIngestionResult
from storage.metadata_store import MetadataStore
from storage.vector_store import VectorStore

logger = logging.getLogger(__name__)


def index_chunks(
    chunks: list[Chunk],
    *,
    settings: Settings | None = None,
    triggered_by: str = "manual",
    ingestion_result: IngestionResult | None = None,
    job_id: str | None = None,
    record_run: bool = True,
) -> str:
    """Embed chunks and atomically publish a new corpus version."""
    if not chunks:
        raise ValueError("Cannot index an empty chunk list")

    cfg = settings or get_settings()
    metadata_store = MetadataStore(settings=cfg)
    vector_store = VectorStore(settings=cfg, metadata_store=metadata_store)

    previous_version = metadata_store.get_corpus_version()
    new_version = metadata_store.next_corpus_version()
    started_at = datetime.now().astimezone()
    run_id = job_id or str(uuid.uuid4())

    try:
        embedded = embed_chunks(chunks, settings=cfg)
        vector_store.upsert(new_version, embedded)

        metadata_store.set_corpus_version(
            active_version=new_version,
            embedding_provider=cfg.embeddings.provider,
            embedding_model_small=cfg.embeddings.model_small,
            embedding_model_large=cfg.embeddings.model_large,
            last_updated_from_sources=MetadataStore.today_source_date(),
        )

        if previous_version and previous_version.active_version != new_version:
            vector_store.delete_version(previous_version.active_version)

        completed_at = datetime.now().astimezone()
        status = ingestion_result.status.value if ingestion_result else IngestionStatus.SUCCESS.value
        if record_run:
            metadata_store.record_ingestion_run(
                job_id=run_id,
                triggered_by=triggered_by,
                status=status,
                documents_processed=ingestion_result.documents_processed if ingestion_result else 0,
                chunks_written=len(chunks),
                started_at=started_at,
                completed_at=completed_at,
            )

        if ingestion_result:
            for source in ingestion_result.source_results:
                metadata_store.upsert_source_document(
                    url=source.url,
                    scheme_name=source.scheme_name,
                    last_status=source.status,
                    last_success_at=completed_at if source.status == "success" else None,
                )

        logger.info("Published corpus version %s with %s chunks", new_version, len(chunks))
        return new_version
    except Exception:
        logger.exception("Failed to publish corpus version %s; keeping previous index", new_version)
        vector_store.delete_version(new_version)
        raise


def update_source_results_with_embedding_counts(
    source_results: list[SourceIngestionResult],
    chunks: list[Chunk],
) -> None:
    counts: dict[str, int] = {}
    for chunk in chunks:
        counts[chunk.scheme_slug] = counts.get(chunk.scheme_slug, 0) + 1
    for result in source_results:
        if result.status == "success":
            result.embedded_count = counts.get(result.scheme_slug, 0)
