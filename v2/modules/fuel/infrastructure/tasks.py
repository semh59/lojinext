"""Yakıt-tahmin coverage hesaplama + ops alarmı (fuel-coverage, 2026-07-07).

``GET /admin/fuel-accuracy`` (``api/fuel_routes.py``) ve
``monitoring.fuel_coverage_check`` beat task'ı aynı "tamamlanmış sefer
başına tahmin var mı" SQL çekirdeğini paylaşır: ``durum = 'Completed'``
+ ``is_deleted = FALSE`` + ``tuketim NOT NULL``/``> 0`` filtresiyle toplam
tamamlanmış sefer sayısı ile ``tahmini_tuketim`` (ve ``mesafe_km``) dolu
olan sefer sayısı.

Endpoint'in MAPE/RMSE/breakdown hesaplarına DOKUNULMADI — davranışı aynen
korumak için bu modül endpoint'i çağırmaz/değiştirmez, sadece coverage
sayaçlarını (aynı filtre semantiğiyle) izole bir yardımcıya çıkarır.

Beat task: ``monitoring.fuel_coverage_check`` — günde bir, son 7 günün
tamamlanmış seferlerinde tahmin (``tahmini_tuketim``) coverage'ı runtime-config
eşiğinin (``FUEL_COVERAGE_ALERT_THRESHOLD_PCT``, varsayılan %50, migration
0042 ile seed'lenir) altına düşerse Telegram ops kanalına uyarı gönderir.

Örneklem < 5 ise (az/boş veri gürültüsü) alarm YOK. Telegram bildirimi
best-effort — hata task'ı kırmaz, sadece warning loglanır (audit-logger'ın
aynı felsefesi: config/notification okuması iş akışını asla kırmamalı).
"""

from __future__ import annotations

import asyncio
from datetime import date, timedelta
from typing import NamedTuple

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.background.celery_app import celery_app
from app.infrastructure.logging.logger import get_logger

logger = get_logger(__name__)

_COVERAGE_WINDOW_DAYS = 7
_MIN_SAMPLE_FOR_ALARM = 5
_DEFAULT_THRESHOLD_PCT = 50.0


class CoverageResult(NamedTuple):
    sample_size: int  # tahmini_tuketim dolu (+ mesafe_km > 0) sefer sayısı
    total_completed: int  # toplam tamamlanmış (tuketim dolu) sefer sayısı
    coverage_pct: float  # sample_size / total_completed * 100 (yüzde 1 ondalık)


async def compute_coverage(db: AsyncSession, days: int) -> CoverageResult:
    """Son ``days`` gündeki tamamlanmış seferler için tahmin coverage'ı.

    Filtre semantiği ``api/fuel_routes.py``'deki ``base_where`` + "paired"
    CTE'siyle birebir aynıdır (durum='Completed', is_deleted=FALSE,
    tuketim NOT NULL/>0; sample ek olarak tahmini_tuketim NOT NULL/>0 VE
    mesafe_km > 0 ister).
    """
    cutoff = date.today() - timedelta(days=days)
    sql = text(
        """
        WITH completed AS (
            SELECT tahmini_tuketim, mesafe_km
            FROM seferler
            WHERE durum = 'Completed'
              AND is_deleted = FALSE
              AND tarih >= :cutoff
              AND tuketim IS NOT NULL
              AND tuketim > 0
        )
        SELECT
            COUNT(*) FILTER (
                WHERE tahmini_tuketim IS NOT NULL
                  AND tahmini_tuketim > 0
                  AND mesafe_km > 0
            ) AS sample_size,
            COUNT(*) AS total_completed
        FROM completed
        """
    )
    row = (await db.execute(sql, {"cutoff": cutoff})).mappings().one()
    sample_size = int(row["sample_size"] or 0)
    total_completed = int(row["total_completed"] or 0)
    coverage_pct = (
        round(sample_size / total_completed * 100.0, 1) if total_completed else 0.0
    )
    return CoverageResult(
        sample_size=sample_size,
        total_completed=total_completed,
        coverage_pct=coverage_pct,
    )


async def _run_fuel_coverage_check() -> None:
    from app.database.unit_of_work import UnitOfWork
    from v2.modules.admin_platform.public import get_runtime_float
    from v2.modules.notification.public import notify_error

    async with UnitOfWork() as uow:
        result = await compute_coverage(uow.session, _COVERAGE_WINDOW_DAYS)
        threshold = await get_runtime_float(
            "FUEL_COVERAGE_ALERT_THRESHOLD_PCT", _DEFAULT_THRESHOLD_PCT, uow=uow
        )

    if result.total_completed < _MIN_SAMPLE_FOR_ALARM:
        return  # az/boş veri — gürültülü alarm istemiyoruz

    if result.coverage_pct >= threshold:
        return  # eşik üstünde — sorun yok

    message = (
        f"⛽ Yakıt tahmini coverage düşük: %{result.coverage_pct:.1f} "
        f"(eşik %{threshold:.1f}) — örneklem {result.sample_size}/"
        f"{result.total_completed}, son {_COVERAGE_WINDOW_DAYS} gün"
    )
    try:
        await notify_error(level="warning", message=message, path="fuel_coverage_check")
    except Exception as exc:  # notification asla iş akışını kırmamalı
        logger.warning("Fuel coverage alarmı Telegram'a iletilemedi: %s", exc)


@celery_app.task(
    bind=True,
    name="monitoring.fuel_coverage_check",
    max_retries=0,
    ignore_result=True,
)
def fuel_coverage_check(self):  # noqa: ARG001
    """Günlük: son 7 gün yakıt-tahmin coverage'ı eşiğin altındaysa ops uyarısı."""
    asyncio.run(_run_fuel_coverage_check())
