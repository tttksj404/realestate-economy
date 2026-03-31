import json
import logging
from collections import defaultdict
from typing import AsyncGenerator

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.data.schemas import ChatRequest
from app.db.database import get_db
from app.services.llm_service import LLMService
from app.services.rag_service import RAGService

logger = logging.getLogger(__name__)

router = APIRouter()

SESSION_HISTORY: dict[str, list[dict[str, str]]] = defaultdict(list)


def _format_sse(event: str, data: dict) -> str:
    payload = json.dumps(data, ensure_ascii=False)
    return f"event: {event}\ndata: {payload}\n\n"


async def _fallback_stream(messages: list[dict[str, str]], context: str) -> AsyncGenerator[str, None]:
    llm = LLMService()
    async for token in llm._fallback_stream(messages=messages, context=context):
        yield _format_sse("token", {"content": token})
    yield _format_sse("done", {"context_used": bool(context), "fallback": True})


async def sse_event_generator(
    messages: list[dict[str, str]],
    region: str | None,
    db: AsyncSession,
) -> AsyncGenerator[str, None]:
    del db

    user_query = ""
    for msg in reversed(messages):
        if msg.get("role") == "user":
            user_query = msg.get("content", "")
            break

    context = ""
    try:
        rag_service = RAGService()
        context = await rag_service.retrieve(query=user_query, region=region)
    except Exception as exc:
        logger.warning("RAG retrieval failed, continue without context: %s", exc)

    yield _format_sse("context", {"region": region, "context_used": bool(context)})

    llm_service = LLMService()
    full_response = ""

    try:
        async for token in llm_service.stream_chat(messages=messages, context=context):
            full_response += token
            yield _format_sse("token", {"content": token})
    except Exception as exc:
        logger.error("LLM stream failed, switching to fallback: %s", exc, exc_info=True)
        async for event in _fallback_stream(messages=messages, context=context):
            yield event
        return

    yield _format_sse(
        "done",
        {
            "context_used": bool(context),
            "full_response": full_response,
        },
    )


@router.post(
    "",
    summary="RAG 기반 부동산 AI 채팅",
    description="RAG 검색 + LLM 추론 기반 SSE 채팅 응답을 반환합니다.",
    responses={200: {"description": "SSE 스트리밍 응답", "content": {"text/event-stream": {}}}},
)
async def chat(
    request: ChatRequest,
    db: AsyncSession = Depends(get_db),
) -> StreamingResponse:
    if not request.messages and not request.session_id:
        raise HTTPException(status_code=400, detail="messages 또는 session_id가 필요합니다.")

    if request.messages:
        last_message = request.messages[-1]
        if last_message.role != "user":
            raise HTTPException(status_code=400, detail="마지막 메시지는 user 역할이어야 합니다.")

    incoming_messages = [{"role": msg.role, "content": msg.content} for msg in request.messages]

    if request.session_id:
        history = SESSION_HISTORY[request.session_id]
        merged_messages = history + incoming_messages
        SESSION_HISTORY[request.session_id] = merged_messages[-30:]
    else:
        merged_messages = incoming_messages

    return StreamingResponse(
        sse_event_generator(messages=merged_messages, region=request.region, db=db),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
