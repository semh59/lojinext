"""Coverage tests for app/api/v1/endpoints/system.py.

system.py provides error-report ingestion, error-events listing,
error-stats, event resolution, and debug/trace chain endpoints —
all mounted under /api/v1/system/.
"""

from unittest.mock import AsyncMock, patch

import pytest

pytestmark = pytest.mark.unit


# ─── POST /system/error-report ───────────────────────────────────────────────


async def test_error_report_requires_auth(async_client):
    """No auth header → 401."""
    payload = {
        "message": "JS crash",
        "url": "http://localhost/page",
        "userAgent": "Mozilla/5.0",
        "timestamp": "2026-06-01T10:00:00Z",
    }
    resp = await async_client.post("/api/v1/system/error-report", json=payload)
    assert resp.status_code == 401


async def test_error_report_success(async_client, admin_auth_headers):
    """Valid report from authenticated user → 204."""
    payload = {
        "message": "Uncaught TypeError",
        "url": "http://localhost/trips",
        "userAgent": "TestAgent/1.0",
        "timestamp": "2026-06-01T10:00:00Z",
        "severity": "error",
    }

    with patch(
        "v2.modules.platform_infra.monitoring.aemit", new_callable=AsyncMock
    ) as mock_emit:
        resp = await async_client.post(
            "/api/v1/system/error-report",
            json=payload,
            headers=admin_auth_headers,
        )

    assert resp.status_code == 204
    mock_emit.assert_awaited_once()


async def test_error_report_severity_fatal(async_client, admin_auth_headers):
    """Fatal severity maps to CRITICAL error level."""
    from v2.modules.platform_infra.monitoring.models import ErrorSeverity

    payload = {
        "message": "Fatal crash",
        "url": "http://localhost/",
        "userAgent": "Bot",
        "timestamp": "2026-06-01T10:00:00Z",
        "severity": "fatal",
    }

    with patch(
        "v2.modules.platform_infra.monitoring.aemit", new_callable=AsyncMock
    ) as mock_emit:
        resp = await async_client.post(
            "/api/v1/system/error-report",
            json=payload,
            headers=admin_auth_headers,
        )

    assert resp.status_code == 204
    emitted = mock_emit.call_args[0][0]
    assert emitted.severity == ErrorSeverity.CRITICAL


async def test_error_report_severity_warning(async_client, admin_auth_headers):
    """Warning severity maps correctly."""
    from v2.modules.platform_infra.monitoring.models import ErrorSeverity

    payload = {
        "message": "Deprecation warning",
        "url": "http://localhost/",
        "userAgent": "Bot",
        "timestamp": "2026-06-01T10:00:00Z",
        "severity": "warning",
    }

    with patch(
        "v2.modules.platform_infra.monitoring.aemit", new_callable=AsyncMock
    ) as mock_emit:
        resp = await async_client.post(
            "/api/v1/system/error-report",
            json=payload,
            headers=admin_auth_headers,
        )

    assert resp.status_code == 204
    emitted = mock_emit.call_args[0][0]
    assert emitted.severity == ErrorSeverity.WARNING


async def test_error_report_with_optional_fields(async_client, admin_auth_headers):
    """Optional fields like stack, componentStack, backend_trace_id accepted."""
    payload = {
        "message": "Error",
        "stack": "Error at line 1",
        "componentStack": "at Component",
        "url": "http://localhost/",
        "userAgent": "TestAgent",
        "timestamp": "2026-06-01",
        "backend_trace_id": "trace-abc-123",
        "frontend_session_id": "session-xyz",
    }

    with patch("v2.modules.platform_infra.monitoring.aemit", new_callable=AsyncMock):
        resp = await async_client.post(
            "/api/v1/system/error-report",
            json=payload,
            headers=admin_auth_headers,
        )

    assert resp.status_code == 204


# ─── POST /system/error-report-batch ─────────────────────────────────────────


async def test_error_report_batch_requires_auth(async_client):
    resp = await async_client.post("/api/v1/system/error-report-batch", json=[])
    assert resp.status_code == 401


async def test_error_report_batch_success(async_client, admin_auth_headers):
    """Two valid reports → 204."""
    report = {
        "message": "Batch error",
        "url": "http://localhost/",
        "userAgent": "UA",
        "timestamp": "2026-06-01",
    }

    with patch(
        "v2.modules.platform_infra.monitoring.aemit", new_callable=AsyncMock
    ) as mock_emit:
        resp = await async_client.post(
            "/api/v1/system/error-report-batch",
            json=[report, report],
            headers=admin_auth_headers,
        )

    assert resp.status_code == 204
    assert mock_emit.await_count == 2


async def test_error_report_batch_too_large(async_client, admin_auth_headers):
    """More than 20 reports → 400.

    The endpoint carries a slowapi ``@limiter.limit("2/minute")`` whose state
    is process-global and not reset by the per-test fixtures. When the full
    suite runs, earlier requests to this route exhaust the budget and a 429
    would mask the batch-size validation we want to assert. Disable the limiter
    for this test so the 400 path is exercised deterministically regardless of
    suite position.
    """
    report = {
        "message": "Batch error",
        "url": "http://localhost/",
        "userAgent": "UA",
        "timestamp": "2026-06-01",
    }
    reports = [report] * 21

    from v2.modules.platform_infra.middleware.slowapi_limiter import limiter

    prev_enabled = limiter.enabled
    limiter.enabled = False
    try:
        with patch("v2.modules.platform_infra.monitoring.aemit", new_callable=AsyncMock):
            resp = await async_client.post(
                "/api/v1/system/error-report-batch",
                json=reports,
                headers=admin_auth_headers,
            )
    finally:
        limiter.enabled = prev_enabled

    assert resp.status_code == 400


# ─── GET /system/error-events ────────────────────────────────────────────────


async def test_get_error_events_requires_admin(async_client):
    resp = await async_client.get("/api/v1/system/error-events")
    assert resp.status_code == 401


async def test_get_error_events_invalid_layer(async_client, admin_auth_headers):
    """Unknown layer value → 422."""
    resp = await async_client.get(
        "/api/v1/system/error-events?layer=unknown_layer",
        headers=admin_auth_headers,
    )
    assert resp.status_code == 422


async def test_get_error_events_invalid_severity(async_client, admin_auth_headers):
    """Unknown severity value → 422."""
    resp = await async_client.get(
        "/api/v1/system/error-events?severity=EXTREME",
        headers=admin_auth_headers,
    )
    assert resp.status_code == 422


async def test_get_error_events_empty_result(
    async_client, admin_auth_headers, db_session
):
    """DB has no events → returns empty list with total=0."""
    resp = await async_client.get(
        "/api/v1/system/error-events",
        headers=admin_auth_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 0
    assert data["items"] == []
    assert data["page"] == 1


async def test_get_error_events_with_valid_layer(
    async_client, admin_auth_headers, db_session
):
    """Valid layer filter → 200 (even if empty)."""
    resp = await async_client.get(
        "/api/v1/system/error-events?layer=api",
        headers=admin_auth_headers,
    )
    assert resp.status_code == 200


async def test_get_error_events_resolved_filter(
    async_client, admin_auth_headers, db_session
):
    """resolved=true includes resolved events query path."""
    resp = await async_client.get(
        "/api/v1/system/error-events?resolved=true",
        headers=admin_auth_headers,
    )
    assert resp.status_code == 200


# ─── GET /system/error-stats ─────────────────────────────────────────────────


async def test_get_error_stats_requires_admin(async_client):
    resp = await async_client.get("/api/v1/system/error-stats")
    assert resp.status_code == 401


async def test_get_error_stats_returns_empty(
    async_client, admin_auth_headers, db_session
):
    """No stats data → returns empty stats list."""
    resp = await async_client.get(
        "/api/v1/system/error-stats",
        headers=admin_auth_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "stats" in data
    assert isinstance(data["stats"], list)


# ─── POST /system/error-events/{id}/resolve ──────────────────────────────────


async def test_resolve_error_event_requires_admin(async_client):
    resp = await async_client.post("/api/v1/system/error-events/1/resolve")
    assert resp.status_code == 401


async def test_resolve_error_event_not_found(
    async_client, admin_auth_headers, db_session
):
    """Resolving non-existent event → 404."""
    resp = await async_client.post(
        "/api/v1/system/error-events/99999/resolve",
        headers=admin_auth_headers,
    )
    assert resp.status_code == 404


# ─── GET /system/debug/trace/{trace_id} ──────────────────────────────────────


async def test_debug_trace_requires_admin(async_client):
    resp = await async_client.get("/api/v1/system/debug/trace/test-trace-id")
    assert resp.status_code == 401


async def test_debug_trace_empty_returns_hint(
    async_client, admin_auth_headers, db_session
):
    """No events for trace_id → returns hint in response."""
    resp = await async_client.get(
        "/api/v1/system/debug/trace/nonexistent-trace-id",
        headers=admin_auth_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["trace_id"] == "nonexistent-trace-id"
    assert data["counts"]["errors"] == 0
    assert "hint" in data


async def test_debug_trace_returns_structure(
    async_client, admin_auth_headers, db_session
):
    """Response always has errors/audit/counts keys."""
    resp = await async_client.get(
        "/api/v1/system/debug/trace/any-trace",
        headers=admin_auth_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "errors" in data
    assert "audit" in data
    assert "counts" in data
