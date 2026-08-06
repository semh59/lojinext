"""Unit tests for v2/modules/ai_assistant/api/internal_routes.py.

New file added 2026-08-04 for the prediction_ml_service extraction (Task 5
Step 2b Option B): prediction_service.py's _log_prediction_to_ai (teach)
and prediction_tasks.py's LLM usage reach ai_assistant over HTTP instead of
importing v2.modules.ai_assistant.public directly. No dedicated test
existed for it yet (caught via the hard-gates unit-lane coverage gate,
2026-08-05).
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from v2.modules.ai_assistant.api import internal_routes


@pytest.mark.asyncio
class TestRequireInternalToken:
    async def test_no_secret_configured_non_prod_passes(self):
        with (
            patch.object(internal_routes.settings, "INTERNAL_API_SECRET", ""),
            patch.object(internal_routes.settings, "ENVIRONMENT", "test"),
        ):
            await internal_routes._require_internal_token(x_internal_token=None)

    async def test_no_secret_configured_prod_raises_503(self):
        with (
            patch.object(internal_routes.settings, "INTERNAL_API_SECRET", ""),
            patch.object(internal_routes.settings, "ENVIRONMENT", "prod"),
        ):
            with pytest.raises(HTTPException) as exc_info:
                await internal_routes._require_internal_token(x_internal_token=None)
        assert exc_info.value.status_code == 503

    async def test_wrong_token_raises_401(self):
        with patch.object(internal_routes.settings, "INTERNAL_API_SECRET", "s3cr3t"):
            with pytest.raises(HTTPException) as exc_info:
                await internal_routes._require_internal_token(x_internal_token="wrong")
        assert exc_info.value.status_code == 401


@pytest.mark.asyncio
class TestTeach:
    async def test_delegates_to_smart_ai_and_returns_ok(self):
        mock_smart_ai = MagicMock()
        mock_smart_ai.teach = AsyncMock(return_value=True)

        with patch.object(internal_routes, "get_smart_ai", return_value=mock_smart_ai):
            body = internal_routes.TeachBody(msg="hello", category="genel")
            result = await internal_routes.teach(body)

        assert result == {"ok": True}
        mock_smart_ai.teach.assert_awaited_once_with("hello", category="genel")


@pytest.mark.asyncio
class TestChat:
    async def test_delegates_to_llm_client_and_returns_answer(self):
        mock_llm = MagicMock()
        mock_llm.chat = AsyncMock(return_value="42")

        with patch.object(internal_routes, "get_llm_client", return_value=mock_llm):
            body = internal_routes.ChatBody(
                messages=[internal_routes.ChatMessageBody(role="user", content="soru")],
                system_prompt="be terse",
                max_tokens=256,
                temperature=0.1,
            )
            result = await internal_routes.chat(body)

        assert result == {"answer": "42"}
        mock_llm.chat.assert_awaited_once()
        call_kwargs = mock_llm.chat.call_args.kwargs
        assert call_kwargs["max_tokens"] == 256
        assert call_kwargs["temperature"] == 0.1
        assert call_kwargs["system_prompt"] == "be terse"
        assert len(call_kwargs["messages"]) == 1
        assert call_kwargs["messages"][0].role == "user"
        assert call_kwargs["messages"][0].content == "soru"
