"""Manual ingestion trigger (dev/admin)."""

from __future__ import annotations

import logging

from fastapi import APIRouter

from api.schemas import IngestRunResponse
from ingestion.pipeline import run_ingestion

logger = logging.getLogger(__name__)

router = APIRouter(tags=["ingest"])


@router.post("/ingest/run", response_model=IngestRunResponse)
def ingest_run() -> IngestRunResponse:
    result = run_ingestion(use_cache=True, embed=True, triggered_by="api")
    return IngestRunResponse(
        status=result.status.value,
        job_id=result.job_id,
        documents_processed=result.documents_processed,
        chunks_written=result.chunks_written,
        corpus_version=result.corpus_version,
    )
