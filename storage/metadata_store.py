"""SQLite metadata store for ingestion runs and corpus versioning."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

from config.settings import Settings, get_settings


@dataclass(frozen=True)
class CorpusVersionInfo:
    active_version: str
    embedding_provider: str
    embedding_model_small: str
    embedding_model_large: str
    last_updated_from_sources: str | None


class MetadataStore:
    def __init__(self, db_path: Path | None = None, settings: Settings | None = None) -> None:
        cfg = settings or get_settings()
        self._db_path = db_path or cfg.metadata_db_path
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self._db_path)
        connection.row_factory = sqlite3.Row
        return connection

    def _init_schema(self) -> None:
        with self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS ingestion_runs (
                    job_id TEXT PRIMARY KEY,
                    triggered_by TEXT,
                    status TEXT,
                    documents_processed INTEGER,
                    chunks_written INTEGER,
                    started_at TEXT,
                    completed_at TEXT,
                    error_log TEXT
                );

                CREATE TABLE IF NOT EXISTS source_documents (
                    url TEXT PRIMARY KEY,
                    scheme_name TEXT,
                    last_success_at TEXT,
                    last_status TEXT
                );

                CREATE TABLE IF NOT EXISTS corpus_version (
                    id INTEGER PRIMARY KEY CHECK (id = 1),
                    active_version TEXT,
                    embedding_provider TEXT,
                    embedding_model_small TEXT,
                    embedding_model_large TEXT,
                    last_updated_from_sources TEXT
                );
                """
            )

    def get_corpus_version(self) -> CorpusVersionInfo | None:
        with self._connect() as connection:
            row = connection.execute("SELECT * FROM corpus_version WHERE id = 1").fetchone()
        if row is None:
            return None
        return CorpusVersionInfo(
            active_version=row["active_version"],
            embedding_provider=row["embedding_provider"] or "",
            embedding_model_small=row["embedding_model_small"] or "",
            embedding_model_large=row["embedding_model_large"] or "",
            last_updated_from_sources=row["last_updated_from_sources"],
        )

    def next_corpus_version(self) -> str:
        current = self.get_corpus_version()
        if current is None or not current.active_version.startswith("v"):
            return "v1"
        try:
            number = int(current.active_version.lstrip("v"))
        except ValueError:
            return "v1"
        return f"v{number + 1}"

    def set_corpus_version(
        self,
        *,
        active_version: str,
        embedding_provider: str,
        embedding_model_small: str,
        embedding_model_large: str,
        last_updated_from_sources: str | None,
    ) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO corpus_version (
                    id, active_version, embedding_provider,
                    embedding_model_small, embedding_model_large,
                    last_updated_from_sources
                ) VALUES (1, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    active_version = excluded.active_version,
                    embedding_provider = excluded.embedding_provider,
                    embedding_model_small = excluded.embedding_model_small,
                    embedding_model_large = excluded.embedding_model_large,
                    last_updated_from_sources = excluded.last_updated_from_sources
                """,
                (
                    active_version,
                    embedding_provider,
                    embedding_model_small,
                    embedding_model_large,
                    last_updated_from_sources,
                ),
            )

    def record_ingestion_run(
        self,
        *,
        job_id: str,
        triggered_by: str,
        status: str,
        documents_processed: int,
        chunks_written: int,
        started_at: datetime,
        completed_at: datetime,
        error_log: str | None = None,
    ) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO ingestion_runs (
                    job_id, triggered_by, status, documents_processed,
                    chunks_written, started_at, completed_at, error_log
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    job_id,
                    triggered_by,
                    status,
                    documents_processed,
                    chunks_written,
                    started_at.isoformat(),
                    completed_at.isoformat(),
                    error_log,
                ),
            )

    def has_running_ingestion(self) -> bool:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT 1 FROM ingestion_runs WHERE status = 'running' LIMIT 1"
            ).fetchone()
        return row is not None

    def begin_ingestion_run(
        self,
        *,
        job_id: str,
        triggered_by: str,
        started_at: datetime,
    ) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO ingestion_runs (
                    job_id, triggered_by, status, documents_processed,
                    chunks_written, started_at, completed_at, error_log
                ) VALUES (?, ?, 'running', 0, 0, ?, NULL, NULL)
                """,
                (job_id, triggered_by, started_at.isoformat()),
            )

    def finalize_ingestion_run(
        self,
        *,
        job_id: str,
        status: str,
        documents_processed: int,
        chunks_written: int,
        completed_at: datetime,
        error_log: str | None = None,
    ) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                UPDATE ingestion_runs
                SET status = ?, documents_processed = ?, chunks_written = ?,
                    completed_at = ?, error_log = ?
                WHERE job_id = ?
                """,
                (
                    status,
                    documents_processed,
                    chunks_written,
                    completed_at.isoformat(),
                    error_log,
                    job_id,
                ),
            )

    def upsert_source_document(
        self,
        *,
        url: str,
        scheme_name: str,
        last_status: str,
        last_success_at: datetime | None = None,
    ) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO source_documents (url, scheme_name, last_success_at, last_status)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(url) DO UPDATE SET
                    scheme_name = excluded.scheme_name,
                    last_success_at = COALESCE(excluded.last_success_at, source_documents.last_success_at),
                    last_status = excluded.last_status
                """,
                (
                    url,
                    scheme_name,
                    last_success_at.isoformat() if last_success_at else None,
                    last_status,
                ),
            )

    def get_last_updated_from_sources(self) -> str | None:
        version = self.get_corpus_version()
        return version.last_updated_from_sources if version else None

    def list_source_documents(self) -> list[dict[str, str | None]]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT url, scheme_name, last_success_at, last_status FROM source_documents ORDER BY scheme_name"
            ).fetchall()
        return [
            {
                "url": row["url"],
                "scheme_name": row["scheme_name"],
                "last_success_at": row["last_success_at"],
                "last_status": row["last_status"],
            }
            for row in rows
        ]

    def get_latest_ingestion_run(self) -> dict[str, str | int | None] | None:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT job_id, triggered_by, status, documents_processed, chunks_written,
                       started_at, completed_at, error_log
                FROM ingestion_runs
                ORDER BY completed_at DESC
                LIMIT 1
                """
            ).fetchone()
        if row is None:
            return None
        return {
            "job_id": row["job_id"],
            "triggered_by": row["triggered_by"],
            "status": row["status"],
            "documents_processed": row["documents_processed"],
            "chunks_written": row["chunks_written"],
            "started_at": row["started_at"],
            "completed_at": row["completed_at"],
            "error_log": row["error_log"],
        }

    @staticmethod
    def today_source_date() -> str:
        return date.today().isoformat()
