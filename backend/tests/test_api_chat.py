import pytest

from app.services.llm_service import LLMService
from app.services.rag_service import RAGService


@pytest.mark.asyncio
async def test_chat_sse_stream_success(monkeypatch, client):
    async def _mock_retrieve(self, query: str, region: str | None = None, **kwargs):
        return "참고 컨텍스트"

    async def _mock_stream_chat(self, messages, context=""):
        for token in ["안녕", "하세요"]:
            yield token

    monkeypatch.setattr(RAGService, "retrieve", _mock_retrieve)
    monkeypatch.setattr(LLMService, "stream_chat", _mock_stream_chat)

    response = await client.post(
        "/api/v1/chat",
        json={
            "messages": [{"role": "user", "content": "서울 시장 어때?"}],
            "region": "11",
            "stream": True,
        },
    )

    assert response.status_code == 200
    assert "event: token" in response.text
    assert "event: done" in response.text


@pytest.mark.asyncio
async def test_chat_invalid_last_role(client):
    response = await client.post(
        "/api/v1/chat",
        json={"messages": [{"role": "assistant", "content": "이미 응답함"}]},
    )

    assert response.status_code == 400
    payload = response.json()
    assert payload["error"]["code"] == "http_error"


@pytest.mark.asyncio
async def test_chat_graceful_fallback_on_llm_error(monkeypatch, client):
    async def _mock_retrieve(self, query: str, region: str | None = None, **kwargs):
        return "컨텍스트"

    async def _broken_stream_chat(self, messages, context=""):
        if False:
            yield ""
        raise RuntimeError("llm unavailable")

    monkeypatch.setattr(RAGService, "retrieve", _mock_retrieve)
    monkeypatch.setattr(LLMService, "stream_chat", _broken_stream_chat)

    response = await client.post(
        "/api/v1/chat",
        json={"messages": [{"role": "user", "content": "부산 전망 알려줘"}]},
    )

    assert response.status_code == 200
    assert "event: token" in response.text
    assert '"fallback": true' in response.text
