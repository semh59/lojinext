"""Feature D.4 — vehicle_health_factor saf yardımcı testleri."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest


# ── _periyodik_age_factor ──────────────────────────────────────────────
@pytest.mark.parametrize(
    "days_ago, expected_factor",
    [
        (0, 0.96),  # bugün yapıldı → taze
        (30, 0.96),  # <90 → taze
        (89, 0.96),  # sınır
        (90, 0.96),  # tam sınır → still taze (<=90)
        (91, 1.00),  # bir sonraki tier
        (200, 1.00),  # normal
        (300, 1.00),  # sınır
        (301, 1.03),  # yaklaşıyor
        (365, 1.03),  # yıl sonu
        (366, 1.07),  # gecikti
        (450, 1.07),  # sınır
        (451, 1.12),  # ciddi gecikti
        (600, 1.12),  # sınır
        (601, 1.15),  # cap
        (1000, 1.15),  # cap
    ],
)
def test_periyodik_age_factor_tiers(days_ago, expected_factor):
    from v2.modules.prediction_ml.domain.vehicle_health_adjustment import (
        _periyodik_age_factor,
    )

    now = datetime(2026, 6, 1, tzinfo=timezone.utc)
    last = now - timedelta(days=days_ago)
    factor, reason = _periyodik_age_factor(last, now=now)
    assert factor == expected_factor
    assert str(days_ago) in reason or "kaydi" in reason.lower()


def test_periyodik_age_factor_none_returns_no_history():
    from v2.modules.prediction_ml.domain.vehicle_health_adjustment import (
        NO_HISTORY_FACTOR,
        _periyodik_age_factor,
    )

    factor, reason = _periyodik_age_factor(None)
    assert factor == NO_HISTORY_FACTOR
    assert "kaydi yok" in reason.lower()


def test_periyodik_age_factor_future_date_treated_as_fresh():
    """Clock skew / gelecek tarihli kayıt → fresh tier (negatif gün → 0)."""
    from v2.modules.prediction_ml.domain.vehicle_health_adjustment import (
        _periyodik_age_factor,
    )

    now = datetime(2026, 6, 1, tzinfo=timezone.utc)
    future_dt = now + timedelta(days=5)
    factor, reason = _periyodik_age_factor(future_dt, now=now)
    assert factor == 0.96  # fresh tier
    # Reason metninde 0 gun yansıtılmalı
    assert "0 gun" in reason


def test_periyodik_age_factor_naive_datetime_treated_as_utc():
    from v2.modules.prediction_ml.domain.vehicle_health_adjustment import (
        _periyodik_age_factor,
    )

    now = datetime(2026, 6, 1, tzinfo=timezone.utc)
    naive_last = datetime(2026, 5, 1)  # no tzinfo
    factor, _ = _periyodik_age_factor(naive_last, now=now)
    # ~31 gün geçti → fresh tier
    assert factor == 0.96


# ── compute_maintenance_factor ────────────────────────────────────────
def test_compute_no_history_no_open():
    from v2.modules.prediction_ml.domain.vehicle_health_adjustment import (
        NO_HISTORY_FACTOR,
        HealthInput,
        compute_maintenance_factor,
    )

    result = compute_maintenance_factor(HealthInput(last_periyodik_date=None))
    assert result.factor == NO_HISTORY_FACTOR
    assert result.arac_penalty == 1.0
    assert result.acil_penalty == 1.0


def test_compute_fresh_periyodik_with_open_acil():
    """Taze PERIYODIK (0.96) + açık ACIL (×1.10) → 0.96 × 1.10 = 1.056."""
    from v2.modules.prediction_ml.domain.vehicle_health_adjustment import (
        HealthInput,
        compute_maintenance_factor,
    )

    now = datetime(2026, 6, 1, tzinfo=timezone.utc)
    last = now - timedelta(days=10)
    result = compute_maintenance_factor(
        HealthInput(last_periyodik_date=last, open_acil_count=1),
        now=now,
    )
    assert result.acil_penalty == 1.10
    assert result.base_factor == 0.96
    assert result.factor == pytest.approx(0.96 * 1.10, abs=1e-3)


def test_compute_severely_overdue_with_ariza_and_acil_clamped():
    """600+ gün + ARIZA + ACIL → 1.15 × 1.05 × 1.10 = 1.328 → clamp 1.25."""
    from v2.modules.prediction_ml.domain.vehicle_health_adjustment import (
        FACTOR_CAP,
        HealthInput,
        compute_maintenance_factor,
    )

    now = datetime(2026, 6, 1, tzinfo=timezone.utc)
    last = now - timedelta(days=800)
    result = compute_maintenance_factor(
        HealthInput(
            last_periyodik_date=last,
            open_ariza_count=2,
            open_acil_count=1,
        ),
        now=now,
    )
    assert result.factor == FACTOR_CAP


def test_compute_factor_never_below_floor():
    """Floor = 0.95; tüm kombinasyonlarda altına düşmez."""
    from v2.modules.prediction_ml.domain.vehicle_health_adjustment import (
        FACTOR_FLOOR,
        HealthInput,
        compute_maintenance_factor,
    )

    now = datetime(2026, 6, 1, tzinfo=timezone.utc)
    # Taze PERIYODIK + 0 ARIZA/ACIL → 0.96, FLOOR'un üstünde
    result = compute_maintenance_factor(HealthInput(last_periyodik_date=now), now=now)
    assert result.factor >= FACTOR_FLOOR


def test_compute_reason_contains_days():
    from v2.modules.prediction_ml.domain.vehicle_health_adjustment import (
        HealthInput,
        compute_maintenance_factor,
    )

    now = datetime(2026, 6, 1, tzinfo=timezone.utc)
    last = now - timedelta(days=400)
    result = compute_maintenance_factor(HealthInput(last_periyodik_date=last), now=now)
    assert "400 gun" in result.reason
    assert "gecikti" in result.reason.lower()


# ── apply_maintenance_factor ───────────────────────────────────────────
def test_apply_factor_one_is_noop():
    from v2.modules.prediction_ml.domain.vehicle_health_adjustment import (
        apply_maintenance_factor,
    )

    payload = {"prediction_liters": 100.0, "faktorler": {}}
    out = apply_maintenance_factor(payload, 1.0, "reason")
    assert out["prediction_liters"] == 100.0
    assert "maintenance_factor" not in out["faktorler"]


def test_apply_factor_multiplies_all_primary_keys():
    from v2.modules.prediction_ml.domain.vehicle_health_adjustment import (
        apply_maintenance_factor,
    )

    payload = {
        "tahmini_tuketim": 30.0,
        "tahmini_litre": 100.0,
        "prediction_liters": 100.0,
        "faktorler": {},
    }
    out = apply_maintenance_factor(payload, 1.07, "PERIYODIK gecikti (400 gün)")
    assert out["tahmini_tuketim"] == pytest.approx(32.1, abs=0.01)
    assert out["tahmini_litre"] == 107.0
    assert out["prediction_liters"] == 107.0
    assert out["faktorler"]["maintenance_factor"] == 1.07
    assert "Bakım faktörü" in out["explanation_summary"]


def test_apply_factor_no_faktorler_creates_dict():
    """Payload'da faktorler dict'i yoksa eklenir."""
    from v2.modules.prediction_ml.domain.vehicle_health_adjustment import (
        apply_maintenance_factor,
    )

    payload = {"prediction_liters": 50.0}
    out = apply_maintenance_factor(payload, 1.10, "test")
    assert "faktorler" in out
    assert out["faktorler"]["maintenance_factor"] == 1.10


def test_apply_factor_explanation_not_duplicated():
    from v2.modules.prediction_ml.domain.vehicle_health_adjustment import (
        apply_maintenance_factor,
    )

    payload = {
        "prediction_liters": 100.0,
        "explanation_summary": "Bakım faktörü: 1.07 (var)",
    }
    out = apply_maintenance_factor(payload, 1.07, "yeniden")
    # Mevcut "Bakım faktörü" görüldü → tekrar eklenmemeli
    assert out["explanation_summary"].count("Bakım faktörü") == 1


def test_apply_factor_handles_missing_prediction_liters():
    """prediction_liters yoksa graceful no-op.

    apply_maintenance_factor yalnızca MEVCUT alanları çarpar (tahmini_tuketim,
    tahmini_litre, prediction_liters hepsi `if payload.get(...)` ile korunur).
    Eksik bir alanı 0.0 olarak UYDURMAK yanlış olur — "0 litre tahmin" gibi sahte
    bir veri üretirdi. Doğru davranış: yokken yok kalsın, faktör yine de yazılsın.
    """
    from v2.modules.prediction_ml.domain.vehicle_health_adjustment import (
        apply_maintenance_factor,
    )

    payload: dict = {"faktorler": {}}
    out = apply_maintenance_factor(payload, 1.10, "x")
    # Absent stays absent (no fabricated 0.0); maintenance_factor still recorded.
    assert "prediction_liters" not in out
    assert out["faktorler"]["maintenance_factor"] == 1.1
