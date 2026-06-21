"""Corpus status API route."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter

from api.schemas import CorpusStatusResponse, IngestionRunStatus, SourceStatus
from config.settings import get_settings
from storage.metadata_store import MetadataStore

logger = logging.getLogger(__name__)

router = APIRouter(tags=["corpus"])

STALE_CORPUS_HOURS = 48


@router.get("/corpus/status", response_model=CorpusStatusResponse)
def corpus_status() -> CorpusStatusResponse:
    settings = get_settings()
    metadata = MetadataStore(settings=settings)
    version = metadata.get_corpus_version()
    latest_run = metadata.get_latest_ingestion_run()
    sources = metadata.list_source_documents()

    if version and version.last_updated_from_sources:
        try:
            updated = datetime.fromisoformat(version.last_updated_from_sources).replace(tzinfo=timezone.utc)
            age = datetime.now(timezone.utc) - updated
            if age > timedelta(hours=STALE_CORPUS_HOURS):
                logger.warning(
                    "Corpus may be stale: last_updated_from_sources=%s (%.1f hours old)",
                    version.last_updated_from_sources,
                    age.total_seconds() / 3600,
                )
        except ValueError:
            logger.debug("Could not parse last_updated_from_sources for staleness check")

    last_ingestion = None
    if latest_run:
        last_ingestion = IngestionRunStatus(
            job_id=str(latest_run["job_id"]),
            triggered_by=str(latest_run["triggered_by"]) if latest_run["triggered_by"] else None,
            status=str(latest_run["status"]) if latest_run["status"] else None,
            documents_processed=int(latest_run["documents_processed"] or 0),
            chunks_written=int(latest_run["chunks_written"] or 0),
            started_at=str(latest_run["started_at"]) if latest_run["started_at"] else None,
            completed_at=str(latest_run["completed_at"]) if latest_run["completed_at"] else None,
        )

    return CorpusStatusResponse(
        active_version=version.active_version if version else None,
        embedding_provider=version.embedding_provider if version else None,
        last_updated_from_sources=version.last_updated_from_sources if version else None,
        last_ingestion=last_ingestion,
        sources=[
            SourceStatus(
                url=str(item["url"]),
                scheme_name=str(item["scheme_name"]),
                last_success_at=str(item["last_success_at"]) if item["last_success_at"] else None,
                last_status=str(item["last_status"]) if item["last_status"] else None,
            )
            for item in sources
        ],
    )
