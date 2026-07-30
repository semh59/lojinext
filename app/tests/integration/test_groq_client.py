"""Real-object integration test for GroqService.chat().

0-mock (2026-07-30): moved here from
app/tests/unit/test_groq_service_coverage.py::test_chat_success -- that
file's `unit` marker lane (CI's "Backend unit tests" step) runs before
api_stub is started, so a success-path test needing a real 200 response
from api_stub's /openai/v1/chat/completions stub can only live under
app/tests/integration/ (excluded from that step via
--ignore=app/tests/integration).
"""

from unittest.mock import AsyncMock

import pytest
from groq import AsyncGroq

from app.config import settings


@pytest.mark.asyncio
async def test_chat_success(monkeypatch):
    """Real HTTP against api_stub. GroqService._get_client() builds a real
    AsyncGroq SDK client, which genuinely round-trips through api_stub's
    deterministic /openai/v1/chat/completions stub -- proving the SDK's
    request/response parsing works against a real server, not just a
    MagicMock shaped like one."""
    from v2.modules.ai_assistant.infrastructure.llm.groq_client import GroqService

    monkeypatch.setattr(
        settings, "GROQ_API_BASE_URL", "http://localhost:9000/openai/v1"
    )

    svc = GroqService.__new__(GroqService)
    svc.api_key = "test-key"  # pragma: allowlist secret
    svc.model_name = "llama-3.1-70b-versatile"
    svc.client = AsyncGroq(api_key=svc.api_key, base_url="http://localhost:9000")
    svc._get_client = AsyncMock(return_value=svc.client)

    result = await svc.chat("Tüketim nedir?")
    assert result == "Bu bir test yanıtıdır."
