"""Feature B.1 — Yakıt Hırsızlığı Şüphe Sınıflandırıcısı.

Saf kural-bazlı (LLM YOK). Skor bileşenleri:
  1. Sapma yüzdesi normalize (abs(sapma)/50 clamp 0..1) — ağırlık 0.5
  2. Severity weight (low=0.1, medium=0.4, high=0.7, critical=1.0) — 0.3
  3. Pattern score (aynı kaynak_id+kaynak_tip son 30g anomali sayısı) — 0.2

Eşikler:
  >= 0.7 → high   → auto-investigation create + Telegram OPS alarm
  >= 0.4 → medium → manuel inceleme tavsiyesi
  <  0.4 → low    → rutin loglama
"""

from __future__ import annotations

import logging
import threading
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import text

from app.database.unit_of_work import UnitOfWork
from app.schemas.investigation import (
    SuspicionLevel,
    TheftClassification,
)

logger = logging.getLogger(__name__)


SEVERITY_WEIGHT: Dict[str, float] = {
    "low": 0.1,
    "medium": 0.4,
    "high": 0.7,
    "critical": 1.0,
}

# Score ağırlıkları — toplamları 1.0
WEIGHT_SAPMA: float = 0.5
WEIGHT_SEVERITY: float = 0.3
WEIGHT_PATTERN: float = 0.2

PATTERN_LOOKBACK_DAYS: int = 30

# count ≥ threshold → score (ilk eşleşme alınır)
PATTERN_THRESHOLDS: List[tuple] = [
    (3, 1.0),
    (2, 0.5),
    (1, 0.0),
]


@dataclass
class _ScoreBreakdown:
    sapma_norm: float
    severity_w: float
    pattern_score: float
    pattern_count: int


class FuelTheftClassifier:
    """Stateless — `get_fuel_theft_classifier()` singleton kullan."""

    async def classify(self, anomaly: Dict[str, Any]) -> TheftClassification:
        """Tek anomali için suspicion classify. Exception fırlatmaz."""
        try:
            breakdown = await self._compute_breakdown(anomaly)
            suspicion = (
                WEIGHT_SAPMA * breakdown.sapma_norm
                + WEIGHT_SEVERITY * breakdown.severity_w
                + WEIGHT_PATTERN * breakdown.pattern_score
            )
            suspicion = max(0.0, min(1.0, suspicion))
            level = self._to_level(suspicion)
            factors = self._explain(anomaly, breakdown)
            action = self._suggest_action(level)

            return TheftClassification(
                anomaly_id=int(anomaly.get("id") or 0),
                suspicion_score=round(suspicion, 3),
                suspicion_level=level,
                factors=factors,
                suggested_action=action,
            )
        except Exception as exc:
            logger.warning(
                "Theft classify failed for anomaly %s: %s",
                anomaly.get("id"),
                exc,
            )
            return TheftClassification(
                anomaly_id=int(anomaly.get("id") or 0),
                suspicion_score=0.0,
                suspicion_level="unknown",
                factors=["Sınıflandırma başarısız (rule engine hatası)"],
                suggested_action="Manuel inceleme önerilir.",
            )

    async def classify_batch(
        self, anomalies: List[Dict[str, Any]]
    ) -> List[TheftClassification]:
        """Çoklu anomali. Sıralı (MVP, küçük N için yeterli)."""
        results: List[TheftClassification] = []
        for a in anomalies:
            results.append(await self.classify(a))
        return results

    # ── İç hesap ──────────────────────────────────────────────────────────

    async def _compute_breakdown(self, anomaly: Dict[str, Any]) -> _ScoreBreakdown:
        sapma_raw = anomaly.get("sapma_yuzde")
        sapma_norm = (
            min(1.0, abs(float(sapma_raw)) / 50.0) if sapma_raw is not None else 0.0
        )
        severity = str(anomaly.get("severity") or "low")
        severity_w = SEVERITY_WEIGHT.get(severity, 0.1)
        pattern_count = await self._pattern_count(
            int(anomaly.get("kaynak_id") or 0),
            str(anomaly.get("kaynak_tip") or ""),
        )
        pattern_score = self._pattern_to_score(pattern_count)
        return _ScoreBreakdown(
            sapma_norm=sapma_norm,
            severity_w=severity_w,
            pattern_score=pattern_score,
            pattern_count=pattern_count,
        )

    async def _pattern_count(self, kaynak_id: int, kaynak_tip: str) -> int:
        """Son 30 gün aynı (kaynak_id, kaynak_tip) için anomali sayısı.

        kaynak_id=0 veya kaynak_tip='' ise 0 (sınıflandırma anlamsız).
        """
        if not kaynak_id or not kaynak_tip:
            return 0
        cutoff = datetime.now(timezone.utc) - timedelta(days=PATTERN_LOOKBACK_DAYS)
        sql = text(
            """
            SELECT COUNT(*) FROM anomalies
            WHERE kaynak_id = :kid AND kaynak_tip = :ktip
              AND created_at >= :cutoff
            """
        )
        async with UnitOfWork() as uow:
            result = await uow.session.execute(
                sql, {"kid": kaynak_id, "ktip": kaynak_tip, "cutoff": cutoff}
            )
            return int(result.scalar() or 0)

    @staticmethod
    def _pattern_to_score(count: int) -> float:
        for threshold, score in PATTERN_THRESHOLDS:
            if count >= threshold:
                return score
        return 0.0

    @staticmethod
    def _to_level(score: float) -> SuspicionLevel:
        if score >= 0.7:
            return "high"
        if score >= 0.4:
            return "medium"
        return "low"

    @staticmethod
    def _explain(anomaly: Dict[str, Any], breakdown: _ScoreBreakdown) -> List[str]:
        """Açıklamada SADECE sayısal/kategorik özet — plaka/isim YOK."""
        factors: List[str] = []
        sapma = anomaly.get("sapma_yuzde")
        if sapma is not None:
            factors.append(
                f"Sapma %{float(sapma):+.1f} (norm {breakdown.sapma_norm:.2f})"
            )
        severity = anomaly.get("severity")
        if severity:
            factors.append(f"Severity={severity} (ağırlık {breakdown.severity_w:.2f})")
        if breakdown.pattern_count >= 2:
            factors.append(
                f"Tekrarlayan örüntü: son {PATTERN_LOOKBACK_DAYS} günde "
                f"aynı kaynak için {breakdown.pattern_count} anomali"
            )
        elif breakdown.pattern_count == 1:
            factors.append("Tekil anomali (tekrar yok)")
        return factors

    @staticmethod
    def _suggest_action(level: SuspicionLevel) -> str:
        if level == "high":
            return (
                "Yüksek şüphe: sefer/yakıt kayıtlarını incele, GPS güzergahını "
                "kontrol et, şoför ile yüz yüze görüş."
            )
        if level == "medium":
            return (
                "Orta şüphe: yakıt fişi + km sayaç tutarlılığını doğrula; "
                "tekrar görülürse soruşturma aç."
            )
        if level == "unknown":
            return "Sınıflandırma başarısız — manuel inceleme önerilir."
        return "Düşük şüphe: rutin loglama yeterli; ek aksiyon gerekmiyor."


_classifier_singleton: Optional[FuelTheftClassifier] = None
_classifier_lock = threading.Lock()


def get_fuel_theft_classifier() -> FuelTheftClassifier:
    """Thread-safe singleton accessor (double-checked locking)."""
    global _classifier_singleton
    if _classifier_singleton is None:
        with _classifier_lock:
            if _classifier_singleton is None:
                _classifier_singleton = FuelTheftClassifier()
    return _classifier_singleton
