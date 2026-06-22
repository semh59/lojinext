import pytest
import respx
from httpx import Response

from app.core.ai.llm_client import LLMClient, LLMMessage


@pytest.mark.anyio
@respx.mock
async def test_llm_client_chat_success_masks_pii():
    route = respx.post("https://api.groq.com/openai/v1/chat/completions").mock(
        return_value=Response(
            200,
            json={
                "choices": [
                    {"message": {"content": "Merhaba, bu bir test cevabıdır."}},
                ]
            },
        )
    )

    client = LLMClient(api_key="dummy", model="llama-3.3-70b-versatile")
    result = await client.chat(
        [
            LLMMessage(role="user", content="TC 12345678901 ile kayıt aç."),
        ],
        system_prompt="Plaka 34ABC123",
    )

    assert "test cevabı" in result
    assert route.called
    # Gönderilen gövde PII maskeli olmalı
    import json

    sent = json.loads(route.calls[0].request.content)
    system = sent["messages"][0]["content"]
    user = sent["messages"][1]["content"]
    assert "[MASKED]" in user
    assert "[PLAKA]" in system


@pytest.mark.anyio
@respx.mock
async def test_llm_client_retries_and_returns_error_on_fail():
    respx.post("https://api.groq.com/openai/v1/chat/completions").mock(
        return_value=Response(500, json={"error": "boom"})
    )

    client = LLMClient(api_key="dummy", timeout_seconds=0.1, max_retries=1)
    result = await client.chat([LLMMessage(role="user", content="hello")])

    assert "LLM hatası" in result
