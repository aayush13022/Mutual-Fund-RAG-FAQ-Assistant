"""Embedding providers with chunk-aware BGE / OpenAI routing."""

from __future__ import annotations

import hashlib
import logging
import struct
from abc import ABC, abstractmethod
from functools import lru_cache

from config.settings import EmbeddingConfig, Settings, get_settings
from ingestion.chunker import count_tokens
from ingestion.models import Chunk, EmbeddedChunk

logger = logging.getLogger(__name__)

MODEL_DIMENSIONS = {
    "small": 384,
    "large": 1024,
    "openai": 1536,
}


def select_embedding_model_key(chunk: Chunk, config: EmbeddingConfig) -> str:
    if config.provider == "openai":
        return "openai"

    mapped = config.section_model_map.get(chunk.section_type)
    if mapped in {"small", "large"}:
        return mapped
    if count_tokens(chunk.text) <= config.token_threshold:
        return "small"
    return "large"


def model_id_for_key(config: EmbeddingConfig, model_key: str) -> str:
    if model_key == "openai":
        return config.openai_model
    if model_key == "small":
        return config.model_small
    return config.model_large


class EmbeddingProvider(ABC):
    @abstractmethod
    def embed_texts(self, texts: list[str], *, model_key: str) -> list[list[float]]:
        raise NotImplementedError

    def dimension(self, model_key: str) -> int:
        return MODEL_DIMENSIONS[model_key]


class HashEmbeddingProvider(EmbeddingProvider):
    """Deterministic local embeddings for fast tests without model downloads."""

    def embed_texts(self, texts: list[str], *, model_key: str) -> list[list[float]]:
        dim = self.dimension(model_key)
        return [_hash_to_vector(text, dim) for text in texts]


class BGEEmbeddingProvider(EmbeddingProvider):
    def __init__(self, config: EmbeddingConfig) -> None:
        self._config = config
        self._models: dict[str, object] = {}

    def _get_model(self, model_key: str):
        if model_key not in self._models:
            from sentence_transformers import SentenceTransformer

            model_name = model_id_for_key(self._config, model_key)
            logger.info("Loading embedding model: %s", model_name)
            self._models[model_key] = SentenceTransformer(model_name)
        return self._models[model_key]

    def embed_texts(self, texts: list[str], *, model_key: str) -> list[list[float]]:
        if not texts:
            return []
        model = self._get_model(model_key)
        vectors = model.encode(texts, normalize_embeddings=True, show_progress_bar=False)
        return [vector.tolist() for vector in vectors]


class OpenAIEmbeddingProvider(EmbeddingProvider):
    def __init__(self, config: EmbeddingConfig, api_key: str) -> None:
        self._config = config
        self._api_key = api_key
        self._client = None

    def _client_instance(self):
        if self._client is None:
            from openai import OpenAI

            self._client = OpenAI(api_key=self._api_key)
        return self._client

    def embed_texts(self, texts: list[str], *, model_key: str) -> list[list[float]]:
        if not texts:
            return []
        if not self._api_key:
            raise ValueError("OPENAI_API_KEY is required when EMBEDDING_PROVIDER=openai")
        client = self._client_instance()
        response = client.embeddings.create(model=self._config.openai_model, input=texts)
        return [list(item.embedding) for item in response.data]


def _hash_to_vector(text: str, dim: int) -> list[float]:
    digest = hashlib.sha256(text.encode("utf-8")).digest()
    values: list[float] = []
    counter = 0
    while len(values) < dim:
        block = hashlib.sha256(digest + counter.to_bytes(4, "big")).digest()
        counter += 1
        for index in range(0, len(block), 4):
            if len(values) >= dim:
                break
            chunk = block[index : index + 4]
            if len(chunk) < 4:
                chunk = chunk.ljust(4, b"\0")
            value = struct.unpack("!i", chunk)[0] / 2_147_483_647
            values.append(value)
    norm = sum(value * value for value in values) ** 0.5 or 1.0
    return [value / norm for value in values]


@lru_cache
def _get_embedding_provider_cached(provider: str, openai_api_key: str = "") -> EmbeddingProvider:
    if provider == "hash":
        return HashEmbeddingProvider()
    if provider == "openai":
        cfg = get_settings().embeddings
        return OpenAIEmbeddingProvider(cfg, openai_api_key)
    cfg = get_settings().embeddings
    return BGEEmbeddingProvider(cfg)


def get_embedding_provider(settings: Settings | None = None) -> EmbeddingProvider:
    cfg = settings or get_settings()
    return _get_embedding_provider_cached(cfg.embeddings.provider, cfg.openai_api_key)


def embed_chunks(
    chunks: list[Chunk],
    *,
    settings: Settings | None = None,
    provider: EmbeddingProvider | None = None,
) -> list[EmbeddedChunk]:
    cfg = (settings or get_settings()).embeddings
    embedder = provider or get_embedding_provider(settings)
    grouped: dict[str, list[Chunk]] = {}

    for chunk in chunks:
        model_key = select_embedding_model_key(chunk, cfg)
        grouped.setdefault(model_key, []).append(chunk)

    embedded: list[EmbeddedChunk] = []
    for model_key, model_chunks in grouped.items():
        model_id = model_id_for_key(cfg, model_key)
        for start in range(0, len(model_chunks), cfg.batch_size):
            batch = model_chunks[start : start + cfg.batch_size]
            texts = [chunk.text for chunk in batch]
            vectors = embedder.embed_texts(texts, model_key=model_key)
            for chunk, vector in zip(batch, vectors, strict=True):
                embedded.append(
                    EmbeddedChunk(
                        chunk=chunk,
                        embedding=tuple(vector),
                        embedding_model=model_id,
                        embedding_model_key=model_key,
                    )
                )

    return embedded


def embed_query(
    query: str,
    *,
    model_key: str | None = None,
    settings: Settings | None = None,
    provider: EmbeddingProvider | None = None,
) -> list[float]:
    cfg = (settings or get_settings()).embeddings
    embedder = provider or get_embedding_provider(settings)
    key = model_key or ("openai" if cfg.provider == "openai" else "large")
    return embedder.embed_texts([query], model_key=key)[0]
