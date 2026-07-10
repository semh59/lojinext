"""token_resolver.resolve_bot_token — admin-configured DB override, else
.env fallback, resolved once at bot process startup.
"""

import sys
from pathlib import Path

import httpx
import respx

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from token_resolver import resolve_bot_token  # noqa: E402

BACKEND = "http://backend:8000"
URL = f"{BACKEND}/api/v1/internal/bot-token/telegram_driver_bot"


@respx.mock
def test_returns_admin_configured_token_when_available():
    respx.get(URL).mock(
        return_value=httpx.Response(200, json={"token": "admin-set-token"})
    )
    result = resolve_bot_token(
        "telegram_driver_bot", BACKEND, "secret", "env-fallback-token"
    )
    assert result == "admin-set-token"


@respx.mock
def test_falls_back_to_env_when_not_configured_404():
    respx.get(URL).mock(return_value=httpx.Response(404))
    result = resolve_bot_token(
        "telegram_driver_bot", BACKEND, "secret", "env-fallback-token"
    )
    assert result == "env-fallback-token"


@respx.mock
def test_falls_back_to_env_on_network_error():
    respx.get(URL).mock(side_effect=httpx.ConnectError("refused"))
    result = resolve_bot_token(
        "telegram_driver_bot", BACKEND, "secret", "env-fallback-token"
    )
    assert result == "env-fallback-token"


@respx.mock
def test_sends_internal_token_header():
    route = respx.get(URL).mock(return_value=httpx.Response(200, json={"token": "x"}))
    resolve_bot_token("telegram_driver_bot", BACKEND, "my-shared-secret", "fallback")
    assert route.calls.last.request.headers["X-Internal-Token"] == "my-shared-secret"


@respx.mock
def test_empty_token_in_response_falls_back_to_env():
    """200 with a null/empty token (row exists but deger_sifreli somehow
    empty) must not be treated as a real value."""
    respx.get(URL).mock(return_value=httpx.Response(200, json={"token": None}))
    result = resolve_bot_token(
        "telegram_driver_bot", BACKEND, "secret", "env-fallback-token"
    )
    assert result == "env-fallback-token"
