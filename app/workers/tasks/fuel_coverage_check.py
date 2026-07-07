"""Yakıt-tahmin coverage ops alarmı (2026-07-07).

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

from app.infrastructure.background.celery_app import celery_app
from app.infrastructure.logging.logger import get_logger

logger = get_logger(__name__)

_COVERAGE_WINDOW_DAYS = 7
_MIN_SAMPLE_FOR_ALARM = 5
_DEFAULT_THRESHOLD_PCT = 50.0


async def _run_fuel_coverage_check() -> None:
    from app.core.services.fuel_coverage import compute_coverage
    from app.core.services.runtime_config import get_runtime_float
    from app.database.unit_of_work import UnitOfWork
    from app.infrastructure.notifications.telegram_notifier import notify_error

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
