"""Intent guardrails: classify user queries before RAG generation."""

from __future__ import annotations

import re
from enum import Enum

from rag.models import RAGResponse
from rag.postprocessor import DISCLAIMER

AMFI_EDUCATIONAL_LINK = "https://www.amfiindia.com/investor/knowledge-center-info"

REFUSAL_MESSAGE = (
    "I can only answer factual questions about mutual fund schemes. "
    "I cannot provide investment advice or recommend funds."
)

ADVISORY_PATTERNS = (
    re.compile(r"\bshould\s+(?:i|we)\s+invest\b", re.I),
    re.compile(r"\bis\s+it\s+(?:good|worth)\b", re.I),
    re.compile(r"\b(?:recommend|recommendation)\b", re.I),
    re.compile(r"\b(?:buy|sell)\b", re.I),
    re.compile(r"\bworth\s+investing\b", re.I),
    re.compile(r"\bgood\s+investment\b", re.I),
)

COMPARISON_PATTERNS = (
    re.compile(r"\bwhich\s+(?:fund\s+)?is\s+better\b", re.I),
    re.compile(r"\bcompare\b", re.I),
    re.compile(r"\bversus\b", re.I),
    re.compile(r"\bvs\.?\b", re.I),
)

PERFORMANCE_CALC_PATTERNS = (
    re.compile(r"\bwhat\s+returns?\s+will\s+i\s+get\b", re.I),
    re.compile(r"\bcalculate\s+returns?\b", re.I),
    re.compile(r"\bexpected\s+returns?\b", re.I),
    re.compile(r"\bhow\s+much\s+will\s+i\s+(?:make|earn|get)\b", re.I),
    re.compile(r"\breturns?\s+in\s+\d+\s+years?\b", re.I),
)

FUND_MANAGEMENT_PATTERNS = (
    re.compile(r"\bfund\s+management\b", re.I),
    re.compile(r"\bfund\s+managers?\b", re.I),
    re.compile(r"\bwho\s+manage", re.I),
    re.compile(r"\btenure\b", re.I),
    re.compile(r"\beducation\b", re.I),
    re.compile(r"\bexperience\b", re.I),
    re.compile(r"\bqualification\b", re.I),
)


class QueryType(str, Enum):
    FACTUAL = "factual"
    FUND_MANAGEMENT = "fund_management"
    ADVISORY = "advisory"
    COMPARISON = "comparison"
    PERFORMANCE_CALC = "performance_calc"


def classify(message: str) -> QueryType:
    """Classify a user message. Refusal types are checked before RAG-eligible types."""
    text = message.strip()
    if not text:
        return QueryType.FACTUAL

    for pattern in ADVISORY_PATTERNS:
        if pattern.search(text):
            return QueryType.ADVISORY

    for pattern in COMPARISON_PATTERNS:
        if pattern.search(text):
            return QueryType.COMPARISON

    for pattern in PERFORMANCE_CALC_PATTERNS:
        if pattern.search(text):
            return QueryType.PERFORMANCE_CALC

    for pattern in FUND_MANAGEMENT_PATTERNS:
        if pattern.search(text):
            return QueryType.FUND_MANAGEMENT

    return QueryType.FACTUAL


def should_refuse(query_type: QueryType) -> bool:
    return query_type in {
        QueryType.ADVISORY,
        QueryType.COMPARISON,
        QueryType.PERFORMANCE_CALC,
    }


def build_refusal_response() -> RAGResponse:
    return RAGResponse(
        answer=REFUSAL_MESSAGE,
        source_url=None,
        last_updated_from_sources=None,
        disclaimer=DISCLAIMER,
        refused=True,
        educational_link=AMFI_EDUCATIONAL_LINK,
    )
