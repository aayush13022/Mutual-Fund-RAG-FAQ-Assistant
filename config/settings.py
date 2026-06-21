from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CORPUS_PATH = PROJECT_ROOT / "config" / "corpus.yaml"

REQUIRED_SECTIONS = frozenset(
    {
        "overview",
        "expense_ratio",
        "exit_load",
        "minimum_investment",
        "benchmark",
        "tax",
        "fund_management",
        "investment_objective",
        "fund_house",
    }
)

EXPECTED_SOURCE_COUNT = 5


@dataclass(frozen=True)
class SourceConfig:
    scheme_name: str
    url: str
    aliases: tuple[str, ...] = ()


@dataclass(frozen=True)
class EmbeddingConfig:
    provider: str
    model_small: str
    model_large: str
    openai_model: str
    token_threshold: int
    section_model_map: dict[str, str]
    batch_size: int
    cache_by_text_hash: bool


@dataclass(frozen=True)
class ChunkingConfig:
    strategy: str
    chunk_size_tokens: int
    chunk_overlap_tokens: int
    fund_management_split: str
    strip_other_schemes_list: bool


@dataclass(frozen=True)
class RetrievalConfig:
    top_k: int
    candidate_k: int
    similarity_threshold: float
    section_boost: dict[str, float]
    section_keywords: dict[str, tuple[str, ...]]


@dataclass(frozen=True)
class LLMConfig:
    provider: str
    model: str
    temperature: float
    max_tokens: int


@dataclass(frozen=True)
class SchedulerConfig:
    enabled: bool
    cron: str
    timezone: str
    max_retries: int
    retry_backoff_seconds: int


@dataclass(frozen=True)
class Settings:
    amc: str
    sources: tuple[SourceConfig, ...]
    chunking: ChunkingConfig
    embeddings: EmbeddingConfig
    retrieval: RetrievalConfig
    llm: LLMConfig
    sections: tuple[str, ...]
    scheduler: SchedulerConfig
    openai_api_key: str
    groq_api_key: str
    embedding_model: str
    embedding_provider: str
    embedding_model_small: str
    embedding_model_large: str
    llm_model: str
    chroma_persist_dir: Path
    metadata_db_path: Path
    log_level: str
    api_host: str
    api_port: int
    project_root: Path = field(default=PROJECT_ROOT)

    @property
    def allowlisted_urls(self) -> frozenset[str]:
        return frozenset(source.url for source in self.sources)


def _resolve_path(value: str) -> Path:
    path = Path(value)
    if not path.is_absolute():
        path = PROJECT_ROOT / path
    return path


def _load_corpus_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"Corpus config not found: {path}")
    with path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or {}
    if not isinstance(data, dict):
        raise ValueError(f"Invalid corpus config format in {path}")
    return data


def _parse_sources(raw_sources: list[dict[str, Any]]) -> tuple[SourceConfig, ...]:
    if len(raw_sources) != EXPECTED_SOURCE_COUNT:
        raise ValueError(
            f"Expected {EXPECTED_SOURCE_COUNT} sources in corpus.yaml, got {len(raw_sources)}"
        )

    sources: list[SourceConfig] = []
    seen_urls: set[str] = set()

    for entry in raw_sources:
        scheme_name = entry.get("scheme_name", "").strip()
        url = entry.get("url", "").strip()
        aliases = tuple(alias.strip().lower() for alias in entry.get("aliases", []) if alias)

        if not scheme_name or not url:
            raise ValueError("Each source must include scheme_name and url")
        if url in seen_urls:
            raise ValueError(f"Duplicate source URL in corpus.yaml: {url}")

        seen_urls.add(url)
        sources.append(SourceConfig(scheme_name=scheme_name, url=url, aliases=aliases))

    return tuple(sources)


def _parse_sections(raw_sections: list[str]) -> tuple[str, ...]:
    sections = tuple(section.strip() for section in raw_sections if section)
    if set(sections) != REQUIRED_SECTIONS:
        missing = REQUIRED_SECTIONS - set(sections)
        extra = set(sections) - REQUIRED_SECTIONS
        details: list[str] = []
        if missing:
            details.append(f"missing={sorted(missing)}")
        if extra:
            details.append(f"unexpected={sorted(extra)}")
        raise ValueError(f"Invalid sections in corpus.yaml ({', '.join(details)})")
    return sections


def load_settings(env_file: Path | None = None) -> Settings:
    """Load settings from .env and corpus.yaml."""
    env_path = env_file or (PROJECT_ROOT / ".env")
    load_dotenv(env_path, override=False)

    corpus = _load_corpus_yaml(CORPUS_PATH)

    sources = _parse_sources(corpus.get("sources", []))
    sections = _parse_sections(corpus.get("sections", []))

    chunking_raw = corpus.get("chunking", {})
    embeddings_raw = corpus.get("embeddings", {})
    retrieval_raw = corpus.get("retrieval", {})
    llm_raw = corpus.get("llm", {})
    scheduler_raw = corpus.get("scheduler", {})

    section_boost = {
        str(key): float(value)
        for key, value in (retrieval_raw.get("section_boost") or {}).items()
    }

    section_model_map = {
        str(key): str(value)
        for key, value in (embeddings_raw.get("section_model_map") or {}).items()
    }

    section_keywords_raw = retrieval_raw.get("section_keywords") or {}
    section_keywords = {
        str(key): tuple(str(term) for term in terms)
        for key, terms in section_keywords_raw.items()
    }

    similarity_default = retrieval_raw.get("similarity_threshold", 0.55)

    return Settings(
        amc=str(corpus.get("amc", "")).strip(),
        sources=sources,
        chunking=ChunkingConfig(
            strategy=str(chunking_raw.get("strategy", "section_first")),
            chunk_size_tokens=int(chunking_raw.get("chunk_size_tokens", 600)),
            chunk_overlap_tokens=int(chunking_raw.get("chunk_overlap_tokens", 0)),
            fund_management_split=str(chunking_raw.get("fund_management_split", "per_manager")),
            strip_other_schemes_list=bool(chunking_raw.get("strip_other_schemes_list", True)),
        ),
        embeddings=EmbeddingConfig(
            provider=os.getenv("EMBEDDING_PROVIDER", str(embeddings_raw.get("provider", "bge"))).lower(),
            model_small=os.getenv(
                "EMBEDDING_MODEL_SMALL",
                str(embeddings_raw.get("model_small", "BAAI/bge-small-en-v1.5")),
            ),
            model_large=os.getenv(
                "EMBEDDING_MODEL_LARGE",
                str(embeddings_raw.get("model_large", "BAAI/bge-large-en-v1.5")),
            ),
            openai_model=os.getenv("EMBEDDING_MODEL", "text-embedding-3-small"),
            token_threshold=int(embeddings_raw.get("token_threshold", 80)),
            section_model_map=section_model_map,
            batch_size=int(embeddings_raw.get("batch_size", 32)),
            cache_by_text_hash=bool(embeddings_raw.get("cache_by_text_hash", True)),
        ),
        retrieval=RetrievalConfig(
            top_k=int(retrieval_raw.get("top_k", 5)),
            candidate_k=int(retrieval_raw.get("candidate_k", 10)),
            similarity_threshold=float(
                os.getenv("RETRIEVAL_SIMILARITY_THRESHOLD", similarity_default)
            ),
            section_boost=section_boost,
            section_keywords=section_keywords,
        ),
        llm=LLMConfig(
            provider=os.getenv("LLM_PROVIDER", str(llm_raw.get("provider", "groq"))).lower(),
            model=os.getenv("LLM_MODEL", str(llm_raw.get("model", "llama-3.3-70b-versatile"))),
            temperature=float(os.getenv("LLM_TEMPERATURE", llm_raw.get("temperature", 0))),
            max_tokens=int(os.getenv("LLM_MAX_TOKENS", llm_raw.get("max_tokens", 256))),
        ),
        sections=sections,
        scheduler=SchedulerConfig(
            enabled=bool(scheduler_raw.get("enabled", True)),
            cron=str(scheduler_raw.get("cron", "0 10 * * *")),
            timezone=str(scheduler_raw.get("timezone", "Asia/Kolkata")),
            max_retries=int(scheduler_raw.get("max_retries", 3)),
            retry_backoff_seconds=int(scheduler_raw.get("retry_backoff_seconds", 60)),
        ),
        openai_api_key=os.getenv("OPENAI_API_KEY", ""),
        groq_api_key=os.getenv("GROQ_API_KEY", ""),
        embedding_model=os.getenv("EMBEDDING_MODEL", "text-embedding-3-small"),
        embedding_provider=os.getenv("EMBEDDING_PROVIDER", str(embeddings_raw.get("provider", "bge"))).lower(),
        embedding_model_small=os.getenv(
            "EMBEDDING_MODEL_SMALL",
            str(embeddings_raw.get("model_small", "BAAI/bge-small-en-v1.5")),
        ),
        embedding_model_large=os.getenv(
            "EMBEDDING_MODEL_LARGE",
            str(embeddings_raw.get("model_large", "BAAI/bge-large-en-v1.5")),
        ),
        llm_model=os.getenv("LLM_MODEL", str(llm_raw.get("model", "llama-3.3-70b-versatile"))),
        chroma_persist_dir=_resolve_path(os.getenv("CHROMA_PERSIST_DIR", "./data/chroma")),
        metadata_db_path=_resolve_path(os.getenv("METADATA_DB_PATH", "./data/metadata.db")),
        log_level=os.getenv("LOG_LEVEL", "INFO").upper(),
        api_host=os.getenv("API_HOST", "0.0.0.0"),
        api_port=int(os.getenv("API_PORT", "8000")),
    )


@lru_cache
def get_settings() -> Settings:
    """Cached settings accessor for application modules."""
    return load_settings()


def configure_logging(level: str | None = None) -> None:
    """Configure structured logging for ingestion and API paths."""
    settings = get_settings()
    log_level_name = (level or settings.log_level).upper()
    log_level = getattr(logging, log_level_name, logging.INFO)

    logging.basicConfig(
        level=log_level,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
        force=True,
    )

    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.access").setLevel(logging.INFO)
