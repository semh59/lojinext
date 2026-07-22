"""GET /admin/pilot-status (Faz 12 pilot izleme KPI)."""

from unittest.mock import MagicMock

import pytest
from httpx import AsyncClient
from httpx._transports.asgi import ASGITransport

pytestmark = pytest.mark.unit


class _Result:
    def __init__(self, val):
        self._v = val

    def scalar(self):
        return self._v


class _FakeSession:
    """execute() çağrı sırasına göre sabit count'lar döndürür."""

    def __init__(self, vals):
        self._it = iter(vals)

    async def execute(self, *a, **k):
        return _Result(next(self._it))


def _client():
    from app.main import app

    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


async def test_pilot_status_aggregates_counts_and_coverage():
    from app.api.deps import get_current_active_admin
    from app.main import app
    from v2.modules.platform_infra.database.connection import get_db

    # sıra: seferler, predicted, araclar, soforler, yakit, anom_open, ack, resolved
    vals = [10, 7, 4, 3, 8, 2, 1, 5]

    async def _fake_db():
        yield _FakeSession(vals)

    async def _fake_admin():
        u = MagicMock()
        u.id = 1
        return u

    app.dependency_overrides[get_db] = _fake_db
    app.dependency_overrides[get_current_active_admin] = _fake_admin
    try:
        async with _client() as client:
            resp = await client.get("/api/v1/admin/pilot-status")
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 200
    body = resp.json()
    assert body["data_volume"] == {
        "seferler": 10,
        "araclar": 4,
        "soforler": 3,
        "yakit_alimlari": 8,
    }
    assert body["prediction_coverage_pct"] == 70.0  # 7/10
    assert body["anomalies"] == {"open": 2, "acknowledged": 1, "resolved": 5}
    assert "sentry" in body["external_surfaces"]


async def test_pilot_status_zero_seferler_no_div_by_zero():
    from app.api.deps import get_current_active_admin
    from app.main import app
    from v2.modules.platform_infra.database.connection import get_db

    async def _fake_db():
        yield _FakeSession([0, 0, 0, 0, 0, 0, 0, 0])

    async def _fake_admin():
        return MagicMock()

    app.dependency_overrides[get_db] = _fake_db
    app.dependency_overrides[get_current_active_admin] = _fake_admin
    try:
        async with _client() as client:
            resp = await client.get("/api/v1/admin/pilot-status")
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 200
    assert resp.json()["prediction_coverage_pct"] == 0.0
