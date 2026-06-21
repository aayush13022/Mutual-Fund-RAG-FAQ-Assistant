"""Phase 7 scheduler and observability tests."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest

from config.settings import get_settings, load_settings
from ingestion.models import IngestionResult, IngestionStatus, SourceIngestionResult, utc_now
from ingestion.scheduler import (
    build_job_contract,
    create_scheduler,
    parse_daily_cron,
    run_scheduled_ingestion,
)
from storage.metadata_store import MetadataStore


@pytest.fixture
def scheduler_settings(tmp_path, monkeypatch):
    monkeypatch.setenv("CHROMA_PERSIST_DIR", str(tmp_path / "chroma"))
    monkeypatch.setenv("METADATA_DB_PATH", str(tmp_path / "metadata.db"))
    get_settings.cache_clear()
    settings = load_settings()
    yield settings
    get_settings.cache_clear()


def test_parse_daily_cron_10am_ist():
    hour, minute = parse_daily_cron("0 10 * * *")
    assert hour == 10
    assert minute == 0


def test_scheduler_registers_daily_job_at_10am(scheduler_settings):
    assert scheduler_settings.scheduler.cron == "0 10 * * *"
    assert scheduler_settings.scheduler.timezone == "Asia/Kolkata"
    scheduler = create_scheduler(scheduler_settings)
    job = scheduler.get_job("daily_corpus_ingestion")
    assert job is not None
    assert job.max_instances == 1
    assert "hour='10'" in str(job.trigger)
    assert "minute='0'" in str(job.trigger)


def test_run_scheduled_ingestion_skips_when_job_running(scheduler_settings):
    metadata = MetadataStore(settings=scheduler_settings)
    metadata.begin_ingestion_run(
        job_id="running-job",
        triggered_by="scheduler",
        started_at=utc_now(),
    )

    with patch("ingestion.scheduler.run_ingestion") as mock_run:
        result = run_scheduled_ingestion(scheduler_settings)

    assert result is None
    mock_run.assert_not_called()


@patch("ingestion.scheduler.run_ingestion")
def test_run_scheduled_ingestion_retries_then_succeeds(mock_run, scheduler_settings):
    success = IngestionResult(
        status=IngestionStatus.SUCCESS,
        started_at=utc_now(),
        completed_at=utc_now(),
        documents_processed=5,
        sections_written=45,
        chunks_written=51,
        corpus_version="v2",
        job_id="job-1",
    )
    mock_run.side_effect = [
        IngestionResult(
            status=IngestionStatus.FAILED,
            started_at=utc_now(),
            completed_at=utc_now(),
            documents_processed=0,
            sections_written=0,
        ),
        success,
    ]

    with patch("ingestion.scheduler.time.sleep"):
        result = run_scheduled_ingestion(scheduler_settings)

    assert result == success
    assert mock_run.call_count == 2

    metadata = MetadataStore(settings=scheduler_settings)
    latest = metadata.get_latest_ingestion_run()
    assert latest is not None
    assert latest["status"] == "success"
    assert latest["documents_processed"] == 5


@patch("ingestion.scheduler.run_ingestion")
def test_run_scheduled_ingestion_logs_job_contract(mock_run, scheduler_settings, caplog):
    mock_run.return_value = IngestionResult(
        status=IngestionStatus.PARTIAL,
        started_at=utc_now(),
        completed_at=utc_now(),
        documents_processed=4,
        sections_written=36,
        chunks_written=40,
        corpus_version="v3",
        job_id="job-partial",
        source_results=[
            SourceIngestionResult(
                url="https://groww.in/mutual-funds/hdfc-defence-fund-direct-growth",
                scheme_name="HDFC Defence Fund Direct Growth",
                scheme_slug="hdfc-defence-fund-direct-growth",
                status="success",
            ),
            SourceIngestionResult(
                url="https://groww.in/mutual-funds/hdfc-mid-cap-fund-direct-growth",
                scheme_name="HDFC Mid Cap Fund Direct Growth",
                scheme_slug="hdfc-mid-cap-fund-direct-growth",
                status="failed",
                error="timeout",
            ),
        ],
    )

    with caplog.at_level("INFO"):
        run_scheduled_ingestion(scheduler_settings)

    contract_logs = [record.message for record in caplog.records if "ingestion_job_contract=" in record.message]
    assert contract_logs
    payload = json.loads(contract_logs[0].split("=", 1)[1])
    assert payload["triggered_by"] == "scheduler"
    assert payload["status"] == "partial"
    assert payload["urls_failed_count"] == 1
    assert "ingestion_run_duration_seconds" in payload


def test_build_job_contract_shape():
    started = utc_now()
    result = IngestionResult(
        status=IngestionStatus.SUCCESS,
        started_at=started,
        completed_at=started,
        documents_processed=5,
        sections_written=45,
        chunks_written=51,
        corpus_version="v1",
        job_id="job-123",
    )
    contract = build_job_contract(
        job_id="job-123",
        triggered_by="scheduler",
        scheduled_at=started,
        urls=["https://example.com/fund"],
        result=result,
        duration_seconds=12.5,
        urls_failed_count=0,
    )
    assert contract["status"] == "success"
    assert contract["documents_processed"] == 5
    assert contract["chunks_written"] == 51


@patch("ingestion.scheduler.logger")
def test_stale_corpus_alert_logged(mock_logger, scheduler_settings):
    metadata = MetadataStore(settings=scheduler_settings)
    stale_date = (datetime.now(timezone.utc) - timedelta(hours=72)).date().isoformat()
    metadata.set_corpus_version(
        active_version="v1",
        embedding_provider="bge",
        embedding_model_small="small",
        embedding_model_large="large",
        last_updated_from_sources=stale_date,
    )

    with patch("ingestion.scheduler.run_ingestion") as mock_run:
        mock_run.return_value = IngestionResult(
            status=IngestionStatus.SUCCESS,
            started_at=utc_now(),
            completed_at=utc_now(),
            documents_processed=5,
            sections_written=45,
            chunks_written=51,
        )
        run_scheduled_ingestion(scheduler_settings)

    warning_calls = [call.args[0] for call in mock_logger.warning.call_args_list]
    assert any("Corpus may be stale" in message for message in warning_calls)
