"""Feature D.4 — Bakım statüsünden yakıt tahmin çarpanı.

Saf fonksiyon: AracBakim kayıtları + bugün → 0.95..1.25 arası çarpan.
PredictionService bu çarpanı `predict_consumption` çıktısına post-process
olarak uygular — hem ensemble hem physics-fallback path'i etkilenir.

Plan kaynağı: docs/superpowers/plans/2026-05-26-feature-d-predictive-maintenance-v3.md §7
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


# ── Sabitler ────────────────────────────────────────────────────────────
# PERIYODIK_AGE_TIERS — başlangıç değerleri pratik kullanımdan kalibre,
# literatür: dizel ağır vasıta yağ değişimi geciktiğinde tüketim
# +%2 ila +%10 arası artar (ATA TMC 2021). 12 aylık PERIYODIK interval
# etrafında simetrik:
#   <90       = bakım taze, peak verim         → 0.96
#   90-300    = normal aralık (%25-82)         → 1.00
#   300-365   = yaklaşıyor (%82-100)           → 1.03
#   365-450   = geçti %0-23                    → 1.07
#   450-600   = ciddi geçti %23-64             → 1.12
#   600+      = cap                            → 1.15
#
# ÖNEMLİ: v1 değerler — 3 ay sonra gerçek tüketim sapması ile recalibrate
# edilmeli (Prometheus: maintenance_factor_applied_total{tier="..."}).
PERIYODIK_AGE_TIERS: list[Tuple[Optional[int], float, str]] = [
    (90, 0.96, "Taze PERIYODIK - verim peak"),
    (300, 1.00, "Normal PERIYODIK araligI"),
    (365, 1.03, "PERIYODIK yaklasIyor"),
    (450, 1.07, "PERIYODIK gecikti"),
    (600, 1.12, "PERIYODIK ciddi gecikti"),
    (None, 1.15, "PERIYODIK cok ciddi gecikti (cap)"),
]
NO_HISTORY_FACTOR = 1.05  # PERIYODIK kaydı hiç yok → belirsizlik
OPEN_ARIZA_PENALTY = 1.05  # tamamlanmamış ARIZA başı çarpan
OPEN_ACIL_PENALTY = 1.10  # tamamlanmamış ACIL
FACTOR_FLOOR = 0.95
FACTOR_CAP = 1.25


# ── Veri sınıfları ──────────────────────────────────────────────────────
@dataclass
class HealthInput:
    """PredictionService → maintenance_factor için minimal veri."""

    last_periyodik_date: Optional[datetime]
    open_ariza_count: int = 0
    open_acil_count: int = 0


@dataclass
class HealthResult:
    factor: float
    base_factor: float  # PERIYODIK katkısı
    arac_penalty: float = 1.0
    acil_penalty: float = 1.0
    reason: str = ""


# ── Saf yardımcılar ────────────────────────────────────────────────────
def _periyodik_age_factor(
    last_dt: Optional[datetime], now: Optional[datetime] = None
) -> Tuple[float, str]:
    """PERIYODIK bakım tarihinden bugüne kadar geçen güne göre çarpan döndür.

    Args:
        last_dt: son tamamlanmış PERIYODIK tarihi (None → NO_HISTORY_FACTOR)
        now: test için clock injection; üretimde None → datetime.now(UTC)

    Returns:
        (factor, human-readable reason)
    """
    if last_dt is None:
        return NO_HISTORY_FACTOR, "PERIYODIK kaydi yok"
    if last_dt.tzinfo is None:
        last_dt = last_dt.replace(tzinfo=timezone.utc)
    if now is None:
        now = datetime.now(timezone.utc)
    days = (now - last_dt).days
    # Clock skew / gelecek tarihli kayıt → en alt tier'a (taze)
    if days < 0:
        days = 0
    for max_days, factor, label in PERIYODIK_AGE_TIERS:
        if max_days is None or days <= max_days:
            return factor, f"{label} ({days} gun)"
    # Mantıken erişilmez (None tier her durumda match eder); savunma amaçlı:
    return PERIYODIK_AGE_TIERS[-1][1], PERIYODIK_AGE_TIERS[-1][2]


def compute_maintenance_factor(
    inp: HealthInput, *, now: Optional[datetime] = None
) -> HealthResult:
    """Bakım statüsünden 0.95..1.25 arası yakıt çarpanı üret."""
    base, reason = _periyodik_age_factor(inp.last_periyodik_date, now=now)
    ariza_part = OPEN_ARIZA_PENALTY if inp.open_ariza_count > 0 else 1.0
    acil_part = OPEN_ACIL_PENALTY if inp.open_acil_count > 0 else 1.0
    raw = base * ariza_part * acil_part
    clamped = max(FACTOR_FLOOR, min(FACTOR_CAP, raw))
    return HealthResult(
        factor=round(clamped, 3),
        base_factor=base,
        arac_penalty=ariza_part,
        acil_penalty=acil_part,
        reason=reason,
    )


async def fetch_health_input(uow, arac_id: int) -> HealthInput:
    """Mevcut UoW içinde DB'den son PERIYODIK + açık ARIZA/ACIL sayısını çeker.

    Nested UoW açmaz — caller (PredictionService) zaten arac fetch ederken
    aynı UoW'da bu sorguyu çalıştırır.
    """
    from sqlalchemy import text

    sql = """
        SELECT
            (SELECT MAX(bakim_tarihi) FROM arac_bakimlari
             WHERE arac_id = :aid AND tamamlandi = TRUE
                   AND bakim_tipi = 'PERIYODIK') AS last_periyodik,
            (SELECT COUNT(*) FROM arac_bakimlari
             WHERE arac_id = :aid AND tamamlandi = FALSE
                   AND bakim_tipi = 'ARIZA') AS open_ariza,
            (SELECT COUNT(*) FROM arac_bakimlari
             WHERE arac_id = :aid AND tamamlandi = FALSE
                   AND bakim_tipi = 'ACIL') AS open_acil
    """
    row = (await uow.session.execute(text(sql), {"aid": int(arac_id)})).mappings().one()
    return HealthInput(
        last_periyodik_date=row["last_periyodik"],
        open_ariza_count=int(row["open_ariza"] or 0),
        open_acil_count=int(row["open_acil"] or 0),
    )


async def fetch_health_input_batch(uow, arac_ids: List[int]) -> Dict[int, HealthInput]:
    """Tek sorguda N araç için HealthInput haritası döner (N+1 önleyen batch).

    Çağıran: cross_feature_aggregator D.4 bloğu.
    """
    from sqlalchemy import text

    if not arac_ids:
        return {}

    sql = """
        SELECT
            a.id AS arac_id,
            MAX(CASE WHEN ab.bakim_tipi = 'PERIYODIK' AND ab.tamamlandi = TRUE
                THEN ab.bakim_tarihi END)             AS last_periyodik,
            COUNT(CASE WHEN ab.bakim_tipi = 'ARIZA' AND ab.tamamlandi = FALSE
                THEN 1 END)                           AS open_ariza,
            COUNT(CASE WHEN ab.bakim_tipi = 'ACIL'  AND ab.tamamlandi = FALSE
                THEN 1 END)                           AS open_acil
        FROM unnest(:arac_ids ::int[]) AS a(id)
        LEFT JOIN arac_bakimlari ab ON ab.arac_id = a.id
        GROUP BY a.id
    """
    rows = (
        (await uow.session.execute(text(sql), {"arac_ids": list(arac_ids)}))
        .mappings()
        .all()
    )

    return {
        int(r["arac_id"]): HealthInput(
            last_periyodik_date=r["last_periyodik"],
            open_ariza_count=int(r["open_ariza"] or 0),
            open_acil_count=int(r["open_acil"] or 0),
        )
        for r in rows
    }


# ── PredictionService payload post-process ────────────────────────────
def apply_maintenance_factor(
    payload: dict, factor: float, reason: Optional[str] = None
) -> dict:
    """`predict_consumption` çıktısına maintenance_factor uygular.

    İki path da (ensemble + physics fallback) aynı payload formatını döner;
    burada tek noktada `prediction_liters` çarpılır ve `faktorler` dict'ine
    yazılır (XAI için frontend gösterimi).

    Geri uyumlu: factor == 1.0 ise no-op.
    """
    if factor == 1.0:
        return payload
    try:
        if payload.get("tahmini_tuketim"):
            payload["tahmini_tuketim"] = round(
                float(payload["tahmini_tuketim"]) * factor, 2
            )
        if payload.get("tahmini_litre"):
            payload["tahmini_litre"] = round(
                float(payload["tahmini_litre"]) * factor, 2
            )
        if payload.get("prediction_liters"):
            payload["prediction_liters"] = round(
                float(payload["prediction_liters"]) * factor, 2
            )
    except (TypeError, ValueError):
        return payload

    faktorler = payload.setdefault("faktorler", {})
    if isinstance(faktorler, dict):
        faktorler["maintenance_factor"] = round(factor, 3)
        if reason:
            faktorler["maintenance_reason"] = reason

    # Insight metnine de ekle (operatör görünürlüğü)
    if reason:
        existing = payload.get("explanation_summary") or ""
        if "Bakım faktörü" not in existing:
            suffix = f"Bakım faktörü: {factor:.2f} ({reason})"
            payload["explanation_summary"] = (
                f"{existing} | {suffix}" if existing else suffix
            ).strip(" |")

    return payload
