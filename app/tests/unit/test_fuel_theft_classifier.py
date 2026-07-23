"""FuelTheftClassifier tests — real DB, no mocked UoW.

The only DB touch is _pattern_count (COUNT of recent anomalies for the same
kaynak). Previously a mocked UnitOfWork faked that count; here we seed real
`anomalies` rows so the classifier's repeat-offender pattern score is computed
against the real COUNT query. Pure-function and the DB-error fallback tests keep
their shape (the latter forces a UoW error — an otherwise-unreachable path).
"""

from __future__ import annotations

import re
from datetime import date
from typing import Any, Dict
from unittest.mock import patch

import pytest
from sqlalchemy import insert

from v2.modules.anomaly.application.classify_theft import FuelTheftClassifier
from v2.modules.anomaly.public import Anomaly
from v2.modules.anomaly.schemas import TheftClassification

pytestmark = pytest.mark.integration


async def _seed_anomalies(
    db_session, n: int, *, kaynak_id: int = 7, kaynak_tip: str = "sefer"
) -> None:
    """Seed n real recent anomalies for a kaynak so _pattern_count() returns n."""
    for _ in range(n):
        await db_session.execute(
            insert(Anomaly).values(
                tarih=date.today(),
                tip="tuketim",
                kaynak_tip=kaynak_tip,
                kaynak_id=kaynak_id,
                deger=1.0,
                beklenen_deger=1.0,
                sapma_yuzde=15.0,
                severity="medium",
                aciklama="seed",
            )
        )
    await db_session.commit()


def _anomaly(
    *,
    id: int = 1,
    tip: str = "tuketim",
    kaynak_id: int = 7,
    kaynak_tip: str = "sefer",
    sapma_yuzde: float | None = 15.0,
    severity: str = "medium",
) -> Dict[str, Any]:
    return {
        "id": id,
        "tip": tip,
        "kaynak_id": kaynak_id,
        "kaynak_tip": kaynak_tip,
        "sapma_yuzde": sapma_yuzde,
        "severity": severity,
    }


# ── Senaryolar ─────────────────────────────────────────────────────────────


@pytest.mark.unit
@pytest.mark.asyncio
async def test_low_sapma_low_severity_no_pattern_yields_low(db_session):
    """Düşük tüm bileşenler + 0 geçmiş anomali → low level."""
    result = await FuelTheftClassifier().classify(
        _anomaly(sapma_yuzde=5, severity="low")
    )
    assert isinstance(result, TheftClassification)
    assert result.suspicion_level == "low"
    assert result.suspicion_score < 0.4


@pytest.mark.unit
@pytest.mark.asyncio
async def test_high_sapma_critical_pattern_yields_high(db_session):
    """Yüksek sapma + critical + 5 gerçek geçmiş anomali → high level."""
    await _seed_anomalies(db_session, 5)
    result = await FuelTheftClassifier().classify(
        _anomaly(sapma_yuzde=40, severity="critical")
    )
    assert result.suspicion_level == "high"
    assert result.suspicion_score >= 0.7


@pytest.mark.unit
@pytest.mark.asyncio
async def test_sapma_clamped_to_one(db_session):
    """Sapma 80% → norm 1.0 (>50 clamp); pattern 0 → medium."""
    result = await FuelTheftClassifier().classify(
        _anomaly(sapma_yuzde=80, severity="low")
    )
    assert result.suspicion_level == "medium"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_unknown_severity_defaults_to_low_weight(db_session):
    """Bilinmeyen severity → 0.1 ağırlık → low."""
    result = await FuelTheftClassifier().classify(
        _anomaly(sapma_yuzde=5, severity="extreme")
    )
    assert result.suspicion_level == "low"


def test_pattern_to_score_thresholds():
    """≥3 → 1.0, 2 → 0.5, 0/1 → 0.0 (pure function, no DB)."""
    assert FuelTheftClassifier._pattern_to_score(3) == 1.0
    assert FuelTheftClassifier._pattern_to_score(5) == 1.0
    assert FuelTheftClassifier._pattern_to_score(2) == 0.5
    assert FuelTheftClassifier._pattern_to_score(1) == 0.0
    assert FuelTheftClassifier._pattern_to_score(0) == 0.0


@pytest.mark.unit
@pytest.mark.asyncio
async def test_classify_exception_falls_back_to_unknown():
    """UoW exception → unknown level + warning factor.

    A DB error mid-classify cannot be triggered with a healthy real DB, so this
    error-path is exercised by forcing the UnitOfWork to raise on enter."""

    class _CM:
        async def __aenter__(self):
            raise RuntimeError("DB error")

        async def __aexit__(self, *args):
            return False

    with patch(
        "v2.modules.anomaly.application.classify_theft.UnitOfWork",
        return_value=_CM(),
    ):
        engine = FuelTheftClassifier()
        result = await engine.classify(_anomaly())
    assert result.suspicion_level == "unknown"
    assert result.suspicion_score == 0.0
    assert any("başarısız" in f.lower() for f in result.factors)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_negative_sapma_uses_abs(db_session):
    """Lehte sapma (-25) → abs ile aynı kabul edilir."""
    result = await FuelTheftClassifier().classify(
        _anomaly(sapma_yuzde=-25, severity="low")
    )
    assert result.suspicion_level == "low"
    assert any("-25" in f or "+25" in f for f in result.factors) or any(
        "%" in f for f in result.factors
    )


@pytest.mark.unit
@pytest.mark.asyncio
async def test_sapma_none_zero_norm(db_session):
    """sapma_yuzde NULL → sapma_norm=0, factor'da görünmez."""
    result = await FuelTheftClassifier().classify(
        _anomaly(sapma_yuzde=None, severity="medium")
    )
    assert result.suspicion_level == "low"
    assert not any("Sapma" in f for f in result.factors)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_empty_kaynak_tip_skips_pattern_query(db_session):
    """kaynak_tip boş → erken-return, pattern_count=0 (seeded rows sayılmaz)."""
    # 5 gerçek anomali olsa bile boş kaynak_tip sorguyu atlamalı.
    await _seed_anomalies(db_session, 5)
    result = await FuelTheftClassifier().classify(
        _anomaly(kaynak_tip="", sapma_yuzde=5, severity="low")
    )
    assert result.suspicion_level == "low"
    assert result.suspicion_score < 0.2


@pytest.mark.unit
@pytest.mark.asyncio
async def test_explain_includes_pattern_when_count_high(db_session):
    """Pattern count ≥2 → açıklama listesinde sayı geçer."""
    await _seed_anomalies(db_session, 5)
    result = await FuelTheftClassifier().classify(_anomaly())
    assert any("5 anomali" in f for f in result.factors)


def test_suggest_action_per_level():
    """Her seviye için ayırt edici mesaj (pure function, no DB)."""
    h = FuelTheftClassifier._suggest_action("high")
    m = FuelTheftClassifier._suggest_action("medium")
    low = FuelTheftClassifier._suggest_action("low")
    u = FuelTheftClassifier._suggest_action("unknown")
    assert "Yüksek şüphe" in h
    assert "Orta şüphe" in m
    assert "Düşük şüphe" in low
    assert "başarısız" in u.lower()
    assert len({h, m, low, u}) == 4


@pytest.mark.unit
@pytest.mark.asyncio
async def test_factors_contain_no_pii(db_session):
    """Q1 PII politikası: classifier çıktısında plaka/isim YOK."""
    result = await FuelTheftClassifier().classify(
        {
            "id": 1,
            "tip": "tuketim",
            "kaynak_id": 7,
            "kaynak_tip": "sefer",
            "sapma_yuzde": 20,
            "severity": "medium",
            "plaka": "34 ABC 1234",
            "sofor_adi": "Ali Veli",
        }
    )
    factors_blob = " | ".join(result.factors)
    suggestion = result.suggested_action

    assert "Ali" not in factors_blob
    assert "Veli" not in factors_blob
    assert "Ali" not in suggestion
    assert "Veli" not in suggestion
    assert not re.search(r"\d{2}\s+[A-Z]{2,3}\s+\d{2,4}", factors_blob)
