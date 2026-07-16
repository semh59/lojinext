"""Faz 4 — muayene (compliance) push hatırlatma task'i (gece beat)."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from app.database.unit_of_work import UnitOfWork
from app.infrastructure.background.celery_app import celery_app
from v2.modules.analytics_executive.application.scan_compliance import scan_compliance
from v2.modules.notification.application.send_push_broadcast import (
    send_push_broadcast,
)

logger = logging.getLogger(__name__)


async def _run_inspection_push() -> dict[str, Any]:
    """Muayenesi 14 gün içinde dolacak/geçmiş araç-dorseler için filo push."""
    async with UnitOfWork() as uow:
        items = await scan_compliance(uow, days_horizon=14)
    # days_horizon=14 → dönen her item ya 'soon' (<=14 gün) ya 'overdue' (geçmiş).
    if not items:
        return {"due": 0, "pushed": False}

    overdue = [i for i in items if getattr(i, "risk_level", None) == "overdue"]
    body = f"{len(items)} araç/dorse muayenesi yaklaşıyor"
    if overdue:
        body += f" ({len(overdue)} tanesi gecikmiş)"
    await send_push_broadcast(title="Muayene hatırlatması", body=body, url="/fleet")
    return {"due": len(items), "overdue": len(overdue), "pushed": True}


@celery_app.task(
    bind=True,
    name="compliance.inspection_push",
    max_retries=1,
    acks_late=True,
)
def inspection_push(self) -> dict[str, Any]:  # noqa: ARG001
    """Her gün muayenesi yaklaşan/geçmiş araçlar için filo geneli push."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(_run_inspection_push())
    except Exception as exc:  # noqa: BLE001
        logger.error("inspection push task failed: %s", exc, exc_info=True)
        return {"due": 0, "pushed": False, "error": str(exc)}
    finally:
        loop.close()
