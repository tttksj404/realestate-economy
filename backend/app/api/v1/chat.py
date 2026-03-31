import json
import logging
import asyncio
from typing import AsyncGenerator

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.data.schemas import ChatRequest, ChatResponse
from app.services.rag_service import RAGService
from app.services.llm_service import LLMService

logger = logging.getLogger(__name__)

router = APIRouter()


async def sse_event_generator(
    messages: list,
    region: str | None,
    db: AsyncSession,
) -> AsyncGenerator[str, None]:
    """
    SSE (Server-Sent Events) 스트리밍 응답 생성기

    RAG 컨텍스트 검색 → LLM 스트리밍 추론 순서로 처리
    """
    try:
        # 마지막 사용자 메시지 추출
        user_query = ""
        for msg in reversed(messages):
            if msg.get("role") == "user":
                user_query = msg.get("content", "")
                break

        # RAG 컨텍스트 검색
        rag_service = RAGService()
        context = await rag_service.retrieve(
            query=user_query,
            region=region,
        )

        # 컨텍스트 로드 완료 이벤트 전송
        yield f"data: {json.dumps({'type': 'context_loaded', 'region': region}, ensure_ascii=False)}\n\n"

        # LLM 스트리밍 응답
        llm_service = LLMService()
        full_response = ""

        async for token in llm_service.stream_chat(messages=messages, context=context):
            full_response += token
            event_data = json.dumps({"type": "token", "content": token}, ensure_ascii=False)
            yield f"data: {event_data}\n\n"
            # 백프레셔 방지를 위한 짧은 대기
            await asyncio.sleep(0)

        # 완료 이벤트 전송
        done_data = json.dumps(
            {
                "type": "done",
                "full_response": full_response,
                "context_used": bool(context),
            },
            ensure_ascii=False,
        )
        yield f"data: {done_data}\n\n"

    except Exception as e:
        logger.error(f"SSE stream error: {e}", exc_info=True)
        error_data = json.dumps(
            {"type": "error", "message": f"응답 생성 중 오류가 발생했습니다: {str(e)}"},
            ensure_ascii=False,
        )
        yield f"data: {error_data}\n\n"


@router.post(
    "",
    summary="RAG 기반 부동산 AI 채팅",
    description="부동산 시장 분석 데이터를 기반으로 RAG 검색 + LLM 추론을 통해 질의에 답변합니다. SSE 스트리밍 응답.",
    responses={
        200: {
            "description": "SSE 스트리밍 응답",
            "content": {"text/event-stream": {}},
        }
    },
)
async def chat(
    request: ChatRequest,
    db: AsyncSession = Depends(get_db),
) -> StreamingResponse:
    """
    RAG 기반 AI 채팅 (SSE 스트리밍)

    요청 형식:
    - messages: 대화 히스토리 (role: user/assistant)
    - region: 분석 대상 지역 (옵션, 지정 시 해당 지역 중심 RAG)

    응답 이벤트 타입:
    - context_loaded: RAG 컨텍스트 로드 완료
    - token: LLM 생성 토큰
    - done: 전체 응답 완료
    - error: 오류 발생
    """
    if not request.messages:
        raise HTTPException(status_code=400, detail="messages 필드가 비어있습니다.")

    # 마지막 메시지가 user 역할인지 확인
    last_message = request.messages[-1]
    if last_message.role != "user":
        raise HTTPException(status_code=400, detail="마지막 메시지는 user 역할이어야 합니다.")

    messages_dict = [{"role": msg.role, "content": msg.content} for msg in request.messages]

    return StreamingResponse(
        sse_event_generator(
            messages=messages_dict,
            region=request.region,
            db=db,
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",  # nginx 버퍼링 비활성화
        },
    )
