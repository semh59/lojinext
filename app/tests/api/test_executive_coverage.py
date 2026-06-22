"""Coverage tests for app/api/v1/endpoints/executive.py.

Targets the 7 endpoint handlers + _ensure_enabled + _get_redis.
All DB/ML/cache calls are mocked so no PostgreSQL required.

pytestmark: unit
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# Helpers / shared fixtures
# ---------------------------------------------------------------------------

BASE = "/api/v1/reports/executive"


def _make_fvi_inputs() -> dict:
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


def _make_fvi_breakdown() -> MagicMock:
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


def _make_carbon_report() -> MagicMock:
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


def _make_compliance_item() -> MagicMock:
    item = MagicMock()
    item.risk_level = "soon"
    item.entity_type = "arac"
    item.entity_id = 1
    item.plaka = "34ABC123"
    item.field = "muayene"
    item.expiry_date = date(2026, 7, 15)
    item.days_until = 42
    return item


def _make_overdue_item() -> MagicMock:
    item = MagicMock()
    item.risk_level = "overdue"
    item.entity_type = "arac"
    item.entity_id = 2
    item.plaka = "06DEF456"
    item.field = "muayene"
    item.expiry_date = date(2026, 5, 1)
    item.days_until = -32
    return item


def _make_cashflow_projection() -> MagicMock:
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


def _make_cross_impact() -> MagicMock:
    i = MagicMock()
    i.period_days = 90
    i.maintenance_delay_loss_tl = 15000.0
    i.coaching_savings_tl = 8000.0
    i.theft_loss_tl = 3000.0
    i.confidence = 0.55
    return i


def _make_bus_factor_report() -> MagicMock:
    r = MagicMock()
    r.n = 3
    r.top_n_drivers_loss_tl = 120000.0
    r.top_n_drivers = [{"score": 1.4, "yearly_km": 85000}]
    r.bottlenecked_routes = []
    r.risk_level = "high"
    return r


def _make_what_if_result() -> MagicMock:
    res = MagicMock()
    res.scenario_type = "fleet_renewal"
    res.inputs = {"max_age_years": 10}
    res.yearly_savings_tl = 80000.0
    res.upfront_cost_tl = 500000.0
    res.payback_years = 6.25
    res.five_year_roi_pct = 62.0
    res.co2_reduction_kg = 25000.0
    res.confidence = 0.8
    res.monte_carlo = None
    res.reasons = ["Fleet renewal ROI positive"]
    return res


# ---------------------------------------------------------------------------
# Auth guard tests (no mocking needed — just hit the endpoint without token)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_kpi_requires_auth(async_client):
    resp = await async_client.get(f"{BASE}/kpi")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_what_if_requires_auth(async_client):
    resp = await async_client.post(
        f"{BASE}/what-if", json={"scenario_type": "training"}
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_carbon_requires_auth(async_client):
    resp = await async_client.get(f"{BASE}/carbon")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_compliance_requires_auth(async_client):
    resp = await async_client.get(f"{BASE}/compliance")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_cashflow_requires_auth(async_client):
    resp = await async_client.get(f"{BASE}/cashflow")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_cross_feature_requires_auth(async_client):
    resp = await async_client.get(f"{BASE}/cross-feature")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_bus_factor_requires_auth(async_client):
    resp = await async_client.get(f"{BASE}/bus-factor")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_pdf_requires_auth(async_client):
    resp = await async_client.get(f"{BASE}/pdf")
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# _ensure_enabled: 503 when feature flag off
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_kpi_503_when_disabled(async_client, admin_auth_headers):
    with patch("app.api.v1.endpoints.executive.settings") as mock_settings:
        mock_settings.EXECUTIVE_ENABLED = False
        resp = await async_client.get(f"{BASE}/kpi", headers=admin_auth_headers)
    assert resp.status_code == 503
    # Error envelope: {"error": {"code": ..., "message": ...}}
    assert "devre" in resp.json()["error"]["message"]


@pytest.mark.asyncio
async def test_what_if_503_when_disabled(async_client, admin_auth_headers):
    with patch("app.api.v1.endpoints.executive.settings") as mock_settings:
        mock_settings.EXECUTIVE_ENABLED = False
        mock_settings.EXECUTIVE_WHAT_IF_ENABLED = True
        resp = await async_client.post(
            f"{BASE}/what-if",
            json={
                "scenario_type": "fleet_renewal",
                "fleet_renewal": {
                    "max_age_years": 10,
                    "replacement_cost_per_vehicle_tl": 800000,
                    "expected_l_100km_improvement_pct": 15.0,
                    "diesel_price_tl": 50.0,
                },
            },
            headers=admin_auth_headers,
        )
    assert resp.status_code == 503


@pytest.mark.asyncio
async def test_what_if_503_when_what_if_disabled(async_client, admin_auth_headers):
    with patch("app.api.v1.endpoints.executive.settings") as mock_settings:
        mock_settings.EXECUTIVE_ENABLED = True
        mock_settings.EXECUTIVE_WHAT_IF_ENABLED = False
        resp = await async_client.post(
            f"{BASE}/what-if",
            json={
                "scenario_type": "fleet_renewal",
                "fleet_renewal": {
                    "max_age_years": 10,
                    "replacement_cost_per_vehicle_tl": 800000,
                    "expected_l_100km_improvement_pct": 15.0,
                    "diesel_price_tl": 50.0,
                },
            },
            headers=admin_auth_headers,
        )
    assert resp.status_code == 503
    assert "What-if devre" in resp.json()["error"]["message"]


# ---------------------------------------------------------------------------
# Validation errors (422) for query params out of range
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_carbon_days_too_low(async_client, admin_auth_headers):
    with patch("app.api.v1.endpoints.executive.settings") as mock_settings:
        mock_settings.EXECUTIVE_ENABLED = True
        resp = await async_client.get(
            f"{BASE}/carbon?days=3", headers=admin_auth_headers
        )
    assert resp.status_code == 400
    assert "7-365" in resp.json()["error"]["message"]


@pytest.mark.asyncio
async def test_carbon_days_too_high(async_client, admin_auth_headers):
    with patch("app.api.v1.endpoints.executive.settings") as mock_settings:
        mock_settings.EXECUTIVE_ENABLED = True
        resp = await async_client.get(
            f"{BASE}/carbon?days=400", headers=admin_auth_headers
        )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_compliance_days_horizon_too_low(async_client, admin_auth_headers):
    with patch("app.api.v1.endpoints.executive.settings") as mock_settings:
        mock_settings.EXECUTIVE_ENABLED = True
        resp = await async_client.get(
            f"{BASE}/compliance?days_horizon=3", headers=admin_auth_headers
        )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_cashflow_days_too_low(async_client, admin_auth_headers):
    with patch("app.api.v1.endpoints.executive.settings") as mock_settings:
        mock_settings.EXECUTIVE_ENABLED = True
        resp = await async_client.get(
            f"{BASE}/cashflow?days=5", headers=admin_auth_headers
        )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_cross_feature_days_too_low(async_client, admin_auth_headers):
    with patch("app.api.v1.endpoints.executive.settings") as mock_settings:
        mock_settings.EXECUTIVE_ENABLED = True
        resp = await async_client.get(
            f"{BASE}/cross-feature?days=5", headers=admin_auth_headers
        )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_bus_factor_n_too_high(async_client, admin_auth_headers):
    with patch("app.api.v1.endpoints.executive.settings") as mock_settings:
        mock_settings.EXECUTIVE_ENABLED = True
        resp = await async_client.get(
            f"{BASE}/bus-factor?n=20", headers=admin_auth_headers
        )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_bus_factor_n_zero(async_client, admin_auth_headers):
    with patch("app.api.v1.endpoints.executive.settings") as mock_settings:
        mock_settings.EXECUTIVE_ENABLED = True
        resp = await async_client.get(
            f"{BASE}/bus-factor?n=0", headers=admin_auth_headers
        )
    assert resp.status_code == 400


# ---------------------------------------------------------------------------
# what-if: missing inputs 400
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_what_if_fleet_renewal_missing_inputs(async_client, admin_auth_headers):
    """fleet_renewal scenario without fleet_renewal payload → 400."""
    with (
        patch("app.api.v1.endpoints.executive.settings") as mock_settings,
        patch(
            "app.api.v1.endpoints.executive._get_redis", new_callable=AsyncMock
        ) as mock_redis,
        patch("app.api.v1.endpoints.executive.UnitOfWork") as mock_uow_cls,
    ):
        mock_settings.EXECUTIVE_ENABLED = True
        mock_settings.EXECUTIVE_WHAT_IF_ENABLED = True
        mock_redis.return_value = None

        mock_uow = AsyncMock()
        mock_uow.__aenter__ = AsyncMock(return_value=mock_uow)
        mock_uow.__aexit__ = AsyncMock(return_value=False)
        mock_uow_cls.return_value = mock_uow

        resp = await async_client.post(
            f"{BASE}/what-if",
            json={"scenario_type": "fleet_renewal"},
            headers=admin_auth_headers,
        )
    # Missing inputs are rejected by the WhatIfRequest model_validator (422, FastAPI
    # request validation) before the handler's legacy 400 branch — that branch is now
    # dead code. Assert the real behavior. (Stale test predating the validator.)
    assert resp.status_code == 422
    assert "inputs gerekli" in str(resp.json())


@pytest.mark.asyncio
async def test_what_if_training_missing_inputs(async_client, admin_auth_headers):
    with (
        patch("app.api.v1.endpoints.executive.settings") as mock_settings,
        patch(
            "app.api.v1.endpoints.executive._get_redis", new_callable=AsyncMock
        ) as mock_redis,
        patch("app.api.v1.endpoints.executive.UnitOfWork") as mock_uow_cls,
    ):
        mock_settings.EXECUTIVE_ENABLED = True
        mock_settings.EXECUTIVE_WHAT_IF_ENABLED = True
        mock_redis.return_value = None

        mock_uow = AsyncMock()
        mock_uow.__aenter__ = AsyncMock(return_value=mock_uow)
        mock_uow.__aexit__ = AsyncMock(return_value=False)
        mock_uow_cls.return_value = mock_uow

        resp = await async_client.post(
            f"{BASE}/what-if",
            json={"scenario_type": "training"},
            headers=admin_auth_headers,
        )
    # Rejected by the model_validator (422) before the handler's dead 400 branch.
    assert resp.status_code == 422
    assert "inputs gerekli" in str(resp.json())


@pytest.mark.asyncio
async def test_what_if_route_portfolio_missing_inputs(async_client, admin_auth_headers):
    with (
        patch("app.api.v1.endpoints.executive.settings") as mock_settings,
        patch(
            "app.api.v1.endpoints.executive._get_redis", new_callable=AsyncMock
        ) as mock_redis,
        patch("app.api.v1.endpoints.executive.UnitOfWork") as mock_uow_cls,
    ):
        mock_settings.EXECUTIVE_ENABLED = True
        mock_settings.EXECUTIVE_WHAT_IF_ENABLED = True
        mock_redis.return_value = None

        mock_uow = AsyncMock()
        mock_uow.__aenter__ = AsyncMock(return_value=mock_uow)
        mock_uow.__aexit__ = AsyncMock(return_value=False)
        mock_uow_cls.return_value = mock_uow

        resp = await async_client.post(
            f"{BASE}/what-if",
            json={"scenario_type": "route_portfolio"},
            headers=admin_auth_headers,
        )
    # Rejected by the model_validator (422) before the handler's dead 400 branch.
    assert resp.status_code == 422
    assert "inputs gerekli" in str(resp.json())


# ---------------------------------------------------------------------------
# Happy path 200 tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_kpi_200_no_cache(async_client, admin_auth_headers):
    """FVI endpoint — no Redis cache, fresh compute."""
    fvi_inputs = _make_fvi_inputs()
    breakdown = _make_fvi_breakdown()

    with (
        patch(
            "app.api.v1.endpoints.executive._get_redis", new_callable=AsyncMock
        ) as mock_redis,
        patch("app.api.v1.endpoints.executive.UnitOfWork") as mock_uow_cls,
        patch(
            "app.api.v1.endpoints.executive.gather_fvi_inputs",
            new_callable=AsyncMock,
        ) as mock_gather,
        patch("app.api.v1.endpoints.executive.compute_fvi", return_value=breakdown),
        patch(
            "app.api.v1.endpoints.executive.log_audit_event",
            new_callable=AsyncMock,
        ),
        patch("app.api.v1.endpoints.executive.settings") as mock_settings,
    ):
        mock_settings.EXECUTIVE_ENABLED = True
        mock_settings.EXECUTIVE_CACHE_TTL_S = 1800

        # Redis returns None (no cache hit)
        mock_redis_client = AsyncMock()
        mock_redis_client.get = AsyncMock(return_value=None)
        mock_redis_client.setex = AsyncMock()
        mock_redis.return_value = mock_redis_client

        mock_uow = AsyncMock()
        mock_uow.__aenter__ = AsyncMock(return_value=mock_uow)
        mock_uow.__aexit__ = AsyncMock(return_value=False)
        mock_uow_cls.return_value = mock_uow

        mock_gather.return_value = fvi_inputs

        resp = await async_client.get(f"{BASE}/kpi", headers=admin_auth_headers)

    assert resp.status_code == 200
    data = resp.json()
    assert data["fvi"] == 75.0
    assert data["fuel_score"] == 80.0
    assert "computed_at" in data


@pytest.mark.asyncio
async def test_kpi_200_cache_hit(async_client, admin_auth_headers):
    """FVI endpoint returns cached response from Redis."""
    import json as _json

    # Build a FleetEfficiencyResponse-like dict
    cached_data = {
        "fvi": 72.0,
        "fuel_score": 78.0,
        "maintenance_score": 68.0,
        "driver_score": 73.0,
        "anomaly_quality_score": 65.0,
        "confidence": 0.8,
        "trend_30d": 1.5,
        "reasons": ["cache"],
        "computed_at": datetime.now(timezone.utc).isoformat(),
    }

    with (
        patch(
            "app.api.v1.endpoints.executive._get_redis", new_callable=AsyncMock
        ) as mock_redis,
        patch("app.api.v1.endpoints.executive.settings") as mock_settings,
    ):
        mock_settings.EXECUTIVE_ENABLED = True

        mock_redis_client = AsyncMock()
        mock_redis_client.get = AsyncMock(return_value=_json.dumps(cached_data))
        mock_redis.return_value = mock_redis_client

        resp = await async_client.get(f"{BASE}/kpi", headers=admin_auth_headers)

    assert resp.status_code == 200
    assert resp.json()["fvi"] == 72.0


@pytest.mark.asyncio
async def test_carbon_200_no_cache(async_client, admin_auth_headers):
    carbon_report = _make_carbon_report()

    with (
        patch(
            "app.api.v1.endpoints.executive._get_redis", new_callable=AsyncMock
        ) as mock_redis,
        patch("app.api.v1.endpoints.executive.UnitOfWork") as mock_uow_cls,
        patch(
            "app.api.v1.endpoints.executive.compute_fleet_carbon",
            new_callable=AsyncMock,
        ) as mock_carbon,
        patch(
            "app.api.v1.endpoints.executive.log_audit_event",
            new_callable=AsyncMock,
        ),
        patch("app.api.v1.endpoints.executive.settings") as mock_settings,
    ):
        mock_settings.EXECUTIVE_ENABLED = True
        mock_settings.EXECUTIVE_CACHE_TTL_S = 1800

        mock_redis_client = AsyncMock()
        mock_redis_client.get = AsyncMock(return_value=None)
        mock_redis_client.setex = AsyncMock()
        mock_redis.return_value = mock_redis_client

        mock_uow = AsyncMock()
        mock_uow.__aenter__ = AsyncMock(return_value=mock_uow)
        mock_uow.__aexit__ = AsyncMock(return_value=False)
        mock_uow_cls.return_value = mock_uow

        mock_carbon.return_value = carbon_report

        resp = await async_client.get(
            f"{BASE}/carbon?days=30", headers=admin_auth_headers
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["total_co2_kg"] == 50000.0
    assert data["vehicle_count"] == 12


@pytest.mark.asyncio
async def test_compliance_200_with_items(async_client, admin_auth_headers):
    soon_item = _make_compliance_item()
    overdue_item = _make_overdue_item()

    with (
        patch(
            "app.api.v1.endpoints.executive._get_redis", new_callable=AsyncMock
        ) as mock_redis,
        patch("app.api.v1.endpoints.executive.UnitOfWork") as mock_uow_cls,
        patch(
            "app.api.v1.endpoints.executive.scan_compliance",
            new_callable=AsyncMock,
        ) as mock_scan,
        patch(
            "app.api.v1.endpoints.executive.log_audit_event",
            new_callable=AsyncMock,
        ),
        patch("app.api.v1.endpoints.executive.settings") as mock_settings,
    ):
        mock_settings.EXECUTIVE_ENABLED = True
        mock_settings.EXECUTIVE_CACHE_TTL_S = 1800

        mock_redis_client = AsyncMock()
        mock_redis_client.get = AsyncMock(return_value=None)
        mock_redis_client.setex = AsyncMock()
        mock_redis.return_value = mock_redis_client

        mock_uow = AsyncMock()
        mock_uow.__aenter__ = AsyncMock(return_value=mock_uow)
        mock_uow.__aexit__ = AsyncMock(return_value=False)
        mock_uow_cls.return_value = mock_uow

        mock_scan.return_value = [soon_item, overdue_item]

        resp = await async_client.get(
            f"{BASE}/compliance?days_horizon=90", headers=admin_auth_headers
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["total_items"] == 2
    assert data["overdue_count"] == 1
    assert data["soon_count"] == 1


@pytest.mark.asyncio
async def test_cashflow_200(async_client, admin_auth_headers):
    projection = _make_cashflow_projection()

    with (
        patch(
            "app.api.v1.endpoints.executive._get_redis", new_callable=AsyncMock
        ) as mock_redis,
        patch("app.api.v1.endpoints.executive.UnitOfWork") as mock_uow_cls,
        patch(
            "app.api.v1.endpoints.executive.project_cashflow",
            new_callable=AsyncMock,
        ) as mock_project,
        patch(
            "app.api.v1.endpoints.executive.log_audit_event",
            new_callable=AsyncMock,
        ),
        patch("app.api.v1.endpoints.executive.settings") as mock_settings,
    ):
        mock_settings.EXECUTIVE_ENABLED = True
        mock_settings.EXECUTIVE_CACHE_TTL_S = 1800
        mock_settings.LITRE_DIESEL_TL = 50.0
        mock_settings.AVG_BAKIM_COST_TL = 2000.0

        mock_redis_client = AsyncMock()
        mock_redis_client.get = AsyncMock(return_value=None)
        mock_redis_client.setex = AsyncMock()
        mock_redis.return_value = mock_redis_client

        mock_uow = AsyncMock()
        mock_uow.__aenter__ = AsyncMock(return_value=mock_uow)
        mock_uow.__aexit__ = AsyncMock(return_value=False)
        mock_uow_cls.return_value = mock_uow

        mock_project.return_value = projection

        resp = await async_client.get(
            f"{BASE}/cashflow?days=90", headers=admin_auth_headers
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["grand_total_tl"] == 250000.0
    assert data["horizon_days"] == 90


@pytest.mark.asyncio
async def test_cross_feature_200(async_client, admin_auth_headers):
    impact = _make_cross_impact()

    with (
        patch(
            "app.api.v1.endpoints.executive._get_redis", new_callable=AsyncMock
        ) as mock_redis,
        patch("app.api.v1.endpoints.executive.UnitOfWork") as mock_uow_cls,
        patch(
            "app.api.v1.endpoints.executive.aggregate_cross_feature",
            new_callable=AsyncMock,
        ) as mock_agg,
        patch(
            "app.api.v1.endpoints.executive.log_audit_event",
            new_callable=AsyncMock,
        ),
        patch("app.api.v1.endpoints.executive.settings") as mock_settings,
    ):
        mock_settings.EXECUTIVE_ENABLED = True
        mock_settings.EXECUTIVE_CACHE_TTL_S = 1800
        mock_settings.LITRE_DIESEL_TL = 50.0

        mock_redis_client = AsyncMock()
        mock_redis_client.get = AsyncMock(return_value=None)
        mock_redis_client.setex = AsyncMock()
        mock_redis.return_value = mock_redis_client

        mock_uow = AsyncMock()
        mock_uow.__aenter__ = AsyncMock(return_value=mock_uow)
        mock_uow.__aexit__ = AsyncMock(return_value=False)
        mock_uow_cls.return_value = mock_uow

        mock_agg.return_value = impact

        resp = await async_client.get(
            f"{BASE}/cross-feature?days=90", headers=admin_auth_headers
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["maintenance_delay_loss_tl"] == 15000.0
    assert data["theft_loss_tl"] == 3000.0


@pytest.mark.asyncio
async def test_bus_factor_200(async_client, admin_auth_headers):
    report = _make_bus_factor_report()

    with (
        patch(
            "app.api.v1.endpoints.executive._get_redis", new_callable=AsyncMock
        ) as mock_redis,
        patch("app.api.v1.endpoints.executive.UnitOfWork") as mock_uow_cls,
        patch(
            "app.api.v1.endpoints.executive.compute_bus_factor",
            new_callable=AsyncMock,
        ) as mock_bus,
        patch(
            "app.api.v1.endpoints.executive.log_audit_event",
            new_callable=AsyncMock,
        ),
        patch("app.api.v1.endpoints.executive.settings") as mock_settings,
    ):
        mock_settings.EXECUTIVE_ENABLED = True
        mock_settings.EXECUTIVE_CACHE_TTL_S = 1800
        mock_settings.LITRE_DIESEL_TL = 50.0

        mock_redis_client = AsyncMock()
        mock_redis_client.get = AsyncMock(return_value=None)
        mock_redis_client.setex = AsyncMock()
        mock_redis.return_value = mock_redis_client

        mock_uow = AsyncMock()
        mock_uow.__aenter__ = AsyncMock(return_value=mock_uow)
        mock_uow.__aexit__ = AsyncMock(return_value=False)
        mock_uow_cls.return_value = mock_uow

        mock_bus.return_value = report

        resp = await async_client.get(
            f"{BASE}/bus-factor?n=3", headers=admin_auth_headers
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["n"] == 3
    assert data["risk_level"] == "high"
    assert len(data["top_n_drivers"]) == 1


@pytest.mark.asyncio
async def test_what_if_fleet_renewal_200(async_client, admin_auth_headers):
    result = _make_what_if_result()

    with (
        patch("app.api.v1.endpoints.executive.UnitOfWork") as mock_uow_cls,
        patch(
            "app.api.v1.endpoints.executive.simulate_fleet_renewal",
            new_callable=AsyncMock,
        ) as mock_sim,
        patch(
            "app.api.v1.endpoints.executive.log_audit_event",
            new_callable=AsyncMock,
        ),
        patch("app.api.v1.endpoints.executive.settings") as mock_settings,
    ):
        mock_settings.EXECUTIVE_ENABLED = True
        mock_settings.EXECUTIVE_WHAT_IF_ENABLED = True

        mock_uow = AsyncMock()
        mock_uow.__aenter__ = AsyncMock(return_value=mock_uow)
        mock_uow.__aexit__ = AsyncMock(return_value=False)
        mock_uow_cls.return_value = mock_uow

        mock_sim.return_value = result

        resp = await async_client.post(
            f"{BASE}/what-if",
            json={
                "scenario_type": "fleet_renewal",
                "fleet_renewal": {
                    "max_age_years": 10,
                    "replacement_cost_per_vehicle_tl": 800000,
                    "expected_l_100km_improvement_pct": 15.0,
                    "diesel_price_tl": 50.0,
                },
            },
            headers=admin_auth_headers,
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["scenario_type"] == "fleet_renewal"
    assert data["yearly_savings_tl"] == 80000.0


@pytest.mark.asyncio
async def test_what_if_training_200(async_client, admin_auth_headers):
    result = _make_what_if_result()
    result.scenario_type = "training"

    with (
        patch("app.api.v1.endpoints.executive.UnitOfWork") as mock_uow_cls,
        patch(
            "app.api.v1.endpoints.executive.simulate_training_program",
            new_callable=AsyncMock,
        ) as mock_sim,
        patch(
            "app.api.v1.endpoints.executive.log_audit_event",
            new_callable=AsyncMock,
        ),
        patch("app.api.v1.endpoints.executive.settings") as mock_settings,
    ):
        mock_settings.EXECUTIVE_ENABLED = True
        mock_settings.EXECUTIVE_WHAT_IF_ENABLED = True

        mock_uow = AsyncMock()
        mock_uow.__aenter__ = AsyncMock(return_value=mock_uow)
        mock_uow.__aexit__ = AsyncMock(return_value=False)
        mock_uow_cls.return_value = mock_uow

        mock_sim.return_value = result

        resp = await async_client.post(
            f"{BASE}/what-if",
            json={
                "scenario_type": "training",
                "training": {
                    "improvement_pct": 10.0,
                    "training_cost_per_driver_tl": 5000.0,
                    "diesel_price_tl": 50.0,
                },
            },
            headers=admin_auth_headers,
        )

    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_what_if_route_portfolio_200(async_client, admin_auth_headers):
    result = _make_what_if_result()
    result.scenario_type = "route_portfolio"

    with (
        patch("app.api.v1.endpoints.executive.UnitOfWork") as mock_uow_cls,
        patch(
            "app.api.v1.endpoints.executive.simulate_route_portfolio",
            new_callable=AsyncMock,
        ) as mock_sim,
        patch(
            "app.api.v1.endpoints.executive.log_audit_event",
            new_callable=AsyncMock,
        ),
        patch("app.api.v1.endpoints.executive.settings") as mock_settings,
    ):
        mock_settings.EXECUTIVE_ENABLED = True
        mock_settings.EXECUTIVE_WHAT_IF_ENABLED = True

        mock_uow = AsyncMock()
        mock_uow.__aenter__ = AsyncMock(return_value=mock_uow)
        mock_uow.__aexit__ = AsyncMock(return_value=False)
        mock_uow_cls.return_value = mock_uow

        mock_sim.return_value = result

        resp = await async_client.post(
            f"{BASE}/what-if",
            json={
                "scenario_type": "route_portfolio",
                "route_portfolio": {
                    "drop_bottom_n": 3,
                    "iterations": 100,
                    "diesel_price_tl": 50.0,
                },
            },
            headers=admin_auth_headers,
        )

    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_pdf_200(async_client, admin_auth_headers):
    """PDF endpoint returns PDF bytes with correct content-type."""
    fvi_inputs = _make_fvi_inputs()
    breakdown = _make_fvi_breakdown()
    cashflow = _make_cashflow_projection()
    impact = _make_cross_impact()
    fake_pdf = b"%PDF-1.4 fake content"

    with (
        patch("app.api.v1.endpoints.executive.UnitOfWork") as mock_uow_cls,
        patch(
            "app.api.v1.endpoints.executive.gather_fvi_inputs",
            new_callable=AsyncMock,
        ) as mock_gather,
        patch("app.api.v1.endpoints.executive.compute_fvi", return_value=breakdown),
        patch(
            "app.api.v1.endpoints.executive.project_cashflow",
            new_callable=AsyncMock,
        ) as mock_cashflow,
        patch(
            "app.api.v1.endpoints.executive.aggregate_cross_feature",
            new_callable=AsyncMock,
        ) as mock_agg,
        patch(
            "app.api.v1.endpoints.executive.generate_executive_pdf",
            return_value=fake_pdf,
        ),
        patch(
            "app.api.v1.endpoints.executive.log_audit_event",
            new_callable=AsyncMock,
        ),
        patch("app.api.v1.endpoints.executive.settings") as mock_settings,
    ):
        mock_settings.EXECUTIVE_ENABLED = True
        mock_settings.LITRE_DIESEL_TL = 50.0
        mock_settings.AVG_BAKIM_COST_TL = 2000.0

        mock_uow = AsyncMock()
        mock_uow.__aenter__ = AsyncMock(return_value=mock_uow)
        mock_uow.__aexit__ = AsyncMock(return_value=False)
        mock_uow_cls.return_value = mock_uow

        mock_gather.return_value = fvi_inputs
        mock_cashflow.return_value = cashflow
        mock_agg.return_value = impact

        resp = await async_client.get(f"{BASE}/pdf", headers=admin_auth_headers)

    assert resp.status_code == 200
    assert resp.headers["content-type"] == "application/pdf"
    assert resp.content == fake_pdf


@pytest.mark.asyncio
async def test_pdf_503_when_disabled(async_client, admin_auth_headers):
    with patch("app.api.v1.endpoints.executive.settings") as mock_settings:
        mock_settings.EXECUTIVE_ENABLED = False
        resp = await async_client.get(f"{BASE}/pdf", headers=admin_auth_headers)
    assert resp.status_code == 503


# ---------------------------------------------------------------------------
# Redis None path (no cache available) — ensures code path without Redis
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_carbon_redis_none(async_client, admin_auth_headers):
    """Carbon endpoint still works when Redis is unavailable (returns None)."""
    carbon_report = _make_carbon_report()

    with (
        patch(
            "app.api.v1.endpoints.executive._get_redis", new_callable=AsyncMock
        ) as mock_redis,
        patch("app.api.v1.endpoints.executive.UnitOfWork") as mock_uow_cls,
        patch(
            "app.api.v1.endpoints.executive.compute_fleet_carbon",
            new_callable=AsyncMock,
        ) as mock_carbon,
        patch(
            "app.api.v1.endpoints.executive.log_audit_event",
            new_callable=AsyncMock,
        ),
        patch("app.api.v1.endpoints.executive.settings") as mock_settings,
    ):
        mock_settings.EXECUTIVE_ENABLED = True
        mock_settings.EXECUTIVE_CACHE_TTL_S = 1800
        mock_redis.return_value = None  # no redis

        mock_uow = AsyncMock()
        mock_uow.__aenter__ = AsyncMock(return_value=mock_uow)
        mock_uow.__aexit__ = AsyncMock(return_value=False)
        mock_uow_cls.return_value = mock_uow

        mock_carbon.return_value = carbon_report

        resp = await async_client.get(
            f"{BASE}/carbon?days=30", headers=admin_auth_headers
        )

    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_compliance_redis_none(async_client, admin_auth_headers):
    """Compliance endpoint works when Redis is None."""
    item = _make_compliance_item()

    with (
        patch(
            "app.api.v1.endpoints.executive._get_redis", new_callable=AsyncMock
        ) as mock_redis,
        patch("app.api.v1.endpoints.executive.UnitOfWork") as mock_uow_cls,
        patch(
            "app.api.v1.endpoints.executive.scan_compliance",
            new_callable=AsyncMock,
        ) as mock_scan,
        patch(
            "app.api.v1.endpoints.executive.log_audit_event",
            new_callable=AsyncMock,
        ),
        patch("app.api.v1.endpoints.executive.settings") as mock_settings,
    ):
        mock_settings.EXECUTIVE_ENABLED = True
        mock_settings.EXECUTIVE_CACHE_TTL_S = 1800
        mock_redis.return_value = None

        mock_uow = AsyncMock()
        mock_uow.__aenter__ = AsyncMock(return_value=mock_uow)
        mock_uow.__aexit__ = AsyncMock(return_value=False)
        mock_uow_cls.return_value = mock_uow

        mock_scan.return_value = [item]

        resp = await async_client.get(
            f"{BASE}/compliance?days_horizon=30", headers=admin_auth_headers
        )

    assert resp.status_code == 200
    assert resp.json()["total_items"] == 1


# ---------------------------------------------------------------------------
# Cache hit from Redis — compliance and cashflow
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_compliance_cache_hit(async_client, admin_auth_headers):
    import json as _json

    cached = {
        "days_horizon": 90,
        "total_items": 5,
        "overdue_count": 1,
        "soon_count": 2,
        "items": [],
    }
    with (
        patch(
            "app.api.v1.endpoints.executive._get_redis", new_callable=AsyncMock
        ) as mock_redis,
        patch("app.api.v1.endpoints.executive.settings") as mock_settings,
    ):
        mock_settings.EXECUTIVE_ENABLED = True

        mock_redis_client = AsyncMock()
        mock_redis_client.get = AsyncMock(return_value=_json.dumps(cached))
        mock_redis.return_value = mock_redis_client

        resp = await async_client.get(
            f"{BASE}/compliance?days_horizon=90", headers=admin_auth_headers
        )

    assert resp.status_code == 200
    assert resp.json()["total_items"] == 5


@pytest.mark.asyncio
async def test_cashflow_cache_hit(async_client, admin_auth_headers):
    import json as _json

    cached = {
        "horizon_days": 90,
        "weeks": [],
        "total_fuel_tl": 100000.0,
        "total_maintenance_tl": 30000.0,
        "total_penalty_tl": None,
        "grand_total_tl": 130000.0,
        "confidence": 0.65,
        "assumptions": {},
    }
    with (
        patch(
            "app.api.v1.endpoints.executive._get_redis", new_callable=AsyncMock
        ) as mock_redis,
        patch("app.api.v1.endpoints.executive.settings") as mock_settings,
    ):
        mock_settings.EXECUTIVE_ENABLED = True

        mock_redis_client = AsyncMock()
        mock_redis_client.get = AsyncMock(return_value=_json.dumps(cached))
        mock_redis.return_value = mock_redis_client

        resp = await async_client.get(
            f"{BASE}/cashflow?days=90", headers=admin_auth_headers
        )

    assert resp.status_code == 200
    assert resp.json()["grand_total_tl"] == 130000.0
