"""
Additional coverage tests for app/api/v1/endpoints/executive.py.

Targets missed lines:
  70-85    — _get_redis: singleton init, success, and failure paths
  113-114  — get_fleet_efficiency_index: Redis cache read exception swallowed
  154-155  — get_fleet_efficiency_index: Redis setex exception swallowed
  282-284  — get_fleet_carbon: Redis cache read exception swallowed
  317-318  — get_fleet_carbon: Redis setex exception swallowed
  369-370  — get_compliance_heatmap: Redis cache read exception
  403-404  — get_compliance_heatmap: Redis setex exception
  458-459  — get_cashflow_projection: Redis cache read exception
  496-497  — get_cashflow_projection: Redis setex exception
  544-546  — get_cross_feature_impact: Redis cache read exception
  570-571  — get_cross_feature_impact: Redis setex exception
  620-622  — get_bus_factor: Redis cache read exception
  649-650  — get_bus_factor: Redis setex exception
  732-733  — get_pdf: (various paths)
  748-749  — get_pdf: (more paths)
  762-763  — get_pdf: (more paths)
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

pytestmark = pytest.mark.unit

BASE = "/api/v1/reports/executive"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_fvi_inputs():
    return {
        "fuel_avg": 32.5,
        "target": 30.0,
        "overdue_count": 2,
        "total_active": 10,
        "driver_avg": 28.0,
        "resolved": 5,
        "acked": 2,
        "total_anomalies": 10,
    }


def _make_fvi_breakdown():
    bd = MagicMock()
    bd.fvi = 75.0
    bd.fuel_score = 80.0
    bd.maintenance_score = 70.0
    bd.driver_score = 75.0
    bd.anomaly_quality_score = 68.0
    bd.confidence = 0.85
    bd.trend_30d = 2.5
    bd.reasons = ["Good fuel"]
    bd.computed_at = datetime.now(timezone.utc)
    return bd


def _make_carbon_report():
    r = MagicMock()
    r.period_start = date(2026, 5, 1)
    r.period_end = date(2026, 5, 31)
    r.total_co2_kg = 50000.0
    r.total_km = 120000.0
    r.co2_per_km = 0.417
    r.benchmark_co2_per_km = 0.62
    r.delta_pct = -32.7
    r.by_euro_class = {"Euro6": 50000.0}
    r.top_emitters = []
    r.vehicle_count = 12
    return r


def _make_compliance_item():
    item = MagicMock()
    item.risk_level = "soon"
    item.entity_type = "arac"
    item.entity_id = 1
    item.plaka = "34ABC123"
    item.field = "muayene"
    item.expiry_date = date(2026, 7, 15)
    item.days_until = 42
    return item


def _make_cashflow_projection():
    p = MagicMock()
    p.horizon_days = 90
    p.weeks = []
    p.total_fuel_tl = 200000.0
    p.total_maintenance_tl = 50000.0
    p.total_penalty_tl = None
    p.grand_total_tl = 250000.0
    p.confidence = 0.7
    p.assumptions = {"diesel_price_tl": 50.0}
    return p


def _make_cross_impact():
    i = MagicMock()
    i.period_days = 90
    i.maintenance_delay_loss_tl = 15000.0
    i.coaching_savings_tl = 8000.0
    i.theft_loss_tl = 3000.0
    i.confidence = 0.55
    return i


def _make_bus_factor_report():
    r = MagicMock()
    r.n = 3
    r.top_n_drivers_loss_tl = 120000.0
    r.top_n_drivers = [{"score": 1.4, "yearly_km": 85000}]
    r.bottlenecked_routes = []
    r.risk_level = "high"
    return r


# ---------------------------------------------------------------------------
# _get_redis — singleton + failure path (lines 70-85)
# ---------------------------------------------------------------------------


async def test_get_redis_returns_singleton():
    """_get_redis returns the same instance on subsequent calls."""
    import app.api.v1.endpoints.executive as mod

    original = mod._exec_redis
    mod._exec_redis = None

    mock_redis_client = AsyncMock()

    try:
        with patch("redis.asyncio.from_url", return_value=mock_redis_client):
            from app.api.v1.endpoints.executive import _get_redis

            r1 = await _get_redis()
            r2 = await _get_redis()
        assert r1 is r2
    finally:
        mod._exec_redis = original


async def test_get_redis_returns_none_on_import_error():
    """When redis.asyncio not available → returns None."""
    import app.api.v1.endpoints.executive as mod

    original = mod._exec_redis
    mod._exec_redis = None

    try:
        import sys

        orig_redis = sys.modules.get("redis.asyncio")
        sys.modules["redis.asyncio"] = None  # type: ignore[assignment]
        try:
            from app.api.v1.endpoints.executive import _get_redis

            result = await _get_redis()
            assert result is None
        finally:
            if orig_redis is None:
                sys.modules.pop("redis.asyncio", None)
            else:
                sys.modules["redis.asyncio"] = orig_redis
    finally:
        mod._exec_redis = original


async def test_get_redis_returns_none_on_connection_error():
    """When redis.from_url raises → returns None."""
    import app.api.v1.endpoints.executive as mod

    original = mod._exec_redis
    mod._exec_redis = None

    try:
        with patch("redis.asyncio.from_url", side_effect=Exception("conn refused")):
            from app.api.v1.endpoints.executive import _get_redis

            result = await _get_redis()
        assert result is None
    finally:
        mod._exec_redis = original


# ---------------------------------------------------------------------------
# KPI endpoint: Redis cache read exception swallowed (lines 113-114)
# and Redis setex exception swallowed (lines 154-155)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_kpi_redis_cache_read_exception_swallowed(
    async_client, admin_auth_headers
):
    """Redis get() raises → exception swallowed, fresh compute done."""
    fvi_inputs = _make_fvi_inputs()
    breakdown = _make_fvi_breakdown()

    with (
        patch(
            "app.api.v1.endpoints.executive._get_redis", new_callable=AsyncMock
        ) as mock_redis,
        patch(
            "app.api.v1.endpoints.executive.gather_fvi_inputs", new_callable=AsyncMock
        ) as mock_gather,
        patch("app.api.v1.endpoints.executive.compute_fvi", return_value=breakdown),
        patch("app.api.v1.endpoints.executive.log_audit_event", new_callable=AsyncMock),
        patch("app.api.v1.endpoints.executive.settings") as mock_settings,
    ):
        mock_settings.EXECUTIVE_ENABLED = True
        mock_settings.EXECUTIVE_CACHE_TTL_S = 1800

        mock_redis_client = AsyncMock()
        mock_redis_client.get = AsyncMock(side_effect=RuntimeError("redis down"))
        mock_redis_client.setex = AsyncMock()
        mock_redis.return_value = mock_redis_client

        mock_gather.return_value = fvi_inputs

        resp = await async_client.get(f"{BASE}/kpi", headers=admin_auth_headers)

    assert resp.status_code == 200
    assert resp.json()["fvi"] == 75.0


@pytest.mark.asyncio
async def test_kpi_redis_setex_exception_swallowed(async_client, admin_auth_headers):
    """Redis setex() raises → exception swallowed, response still returned."""
    fvi_inputs = _make_fvi_inputs()
    breakdown = _make_fvi_breakdown()

    with (
        patch(
            "app.api.v1.endpoints.executive._get_redis", new_callable=AsyncMock
        ) as mock_redis,
        patch(
            "app.api.v1.endpoints.executive.gather_fvi_inputs", new_callable=AsyncMock
        ) as mock_gather,
        patch("app.api.v1.endpoints.executive.compute_fvi", return_value=breakdown),
        patch("app.api.v1.endpoints.executive.log_audit_event", new_callable=AsyncMock),
        patch("app.api.v1.endpoints.executive.settings") as mock_settings,
    ):
        mock_settings.EXECUTIVE_ENABLED = True
        mock_settings.EXECUTIVE_CACHE_TTL_S = 1800

        mock_redis_client = AsyncMock()
        mock_redis_client.get = AsyncMock(return_value=None)
        mock_redis_client.setex = AsyncMock(side_effect=RuntimeError("setex fail"))
        mock_redis.return_value = mock_redis_client

        mock_gather.return_value = fvi_inputs

        resp = await async_client.get(f"{BASE}/kpi", headers=admin_auth_headers)

    assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Carbon: Redis cache read/write exceptions (lines 282-284, 317-318)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_carbon_redis_read_exception_swallowed(async_client, admin_auth_headers):
    """Carbon Redis get() raises → exception swallowed, fresh compute done."""
    carbon_report = _make_carbon_report()

    with (
        patch(
            "app.api.v1.endpoints.executive._get_redis", new_callable=AsyncMock
        ) as mock_redis,
        patch(
            "app.api.v1.endpoints.executive.compute_fleet_carbon",
            new_callable=AsyncMock,
        ) as mock_carbon,
        patch("app.api.v1.endpoints.executive.log_audit_event", new_callable=AsyncMock),
        patch("app.api.v1.endpoints.executive.settings") as mock_settings,
    ):
        mock_settings.EXECUTIVE_ENABLED = True
        mock_settings.EXECUTIVE_CACHE_TTL_S = 1800

        mock_redis_client = AsyncMock()
        mock_redis_client.get = AsyncMock(side_effect=RuntimeError("redis down"))
        mock_redis_client.setex = AsyncMock()
        mock_redis.return_value = mock_redis_client

        mock_carbon.return_value = carbon_report

        resp = await async_client.get(
            f"{BASE}/carbon?days=30", headers=admin_auth_headers
        )

    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_carbon_redis_setex_exception_swallowed(async_client, admin_auth_headers):
    """Carbon Redis setex() raises → swallowed."""
    carbon_report = _make_carbon_report()

    with (
        patch(
            "app.api.v1.endpoints.executive._get_redis", new_callable=AsyncMock
        ) as mock_redis,
        patch(
            "app.api.v1.endpoints.executive.compute_fleet_carbon",
            new_callable=AsyncMock,
        ) as mock_carbon,
        patch("app.api.v1.endpoints.executive.log_audit_event", new_callable=AsyncMock),
        patch("app.api.v1.endpoints.executive.settings") as mock_settings,
    ):
        mock_settings.EXECUTIVE_ENABLED = True
        mock_settings.EXECUTIVE_CACHE_TTL_S = 1800

        mock_redis_client = AsyncMock()
        mock_redis_client.get = AsyncMock(return_value=None)
        mock_redis_client.setex = AsyncMock(side_effect=RuntimeError("setex fail"))
        mock_redis.return_value = mock_redis_client

        mock_carbon.return_value = carbon_report

        resp = await async_client.get(
            f"{BASE}/carbon?days=30", headers=admin_auth_headers
        )

    assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Compliance: Redis exceptions (lines 369-370, 403-404)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_compliance_redis_read_exception_swallowed(
    async_client, admin_auth_headers
):
    item = _make_compliance_item()

    with (
        patch(
            "app.api.v1.endpoints.executive._get_redis", new_callable=AsyncMock
        ) as mock_redis,
        patch(
            "app.api.v1.endpoints.executive.scan_compliance", new_callable=AsyncMock
        ) as mock_scan,
        patch("app.api.v1.endpoints.executive.log_audit_event", new_callable=AsyncMock),
        patch("app.api.v1.endpoints.executive.settings") as mock_settings,
    ):
        mock_settings.EXECUTIVE_ENABLED = True
        mock_settings.EXECUTIVE_CACHE_TTL_S = 1800

        mock_redis_client = AsyncMock()
        mock_redis_client.get = AsyncMock(side_effect=RuntimeError("redis down"))
        mock_redis_client.setex = AsyncMock()
        mock_redis.return_value = mock_redis_client

        mock_scan.return_value = [item]

        resp = await async_client.get(
            f"{BASE}/compliance?days_horizon=30", headers=admin_auth_headers
        )

    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_compliance_redis_setex_exception_swallowed(
    async_client, admin_auth_headers
):
    item = _make_compliance_item()

    with (
        patch(
            "app.api.v1.endpoints.executive._get_redis", new_callable=AsyncMock
        ) as mock_redis,
        patch(
            "app.api.v1.endpoints.executive.scan_compliance", new_callable=AsyncMock
        ) as mock_scan,
        patch("app.api.v1.endpoints.executive.log_audit_event", new_callable=AsyncMock),
        patch("app.api.v1.endpoints.executive.settings") as mock_settings,
    ):
        mock_settings.EXECUTIVE_ENABLED = True
        mock_settings.EXECUTIVE_CACHE_TTL_S = 1800

        mock_redis_client = AsyncMock()
        mock_redis_client.get = AsyncMock(return_value=None)
        mock_redis_client.setex = AsyncMock(side_effect=RuntimeError("setex fail"))
        mock_redis.return_value = mock_redis_client

        mock_scan.return_value = [item]

        resp = await async_client.get(
            f"{BASE}/compliance?days_horizon=30", headers=admin_auth_headers
        )

    assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Cashflow: Redis exceptions (lines 458-459, 496-497)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_cashflow_redis_read_exception_swallowed(
    async_client, admin_auth_headers
):
    projection = _make_cashflow_projection()

    with (
        patch(
            "app.api.v1.endpoints.executive._get_redis", new_callable=AsyncMock
        ) as mock_redis,
        patch(
            "app.api.v1.endpoints.executive.project_cashflow", new_callable=AsyncMock
        ) as mock_project,
        patch("app.api.v1.endpoints.executive.log_audit_event", new_callable=AsyncMock),
        patch("app.api.v1.endpoints.executive.settings") as mock_settings,
    ):
        mock_settings.EXECUTIVE_ENABLED = True
        mock_settings.EXECUTIVE_CACHE_TTL_S = 1800
        mock_settings.LITRE_DIESEL_TL = 50.0
        mock_settings.AVG_BAKIM_COST_TL = 2000.0

        mock_redis_client = AsyncMock()
        mock_redis_client.get = AsyncMock(side_effect=RuntimeError("redis down"))
        mock_redis_client.setex = AsyncMock()
        mock_redis.return_value = mock_redis_client

        mock_project.return_value = projection

        resp = await async_client.get(
            f"{BASE}/cashflow?days=90", headers=admin_auth_headers
        )

    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_cashflow_redis_setex_exception_swallowed(
    async_client, admin_auth_headers
):
    projection = _make_cashflow_projection()

    with (
        patch(
            "app.api.v1.endpoints.executive._get_redis", new_callable=AsyncMock
        ) as mock_redis,
        patch(
            "app.api.v1.endpoints.executive.project_cashflow", new_callable=AsyncMock
        ) as mock_project,
        patch("app.api.v1.endpoints.executive.log_audit_event", new_callable=AsyncMock),
        patch("app.api.v1.endpoints.executive.settings") as mock_settings,
    ):
        mock_settings.EXECUTIVE_ENABLED = True
        mock_settings.EXECUTIVE_CACHE_TTL_S = 1800
        mock_settings.LITRE_DIESEL_TL = 50.0
        mock_settings.AVG_BAKIM_COST_TL = 2000.0

        mock_redis_client = AsyncMock()
        mock_redis_client.get = AsyncMock(return_value=None)
        mock_redis_client.setex = AsyncMock(side_effect=RuntimeError("setex fail"))
        mock_redis.return_value = mock_redis_client

        mock_project.return_value = projection

        resp = await async_client.get(
            f"{BASE}/cashflow?days=90", headers=admin_auth_headers
        )

    assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Cross-feature: Redis exceptions (lines 544-546, 570-571)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_cross_feature_redis_read_exception_swallowed(
    async_client, admin_auth_headers
):
    impact = _make_cross_impact()

    with (
        patch(
            "app.api.v1.endpoints.executive._get_redis", new_callable=AsyncMock
        ) as mock_redis,
        patch(
            "app.api.v1.endpoints.executive.aggregate_cross_feature",
            new_callable=AsyncMock,
        ) as mock_agg,
        patch("app.api.v1.endpoints.executive.log_audit_event", new_callable=AsyncMock),
        patch("app.api.v1.endpoints.executive.settings") as mock_settings,
    ):
        mock_settings.EXECUTIVE_ENABLED = True
        mock_settings.EXECUTIVE_CACHE_TTL_S = 1800
        mock_settings.LITRE_DIESEL_TL = 50.0

        mock_redis_client = AsyncMock()
        mock_redis_client.get = AsyncMock(side_effect=RuntimeError("redis down"))
        mock_redis_client.setex = AsyncMock()
        mock_redis.return_value = mock_redis_client

        mock_agg.return_value = impact

        resp = await async_client.get(
            f"{BASE}/cross-feature?days=90", headers=admin_auth_headers
        )

    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_cross_feature_redis_setex_exception_swallowed(
    async_client, admin_auth_headers
):
    impact = _make_cross_impact()

    with (
        patch(
            "app.api.v1.endpoints.executive._get_redis", new_callable=AsyncMock
        ) as mock_redis,
        patch(
            "app.api.v1.endpoints.executive.aggregate_cross_feature",
            new_callable=AsyncMock,
        ) as mock_agg,
        patch("app.api.v1.endpoints.executive.log_audit_event", new_callable=AsyncMock),
        patch("app.api.v1.endpoints.executive.settings") as mock_settings,
    ):
        mock_settings.EXECUTIVE_ENABLED = True
        mock_settings.EXECUTIVE_CACHE_TTL_S = 1800
        mock_settings.LITRE_DIESEL_TL = 50.0

        mock_redis_client = AsyncMock()
        mock_redis_client.get = AsyncMock(return_value=None)
        mock_redis_client.setex = AsyncMock(side_effect=RuntimeError("setex fail"))
        mock_redis.return_value = mock_redis_client

        mock_agg.return_value = impact

        resp = await async_client.get(
            f"{BASE}/cross-feature?days=90", headers=admin_auth_headers
        )

    assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Bus-factor: Redis exceptions (lines 620-622, 649-650)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_bus_factor_redis_read_exception_swallowed(
    async_client, admin_auth_headers
):
    report = _make_bus_factor_report()

    with (
        patch(
            "app.api.v1.endpoints.executive._get_redis", new_callable=AsyncMock
        ) as mock_redis,
        patch(
            "app.api.v1.endpoints.executive.compute_bus_factor", new_callable=AsyncMock
        ) as mock_bus,
        patch("app.api.v1.endpoints.executive.log_audit_event", new_callable=AsyncMock),
        patch("app.api.v1.endpoints.executive.settings") as mock_settings,
    ):
        mock_settings.EXECUTIVE_ENABLED = True
        mock_settings.EXECUTIVE_CACHE_TTL_S = 1800
        mock_settings.LITRE_DIESEL_TL = 50.0

        mock_redis_client = AsyncMock()
        mock_redis_client.get = AsyncMock(side_effect=RuntimeError("redis down"))
        mock_redis_client.setex = AsyncMock()
        mock_redis.return_value = mock_redis_client

        mock_bus.return_value = report

        resp = await async_client.get(
            f"{BASE}/bus-factor?n=3", headers=admin_auth_headers
        )

    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_bus_factor_redis_setex_exception_swallowed(
    async_client, admin_auth_headers
):
    report = _make_bus_factor_report()

    with (
        patch(
            "app.api.v1.endpoints.executive._get_redis", new_callable=AsyncMock
        ) as mock_redis,
        patch(
            "app.api.v1.endpoints.executive.compute_bus_factor", new_callable=AsyncMock
        ) as mock_bus,
        patch("app.api.v1.endpoints.executive.log_audit_event", new_callable=AsyncMock),
        patch("app.api.v1.endpoints.executive.settings") as mock_settings,
    ):
        mock_settings.EXECUTIVE_ENABLED = True
        mock_settings.EXECUTIVE_CACHE_TTL_S = 1800
        mock_settings.LITRE_DIESEL_TL = 50.0

        mock_redis_client = AsyncMock()
        mock_redis_client.get = AsyncMock(return_value=None)
        mock_redis_client.setex = AsyncMock(side_effect=RuntimeError("setex fail"))
        mock_redis.return_value = mock_redis_client

        mock_bus.return_value = report

        resp = await async_client.get(
            f"{BASE}/bus-factor?n=3", headers=admin_auth_headers
        )

    assert resp.status_code == 200
