"""
Coverage tests for app/core/ai/groq_service.py
Targets: ChatMessage, GroqService.__init__, chat, chat_stream, _prepare_messages,
         get_groq_service singleton.
"""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

pytestmark = pytest.mark.unit

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_service_no_key():
    """GroqService with no API key."""
    from app.core.ai.groq_service import GroqService

    svc = GroqService.__new__(GroqService)
    svc.api_key = None
    svc.model_name = "llama-3.1-70b-versatile"
    svc.client = None
    return svc


def _make_service_with_client():
    """GroqService with a mocked Groq client."""
    from app.core.ai.groq_service import GroqService

    svc = GroqService.__new__(GroqService)
    svc.api_key = "test-key"  # pragma: allowlist secret
    svc.model_name = "llama-3.1-70b-versatile"
    svc.client = MagicMock()
    return svc


def _make_chat_message(role: str = "user", content: str = "hello"):
    from app.core.ai.groq_service import ChatMessage

    return ChatMessage(role=role, content=content)


# ---------------------------------------------------------------------------
# ChatMessage dataclass
# ---------------------------------------------------------------------------


def test_chat_message_defaults():
    msg = _make_chat_message()
    assert msg.role == "user"
    assert msg.content == "hello"
    assert msg.timestamp is not None
    assert msg.timestamp.tzinfo is not None  # UTC


def test_chat_message_explicit_timestamp():
    from app.core.ai.groq_service import ChatMessage

    ts = datetime(2024, 1, 1, 12, 0, tzinfo=timezone.utc)
    msg = ChatMessage(role="assistant", content="response", timestamp=ts)
    assert msg.timestamp == ts


def test_chat_message_role_assistant():
    msg = _make_chat_message(role="assistant", content="I'm here to help.")
    assert msg.role == "assistant"


# ---------------------------------------------------------------------------
# GroqService.__init__ — no API key
# ---------------------------------------------------------------------------


def test_groq_service_init_no_key():
    from app.core.ai.groq_service import GroqService

    mock_settings = MagicMock()
    mock_settings.GROQ_API_KEY = None
    mock_settings.GROQ_MODEL_NAME = "test-model"

    with patch("app.core.ai.groq_service.settings", mock_settings):
        svc = GroqService()
    assert svc.client is None


def test_groq_service_init_with_key_no_groq_package():
    """When groq package is absent, client stays None but no exception."""
    from app.core.ai.groq_service import GroqService

    mock_settings = MagicMock()
    mock_key = MagicMock()
    mock_key.get_secret_value.return_value = "sk-test"  # pragma: allowlist secret
    mock_settings.GROQ_API_KEY = mock_key
    mock_settings.GROQ_MODEL_NAME = "llama"

    with (
        patch("app.core.ai.groq_service.settings", mock_settings),
        patch("app.core.ai.groq_service.AsyncGroq", None),
    ):
        svc = GroqService()
    assert svc.client is None


def test_groq_service_init_with_key_and_groq():
    """Happy path: key present + AsyncGroq available → client created."""
    from app.core.ai.groq_service import GroqService

    mock_settings = MagicMock()
    mock_key = MagicMock()
    mock_key.get_secret_value.return_value = "sk-real-key"  # pragma: allowlist secret
    mock_settings.GROQ_API_KEY = mock_key
    mock_settings.GROQ_MODEL_NAME = "llama-70b"

    mock_groq_cls = MagicMock()
    mock_groq_cls.return_value = MagicMock()

    with (
        patch("app.core.ai.groq_service.settings", mock_settings),
        patch("app.core.ai.groq_service.AsyncGroq", mock_groq_cls),
    ):
        svc = GroqService()

    expected_key = "sk-real-key"  # pragma: allowlist secret
    assert svc.client is not None
    mock_groq_cls.assert_called_once_with(api_key=expected_key)


# ---------------------------------------------------------------------------
# GroqService.chat — no client
# ---------------------------------------------------------------------------


async def test_chat_no_client_returns_error_message():
    svc = _make_service_no_key()
    result = await svc.chat("Merhaba")
    assert "anahtarı" in result or "ayarlanmamış" in result


# ---------------------------------------------------------------------------
# GroqService.chat — with client, success
# ---------------------------------------------------------------------------


async def test_chat_success():
    svc = _make_service_with_client()

    mock_completion = MagicMock()
    mock_completion.choices[0].message.content = "Yakıt tüketimi normaldir."
    svc.client.chat = MagicMock()
    svc.client.chat.completions = MagicMock()
    svc.client.chat.completions.create = AsyncMock(return_value=mock_completion)

    result = await svc.chat("Tüketim nedir?")
    assert result == "Yakıt tüketimi normaldir."


async def test_chat_with_history():
    svc = _make_service_with_client()
    history = [_make_chat_message("user", "Q1"), _make_chat_message("assistant", "A1")]

    mock_completion = MagicMock()
    mock_completion.choices[0].message.content = "Cevap."
    svc.client.chat = MagicMock()
    svc.client.chat.completions = MagicMock()
    svc.client.chat.completions.create = AsyncMock(return_value=mock_completion)

    result = await svc.chat("Soru?", history=history)
    assert result == "Cevap."

    # Check messages dict was passed
    assert svc.client.chat.completions.create.called


async def test_chat_with_context():
    svc = _make_service_with_client()

    mock_completion = MagicMock()
    mock_completion.choices[0].message.content = "Yanıt."
    svc.client.chat = MagicMock()
    svc.client.chat.completions = MagicMock()
    svc.client.chat.completions.create = AsyncMock(return_value=mock_completion)

    result = await svc.chat("Soru?", context="Araç verisi: 35 L/100km")
    assert result == "Yanıt."


async def test_chat_with_system_prompt():
    svc = _make_service_with_client()

    mock_completion = MagicMock()
    mock_completion.choices[0].message.content = "Sistem yanıtı."
    svc.client.chat = MagicMock()
    svc.client.chat.completions = MagicMock()
    svc.client.chat.completions.create = AsyncMock(return_value=mock_completion)

    result = await svc.chat("Soru?", system_prompt="Sen bir uzman AI'sın.")
    assert result == "Sistem yanıtı."


async def test_chat_exception_returns_error_str():
    svc = _make_service_with_client()
    svc.client.chat = MagicMock()
    svc.client.chat.completions = MagicMock()
    svc.client.chat.completions.create = AsyncMock(
        side_effect=Exception("Connection refused")
    )

    result = await svc.chat("Soru?")
    assert "Hata" in result
    assert "Connection refused" in result


# ---------------------------------------------------------------------------
# GroqService.chat_stream — no client
# ---------------------------------------------------------------------------


async def test_chat_stream_no_client():
    svc = _make_service_no_key()
    chunks = []
    async for chunk in svc.chat_stream("Test"):
        chunks.append(chunk)
    assert len(chunks) == 1
    assert "anahtarı" in chunks[0] or "ayarlanmamış" in chunks[0]


# ---------------------------------------------------------------------------
# GroqService.chat_stream — with client
# ---------------------------------------------------------------------------


async def test_chat_stream_success():
    svc = _make_service_with_client()

    # Build fake async iterable of chunks
    mock_chunk1 = MagicMock()
    mock_chunk1.choices[0].delta.content = "Merhaba "
    mock_chunk2 = MagicMock()
    mock_chunk2.choices[0].delta.content = "dünya"
    mock_chunk3 = MagicMock()
    mock_chunk3.choices[0].delta.content = None  # empty content → skipped

    async def _fake_stream():
        for c in [mock_chunk1, mock_chunk2, mock_chunk3]:
            yield c

    mock_stream = _fake_stream()
    svc.client.chat = MagicMock()
    svc.client.chat.completions = MagicMock()
    svc.client.chat.completions.create = AsyncMock(return_value=mock_stream)

    chunks = []
    async for chunk in svc.chat_stream("Test"):
        chunks.append(chunk)

    assert "Merhaba " in chunks
    assert "dünya" in chunks
    assert None not in chunks


async def test_chat_stream_exception():
    svc = _make_service_with_client()
    svc.client.chat = MagicMock()
    svc.client.chat.completions = MagicMock()
    svc.client.chat.completions.create = AsyncMock(
        side_effect=Exception("Stream error")
    )

    chunks = []
    async for chunk in svc.chat_stream("Test"):
        chunks.append(chunk)

    assert len(chunks) == 1
    assert "Hata" in chunks[0]


# ---------------------------------------------------------------------------
# _prepare_messages
# ---------------------------------------------------------------------------


def test_prepare_messages_no_optional():
    svc = _make_service_no_key()
    msgs = svc._prepare_messages("Hello", None, None, None)
    assert len(msgs) == 1
    assert msgs[0]["role"] == "user"
    assert msgs[0]["content"] == "Hello"


def test_prepare_messages_with_system_prompt():
    svc = _make_service_no_key()
    msgs = svc._prepare_messages("Q?", None, None, "Be helpful.")
    assert msgs[0]["role"] == "system"
    assert msgs[0]["content"] == "Be helpful."
    assert msgs[-1]["role"] == "user"


def test_prepare_messages_with_context():
    svc = _make_service_no_key()
    msgs = svc._prepare_messages("Q?", None, "Context data here", None)
    system_msgs = [m for m in msgs if m["role"] == "system"]
    assert len(system_msgs) == 1
    assert "Context data here" in system_msgs[0]["content"]


def test_prepare_messages_with_history_last5():
    svc = _make_service_no_key()
    history = [_make_chat_message("user", f"Q{i}") for i in range(10)]
    msgs = svc._prepare_messages("Final Q", history, None, None)
    # Should include last 5 from history + 1 final user message
    assert len(msgs) == 6  # 5 history + 1 current


def test_prepare_messages_with_system_context_history():
    svc = _make_service_no_key()
    history = [
        _make_chat_message("user", "Q1"),
        _make_chat_message("assistant", "A1"),
    ]
    msgs = svc._prepare_messages("Q?", history, "ctx", "sys")
    roles = [m["role"] for m in msgs]
    # system first (system_prompt), then system (context), then history, then user
    assert roles[0] == "system"
    assert roles[-1] == "user"


def test_prepare_messages_empty_history():
    svc = _make_service_no_key()
    msgs = svc._prepare_messages("Q?", [], None, None)
    assert len(msgs) == 1
    assert msgs[0]["role"] == "user"


# ---------------------------------------------------------------------------
# get_groq_service singleton
# ---------------------------------------------------------------------------


def test_get_groq_service_singleton():
    import app.core.ai.groq_service as mod

    orig = mod._groq_service
    mod._groq_service = None
    try:
        mock_settings = MagicMock()
        mock_settings.GROQ_API_KEY = None
        mock_settings.GROQ_MODEL_NAME = "test"

        with patch("app.core.ai.groq_service.settings", mock_settings):
            s1 = mod.get_groq_service()
            s2 = mod.get_groq_service()
        assert s1 is s2
    finally:
        mod._groq_service = orig


def test_get_groq_service_returns_groq_service_instance():
    import app.core.ai.groq_service as mod
    from app.core.ai.groq_service import GroqService

    orig = mod._groq_service
    mod._groq_service = None
    try:
        mock_settings = MagicMock()
        mock_settings.GROQ_API_KEY = None
        mock_settings.GROQ_MODEL_NAME = "test"

        with patch("app.core.ai.groq_service.settings", mock_settings):
            svc = mod.get_groq_service()
        assert isinstance(svc, GroqService)
    finally:
        mod._groq_service = orig
