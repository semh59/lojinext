"""Feature D.1 — MaintenancePredictor saf yardımcı ve scenario testleri."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest


# ── _consumption_trend_pct ──────────────────────────────────────────────
@pytest.mark.parametrize(
    "recent, previous, expected",
    [
        (None, 30, None),
        (30, None, None),
        (30, 0, None),
        (30, 30, 0.0),
        (33, 30, 10.0),
        (27, 30, -10.0),
        (30, 25, 20.0),
    ],
)
def test_consumption_trend_pct(recent, previous, expected):
    from app.core.ml.maintenance_predictor import _consumption_trend_pct

    assert _consumption_trend_pct(recent, previous) == expected


# ── _trend_correction_days ─────────────────────────────────────────────
@pytest.mark.parametrize(
    "trend_pct, expected_min, expected_max",
    [
        (None, 0, 0),  # veri yok → düzeltme yok
        (3.0, 0, 0),  # %5 altı → ihmal
        (5.0, -4, -3),  # eşikte, lineer 0.7 → -3 veya -4
        (10.0, -8, -6),  # ~%10 → -7
        (20.0, -15, -13),  # ~%20 → -14
        (50.0, -30, -30),  # cap
        (100.0, -30, -30),  # cap
        (-10.0, 0, 0),  # negatif → düzeltme yok (tüketim azaldı)
    ],
)
def test_trend_correction_days(trend_pct, expected_min, expected_max):
    from app.core.ml.maintenance_predictor import _trend_correction_days

    result = _trend_correction_days(trend_pct)
    assert expected_min <= result <= expected_max


# ── _risk_level ────────────────────────────────────────────────────────
@pytest.mark.parametrize(
    "days, expected",
    [
        (-30, "overdue"),
        (-1, "overdue"),
        (0, "soon"),
        (14, "soon"),
        (15, "normal"),
        (60, "normal"),
        (61, "low"),
        (365, "low"),
    ],
)
def test_risk_level_boundaries(days, expected):
    from app.core.ml.maintenance_predictor import _risk_level

    assert _risk_level(days) == expected


# ── _confidence ────────────────────────────────────────────────────────
def test_confidence_no_data():
    from app.core.ml.maintenance_predictor import _confidence

    assert (
        _confidence(
            has_periyodik_history=False,
            enough_usage=False,
            has_consumption_trend=False,
        )
        == 0.5
    )


def test_confidence_all_signals():
    from app.core.ml.maintenance_predictor import _confidence

    assert (
        _confidence(
            has_periyodik_history=True,
            enough_usage=True,
            has_consumption_trend=True,
        )
        == 1.0
    )


def test_confidence_partial():
    from app.core.ml.maintenance_predictor import _confidence

    # Sadece history → 0.5 + 0.2 = 0.7
    assert (
        _confidence(
            has_periyodik_history=True,
            enough_usage=False,
            has_consumption_trend=False,
        )
        == 0.7
    )


# ── _savings_pct ───────────────────────────────────────────────────────
def test_savings_pct_no_data():
    from app.core.ml.maintenance_predictor import _savings_pct

    assert _savings_pct(None, 30.0) == 0.0
    assert _savings_pct(35.0, None) == 0.0
    assert _savings_pct(None, None) == 0.0


def test_savings_pct_below_benchmark():
    from app.core.ml.maintenance_predictor import _savings_pct

    # Filo medyandan düşükse tasarruf yok
    assert _savings_pct(28.0, 30.0) == 0.0
    assert _savings_pct(30.0, 30.0) == 0.0


def test_savings_pct_above_benchmark():
    from app.core.ml.maintenance_predictor import _savings_pct

    # 33 vs 30 → (33-30)/33 * 100 ≈ 9.1
    assert _savings_pct(33.0, 30.0) == pytest.approx(9.1, abs=0.1)


def test_savings_pct_capped_at_20():
    from app.core.ml.maintenance_predictor import _savings_pct

    # Aşırı yüksek tüketim cap'lenmeli
    assert _savings_pct(100.0, 10.0) == 20.0


# ── _predict_for_vehicle scenarios ─────────────────────────────────────
def _build_engine():
    from app.core.ml.maintenance_predictor import MaintenancePredictor

    return MaintenancePredictor()


def _build_input(**overrides):
    from app.core.ml.maintenance_predictor import PredictionInput

    base = {
        "arac_id": 1,
        "plaka": "34 ABC 123",
        "yil": 2020,
        "last_periyodik_date": None,
        "last_periyodik_km": None,
        "km_per_month": 0.0,
        "consumption_recent": None,
        "consumption_previous": None,
        "filo_consumption_median": None,
    }
    base.update(overrides)
    return PredictionInput(**base)


def test_predict_no_data_not_predictable():
    """Bakım geçmişi yok + kullanım yok → predictable=False."""
    engine = _build_engine()
    pred = engine._predict_for_vehicle(_build_input())
    assert pred.predictable is False
    assert pred.predicted_date is None
    assert any("Yeterli veri yok" in r for r in pred.reasons)


def test_predict_fresh_periyodik_low_risk():
    """7 gün önce PERIYODIK + normal kullanım → low risk, 350+ gün kaldı."""
    engine = _build_engine()
    pred = engine._predict_for_vehicle(
        _build_input(
            last_periyodik_date=datetime.now(timezone.utc) - timedelta(days=7),
            last_periyodik_km=200_000,
            km_per_month=2_000,  # normal kullanım
        )
    )
    assert pred.predictable is True
    assert pred.days_remaining is not None
    assert pred.days_remaining > 300
    assert pred.risk_level == "low"
    assert pred.is_overdue is False
    assert pred.confidence >= 0.7  # history + usage


def test_predict_overdue_periyodik():
    """400 gün önce PERIYODIK + düşük kullanım → overdue + negative days."""
    engine = _build_engine()
    pred = engine._predict_for_vehicle(
        _build_input(
            last_periyodik_date=datetime.now(timezone.utc) - timedelta(days=400),
            last_periyodik_km=200_000,
            km_per_month=500,  # az kullanım → süre bazında düşer
        )
    )
    assert pred.predictable is True
    assert pred.is_overdue is True
    assert pred.days_remaining is not None
    assert pred.days_remaining < 0
    assert pred.risk_level == "overdue"
    assert any("GECİKMİŞ" in r for r in pred.reasons)


def test_predict_trend_correction_brings_earlier():
    """Tüketim artmış → bakım önerisi erkene çekilmeli."""
    engine = _build_engine()
    base_input = _build_input(
        last_periyodik_date=datetime.now(timezone.utc) - timedelta(days=200),
        last_periyodik_km=200_000,
        km_per_month=2_000,
    )
    no_trend_input = _build_input(
        **{
            **base_input.__dict__,
            "consumption_recent": 30.0,
            "consumption_previous": 30.0,
        }
    )
    rising_trend_input = _build_input(
        **{
            **base_input.__dict__,
            "consumption_recent": 36.0,
            "consumption_previous": 30.0,
        }  # %20 artış
    )
    pred_no = engine._predict_for_vehicle(no_trend_input)
    pred_rise = engine._predict_for_vehicle(rising_trend_input)
    assert pred_rise.days_remaining < pred_no.days_remaining
    assert any("Tüketim trendi" in r for r in pred_rise.reasons)


def test_predict_uses_min_of_time_and_km():
    """Mesafe interval'i süreden daha erken doluyorsa → o seçilir."""
    engine = _build_engine()
    # 100 gün önce bakım + 5000 km/ay = 17000 km elapsed → kalan 8000 km
    # 8000 / (5000/30) ≈ 48 gün → süreden (265 gün) ÇOK daha erken
    pred = engine._predict_for_vehicle(
        _build_input(
            last_periyodik_date=datetime.now(timezone.utc) - timedelta(days=100),
            last_periyodik_km=200_000,
            km_per_month=5_000,
        )
    )
    assert pred.predictable is True
    assert pred.days_remaining is not None
    # km-bazında 50 gün civarı bekleniyor
    assert pred.days_remaining < 100
    assert any("km kaldı" in r for r in pred.reasons)


def test_predict_high_consumption_yields_savings_projection():
    """Aracın tüketimi filo medyandan yüksekse → savings_pct > 0."""
    engine = _build_engine()
    pred = engine._predict_for_vehicle(
        _build_input(
            last_periyodik_date=datetime.now(timezone.utc) - timedelta(days=200),
            last_periyodik_km=200_000,
            km_per_month=2_000,
            consumption_recent=36.0,
            consumption_previous=35.0,
            filo_consumption_median=30.0,
        )
    )
    assert pred.savings_pct > 0
    assert any("tasarruf" in r for r in pred.reasons)
