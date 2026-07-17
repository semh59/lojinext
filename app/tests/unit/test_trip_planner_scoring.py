"""Feature C.1 — Trip Planner saf yardımcı fonksiyonları (DB yok)."""

from __future__ import annotations

from datetime import date

import pytest


# ── _risk_label ─────────────────────────────────────────────────────────
@pytest.mark.parametrize(
    "impact, expected",
    [
        (1.0, "unknown"),
        (0.95, "low"),
        (0.85, "low"),
        (1.05, "medium"),
        (1.10, "medium"),
        (1.11, "high"),
        (1.30, "high"),
    ],
)
def test_risk_label_boundaries(impact, expected):
    from v2.modules.ai_assistant.domain.planner_scoring import _risk_label

    assert _risk_label(impact) == expected


# ── _availability_score ────────────────────────────────────────────────
@pytest.mark.parametrize(
    "trips, expected",
    [
        (0, 1.0),  # boşta → tam puan
        (1, 6 / 7),
        (3, 4 / 7),
        (7, 0.0),  # tam doluluk → 0
        (10, 0.0),  # clamp
        (-1, 1.0),  # negative → 0 trip kabul edilir
    ],
)
def test_availability_score_boundaries(trips, expected):
    from v2.modules.ai_assistant.domain.planner_scoring import _availability_score

    assert _availability_score(trips) == pytest.approx(expected, abs=1e-9)


# ── _vehicle_age_years ─────────────────────────────────────────────────
def test_vehicle_age_years_from_yil():
    from v2.modules.ai_assistant.domain.planner_scoring import _vehicle_age_years

    current = date.today().year
    assert _vehicle_age_years({"yil": current}) == 0
    assert _vehicle_age_years({"yil": current - 5}) == 5
    assert _vehicle_age_years({"yil": None}) == 0
    assert _vehicle_age_years({}) == 0
    assert _vehicle_age_years({"yil": 0}) == 0


# ── _vehicle_health_score ──────────────────────────────────────────────
def test_vehicle_health_score_age_only():
    from v2.modules.ai_assistant.domain.planner_scoring import _vehicle_health_score

    assert _vehicle_health_score(0, False) == 1.0
    assert _vehicle_health_score(25, False) == 0.0
    assert _vehicle_health_score(50, False) == 0.0  # clamp
    # 12.5 yaş ≈ 0.5
    assert _vehicle_health_score(12, False) == pytest.approx(0.52, abs=1e-2)


def test_vehicle_health_score_with_open_alert_halves():
    from v2.modules.ai_assistant.domain.planner_scoring import _vehicle_health_score

    base = _vehicle_health_score(5, False)
    with_alert = _vehicle_health_score(5, True)
    assert with_alert == pytest.approx(base * 0.5, abs=1e-3)


# ── _route_type_perf ───────────────────────────────────────────────────
def test_route_type_perf_low_trip_count_returns_neutral():
    from v2.modules.ai_assistant.domain.planner_scoring import _route_type_perf

    assert _route_type_perf(deviation_pct=10, trip_count=0) == 0.5
    assert _route_type_perf(deviation_pct=20, trip_count=4) == 0.5  # eşik altı


def test_route_type_perf_low_deviation_is_high():
    from v2.modules.ai_assistant.domain.planner_scoring import _route_type_perf

    # |dev|=0 → score 1.0
    assert _route_type_perf(0, 10) == 1.0
    # |dev|=15 → score = 1 - 15/30 = 0.5
    assert _route_type_perf(15, 10) == 0.5
    # |dev|=30 → score 0
    assert _route_type_perf(30, 10) == 0.0
    # |dev|>30 → clamp 0
    assert _route_type_perf(45, 10) == 0.0
    # Negatif sapma da abs alındığından aynı
    assert _route_type_perf(-15, 10) == 0.5


# ── _vehicle_reasons ───────────────────────────────────────────────────
def test_vehicle_reasons_top_score_includes_low_consumption():
    from v2.modules.ai_assistant.domain.planner_scoring import _vehicle_reasons

    reasons = _vehicle_reasons(
        fuel_score=0.98,
        similar_trip_count=4,
        age_years=2,
        has_open_alert=False,
        availability_score=0.95,
    )
    assert any("en düşük tahmini" in r for r in reasons)
    assert any("benzer sefer" in r for r in reasons)
    assert any("Yeni araç" in r for r in reasons)
    assert any("Müsait" in r for r in reasons)
    # Maks 5 madde
    assert len(reasons) <= 5


def test_vehicle_reasons_open_alert_and_old_age():
    from v2.modules.ai_assistant.domain.planner_scoring import _vehicle_reasons

    reasons = _vehicle_reasons(
        fuel_score=0.5,
        similar_trip_count=0,
        age_years=15,
        has_open_alert=True,
        availability_score=0.2,
    )
    assert any("Eski araç" in r for r in reasons)
    assert any("bakım kaydı" in r for r in reasons)
    assert any("yoğun kullanım" in r for r in reasons)


# ── _driver_reasons ────────────────────────────────────────────────────
def test_driver_reasons_cold_start_says_new_driver():
    from v2.modules.ai_assistant.domain.planner_scoring import _driver_reasons

    reasons = _driver_reasons(
        route_type="highway_dominant",
        deviation_pct=0,
        route_type_perf=0.5,
        overall_hybrid=0.5,
        availability_score=0.5,
        cold_start=True,
    )
    assert any("Yeni şoför" in r for r in reasons)


def test_driver_reasons_savings_message_when_negative_deviation():
    from v2.modules.ai_assistant.domain.planner_scoring import _driver_reasons

    reasons = _driver_reasons(
        route_type="highway_dominant",
        deviation_pct=-6.0,
        route_type_perf=0.9,
        overall_hybrid=0.85,
        availability_score=0.9,
        cold_start=False,
    )
    assert any("tasarruflu" in r for r in reasons)
    assert any("Yüksek hibrit" in r for r in reasons)


def test_driver_reasons_risk_high_deviation_warning():
    from v2.modules.ai_assistant.domain.planner_scoring import _driver_reasons

    reasons = _driver_reasons(
        route_type="mountain",
        deviation_pct=25.0,
        route_type_perf=0.2,
        overall_hybrid=0.35,
        availability_score=0.2,
        cold_start=False,
    )
    assert any("riskli" in r for r in reasons)
    assert any("Düşük hibrit" in r for r in reasons)
    assert any("yoğun kullanım" in r for r in reasons)
