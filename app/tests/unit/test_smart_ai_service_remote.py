import pytest


class _DummyKB:
    def __init__(self):
        self.model = None

    async def search(self, question: str, top_k: int = 3):
        return [
            {"id": "1", "category": "demo", "score": 0.9, "content": "demo content"},
        ]

    def get_stats(self):
        return {"total_documents": 1, "storage_path": "/tmp", "initialized": True}


class _FakeLLM:
    def __init__(self):
        self.calls = []

    async def chat(
        self, messages, max_tokens: int, temperature: float, system_prompt: str
    ):
        self.calls.append(
            {
                "messages": messages,
                "max_tokens": max_tokens,
                "temperature": temperature,
                "system_prompt": system_prompt,
            }
        )
        return "OK"


@pytest.mark.asyncio
async def test_smart_ai_ask_uses_remote_llm(monkeypatch):
    # Lazy import to patch before class creation
    import app.services.smart_ai_service as sai

    # KB'yi hafif stub ile değiştir
    monkeypatch.setattr(sai, "KnowledgeBase", _DummyKB)
    fake_llm = _FakeLLM()
    # _get_llm içinde dinamik import edilen fonksiyonu patch'le
    import app.core.ai.llm_client as llm_mod

    monkeypatch.setattr(llm_mod, "get_llm_client", lambda: fake_llm)

    svc = sai.SmartAIService()

    resp = await svc.ask("test question", use_context=True)

    assert resp["answer"] == "OK"
    assert resp["context_used"] is True
    assert fake_llm.calls, "LLM should be called"
    # system prompt must include logistics hint
    assert "lojistik" in fake_llm.calls[0]["system_prompt"]
