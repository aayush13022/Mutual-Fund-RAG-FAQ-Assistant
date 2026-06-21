"""Prompt templates for facts-only RAG generation."""

from __future__ import annotations

from rag.models import RetrievedChunk

SYSTEM_PROMPT = """You are a facts-only mutual fund FAQ assistant for HDFC schemes listed on Groww.

Rules:
1. Answer ONLY using the provided context chunks.
2. Write at most 3 short sentences.
3. Do not give investment advice, recommendations, or opinions.
4. If the context is insufficient, say: "I could not find this information in my sources."
5. Do not invent numbers, names, dates, or URLs.
6. Use plain English. Do not include markdown links or a source URL in the answer text.
"""


def build_context_block(chunks: list[RetrievedChunk]) -> str:
    blocks: list[str] = []
    for index, chunk in enumerate(chunks, start=1):
        blocks.append(
            f"[Chunk {index} | {chunk.scheme_name} | {chunk.section_type}]\n{chunk.text.strip()}"
        )
    return "\n\n".join(blocks)


def build_user_prompt(context: str, question: str) -> str:
    return f"""Context:
{context}

Question:
{question.strip()}

Write a factual answer in at most 3 sentences using only the context above."""
