"""Feature B.1 — FuelTheftClassifier unit testleri.

Engine'in fonksiyonel davranışı + PII regex doğrulaması.
"""

from __future__ import annotations

import re
from typing import Any, Dict
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.ai.fuel_theft_classifier import (
    FuelTheftClassifier,
)
from app.schemas.investigation import TheftClassification


def _mock_uow_with_count(count: int):
    """UnitOfWork patch'ini count döndürecek şekilde kur."""

    class _Result:
        def scalar(self):
            return count

    fake_session = MagicMock()
    fake_session.execute = AsyncMock(return_value=_Result())

    fake_uow = MagicMock()
    fake_uow.session = fake_session

    class _CM:
        async def __aenter__(self):
            return fake_uow

        async def __aexit__(self, exc_type, exc, tb):
            return False

    return patch(
        "app.core.ai.fuel_theft_classifier.UnitOfWork",
        return_value=_CM(),
    )


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
async def test_low_sapma_low_severity_no_pattern_yields_low():
    """Düşük tüm bileşenler → low level."""
    with _mock_uow_with_count(0):
        engine = FuelTheftClassifier()
        result = await engine.classify(_anomaly(sapma_yuzde=5, severity="low"))
    assert isinstance(result, TheftClassification)
    assert result.suspicion_level == "low"
    # 0.5*0.1 + 0.3*0.1 + 0.2*0 = 0.08
    assert result.suspicion_score < 0.4


@pytest.mark.unit
@pytest.mark.asyncio
async def test_high_sapma_critical_pattern_yields_high():
    """Yüksek tüm bileşenler → high level."""
    with _mock_uow_with_count(5):
        engine = FuelTheftClassifier()
        result = await engine.classify(_anomaly(sapma_yuzde=40, severity="critical"))
    # 0.5*0.8 + 0.3*1.0 + 0.2*1.0 = 0.9
    assert result.suspicion_level == "high"
    assert result.suspicion_score >= 0.7


@pytest.mark.unit
@pytest.mark.asyncio
async def test_sapma_clamped_to_one():
    """Sapma 80% → norm 1.0 (>50 clamp)."""
    with _mock_uow_with_count(0):
        engine = FuelTheftClassifier()
        result = await engine.classify(_anomaly(sapma_yuzde=80, severity="low"))
    # 0.5*1.0 + 0.3*0.1 + 0 = 0.53 → medium
    assert result.suspicion_level == "medium"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_unknown_severity_defaults_to_low_weight():
    """Bilinmeyen severity → 0.1 ağırlık."""
    with _mock_uow_with_count(0):
        engine = FuelTheftClassifier()
        result = await engine.classify(_anomaly(sapma_yuzde=5, severity="extreme"))
    assert result.suspicion_level == "low"
    # severity weight 0.1 olduğu için low kalmalı


def test_pattern_to_score_thresholds():
    """≥3 → 1.0, 2 → 0.5, 0/1 → 0.0."""
    assert FuelTheftClassifier._pattern_to_score(3) == 1.0
    assert FuelTheftClassifier._pattern_to_score(5) == 1.0
    assert FuelTheftClassifier._pattern_to_score(2) == 0.5
    assert FuelTheftClassifier._pattern_to_score(1) == 0.0
    assert FuelTheftClassifier._pattern_to_score(0) == 0.0


@pytest.mark.unit
@pytest.mark.asyncio
async def test_classify_exception_falls_back_to_unknown():
    """UoW exception → unknown level + warning log."""

    class _CM:
        async def __aenter__(self):
            raise RuntimeError("DB error")

        async def __aexit__(self, *args):
            return False

    with patch(
        "app.core.ai.fuel_theft_classifier.UnitOfWork",
        return_value=_CM(),
    ):
        engine = FuelTheftClassifier()
        result = await engine.classify(_anomaly())
    assert result.suspicion_level == "unknown"
    assert result.suspicion_score == 0.0
    assert any("başarısız" in f.lower() for f in result.factors)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_negative_sapma_uses_abs():
    """Lehte sapma (-25) → abs ile aynı kabul edilir."""
    with _mock_uow_with_count(0):
        engine = FuelTheftClassifier()
        result = await engine.classify(_anomaly(sapma_yuzde=-25, severity="low"))
    # |sapma|/50 = 0.5 → score = 0.5*0.5 + 0.3*0.1 + 0 = 0.28 → low
    assert result.suspicion_level == "low"
    # Factors -25.0 değerini göstermeli
    assert any("-25" in f or "+25" in f for f in result.factors) or any(
        "%" in f for f in result.factors
    )


@pytest.mark.unit
@pytest.mark.asyncio
async def test_sapma_none_zero_norm():
    """sapma_yuzde NULL → sapma_norm=0, factor'da görünmez."""
    with _mock_uow_with_count(0):
        engine = FuelTheftClassifier()
        result = await engine.classify(_anomaly(sapma_yuzde=None, severity="medium"))
    # 0.5*0 + 0.3*0.4 + 0 = 0.12 → low
    assert result.suspicion_level == "low"
    # Sapma factor'ı bulunmamalı (None geçti)
    assert not any("Sapma" in f for f in result.factors)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_empty_kaynak_tip_skips_pattern_query():
    """kaynak_tip boş → pattern_count=0, DB sorgu YOK."""
    # Mock UoW execute ediliyor olsaydı ama erken-return ile gelmemeli
    with _mock_uow_with_count(99):  # high count ama kullanılmamalı
        engine = FuelTheftClassifier()
        result = await engine.classify(
            _anomaly(kaynak_tip="", sapma_yuzde=5, severity="low")
        )
    # Pattern score 0 olmalı (kaynak_tip boş erken-return)
    assert result.suspicion_level == "low"
    # 0.5*0.1 + 0.3*0.1 + 0 = 0.08
    assert result.suspicion_score < 0.2


@pytest.mark.unit
@pytest.mark.asyncio
async def test_explain_includes_pattern_when_count_high():
    """Pattern count ≥2 → açıklama listesinde sayı geçer."""
    with _mock_uow_with_count(5):
        engine = FuelTheftClassifier()
        result = await engine.classify(_anomaly())
    assert any("5 anomali" in f for f in result.factors)


def test_suggest_action_per_level():
    """Her seviye için ayırt edici mesaj."""
    h = FuelTheftClassifier._suggest_action("high")
    m = FuelTheftClassifier._suggest_action("medium")
    low = FuelTheftClassifier._suggest_action("low")
    u = FuelTheftClassifier._suggest_action("unknown")
    assert "Yüksek şüphe" in h
    assert "Orta şüphe" in m
    assert "Düşük şüphe" in low
    assert "başarısız" in u.lower()
    # Hepsi farklı
    assert len({h, m, low, u}) == 4


@pytest.mark.unit
@pytest.mark.asyncio
async def test_factors_contain_no_pii():
    """Q1 PII politikası: classifier çıktısında plaka/isim YOK.

    Anomaly metadata'sına eklenmiş plaka/sofor_adi field'ları classify
    sonucu factors listesine HİÇ kopyalanmaz.
    """
    with _mock_uow_with_count(0):
        engine = FuelTheftClassifier()
        result = await engine.classify(
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

    # İsim/plaka yok
    assert "Ali" not in factors_blob
    assert "Veli" not in factors_blob
    assert "Ali" not in suggestion
    assert "Veli" not in suggestion
    assert not re.search(r"\d{2}\s+[A-Z]{2,3}\s+\d{2,4}", factors_blob)
    assert not re.search(r"\d{2}\s+[A-Z]{2,3}\s+\d{2,4}", suggestion)
