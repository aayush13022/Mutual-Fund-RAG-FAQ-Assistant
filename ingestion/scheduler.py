"""Daily ingestion scheduler worker (Phase 7).

Run as a separate process from the API:

    python -m ingestion.scheduler

For a one-off scheduled job (manual trigger / tests):

    python -m ingestion.scheduler --once

Production cron equivalent (10:00 AM IST daily):

    0 10 * * * cd /path/to/rag-project && .venv/bin/python -m ingestion.scheduler --once
"""

from __future__ import annotations

import argparse
import json
import logging
import threading
import time
import uuid
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger

from config.settings import Settings, configure_logging, get_settings
from ingestion.models import IngestionResult, IngestionStatus, utc_now
from ingestion.pipeline import run_ingestion
from storage.metadata_store import MetadataStore

logger = logging.getLogger(__name__)

STALE_CORPUS_HOURS = 48
_job_lock = threading.Lock()


def parse_daily_cron(cron: str) -> tuple[int, int]:
    """Parse a daily cron expression (minute hour dom month dow) into hour and minute."""
    parts = cron.strip().split()
    if len(parts) != 5:
        raise ValueError(f"Expected 5-field cron expression, got: {cron!r}")
    minute, hour = int(parts[0]), int(parts[1])
    return hour, minute


def build_job_contract(
    *,
    job_id: str,
    triggered_by: str,
    scheduled_at: datetime,
    urls: list[str],
    result: IngestionResult | None,
    duration_seconds: float,
    urls_failed_count: int,
) -> dict[str, object]:
    completed_at = result.completed_at if result else utc_now()
    return {
        "job_id": job_id,
        "triggered_by": triggered_by,
        "scheduled_at": scheduled_at.isoformat(),
        "urls": urls,
        "status": result.status.value if result else IngestionStatus.FAILED.value,
        "documents_processed": result.documents_processed if result else 0,
        "chunks_written": result.chunks_written if result else 0,
        "corpus_version": result.corpus_version if result else None,
        "completed_at": completed_at.isoformat(),
        "ingestion_run_duration_seconds": round(duration_seconds, 2),
        "urls_failed_count": urls_failed_count,
    }


def log_stale_corpus_alert(metadata: MetadataStore) -> None:
    version = metadata.get_corpus_version()
    if not version or not version.last_updated_from_sources:
        return
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


def run_scheduled_ingestion(settings: Settings | None = None) -> IngestionResult | None:
    """Run the daily ingestion job with overlap prevention, retries, and observability."""
    cfg = settings or get_settings()
    metadata = MetadataStore(settings=cfg)
    urls = [source.url for source in cfg.sources]

    if metadata.has_running_ingestion():
        logger.info("Skipping scheduled ingestion: another job is already running")
        return None

    if not _job_lock.acquire(blocking=False):
        logger.info("Skipping scheduled ingestion: worker lock held")
        return None

    job_id = str(uuid.uuid4())
    tz = ZoneInfo(cfg.scheduler.timezone)
    started_at = datetime.now(tz)
    result: IngestionResult | None = None
    error_log: str | None = None

    try:
        metadata.begin_ingestion_run(
            job_id=job_id,
            triggered_by="scheduler",
            started_at=started_at,
        )

        for attempt in range(1, cfg.scheduler.max_retries + 1):
            try:
                result = run_ingestion(
                    settings=cfg,
                    embed=True,
                    triggered_by="scheduler",
                    job_id=job_id,
                    record_run=False,
                )
                if result.status != IngestionStatus.FAILED:
                    break
                error_log = f"status={result.status.value}"
                logger.warning(
                    "Scheduled ingestion attempt %s/%s returned %s",
                    attempt,
                    cfg.scheduler.max_retries,
                    result.status.value,
                )
            except Exception as exc:
                error_log = str(exc)
                logger.exception(
                    "Scheduled ingestion attempt %s/%s failed",
                    attempt,
                    cfg.scheduler.max_retries,
                )
            if attempt < cfg.scheduler.max_retries:
                delay = cfg.scheduler.retry_backoff_seconds * (2 ** (attempt - 1))
                logger.info("Retrying scheduled ingestion in %ss", delay)
                time.sleep(delay)
    finally:
        completed_at = datetime.now(tz)
        duration = (completed_at - started_at).total_seconds()
        urls_failed_count = (
            sum(1 for item in result.source_results if item.status != "success")
            if result
            else len(urls)
        )
        final_status = result.status.value if result else IngestionStatus.FAILED.value

        metadata.finalize_ingestion_run(
            job_id=job_id,
            status=final_status,
            documents_processed=result.documents_processed if result else 0,
            chunks_written=result.chunks_written if result else 0,
            completed_at=completed_at,
            error_log=error_log,
        )

        contract = build_job_contract(
            job_id=job_id,
            triggered_by="scheduler",
            scheduled_at=started_at,
            urls=urls,
            result=result,
            duration_seconds=duration,
            urls_failed_count=urls_failed_count,
        )
        logger.info("ingestion_job_contract=%s", json.dumps(contract, sort_keys=True))
        logger.info(
            "ingestion_run_duration_seconds=%.2f urls_failed_count=%s",
            duration,
            urls_failed_count,
        )
        log_stale_corpus_alert(metadata)
        _job_lock.release()

    return result


def create_scheduler(settings: Settings | None = None) -> BlockingScheduler:
    cfg = settings or get_settings()
    hour, minute = parse_daily_cron(cfg.scheduler.cron)
    scheduler = BlockingScheduler(timezone=cfg.scheduler.timezone)
    scheduler.add_job(
        run_scheduled_ingestion,
        trigger=CronTrigger(hour=hour, minute=minute, timezone=cfg.scheduler.timezone),
        id="daily_corpus_ingestion",
        max_instances=1,
        replace_existing=True,
        kwargs={"settings": cfg},
    )
    return scheduler


def main() -> None:
    parser = argparse.ArgumentParser(description="Daily corpus ingestion scheduler worker")
    parser.add_argument(
        "--once",
        action="store_true",
        help="Run one scheduled ingestion job and exit",
    )
    args = parser.parse_args()

    configure_logging()
    settings = get_settings()

    if args.once:
        run_scheduled_ingestion(settings)
        return

    if not settings.scheduler.enabled:
        logger.info("Scheduler disabled in corpus.yaml; exiting")
        return

    scheduler = create_scheduler(settings)
    logger.info(
        "Starting scheduler worker (cron=%s, timezone=%s)",
        settings.scheduler.cron,
        settings.scheduler.timezone,
    )
    scheduler.start()


if __name__ == "__main__":
    main()
