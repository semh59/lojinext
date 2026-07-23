"""
Integration tests for the error detection pipeline: EventBus → Redis/PG → API.

Uses the shared test fixtures (db_session, async_client, admin_auth_headers).

Run:
    pytest app/tests/integration/test_error_detector_integration.py -x -q -m integration
"""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy import text

from v2.modules.platform_infra.monitoring.event_bus import (
    ErrorEventBus,
    reset_event_bus,
)
from v2.modules.platform_infra.monitoring.models import (
    ErrorEvent,
    ErrorLayer,
    ErrorSeverity,
)

pytestmark = [pytest.mark.integration]


@pytest.fixture()
async def fresh_bus(monkeypatch):
    """Isolated EventBus for each test. Monkeypatches _bus to return this bus."""
    reset_event_bus()
    bus = ErrorEventBus()
    monkeypatch.setattr("v2.modules.platform_infra.monitoring.event_bus._bus", bus)
    yield bus
    await bus.stop()
    reset_event_bus()


def _make_ev(
    layer=ErrorLayer.API,
    category="integration_test",
    severity=ErrorSeverity.ERROR,
    message="integration test error",
):
    return ErrorEvent(
        layer=layer,
        category=category,
        severity=severity,
        message=message,
    )


async def _insert_error_event(session, ev: ErrorEvent) -> int:
    """Insert an error_event row and return its id. Uses ORM model to avoid asyncpg cast issues."""
    from v2.modules.shared_kernel.infrastructure.error_monitoring_models import (
        ErrorEvent as ErrorEventModel,
    )

    db_ev = ErrorEventModel(
        fingerprint=ev.fingerprint,
        layer=ev.layer.value,
        category=ev.category,
        severity=ev.severity.value,
        message=ev.message,
        count=1,
        first_seen=datetime.now(timezone.utc),
        last_seen=datetime.now(timezone.utc),
    )
    session.add(db_ev)
    await session.flush()
    await session.commit()
    return db_ev.id


# ─── PostgreSQL direct ORM write ──────────────────────────────────────────────


@pytest.mark.integration
async def test_direct_orm_write_to_error_events_table(db_session):
    """ORM INSERT into error_events works and can be queried."""
    from v2.modules.shared_kernel.infrastructure.error_monitoring_models import (
        ErrorEvent as ErrorEventModel,
    )

    ev = _make_ev(
        category="pg_write_test",
        message=f"PG write test {datetime.now(timezone.utc).isoformat()}",
    )

    db_ev = ErrorEventModel(
        fingerprint=ev.fingerprint,
        layer=ev.layer.value,
        category=ev.category,
        severity=ev.severity.value,
        message=ev.message,
        count=1,
        first_seen=datetime.now(timezone.utc),
        last_seen=datetime.now(timezone.utc),
    )
    db_session.add(db_ev)
    await db_session.commit()

    row = await db_session.execute(
        text("SELECT layer, severity, count FROM error_events WHERE fingerprint = :fp"),
        {"fp": ev.fingerprint},
    )
    result = row.fetchone()
    assert result is not None, "Row missing from error_events"
    assert result.layer == "api"
    assert result.severity == "error"
    assert result.count == 1

    # Cleanup
    await db_session.execute(
        text("DELETE FROM error_events WHERE fingerprint = :fp"), {"fp": ev.fingerprint}
    )
    await db_session.commit()


@pytest.mark.integration
async def test_error_occurrences_table_exists(db_session):
    """error_occurrences table is present in the test DB schema."""
    row = await db_session.execute(
        text(
            "SELECT COUNT(*) FROM information_schema.tables "
            "WHERE table_schema = 'public' AND table_name = 'error_occurrences'"
        )
    )
    count = row.scalar_one()
    assert count == 1, "error_occurrences table missing from test schema"


@pytest.mark.integration
async def test_upsert_increments_count_on_duplicate_fingerprint(db_session):
    """Two events with identical fingerprint → count=2 via UPSERT."""
    from v2.modules.shared_kernel.infrastructure.error_monitoring_models import (
        ErrorEvent as ErrorEventModel,
    )

    ev = _make_ev(category="upsert_test", message="duplicate upsert integration test")
    now = datetime.now(timezone.utc)

    # First insert
    db_ev = ErrorEventModel(
        fingerprint=ev.fingerprint,
        layer=ev.layer.value,
        category=ev.category,
        severity=ev.severity.value,
        message=ev.message,
        count=1,
        first_seen=now,
        last_seen=now,
    )
    db_session.add(db_ev)
    await db_session.flush()

    # Second insert via UPSERT
    await db_session.execute(
        text(
            "INSERT INTO error_events "
            "(fingerprint, layer, category, severity, message, count, first_seen, last_seen) "
            "VALUES (:fp, :layer, :category, :severity, :message, 1, :now, :now) "
            "ON CONFLICT (fingerprint) WHERE resolved_at IS NULL "
            "DO UPDATE SET count = error_events.count + EXCLUDED.count, last_seen = EXCLUDED.last_seen"
        ),
        {
            "fp": ev.fingerprint,
            "layer": ev.layer.value,
            "category": ev.category,
            "severity": ev.severity.value,
            "message": ev.message,
            "now": now,
        },
    )
    await db_session.commit()

    row = await db_session.execute(
        text("SELECT count FROM error_events WHERE fingerprint = :fp"),
        {"fp": ev.fingerprint},
    )
    result = row.fetchone()
    assert result is not None
    assert result.count == 2

    await db_session.execute(
        text("DELETE FROM error_events WHERE fingerprint = :fp"), {"fp": ev.fingerprint}
    )
    await db_session.commit()


# ─── EventBus flush with mocked writes ─────────────────────────────────────────


@pytest.mark.integration
async def test_flush_batch_emits_and_drains_queue(fresh_bus):
    """emit → _flush_batch → queue is empty after flush."""
    for _ in range(3):
        await fresh_bus.emit(_make_ev())

    assert fresh_bus._queue.qsize() == 3

    with (
        patch.object(fresh_bus, "_write_redis", new_callable=AsyncMock),
        patch.object(fresh_bus, "_write_postgres", new_callable=AsyncMock),
        patch(
            "v2.modules.platform_infra.monitoring.alarm_router.AlarmRouter.route",
            new_callable=AsyncMock,
        ),
    ):
        await fresh_bus._flush_batch()

    assert fresh_bus._queue.qsize() == 0


@pytest.mark.integration
async def test_flush_batch_records_success_when_pg_succeeds(fresh_bus):
    """Successful PG write → failure_count=0, circuit_open=False."""
    fresh_bus._failure_count = 1  # simulate previous failure
    await fresh_bus.emit(_make_ev())

    with (
        patch.object(fresh_bus, "_write_redis", new_callable=AsyncMock),
        patch.object(fresh_bus, "_write_postgres", new_callable=AsyncMock),
        patch(
            "v2.modules.platform_infra.monitoring.alarm_router.AlarmRouter.route",
            new_callable=AsyncMock,
        ),
    ):
        await fresh_bus._flush_batch()

    assert fresh_bus._failure_count == 0
    assert fresh_bus._circuit_open is False


# ─── CRITICAL → Telegram mock ─────────────────────────────────────────────────


@pytest.mark.integration
async def test_critical_event_triggers_telegram_call(fresh_bus):
    """CRITICAL emit → _flush_batch → Telegram notify_error called."""
    ev = _make_ev(
        layer=ErrorLayer.DB,
        category="telegram_integration_test",
        severity=ErrorSeverity.CRITICAL,
        message="critical DB failure integration",
    )
    await fresh_bus.emit(ev)

    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.post = AsyncMock(return_value=mock_response)

    with (
        patch.object(fresh_bus, "_write_redis", new_callable=AsyncMock),
        patch.object(fresh_bus, "_write_postgres", new_callable=AsyncMock),
        patch(
            "v2.modules.platform_infra.monitoring.alarm_router.AnomalyDetector.check",
            new_callable=AsyncMock,
            return_value=False,
        ),
        patch(
            "v2.modules.notification.infrastructure.telegram_client.get_monitored_client",
            return_value=mock_client,
        ),
    ):
        await fresh_bus._flush_batch()
        # Give fire-and-forget task a moment to complete
        import asyncio

        await asyncio.sleep(0.1)

    mock_client.post.assert_called_once()
    payload = mock_client.post.call_args[1]["json"]
    assert payload["level"] == "critical"


# ─── API endpoint tests ───────────────────────────────────────────────────────


@pytest.mark.integration
async def test_error_events_api_returns_200(async_client, admin_auth_headers):
    """GET /api/v1/system/error-events → 200 with items list."""
    response = await async_client.get(
        "/api/v1/system/error-events",
        headers=admin_auth_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    assert "total" in data


@pytest.mark.integration
async def test_error_events_api_layer_filter(async_client, admin_auth_headers):
    """?layer=db → all returned items have layer='db'."""
    response = await async_client.get(
        "/api/v1/system/error-events?layer=db",
        headers=admin_auth_headers,
    )
    assert response.status_code == 200
    for item in response.json()["items"]:
        assert item["layer"] == "db"


@pytest.mark.integration
async def test_error_events_api_invalid_layer_422(async_client, admin_auth_headers):
    """?layer=nonexistent → 422."""
    response = await async_client.get(
        "/api/v1/system/error-events?layer=nonexistent_layer",
        headers=admin_auth_headers,
    )
    assert response.status_code == 422


@pytest.mark.integration
async def test_error_events_api_unauthorized(async_client):
    """No auth → 401 or 403."""
    response = await async_client.get("/api/v1/system/error-events")
    assert response.status_code in (401, 403)


@pytest.mark.integration
async def test_resolve_nonexistent_event_returns_404(async_client, admin_auth_headers):
    """POST /resolve on nonexistent event → 404."""
    response = await async_client.post(
        "/api/v1/system/error-events/999999999/resolve",
        headers=admin_auth_headers,
    )
    assert response.status_code == 404


@pytest.mark.integration
async def test_resolve_event_end_to_end(async_client, db_session):
    """Insert event via ORM → resolve API (real admin user) → resolved_at is set in DB."""
    from datetime import timedelta

    from sqlalchemy import select

    from v2.modules.auth_rbac.domain.security import (
        create_access_token,
        get_password_hash,
    )
    from v2.modules.auth_rbac.public import Kullanici, Rol
    from v2.modules.platform_infra.security.pii_encryption import blind_index
    from v2.modules.shared_kernel.infrastructure.error_monitoring_models import (
        ErrorEvent as ErrorEventModel,
    )

    # Create a real admin role + user so resolved_by FK is satisfied
    role_result = await db_session.execute(select(Rol).where(Rol.ad == "admin"))
    role = role_result.scalar_one_or_none()
    if not role:
        role = Rol(ad="admin", yetkiler={"*": True})
        db_session.add(role)
        await db_session.flush()

    user_result = await db_session.execute(
        select(Kullanici).where(
            Kullanici.email_bidx == blind_index("resolve_test_admin@lojinext.test")
        )
    )
    admin_user = user_result.scalar_one_or_none()
    if not admin_user:
        admin_user = Kullanici(
            email="resolve_test_admin@lojinext.test",
            sifre_hash=get_password_hash("adminpassword"),
            ad_soyad="Resolve Test Admin",
            rol_id=role.id,
            aktif=True,
        )
        db_session.add(admin_user)
        await db_session.flush()

    await db_session.commit()

    # Create a token for this real admin
    token = create_access_token(
        data={"sub": admin_user.email},
        expires_delta=timedelta(minutes=30),
    )
    headers = {"Authorization": f"Bearer {token}"}

    # Insert the error event to resolve
    ev = _make_ev(category="resolve_e2e", message="resolve test event")
    now = datetime.now(timezone.utc)

    db_ev = ErrorEventModel(
        fingerprint=ev.fingerprint,
        layer=ev.layer.value,
        category=ev.category,
        severity=ev.severity.value,
        message=ev.message,
        count=1,
        first_seen=now,
        last_seen=now,
    )
    db_session.add(db_ev)
    await db_session.flush()
    event_id = db_ev.id
    await db_session.commit()

    assert event_id is not None, "Event not written to DB"

    # Call resolve endpoint with real admin user token
    response = await async_client.post(
        f"/api/v1/system/error-events/{event_id}/resolve",
        headers=headers,
    )
    assert response.status_code == 204

    # Verify resolved_at set
    row = await db_session.execute(
        text("SELECT resolved_at FROM error_events WHERE id = :id"),
        {"id": event_id},
    )
    resolved_at = row.scalar_one()
    assert resolved_at is not None

    # Cleanup
    await db_session.execute(
        text("DELETE FROM error_events WHERE id = :id"), {"id": event_id}
    )
    await db_session.execute(
        text(
            "DELETE FROM kullanicilar WHERE email = 'resolve_test_admin@lojinext.test'"
        )
    )
    await db_session.commit()


@pytest.mark.integration
async def test_frontend_error_report_endpoint(async_client, admin_auth_headers):
    """POST /error-report → 204, no exception."""
    payload = {
        "message": "ReferenceError: x is not defined",
        "url": "https://app.lojinext.com/seferler",
        "userAgent": "Mozilla/5.0 Test",
        "timestamp": "2026-05-19T10:00:00Z",
        "severity": "error",
    }
    response = await async_client.post(
        "/api/v1/system/error-report",
        json=payload,
        headers=admin_auth_headers,
    )
    assert response.status_code == 204


@pytest.mark.integration
async def test_error_stats_returns_200(async_client, admin_auth_headers):
    """GET /api/v1/system/error-stats → 200 with stats list."""
    response = await async_client.get(
        "/api/v1/system/error-stats",
        headers=admin_auth_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert "stats" in data


@pytest.mark.integration
async def test_sse_token_endpoint_returns_token(async_client, admin_auth_headers):
    """POST /error-stream-token → 200 with token + expires_in=90."""
    mock_redis = AsyncMock()
    mock_mgr = MagicMock()
    mock_mgr.redis = mock_redis

    with patch(
        "v2.modules.platform_infra.cache.redis_pubsub.get_pubsub_manager",
        return_value=mock_mgr,
    ):
        response = await async_client.post(
            "/api/v1/system/error-stream-token",
            headers=admin_auth_headers,
        )

    assert response.status_code == 200
    data = response.json()
    assert "token" in data
    assert data["expires_in"] == 90
    import uuid

    uuid.UUID(data["token"])  # must be valid UUID
