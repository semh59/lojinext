"""Coverage tests for v2/modules/platform_infra/monitoring/external_api_probe.py

Targets ~68% → ≥75%
Covers: _identify_service, _sanitize_url, get_monitored_client,
        emit_network_error, _on_request, _on_response (5xx, 429, slow, ok)
"""

import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# _identify_service
# ---------------------------------------------------------------------------


class TestIdentifyService:
    def test_ors_by_hostname(self):
        from v2.modules.platform_infra.monitoring.external_api_probe import (
            _identify_service,
        )

        assert (
            _identify_service("https://api.openrouteservice.org/v2/directions") == "ors"
        )

    def test_ors_by_prefix(self):
        from v2.modules.platform_infra.monitoring.external_api_probe import (
            _identify_service,
        )

        assert _identify_service("https://ors.example.com/route") == "ors"

    def test_groq_identified(self):
        from v2.modules.platform_infra.monitoring.external_api_probe import (
            _identify_service,
        )

        assert _identify_service("https://api.groq.com/openai/v1/chat") == "groq"

    def test_telegram_identified(self):
        from v2.modules.platform_infra.monitoring.external_api_probe import (
            _identify_service,
        )

        assert (
            _identify_service("https://api.telegram.org/bot123/sendMessage")
            == "telegram"
        )

    def test_mapbox_identified(self):
        from v2.modules.platform_infra.monitoring.external_api_probe import (
            _identify_service,
        )

        assert _identify_service("https://api.mapbox.com/directions/v5") == "mapbox"

    def test_unknown_returns_external(self):
        from v2.modules.platform_infra.monitoring.external_api_probe import (
            _identify_service,
        )

        assert _identify_service("https://some-random-api.io/data") == "external"

    def test_invalid_url_falls_back(self):
        from v2.modules.platform_infra.monitoring.external_api_probe import (
            _identify_service,
        )

        # Should not raise; invalid URL handled via except
        result = _identify_service("not-a-valid-url")
        assert isinstance(result, str)


# ---------------------------------------------------------------------------
# _sanitize_url
# ---------------------------------------------------------------------------


class TestSanitizeUrl:
    def test_removes_query_string(self):
        from v2.modules.platform_infra.monitoring.external_api_probe import (
            _sanitize_url,
        )

        result = _sanitize_url(
            "https://api.mapbox.com/route?access_token=SECRET&steps=true"
        )
        assert "SECRET" not in result
        assert "access_token" not in result

    def test_removes_fragment(self):
        from v2.modules.platform_infra.monitoring.external_api_probe import (
            _sanitize_url,
        )

        result = _sanitize_url("https://example.com/path#section")
        assert "#section" not in result

    def test_truncates_long_url(self):
        from v2.modules.platform_infra.monitoring.external_api_probe import (
            _sanitize_url,
        )

        long_url = "https://example.com/" + "x" * 300
        result = _sanitize_url(long_url)
        assert len(result) <= 200

    def test_port_preserved(self):
        from v2.modules.platform_infra.monitoring.external_api_probe import (
            _sanitize_url,
        )

        result = _sanitize_url("https://example.com:8080/path?q=1")
        assert "8080" in result

    def test_invalid_url_truncates(self):
        from v2.modules.platform_infra.monitoring.external_api_probe import (
            _sanitize_url,
        )

        bad = "not_valid://" + "x" * 300
        result = _sanitize_url(bad)
        assert len(result) <= 200


# ---------------------------------------------------------------------------
# get_monitored_client
# ---------------------------------------------------------------------------


class TestGetMonitoredClient:
    def test_returns_async_client(self):
        """get_monitored_client returns an httpx.AsyncClient."""
        import httpx

        from v2.modules.platform_infra.monitoring.external_api_probe import (
            get_monitored_client,
        )

        client = get_monitored_client(timeout=5.0)
        assert isinstance(client, httpx.AsyncClient)

    def test_event_hooks_include_probe_functions(self):
        """get_monitored_client wires _on_request and _on_response."""
        from v2.modules.platform_infra.monitoring.external_api_probe import (
            _on_request,
            _on_response,
            get_monitored_client,
        )

        client = get_monitored_client()
        assert _on_request in client.event_hooks["request"]
        assert _on_response in client.event_hooks["response"]

    def test_custom_event_hooks_merged(self):
        """get_monitored_client merges custom hooks with probe hooks."""
        from v2.modules.platform_infra.monitoring.external_api_probe import (
            _on_request,
            get_monitored_client,
        )

        my_hook = AsyncMock()
        client = get_monitored_client(event_hooks={"request": [my_hook]})
        # Both probe hook and custom hook should be present
        assert my_hook in client.event_hooks["request"]
        assert _on_request in client.event_hooks["request"]


# ---------------------------------------------------------------------------
# _on_request
# ---------------------------------------------------------------------------


class TestOnRequest:
    async def test_on_request_stores_start_time(self):
        """_on_request stores monotonic start time in request.extensions."""
        from v2.modules.platform_infra.monitoring.external_api_probe import _on_request

        mock_request = MagicMock()
        mock_request.extensions = {}

        before = time.monotonic()
        await _on_request(mock_request)
        after = time.monotonic()

        key = "_probe_start_" + str(id(mock_request))
        assert key in mock_request.extensions
        start = mock_request.extensions[key]
        assert before <= start <= after


# ---------------------------------------------------------------------------
# _on_response
# ---------------------------------------------------------------------------


class TestOnResponse:
    def _make_response(self, status: int, url: str = "https://api.mapbox.com/route"):
        resp = MagicMock()
        resp.status_code = status
        resp.url = url
        req = MagicMock()
        req.extensions = {}
        # Pre-plant a start time
        key = "_probe_start_" + str(id(req))
        req.extensions[key] = time.monotonic() - 0.1  # 100ms ago
        resp.request = req
        return resp

    async def test_on_response_5xx_emits_error(self):
        """_on_response emits ERROR event on 5xx status."""
        from v2.modules.platform_infra.monitoring.external_api_probe import _on_response

        resp = self._make_response(500)

        with patch(
            "v2.modules.platform_infra.monitoring.aemit", new_callable=AsyncMock
        ) as mock_emit:
            await _on_response(resp)
            mock_emit.assert_called()
            event = mock_emit.call_args[0][0]
            assert event.category == "api_5xx"

    async def test_on_response_429_emits_rate_limited(self):
        """_on_response emits WARNING event on 429 status."""
        from v2.modules.platform_infra.monitoring.external_api_probe import _on_response

        resp = self._make_response(429)

        with patch(
            "v2.modules.platform_infra.monitoring.aemit", new_callable=AsyncMock
        ) as mock_emit:
            await _on_response(resp)
            mock_emit.assert_called()
            event = mock_emit.call_args[0][0]
            assert event.category == "api_rate_limited"

    async def test_on_response_slow_emits_warning(self):
        """_on_response emits WARNING event when response is slow."""
        from v2.modules.platform_infra.monitoring.external_api_probe import _on_response

        resp = self._make_response(200)
        # Make it appear very slow (12s elapsed)
        key = "_probe_start_" + str(id(resp.request))
        resp.request.extensions[key] = time.monotonic() - 12.0  # 12s ago

        with patch(
            "v2.modules.platform_infra.monitoring.aemit", new_callable=AsyncMock
        ) as mock_emit:
            await _on_response(resp)
            mock_emit.assert_called()
            categories = [c[0][0].category for c in mock_emit.call_args_list]
            assert "api_slow" in categories

    async def test_on_response_200_no_emit_fast(self):
        """_on_response does not emit events for fast 200 responses."""
        from v2.modules.platform_infra.monitoring.external_api_probe import _on_response

        resp = self._make_response(200)
        # Very fast (start time very close to now)
        key = "_probe_start_" + str(id(resp.request))
        resp.request.extensions[key] = time.monotonic()

        with patch(
            "v2.modules.platform_infra.monitoring.aemit", new_callable=AsyncMock
        ) as mock_emit:
            await _on_response(resp)
            mock_emit.assert_not_called()

    async def test_on_response_no_start_time(self):
        """_on_response handles missing start time (no elapsed_ms)."""
        from v2.modules.platform_infra.monitoring.external_api_probe import _on_response

        resp = self._make_response(200)
        resp.request.extensions = {}  # no start time

        # Should not raise
        with patch(
            "v2.modules.platform_infra.monitoring.aemit", new_callable=AsyncMock
        ) as mock_emit:
            await _on_response(resp)
            mock_emit.assert_not_called()


# ---------------------------------------------------------------------------
# emit_network_error
# ---------------------------------------------------------------------------


class TestEmitNetworkError:
    async def test_emit_network_error_emits_critical(self):
        """emit_network_error emits CRITICAL event for connection failure."""
        import httpx

        from v2.modules.platform_infra.monitoring.external_api_probe import (
            emit_network_error,
        )

        exc = httpx.ConnectError("Connection refused")
        url = "https://api.openrouteservice.org/v2/directions"

        with patch(
            "v2.modules.platform_infra.monitoring.aemit", new_callable=AsyncMock
        ) as mock_emit:
            await emit_network_error(exc, url)
            mock_emit.assert_called_once()
            event = mock_emit.call_args[0][0]
            assert event.category == "api_unreachable"
            assert event.severity.value == "critical"
            assert event.metadata["service"] == "ors"

    async def test_emit_network_error_identifies_service(self):
        """emit_network_error correctly identifies the service."""
        import httpx

        from v2.modules.platform_infra.monitoring.external_api_probe import (
            emit_network_error,
        )

        exc = httpx.TimeoutException("Timeout")
        url = "https://api.groq.com/openai/v1/chat"

        with patch(
            "v2.modules.platform_infra.monitoring.aemit", new_callable=AsyncMock
        ) as mock_emit:
            await emit_network_error(exc, url)
            event = mock_emit.call_args[0][0]
            assert event.metadata["service"] == "groq"
