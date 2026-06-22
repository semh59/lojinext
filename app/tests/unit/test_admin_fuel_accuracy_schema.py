"""admin_fuel_accuracy endpoint schema testleri (Phase 5.3).

DB'siz smoke. Endpoint integration test'i DB ile CI'da koşacak.
"""

from __future__ import annotations

from app.api.v1.endpoints.admin_fuel_accuracy import (
    FuelAccuracyStats,
    router,
)


def test_router_has_fuel_accuracy_endpoint():
    """Router doğru path'i export ediyor."""
    paths = [r.path for r in router.routes]
    assert "/fuel-accuracy" in paths


def test_schema_has_required_fields():
    """FuelAccuracyStats response shape — UI/dashboard'un beklediği alanlar."""
    fields = FuelAccuracyStats.model_fields.keys()
    required = {
        "period_days",
        "sample_size",
        "mape_pct",
        "rmse_l_100km",
        "mean_predicted",
        "mean_actual",
        "bias_pct",
        "coverage_pct",
        "breakdown_by_arac",
    }
    assert required <= set(fields)


def test_schema_accepts_empty_state():
    """Sample yokken (yeni deploy sonrası) tüm metrikler None ama valid."""
    stats = FuelAccuracyStats(
        period_days=30,
        sample_size=0,
        coverage_pct=0.0,
    )
    assert stats.mape_pct is None
    assert stats.rmse_l_100km is None
    assert stats.breakdown_by_arac == []


def test_schema_accepts_populated_state():
    """4 hafta veri biriktikten sonra tipik response."""
    stats = FuelAccuracyStats(
        period_days=30,
        sample_size=120,
        mape_pct=12.5,
        rmse_l_100km=3.2,
        mean_predicted=28.4,
        mean_actual=29.1,
        bias_pct=-2.4,
        coverage_pct=87.5,
        breakdown_by_arac=[
            {"arac_id": 1, "samples": 30, "mape_pct": 10.2, "bias_pct": -1.5},
            {"arac_id": 2, "samples": 25, "mape_pct": 15.0, "bias_pct": 3.2},
        ],
    )
    assert stats.mape_pct == 12.5
    assert len(stats.breakdown_by_arac) == 2
