"""ChromaDB vector store with dual-collection support for BGE models."""

from __future__ import annotations

import logging
from functools import lru_cache
from typing import Any

import chromadb

from config.settings import Settings, get_settings
from ingestion.models import EmbeddedChunk, SearchResult
from storage.metadata_store import MetadataStore

logger = logging.getLogger(__name__)


class VectorStore:
    def __init__(
        self,
        settings: Settings | None = None,
        metadata_store: MetadataStore | None = None,
    ) -> None:
        self._settings = settings or get_settings()
        self._metadata = metadata_store or MetadataStore(settings=self._settings)
        self._client = chromadb.PersistentClient(path=str(self._settings.chroma_persist_dir))

    def _collection_name(self, version: str, model_key: str) -> str:
        if self._settings.embeddings.provider == "openai":
            return f"corpus_{version}_openai"
        return f"corpus_{version}_bge_{model_key}"

    def _get_collection(self, version: str, model_key: str):
        return self._client.get_or_create_collection(
            name=self._collection_name(version, model_key),
            metadata={"hnsw:space": "cosine"},
        )

    def active_version(self) -> str | None:
        info = self._metadata.get_corpus_version()
        return info.active_version if info else None

    def model_keys_for_provider(self) -> list[str]:
        if self._settings.embeddings.provider == "openai":
            return ["openai"]
        return ["small", "large"]

    def upsert(self, version: str, embedded_chunks: list[EmbeddedChunk]) -> None:
        grouped: dict[str, list[EmbeddedChunk]] = {}
        for item in embedded_chunks:
            grouped.setdefault(item.embedding_model_key, []).append(item)

        for model_key, items in grouped.items():
            collection = self._get_collection(version, model_key)
            collection.upsert(
                ids=[item.chunk.chunk_id for item in items],
                embeddings=[list(item.embedding) for item in items],
                documents=[item.chunk.text for item in items],
                metadatas=[self._chunk_metadata(item) for item in items],
            )
            logger.info(
                "Upserted %s chunks into %s",
                len(items),
                self._collection_name(version, model_key),
            )

    def delete_version(self, version: str) -> None:
        for model_key in self.model_keys_for_provider():
            name = self._collection_name(version, model_key)
            try:
                self._client.delete_collection(name)
                logger.info("Deleted collection %s", name)
            except Exception:
                logger.debug("Collection %s not found for deletion", name)

    def count(self, *, version: str | None = None, model_key: str | None = None) -> int:
        active = version or self.active_version()
        if not active:
            return 0
        if model_key:
            return self._get_collection(active, model_key).count()
        return sum(self.count(version=active, model_key=key) for key in self.model_keys_for_provider())

    @staticmethod
    def _build_where(
        scheme_filter: str | None = None,
        section_filter: str | None = None,
    ) -> dict[str, Any] | None:
        clauses: list[dict[str, str]] = []
        if scheme_filter:
            clauses.append({"scheme_name": scheme_filter})
        if section_filter:
            clauses.append({"section_type": section_filter})
        if not clauses:
            return None
        if len(clauses) == 1:
            return clauses[0]
        return {"$and": clauses}

    def fetch_by_metadata(
        self,
        *,
        scheme_name: str,
        section_type: str,
        model_key: str,
        version: str | None = None,
    ) -> list[SearchResult]:
        """Fetch chunks by scheme + section without vector similarity (Tier 1 routing)."""
        active = version or self.active_version()
        if not active:
            return []

        where = self._build_where(scheme_filter=scheme_name, section_filter=section_type)
        collection = self._get_collection(active, model_key)
        if collection.count() == 0:
            return []

        result = collection.get(where=where, include=["documents", "metadatas"])
        ids = result.get("ids") or []
        documents = result.get("documents") or []
        metadatas = result.get("metadatas") or []

        parsed: list[SearchResult] = []
        for chunk_id, text, metadata in zip(ids, documents, metadatas, strict=True):
            parsed.append(
                SearchResult(
                    chunk_id=chunk_id,
                    text=text or "",
                    source_url=str(metadata.get("source_url", "")),
                    scheme_name=str(metadata.get("scheme_name", "")),
                    section_type=str(metadata.get("section_type", "")),
                    score=1.0,
                    embedding_model_key=str(metadata.get("embedding_model_key", model_key)),
                )
            )
        parsed.sort(key=lambda item: item.chunk_id)
        return parsed

    def search(
        self,
        query_embedding: list[float],
        *,
        model_key: str,
        top_k: int = 5,
        version: str | None = None,
        scheme_filter: str | None = None,
        section_filter: str | None = None,
    ) -> list[SearchResult]:
        active = version or self.active_version()
        if not active:
            return []

        where = self._build_where(scheme_filter=scheme_filter, section_filter=section_filter)

        collection = self._get_collection(active, model_key)
        if collection.count() == 0:
            return []

        result = collection.query(
            query_embeddings=[query_embedding],
            n_results=min(top_k, collection.count()),
            where=where,
        )
        return self._parse_results(result, model_key)

    def search_all(
        self,
        query_embeddings: dict[str, list[float]],
        *,
        top_k: int = 5,
        version: str | None = None,
        scheme_filter: str | None = None,
        section_filter: str | None = None,
    ) -> list[SearchResult]:
        merged: list[SearchResult] = []
        for model_key, embedding in query_embeddings.items():
            merged.extend(
                self.search(
                    embedding,
                    model_key=model_key,
                    top_k=top_k,
                    version=version,
                    scheme_filter=scheme_filter,
                    section_filter=section_filter,
                )
            )
        merged.sort(key=lambda item: item.score, reverse=True)
        return merged[:top_k]

    @staticmethod
    def _chunk_metadata(item: EmbeddedChunk) -> dict[str, str | int | float]:
        chunk = item.chunk
        metadata: dict[str, str | int | float] = {
            "source_url": chunk.source_url,
            "scheme_name": chunk.scheme_name,
            "scheme_slug": chunk.scheme_slug,
            "section_type": chunk.section_type,
            "embedding_model": item.embedding_model,
            "embedding_model_key": item.embedding_model_key,
            "ingested_at": chunk.ingested_at.isoformat(),
            "sequence": chunk.sequence,
        }
        if chunk.manager_name:
            metadata["manager_name"] = chunk.manager_name
        return metadata

    @staticmethod
    def _parse_results(result: dict[str, Any], model_key: str) -> list[SearchResult]:
        parsed: list[SearchResult] = []
        ids = (result.get("ids") or [[]])[0]
        documents = (result.get("documents") or [[]])[0]
        metadatas = (result.get("metadatas") or [[]])[0]
        distances = (result.get("distances") or [[]])[0]

        for chunk_id, text, metadata, distance in zip(ids, documents, metadatas, distances, strict=True):
            score = 1.0 - float(distance)
            parsed.append(
                SearchResult(
                    chunk_id=chunk_id,
                    text=text or "",
                    source_url=str(metadata.get("source_url", "")),
                    scheme_name=str(metadata.get("scheme_name", "")),
                    section_type=str(metadata.get("section_type", "")),
                    score=score,
                    embedding_model_key=str(metadata.get("embedding_model_key", model_key)),
                )
            )
        return parsed


@lru_cache
def get_vector_store() -> VectorStore:
    """Cached vector store for request-time retrieval."""
    return VectorStore(settings=get_settings())
