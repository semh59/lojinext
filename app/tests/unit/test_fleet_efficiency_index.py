"""Feature E.1 — FleetEfficiencyIndex saf yardımcı testleri."""

from __future__ import annotations

import pytest


# ── _fuel_score ─────────────────────────────────────────────────────────
def test_fuel_score_cold_start_with_none_avg():
    from v2.modules.analytics_executive.domain.fleet_efficiency import (
        COLD_START_DEFAULT,
        _fuel_score,
    )

    score, reason = _fuel_score(None, 32.0)
    assert score == COLD_START_DEFAULT
    assert "cold-start" in reason.lower()


def test_fuel_score_cold_start_with_none_target():
    from v2.modules.analytics_executive.domain.fleet_efficiency import (
        COLD_START_DEFAULT,
        _fuel_score,
    )

    score, _ = _fuel_score(30.0, None)
    assert score == COLD_START_DEFAULT


def test_fuel_score_cold_start_zero_target():
    from v2.modules.analytics_executive.domain.fleet_efficiency import (
        COLD_START_DEFAULT,
        _fuel_score,
    )

    score, _ = _fuel_score(30.0, 0.0)
    assert score == COLD_START_DEFAULT


def test_fuel_score_exactly_at_target_is_50():
    """avg == target → dev=0 → score 50 (orta)."""
    from v2.modules.analytics_executive.domain.fleet_efficiency import _fuel_score

    score, _ = _fuel_score(32.0, 32.0)
    assert score == pytest.approx(50.0, abs=0.1)


def test_fuel_score_below_target_is_high():
    """avg=27.2, target=32 → dev=-15% → daha iyi skor."""
    from v2.modules.analytics_executive.domain.fleet_efficiency import _fuel_score

    score, _ = _fuel_score(27.2, 32.0)
    # dev = -0.15 → normalized to (0.15 / 0.6) = 0.25 → score 75
    assert score == pytest.approx(75.0, abs=1.0)


def test_fuel_score_above_target_clamp_30pct():
    """avg=50, target=32 → dev=+56% → cap +30% → score 0."""
    from v2.modules.analytics_executive.domain.fleet_efficiency import _fuel_score

    score, _ = _fuel_score(50.0, 32.0)
    assert score == 0.0


# ── _maintenance_score ────────────────────────────────────────────────
def test_maintenance_score_no_active_vehicles():
    from v2.modules.analytics_executive.domain.fleet_efficiency import (
        COLD_START_DEFAULT,
        _maintenance_score,
    )

    score, reason = _maintenance_score(0, 0)
    assert score == COLD_START_DEFAULT
    assert "yok" in reason.lower()


def test_maintenance_score_all_overdue():
    from v2.modules.analytics_executive.domain.fleet_efficiency import (
        _maintenance_score,
    )

    score, _ = _maintenance_score(10, 10)
    assert score == 0.0


def test_maintenance_score_none_overdue():
    from v2.modules.analytics_executive.domain.fleet_efficiency import (
        _maintenance_score,
    )

    score, _ = _maintenance_score(0, 10)
    assert score == 100.0


def test_maintenance_score_half_overdue():
    from v2.modules.analytics_executive.domain.fleet_efficiency import (
        _maintenance_score,
    )

    score, _ = _maintenance_score(5, 10)
    assert score == 50.0


# ── _driver_score ──────────────────────────────────────────────────────
def test_driver_score_none_is_cold_start():
    from v2.modules.analytics_executive.domain.fleet_efficiency import (
        COLD_START_DEFAULT,
        _driver_score,
    )

    score, _ = _driver_score(None)
    assert score == COLD_START_DEFAULT


def test_driver_score_min_floor():
    from v2.modules.analytics_executive.domain.fleet_efficiency import _driver_score

    # 0.5 altı clamp 0
    score, _ = _driver_score(0.1)
    assert score == 0.0


def test_driver_score_neutral():
    """1.0 → (1.0-0.5) * 100 / 1.5 ≈ 33.3."""
    from v2.modules.analytics_executive.domain.fleet_efficiency import _driver_score

    score, _ = _driver_score(1.0)
    assert score == pytest.approx(33.3, abs=0.5)


def test_driver_score_max():
    """2.0 → 100."""
    from v2.modules.analytics_executive.domain.fleet_efficiency import _driver_score

    score, _ = _driver_score(2.0)
    assert score == 100.0


# ── _anomaly_quality_score ────────────────────────────────────────────
def test_anomaly_quality_no_anomalies_is_cold_start():
    from v2.modules.analytics_executive.domain.fleet_efficiency import (
        COLD_START_DEFAULT,
        _anomaly_quality_score,
    )

    score, _ = _anomaly_quality_score(0, 0, 0)
    assert score == COLD_START_DEFAULT


def test_anomaly_quality_all_resolved():
    from v2.modules.analytics_executive.domain.fleet_efficiency import (
        _anomaly_quality_score,
    )

    score, _ = _anomaly_quality_score(10, 0, 10)
    assert score == 100.0


def test_anomaly_quality_all_pending():
    from v2.modules.analytics_executive.domain.fleet_efficiency import (
        _anomaly_quality_score,
    )

    score, _ = _anomaly_quality_score(0, 0, 10)
    assert score == 0.0


def test_anomaly_quality_mixed():
    from v2.modules.analytics_executive.domain.fleet_efficiency import (
        _anomaly_quality_score,
    )

    # 3 resolved + 2 acked = 5/10 → 50
    score, _ = _anomaly_quality_score(3, 2, 10)
    assert score == 50.0


# ── compute_fvi e2e ────────────────────────────────────────────────────
def test_compute_fvi_all_cold_start():
    """Hiç veri yok → fvi=75, confidence=0."""
    from v2.modules.analytics_executive.domain.fleet_efficiency import compute_fvi

    result = compute_fvi(
        fuel_avg=None,
        fuel_target=None,
        overdue_maintenance=0,
        total_active_vehicles=0,
        driver_avg_hybrid=None,
        resolved_anomalies=0,
        acked_anomalies=0,
        total_anomalies=0,
    )
    assert result.fvi == 75.0
    assert result.confidence == 0.0
    assert len(result.reasons) == 4


def test_compute_fvi_full_signals():
    """Tüm sinyaller var → confidence=1.0."""
    from v2.modules.analytics_executive.domain.fleet_efficiency import compute_fvi

    result = compute_fvi(
        fuel_avg=30.0,
        fuel_target=32.0,
        overdue_maintenance=2,
        total_active_vehicles=20,
        driver_avg_hybrid=1.4,
        resolved_anomalies=5,
        acked_anomalies=2,
        total_anomalies=10,
    )
    assert result.confidence == 1.0
    # FVI alt-skor weighted average olmalı
    expected = round(
        0.35 * result.fuel_score
        + 0.25 * result.maintenance_score
        + 0.25 * result.driver_score
        + 0.15 * result.anomaly_quality_score,
        1,
    )
    assert result.fvi == expected


def test_compute_fvi_partial_signals():
    """Sadece yakıt + bakım var → confidence=0.5."""
    from v2.modules.analytics_executive.domain.fleet_efficiency import compute_fvi

    result = compute_fvi(
        fuel_avg=30.0,
        fuel_target=32.0,
        overdue_maintenance=1,
        total_active_vehicles=10,
        driver_avg_hybrid=None,
        resolved_anomalies=0,
        acked_anomalies=0,
        total_anomalies=0,
    )
    assert result.confidence == 0.5


def test_compute_fvi_with_trend():
    from v2.modules.analytics_executive.domain.fleet_efficiency import compute_fvi

    result = compute_fvi(
        fuel_avg=30.0,
        fuel_target=32.0,
        overdue_maintenance=0,
        total_active_vehicles=10,
        driver_avg_hybrid=1.4,
        resolved_anomalies=5,
        acked_anomalies=2,
        total_anomalies=10,
        previous_fvi=70.0,
    )
    assert result.trend_30d == round(result.fvi - 70.0, 1)


def test_compute_fvi_reasons_all_present():
    """Her alt-skor için bir sebep döner — toplam 4."""
    from v2.modules.analytics_executive.domain.fleet_efficiency import compute_fvi

    result = compute_fvi(
        fuel_avg=30.0,
        fuel_target=32.0,
        overdue_maintenance=2,
        total_active_vehicles=20,
        driver_avg_hybrid=1.4,
        resolved_anomalies=5,
        acked_anomalies=2,
        total_anomalies=10,
    )
    assert len(result.reasons) == 4
    # Her sebep dolu olmalı
    assert all(r and len(r) > 5 for r in result.reasons)


def test_weights_sum_to_one():
    """Alt-skor ağırlıkları toplamı 1.0 olmalı."""
    from v2.modules.analytics_executive.domain.fleet_efficiency import SUBSCORE_WEIGHTS

    assert sum(SUBSCORE_WEIGHTS.values()) == pytest.approx(1.0, abs=1e-9)
