"""Insight Engine — fleet/vehicle/driver içgörüleri üret ve toplu kaydet.

dalga 11 — B.1: eski `InsightEngine` sınıfı kaldırıldı (constructor state
taşımıyordu, her metot bağımsız bir use-case'ti) — free function'lara
bölündü, location/notification/fleet/fuel/driver/auth_rbac ile aynı karar.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional

from app.infrastructure.logging.logger import get_logger

logger = get_logger(__name__)


class InsightType(Enum):
    UYARI = "uyari"
    ONERI = "oneri"
    BILGI = "bilgi"


@dataclass
class Insight:
    tip: InsightType
    hedef_tur: str
    hedef_id: Optional[int]
    mesaj: str
    seviye: str = "medium"


def get_uow():
    """
    Async context manager factory.
    Kept as a function to make monkeypatching in tests straightforward.
    """
    return _UnitOfWorkContext()


class _UnitOfWorkContext:
    async def __aenter__(self):
        from app.database.unit_of_work import UnitOfWork

        self._uow = UnitOfWork()
        return await self._uow.__aenter__()

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        return await self._uow.__aexit__(exc_type, exc_val, exc_tb)


async def _safe_await(value_or_coro):
    if asyncio.iscoroutine(value_or_coro):
        return await value_or_coro
    return value_or_coro


async def generate_fleet_insights() -> List[Insight]:
    try:
        async with get_uow() as uow:
            stats = await _safe_await(uow.analiz_repo.get_dashboard_stats())
    except Exception as exc:
        logger.warning("Fleet insight generation failed: %s", exc)
        return []

    avg = float(stats.get("filo_ortalama", 0) or 0)
    if avg <= 0:
        return []
    if avg > 38:
        return [
            Insight(
                tip=InsightType.UYARI,
                hedef_tur="filo",
                hedef_id=None,
                mesaj="Filo ortalama tüketimi kritik eşik üzerinde.",
                seviye="high",
            )
        ]
    return []


async def generate_vehicle_insights_bulk() -> List[Insight]:
    try:
        async with get_uow() as uow:
            rows = await _safe_await(
                uow.analiz_repo.get_all_vehicles_consumption_stats()
            )
    except Exception as exc:
        logger.warning("Vehicle insight generation failed: %s", exc)
        return []

    insights: List[Insight] = []
    for row in rows or []:
        hedef = float(row.get("hedef_tuketim", 0) or 0)
        ort = float(row.get("ort_tuketim", 0) or 0)
        if hedef <= 0:
            continue
        if ort > hedef * 1.10:
            plaka = row.get("plaka", "Bilinmeyen araç")
            insights.append(
                Insight(
                    tip=InsightType.UYARI,
                    hedef_tur="arac",
                    hedef_id=row.get("arac_id"),
                    mesaj=f"{plaka} için tüketim hedefin üzerinde ({ort:.1f} L/100km).",
                    seviye="high",
                )
            )
    return insights


async def generate_driver_insights_bulk() -> List[Insight]:
    try:
        async with get_uow() as uow:
            method = getattr(uow.analiz_repo, "get_all_drivers_consumption_stats", None)
            rows = await _safe_await(method()) if callable(method) else []
    except Exception as exc:
        logger.warning("Driver insight generation failed: %s", exc)
        return []

    insights: List[Insight] = []
    for row in rows or []:
        score = float(row.get("performans_skoru", 0) or 0)
        if score and score < 50:
            insights.append(
                Insight(
                    tip=InsightType.UYARI,
                    hedef_tur="sofor",
                    hedef_id=row.get("sofor_id"),
                    mesaj=f"Şoför performansı düşük: {row.get('ad_soyad', 'Bilinmiyor')}.",
                    seviye="medium",
                )
            )
    return insights


def _to_alert_payload(insight: Insight) -> Dict[str, Any]:
    tip_label = insight.tip.value.title()
    return {
        "title": f"Sistem Analizi: {tip_label}",
        "message": insight.mesaj,
        "severity": insight.seviye,
        "kaynak_tur": insight.hedef_tur,
        "kaynak_id": insight.hedef_id,
    }


async def _notify_serious_alerts(payloads: List[Dict[str, Any]]) -> None:
    """Faz 4 — high/critical seviyeli uyarılarda filo geneli push (best-effort).

    Push hatası asla insight kaydını/akışını bozmaz (yalnız warning log).
    """
    serious = [p for p in payloads if p.get("severity") in ("high", "critical")]
    if not serious:
        return
    try:
        from v2.modules.notification.application.send_push_broadcast import (
            send_push_broadcast,
        )

        body = (
            serious[0]["message"]
            if len(serious) == 1
            else f"{len(serious)} kritik/yüksek öncelikli uyarı tespit edildi."
        )
        await send_push_broadcast(title="Kritik filo uyarısı", body=body, url="/alerts")
    except Exception as exc:  # noqa: BLE001 — push asla anomali akışını bozmaz
        logger.warning("kritik anomali push'u başarısız: %s", exc)


async def generate_all_and_save() -> int:
    fleet_task = generate_fleet_insights()
    vehicle_task = generate_vehicle_insights_bulk()
    driver_task = generate_driver_insights_bulk()
    fleet, vehicles, drivers = await asyncio.gather(
        fleet_task, vehicle_task, driver_task
    )

    insights = [*fleet, *vehicles, *drivers]
    if not insights:
        return 0

    payload = [_to_alert_payload(i) for i in insights]
    async with get_uow() as uow:
        saved = int(await _safe_await(uow.analiz_repo.bulk_create_alerts(payload)))
        # bulk_create_alerts uses a core INSERT and only self-commits when it
        # owns its session; via the UoW the repo has a session, so the owning
        # UoW must commit here — otherwise __aexit__'s ghost-guard (which only
        # inspects ORM session.new/dirty, not core inserts) treats it as a
        # clean read-only exit and rolls the alerts back (silent data loss).
        await uow.commit()
    # Faz 4 — kritik/yüksek seviyeli uyarılarda filo geneli push tetikle.
    await _notify_serious_alerts(payload)
    return saved
