"""RAG retrieval layer: scheme detection, section hints, and ranked chunk retrieval."""

from rag.generator import answer
from rag.models import RAGResponse, RetrievedChunk
from rag.retriever import apply_section_boost, retrieve
from rag.scheme_detector import detect_scheme
from rag.section_detector import detect_section_hint

__all__ = [
    "RAGResponse",
    "RetrievedChunk",
    "answer",
    "apply_section_boost",
    "detect_scheme",
    "detect_section_hint",
    "retrieve",
]
