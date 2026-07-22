"""
ExternalService coverage tests.

Targets missing lines in v2/modules/route_simulation/infrastructure/external_service.py (~30% → ≥70%).
Covers:
  - Circuit breaker logic (closed, open, half-open recovery)
  - get_weather_forecast (happy path, circuit open, HTTP error, network exception)
  - get_weather_current_batch (empty coords, circuit open, 429 retry, happy path, exception)
  - get_weather_archive (circuit open, happy path, exception)
  - close() client lifecycle
  - get_external_service() singleton
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# Helper factories
# ---------------------------------------------------------------------------


def _make_service():
    """Fresh ExternalService with mocked HTTP client factory."""
    from v2.modules.route_simulation.infrastructure.external_service import (
        ExternalService,
    )

    svc = ExternalService()
    return svc


def _mock_response(status_code=200, json_data=None):
    resp = MagicMock(spec=httpx.Response)
    resp.status_code = status_code
    resp.headers = {}
    resp.json = MagicMock(return_value=json_data or {"daily": {}})
    if status_code >= 400:
        resp.raise_for_status = MagicMock(
            side_effect=httpx.HTTPStatusError(
                "error", request=MagicMock(), response=resp
            )
        )
    else:
        resp.raise_for_status = MagicMock()
    return resp


def _make_mock_client(response=None, side_effect=None):
    client = AsyncMock(spec=httpx.AsyncClient)
    client.is_closed = False
    if side_effect is not None:
        client.get = AsyncMock(side_effect=side_effect)
    else:
        client.get = AsyncMock(return_value=response or _mock_response())
    client.aclose = AsyncMock()
    return client


# ---------------------------------------------------------------------------
# Circuit breaker unit tests
# ---------------------------------------------------------------------------


class TestCircuitBreaker:
    async def test_circuit_initially_closed(self):
        svc = _make_service()
        is_allowed = await svc._check_circuit_breaker()
        assert is_allowed is True

    async def test_circuit_opens_after_threshold_failures(self):
        svc = _make_service()
        for _ in range(svc.CB_FAILURE_THRESHOLD):
            await svc._record_failure()

        assert svc._cb_is_open is True

    async def test_circuit_open_blocks_requests(self):
        svc = _make_service()
        for _ in range(svc.CB_FAILURE_THRESHOLD):
            await svc._record_failure()

        is_allowed = await svc._check_circuit_breaker()
        assert is_allowed is False

    async def test_circuit_recovers_after_timeout(self):
        svc = _make_service()
        for _ in range(svc.CB_FAILURE_THRESHOLD):
            await svc._record_failure()

        # Simulate time passing past the recovery timeout
        past_time = datetime.now(timezone.utc) - timedelta(
            seconds=svc.CB_RECOVERY_TIMEOUT + 5
        )
        svc._cb_last_failure_time = past_time

        is_allowed = await svc._check_circuit_breaker()
        assert is_allowed is True
        assert svc._cb_is_open is False

    async def test_record_success_resets_failures(self):
        svc = _make_service()
        for _ in range(3):
            await svc._record_failure()

        await svc._record_success()

        assert svc._cb_failure_count == 0
        assert svc._cb_is_open is False

    async def test_circuit_stays_open_within_timeout(self):
        svc = _make_service()
        for _ in range(svc.CB_FAILURE_THRESHOLD):
            await svc._record_failure()

        # Recent failure — no recovery yet
        svc._cb_last_failure_time = datetime.now(timezone.utc)

        is_allowed = await svc._check_circuit_breaker()
        assert is_allowed is False


# ---------------------------------------------------------------------------
# get_weather_forecast
# ---------------------------------------------------------------------------


class TestGetWeatherForecast:
    async def test_happy_path(self):
        svc = _make_service()
        weather_data = {"daily": {"temperature_2m_max": [25, 26]}}
        mock_client = _make_mock_client(response=_mock_response(json_data=weather_data))

        with patch.object(svc, "_get_client", return_value=mock_client):
            result = await svc.get_weather_forecast(39.9, 32.8)

        assert "daily" in result
        assert svc._cb_failure_count == 0  # success recorded

    async def test_circuit_open_returns_error_payload(self):
        svc = _make_service()
        # Force circuit open
        svc._cb_is_open = True
        svc._cb_last_failure_time = datetime.now(timezone.utc)

        result = await svc.get_weather_forecast(39.9, 32.8)

        assert result.get("error_code") == "SERVICE_UNAVAILABLE"
        assert result.get("source") == "circuit_breaker"

    async def test_http_error_returns_error_payload(self):
        svc = _make_service()
        mock_client = _make_mock_client(response=_mock_response(status_code=500))

        with patch.object(svc, "_get_client", return_value=mock_client):
            result = await svc.get_weather_forecast(39.9, 32.8)

        assert result.get("error_code") == "SERVICE_UNAVAILABLE"
        assert result.get("source") == "provider_error"
        assert svc._cb_failure_count > 0  # failure recorded

    async def test_network_exception_returns_error_payload(self):
        svc = _make_service()
        mock_client = _make_mock_client(side_effect=httpx.ConnectError("timeout"))

        with patch.object(svc, "_get_client", return_value=mock_client):
            result = await svc.get_weather_forecast(39.9, 32.8)

        assert "error" in result
        assert result.get("source") == "provider_error"

    async def test_records_failure_and_can_open_circuit(self):
        svc = _make_service()
        mock_client = _make_mock_client(side_effect=httpx.TimeoutException("timeout"))

        with patch.object(svc, "_get_client", return_value=mock_client):
            for _ in range(svc.CB_FAILURE_THRESHOLD):
                await svc.get_weather_forecast(39.9, 32.8)

        assert svc._cb_is_open is True


# ---------------------------------------------------------------------------
# get_weather_current_batch
# ---------------------------------------------------------------------------


class TestGetWeatherCurrentBatch:
    async def test_empty_coords_returns_empty_data(self):
        svc = _make_service()
        result = await svc.get_weather_current_batch([])
        assert result == {"data": []}

    async def test_circuit_open_returns_error_payload(self):
        svc = _make_service()
        svc._cb_is_open = True
        svc._cb_last_failure_time = datetime.now(timezone.utc)

        result = await svc.get_weather_current_batch([(32.8, 39.9)])

        assert result.get("error_code") == "SERVICE_UNAVAILABLE"
        assert result.get("source") == "circuit_breaker"

    async def test_happy_path_single_coord(self):
        svc = _make_service()
        batch_data = {"current": {"temperature_2m": 22}}
        mock_client = _make_mock_client(response=_mock_response(json_data=batch_data))

        with patch.object(svc, "_get_client", return_value=mock_client):
            result = await svc.get_weather_current_batch([(32.8, 39.9)])

        assert "data" in result
        assert isinstance(result["data"], list)
        assert len(result["data"]) == 1

    async def test_happy_path_list_response_from_api(self):
        """Open-Meteo returns list for multiple coords."""
        svc = _make_service()
        batch_data = [
            {"current": {"temperature_2m": 22}},
            {"current": {"temperature_2m": 18}},
        ]
        mock_client = _make_mock_client(response=_mock_response(json_data=batch_data))

        with patch.object(svc, "_get_client", return_value=mock_client):
            result = await svc.get_weather_current_batch([(32.8, 39.9), (27.0, 38.4)])

        assert len(result["data"]) == 2

    async def test_429_triggers_retry_and_succeeds(self):
        """429 response → retry-after → second call succeeds."""
        svc = _make_service()

        success_resp = _mock_response(json_data={"current": {}})
        rate_limit_resp = MagicMock(spec=httpx.Response)
        rate_limit_resp.status_code = 429
        rate_limit_resp.headers = {"Retry-After": "0.1"}  # tiny delay for tests
        rate_limit_resp.raise_for_status = MagicMock()

        call_count = 0

        async def _get_side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return rate_limit_resp
            return success_resp

        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.is_closed = False
        mock_client.get = AsyncMock(side_effect=_get_side_effect)
        mock_client.aclose = AsyncMock()

        with patch.object(svc, "_get_client", return_value=mock_client):
            result = await svc.get_weather_current_batch([(32.8, 39.9)])

        assert call_count == 2  # initial + retry
        assert "data" in result

    async def test_exception_returns_error_payload(self):
        svc = _make_service()
        mock_client = _make_mock_client(side_effect=httpx.ConnectError("no route"))

        with patch.object(svc, "_get_client", return_value=mock_client):
            result = await svc.get_weather_current_batch([(32.8, 39.9)])

        assert result.get("error_code") == "SERVICE_UNAVAILABLE"
        assert result.get("source") == "provider_error"


# ---------------------------------------------------------------------------
# get_weather_archive
# ---------------------------------------------------------------------------


class TestGetWeatherArchive:
    async def test_circuit_open_returns_error_payload(self):
        svc = _make_service()
        svc._cb_is_open = True
        svc._cb_last_failure_time = datetime.now(timezone.utc)

        result = await svc.get_weather_archive(39.9, 32.8, "2025-01-01", "2025-01-07")

        assert result.get("error_code") == "SERVICE_UNAVAILABLE"
        assert (
            "open" in result.get("error", "").lower()
            or result.get("error_code") == "SERVICE_UNAVAILABLE"
        )

    async def test_happy_path(self):
        svc = _make_service()
        archive_data = {"hourly": {"temperature_2m": [10, 12, 11]}}
        mock_client = _make_mock_client(response=_mock_response(json_data=archive_data))

        with patch.object(svc, "_get_client", return_value=mock_client):
            result = await svc.get_weather_archive(
                39.9, 32.8, "2025-01-01", "2025-01-07"
            )

        assert "hourly" in result

    async def test_http_error_returns_error_payload(self):
        svc = _make_service()
        mock_client = _make_mock_client(response=_mock_response(status_code=429))

        with patch.object(svc, "_get_client", return_value=mock_client):
            result = await svc.get_weather_archive(
                39.9, 32.8, "2025-01-01", "2025-01-07"
            )

        assert result.get("error_code") == "SERVICE_UNAVAILABLE"

    async def test_network_exception_returns_error_payload(self):
        svc = _make_service()
        mock_client = _make_mock_client(side_effect=httpx.ReadTimeout("timeout"))

        with patch.object(svc, "_get_client", return_value=mock_client):
            result = await svc.get_weather_archive(
                39.9, 32.8, "2025-01-01", "2025-01-07"
            )

        assert "error" in result


# ---------------------------------------------------------------------------
# close() and _get_client()
# ---------------------------------------------------------------------------


class TestClientLifecycle:
    async def test_close_open_client(self):
        svc = _make_service()
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.is_closed = False
        mock_client.aclose = AsyncMock()
        svc._client = mock_client

        await svc.close()

        mock_client.aclose.assert_called_once()

    async def test_close_no_client_is_safe(self):
        svc = _make_service()
        svc._client = None
        await svc.close()  # Should not raise

    async def test_close_already_closed_client_is_safe(self):
        svc = _make_service()
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.is_closed = True
        mock_client.aclose = AsyncMock()
        svc._client = mock_client

        await svc.close()

        mock_client.aclose.assert_not_called()

    async def test_get_client_creates_new_when_none(self):
        svc = _make_service()
        assert svc._client is None

        fake_client = MagicMock(spec=httpx.AsyncClient)
        fake_client.is_closed = False

        with patch(
            "v2.modules.route_simulation.infrastructure.external_service.get_monitored_client",
            return_value=fake_client,
        ):
            client = await svc._get_client()

        assert client is fake_client

    async def test_get_client_reuses_existing_open_client(self):
        svc = _make_service()
        fake_client = MagicMock(spec=httpx.AsyncClient)
        fake_client.is_closed = False
        svc._client = fake_client

        with patch(
            "v2.modules.route_simulation.infrastructure.external_service.get_monitored_client",
        ) as mock_factory:
            client = await svc._get_client()

        mock_factory.assert_not_called()
        assert client is fake_client


# ---------------------------------------------------------------------------
# Singleton getter
# ---------------------------------------------------------------------------


class TestGetExternalServiceSingleton:
    def test_returns_same_instance(self):
        import v2.modules.route_simulation.infrastructure.external_service as ext_mod

        # Reset singleton for a clean test
        original = ext_mod._external_service
        ext_mod._external_service = None
        try:
            from v2.modules.route_simulation.infrastructure.external_service import (
                get_external_service,
            )

            svc1 = get_external_service()
            svc2 = get_external_service()
            assert svc1 is svc2
        finally:
            ext_mod._external_service = original

    def test_returns_external_service_instance(self):
        from v2.modules.route_simulation.infrastructure.external_service import (
            ExternalService,
            get_external_service,
        )

        svc = get_external_service()
        assert isinstance(svc, ExternalService)
