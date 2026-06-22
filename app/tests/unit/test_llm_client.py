import httpx
import pytest

from app.core.ai.llm_client import LLMClient, LLMMessage


class _FakeResponse:
    def __init__(self, content: str):
        self._content = content

    def raise_for_status(self):
        return None

    def json(self):
        return {"choices": [{"message": {"content": self._content}}]}


class _FakeClient:
    def __init__(self, *, fail=False, call_counter=None, **kwargs):
        self.fail = fail
        self.call_counter = call_counter

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def post(self, *args, **kwargs):
        if self.call_counter is not None:
            self.call_counter["count"] += 1
        if self.fail:
            raise httpx.HTTPError("boom")
        return _FakeResponse("hello")


@pytest.mark.asyncio
async def test_llm_client_success(monkeypatch):
    # Arrange: stub get_monitored_client (llm_client no longer imports httpx directly)
    monkeypatch.setattr(
        "app.core.ai.llm_client.get_monitored_client",
        lambda **kwargs: _FakeClient(),
    )
    client = LLMClient(api_key="key", model="m")
    msgs = [LLMMessage(role="user", content="hi")]

    # Act
    result = await client.chat(messages=msgs)

    # Assert
    assert result == "hello"


@pytest.mark.asyncio
async def test_llm_client_retries_then_fails(monkeypatch):
    counter = {"count": 0}
    monkeypatch.setattr(
        "app.core.ai.llm_client.get_monitored_client",
        lambda **kwargs: _FakeClient(fail=True, call_counter=counter),
    )
    client = LLMClient(api_key="key", model="m", max_retries=1, timeout_seconds=0.1)
    msgs = [LLMMessage(role="user", content="hi")]

    result = await client.chat(messages=msgs)

    assert "LLM hata" in result
    # 1 initial + 1 retry
    assert counter["count"] == 2
