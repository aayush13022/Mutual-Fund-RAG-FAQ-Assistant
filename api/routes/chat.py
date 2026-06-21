"""Chat API route."""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException
from openai import AuthenticationError

from api.schemas import ChatRequest, ChatResponse
from rag.generator import answer
from rag.guardrails import build_refusal_response, classify, should_refuse

logger = logging.getLogger(__name__)

router = APIRouter(tags=["chat"])


@router.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest) -> ChatResponse:
    message = request.message.strip()
    if not message:
        raise HTTPException(status_code=400, detail="Message cannot be empty.")

    query_type = classify(message)
    logger.info("Classified query as %s", query_type.value)

    if should_refuse(query_type):
        refusal = build_refusal_response()
        return ChatResponse(
            answer=refusal.answer,
            source_url=refusal.source_url,
            last_updated_from_sources=refusal.last_updated_from_sources,
            disclaimer=refusal.disclaimer,
            refused=True,
            educational_link=refusal.educational_link,
        )

    try:
        response = answer(message)
    except AuthenticationError as exc:
        logger.exception("Invalid Groq API key for chat request")
        raise HTTPException(
            status_code=503,
            detail=(
                "Invalid GROQ_API_KEY. Add a valid key to .env or set "
                "LLM_PROVIDER=mock for local development."
            ),
        ) from exc
    except Exception as exc:
        logger.exception("Generation failed for chat request")
        raise HTTPException(
            status_code=503,
            detail="The assistant is temporarily unavailable. Please try again shortly.",
        ) from exc

    return ChatResponse(
        answer=response.answer,
        source_url=response.source_url,
        last_updated_from_sources=response.last_updated_from_sources,
        disclaimer=response.disclaimer,
        refused=response.refused,
        educational_link=response.educational_link,
    )
