"""Feature D — Tahmine Dayalı Bakım motoru.

Hibrit: kural-tabanlı interval + aracın gerçek kullanım hızı + tüketim
trendi düzeltmesi. ML modeli eğitilmez; her istekte hesaplanır.

Plan kaynağı: docs/superpowers/plans/2026-05-26-feature-d-predictive-maintenance-v3.md

Fleet-içi kalır (prediction_ml'e taşınmadı) — bakım-tahmini fleet'in kendi
iş kuralı; vehicle_health_factor'dan farklı olarak trip/fuel prediction
pipeline'ına post-process olarak eklenmiyor (bkz. TASKS/modules/fleet.md §5.3).
"""

from __future__ import annotations

import logging
import statistics
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# ── Sabitler ────────────────────────────────────────────────────────────
INTERVAL_MONTHS: Dict[str, int] = {"PERIYODIK": 12}  # ARIZA/ACIL tahmin edilmez
INTERVAL_KM: Dict[str, int] = {"PERIYODIK": 25_000}
CONSUMPTION_LOOKBACK_DAYS = 90
USAGE_LOOKBACK_DAYS = 180
MIN_TRIPS_FOR_USAGE = 5
MAX_TREND_CORRECTION_DAYS = 30
FILO_MIN_TRIPS_FOR_BENCHMARK = 20
SAVINGS_CAP_PCT = 20.0


# ── Veri sınıfları ──────────────────────────────────────────────────────
@dataclass
class PredictionInput:
    """Engine'in tek araç için ihtiyaç duyduğu pre-aggregated veri."""

    arac_id: int
    plaka: str
    yil: Optional[int]
    last_periyodik_date: Optional[datetime]
    last_periyodik_km: Optional[int]
    km_per_month: float
    consumption_recent: Optional[float]  # son 90 gün avg
    consumption_previous: Optional[float]  # önceki 90 gün avg
    filo_consumption_median: Optional[float]


@dataclass
class Prediction:
    arac_id: int
    plaka: str
    bakim_tipi: str
    predictable: bool
    predicted_date: Optional[date] = None
    days_remaining: Optional[int] = None
    is_overdue: bool = False
    confidence: float = 0.0
    risk_level: str = "low"  # overdue|soon|normal|low
    savings_pct: float = 0.0
    reasons: List[str] = field(default_factory=list)


# ── Saf yardımcılar (test edilebilir) ───────────────────────────────────
def _consumption_trend_pct(
    recent: Optional[float], previous: Optional[float]
) -> Optional[float]:
    """Son 90g vs önceki 90g tüketim değişim yüzdesi."""
    if recent is None or previous is None or previous == 0:
        return None
    return round((recent - previous) / previous * 100.0, 1)


def _trend_correction_days(trend_pct: Optional[float]) -> int:
    """Tüketim artışı (% pozitif) → bakım tarihini erkene al.

    %5 altı düzeltme yok; lineer 0.7 katsayı; cap MAX_TREND_CORRECTION_DAYS.
    """
    if trend_pct is None or trend_pct < 5.0:
        return 0
    correction = -int(round(trend_pct * 0.7))
    return max(correction, -MAX_TREND_CORRECTION_DAYS)


def _risk_level(days_remaining: int) -> str:
    """Kalan güne göre risk etiketi."""
    if days_remaining < 0:
        return "overdue"
    if days_remaining <= 14:
        return "soon"
    if days_remaining <= 60:
        return "normal"
    return "low"


def _confidence(
    *,
    has_periyodik_history: bool,
    enough_usage: bool,
    has_consumption_trend: bool,
) -> float:
    """0..1 güven skoru."""
    score = 0.5
    if has_periyodik_history:
        score += 0.2
    if enough_usage:
        score += 0.2
    if has_consumption_trend:
        score += 0.1
    return round(min(1.0, max(0.0, score)), 2)


def _savings_pct(arac_avg: Optional[float], filo_median: Optional[float]) -> float:
    """Aracın tüketimi filo medyanından yüksekse tasarruf projeksiyonu.

    Cap SAVINGS_CAP_PCT (%20) — tek bakım daha fazlasını gerçekleştirmez.
    """
    if not arac_avg or not filo_median or arac_avg <= filo_median:
        return 0.0
    pct = (arac_avg - filo_median) / arac_avg * 100.0
    return round(min(pct, SAVINGS_CAP_PCT), 1)


# ── Engine ──────────────────────────────────────────────────────────────
class MaintenancePredictor:
    """Stateless engine — HTTP layer her istekte oluşturur."""

    async def predict_all(self) -> List[Prediction]:
        """Tüm aktif araçlar için PERIYODIK bakım tahmini döndürür."""
        from v2.modules.shared_kernel.infrastructure.unit_of_work import UnitOfWork

        async with UnitOfWork() as uow:
            inputs = await self._gather_inputs(uow)
        return [self._predict_for_vehicle(inp) for inp in inputs]

    async def predict_for_arac(self, arac_id: int) -> Optional[Prediction]:
        """Tek araç için tahmin; araç yoksa None."""
        from v2.modules.shared_kernel.infrastructure.unit_of_work import UnitOfWork

        async with UnitOfWork() as uow:
            inputs = await self._gather_inputs(uow, arac_id=arac_id)
        if not inputs:
            return None
        return self._predict_for_vehicle(inputs[0])

    async def _gather_inputs(
        self, uow, arac_id: Optional[int] = None
    ) -> List[PredictionInput]:
        """Tek SQL ile araç + son PERIYODIK + 180g km + 90g/önceki tüketim."""
        from sqlalchemy import text

        sql = """
            WITH last_bak AS (
                SELECT DISTINCT ON (b.arac_id)
                    b.arac_id, b.bakim_tarihi, b.km_bilgisi
                FROM arac_bakimlari b
                WHERE b.bakim_tipi = 'PERIYODIK' AND b.tamamlandi = TRUE
                ORDER BY b.arac_id, b.bakim_tarihi DESC
            ),
            usage_recent AS (
                SELECT s.arac_id, COALESCE(SUM(s.mesafe_km), 0) AS km_180d
                FROM seferler s
                WHERE s.is_deleted = FALSE
                  AND s.tarih >= CURRENT_DATE - INTERVAL '180 days'
                GROUP BY s.arac_id
            ),
            consum_recent AS (
                SELECT s.arac_id, AVG(s.tuketim) AS avg_t
                FROM seferler s
                WHERE s.is_deleted = FALSE AND s.tuketim IS NOT NULL
                  AND s.tarih >= CURRENT_DATE - INTERVAL '90 days'
                GROUP BY s.arac_id
            ),
            consum_previous AS (
                SELECT s.arac_id, AVG(s.tuketim) AS avg_t
                FROM seferler s
                WHERE s.is_deleted = FALSE AND s.tuketim IS NOT NULL
                  AND s.tarih BETWEEN
                        CURRENT_DATE - INTERVAL '180 days'
                    AND CURRENT_DATE - INTERVAL '90 days'
                GROUP BY s.arac_id
            )
            SELECT
                a.id, a.plaka, a.yil,
                lb.bakim_tarihi   AS last_periyodik_date,
                lb.km_bilgisi     AS last_periyodik_km,
                COALESCE(ur.km_180d, 0) AS km_180d,
                cr.avg_t          AS consum_recent,
                cp.avg_t          AS consum_previous
            FROM araclar a
            LEFT JOIN last_bak       lb ON lb.arac_id = a.id
            LEFT JOIN usage_recent   ur ON ur.arac_id = a.id
            LEFT JOIN consum_recent  cr ON cr.arac_id = a.id
            LEFT JOIN consum_previous cp ON cp.arac_id = a.id
            WHERE a.aktif = TRUE AND a.is_deleted = FALSE
                  {arac_filter}
            ORDER BY a.id
        """
        params: Dict[str, Any] = {}
        if arac_id is not None:
            sql = sql.format(arac_filter="AND a.id = :arac_id")
            params["arac_id"] = arac_id
        else:
            sql = sql.format(arac_filter="")
        rows = (await uow.session.execute(text(sql), params)).mappings().all()

        # Filo medyanı (ayrı sorgu) — yeterli sefer varsa hesapla
        filo_median: Optional[float] = None
        filo_rows = (
            await uow.session.execute(
                text(
                    "SELECT tuketim FROM seferler WHERE is_deleted = FALSE "
                    "AND tuketim IS NOT NULL "
                    "AND tarih >= CURRENT_DATE - INTERVAL '90 days'"
                )
            )
        ).all()
        if len(filo_rows) >= FILO_MIN_TRIPS_FOR_BENCHMARK:
            try:
                filo_median = float(statistics.median(r[0] for r in filo_rows))
            except statistics.StatisticsError:  # pragma: no cover
                filo_median = None

        out: List[PredictionInput] = []
        for r in rows:
            km_per_month = float(r["km_180d"]) / 6.0
            out.append(
                PredictionInput(
                    arac_id=int(r["id"]),
                    plaka=str(r["plaka"]),
                    yil=int(r["yil"]) if r["yil"] else None,
                    last_periyodik_date=r["last_periyodik_date"],
                    last_periyodik_km=(
                        int(r["last_periyodik_km"])
                        if r["last_periyodik_km"] is not None
                        else None
                    ),
                    km_per_month=km_per_month,
                    consumption_recent=(
                        float(r["consum_recent"])
                        if r["consum_recent"] is not None
                        else None
                    ),
                    consumption_previous=(
                        float(r["consum_previous"])
                        if r["consum_previous"] is not None
                        else None
                    ),
                    filo_consumption_median=filo_median,
                )
            )
        return out

    def _predict_for_vehicle(self, inp: PredictionInput) -> Prediction:
        """Saf hesaplama — inputs verili, DB'ye dokunmaz."""
        pred = Prediction(
            arac_id=inp.arac_id,
            plaka=inp.plaka,
            bakim_tipi="PERIYODIK",
            predictable=False,
        )

        # 1. Ortak referans: gerçek son PERIYODIK var mı?
        days_since: Optional[int] = None
        if inp.last_periyodik_date is not None:
            last_dt = inp.last_periyodik_date
            if last_dt.tzinfo is None:
                last_dt = last_dt.replace(tzinfo=timezone.utc)
            days_since = (datetime.now(timezone.utc) - last_dt).days

        # 2. Süreye göre kalan gün
        days_by_time: Optional[int] = (
            365 - days_since if days_since is not None else None
        )

        # 3. Mesafeye göre kalan gün — last_periyodik_km + km_per_month + days_since gerekli
        days_by_km: Optional[int] = None
        if (
            inp.last_periyodik_km is not None
            and inp.km_per_month > 0
            and days_since is not None
        ):
            km_per_day = inp.km_per_month / 30.0
            elapsed_km = km_per_day * days_since
            remaining_km = INTERVAL_KM["PERIYODIK"] - elapsed_km
            days_by_km = int(remaining_km / km_per_day) if km_per_day > 0 else None

        # 4. Hangisi daha erken? İkisi de None ise predictable=False
        candidates = [d for d in (days_by_time, days_by_km) if d is not None]
        if not candidates:
            pred.reasons.append("Yeterli veri yok (bakım geçmişi veya kullanım eksik)")
            return pred

        days_remaining = min(candidates)

        # 5. Tüketim trendi düzeltmesi
        trend_pct = _consumption_trend_pct(
            inp.consumption_recent, inp.consumption_previous
        )
        correction = _trend_correction_days(trend_pct)
        days_remaining += correction

        # 6. Sonuç doldur
        pred.predictable = True
        pred.days_remaining = days_remaining
        pred.predicted_date = (
            datetime.now(timezone.utc) + timedelta(days=days_remaining)
        ).date()
        pred.is_overdue = days_remaining < 0
        pred.risk_level = _risk_level(days_remaining)
        pred.confidence = _confidence(
            has_periyodik_history=inp.last_periyodik_date is not None,
            enough_usage=inp.km_per_month >= 100.0,
            has_consumption_trend=trend_pct is not None,
        )
        pred.savings_pct = _savings_pct(
            inp.consumption_recent, inp.filo_consumption_median
        )

        # 7. Reasons
        if days_by_time is not None and days_by_time == min(candidates):
            pred.reasons.append(
                f"Son PERIYODIK bakımdan {365 - days_by_time} gün geçti"
            )
        if days_by_km is not None and days_by_km == min(candidates):
            km_per_day = inp.km_per_month / 30.0
            elapsed_km = int(km_per_day * (days_since or 0))
            remaining_km = INTERVAL_KM["PERIYODIK"] - elapsed_km
            pred.reasons.append(
                f"Tahmini {max(0, remaining_km):,} km kaldı (PERIYODIK 25.000 km)"
            )
        if correction < 0 and trend_pct is not None:
            pred.reasons.append(
                f"Tüketim trendi %{trend_pct:+.1f} → {abs(correction)} gün erkene alındı"
            )
        if pred.is_overdue:
            pred.reasons.append("GECİKMİŞ — derhal planlanmalı")
        if pred.savings_pct > 0:
            pred.reasons.append(f"Bakım sonrası tahmini tasarruf: %{pred.savings_pct}")

        return pred
