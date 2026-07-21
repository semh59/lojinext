"""Faz 12 — pilot izleme KPI konsolidasyonu.

2 haftalık pilot gözleminde tek bakışta görülecek SİSTEM-İÇİ metrikler:
- Veri hacmi (kesintisiz veri girişi sinyali)
- Tahmin coverage (tahminli sefer / tüm sefer)
- Anomali durum kırılımı (açık/onaylı/çözülmüş)

DIŞ yüzeyler (bu endpoint kapsamı dışında, ayrı izlenir):
- Sentry hataları → de.sentry.io (EU region)
- Open-Meteo 429 → backend logları / Prometheus
- Pilot feedback → Telegram OPS kanalı (POST /feedback → ops_bot)
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import text

from app.api.deps import SessionDep, get_current_active_admin
from v2.modules.auth_rbac.public import Kullanici

router = APIRouter()


class PilotStatus(BaseModel):
    data_volume: dict[str, int]  # seferler/araclar/soforler/yakit_alimlari
    prediction_coverage_pct: float  # tahmini_tuketim dolu sefer / tüm sefer
    anomalies: dict[str, int]  # open / acknowledged / resolved
    external_surfaces: dict[str, str]  # dış izleme hatırlatıcı


async def _scalar(db, sql: str) -> int:
    return int((await db.execute(text(sql))).scalar() or 0)


@router.get("/pilot-status", response_model=PilotStatus)
async def get_pilot_status(
    db: SessionDep,
    _admin: Annotated[Kullanici, Depends(get_current_active_admin)],
) -> PilotStatus:
    """Pilot gözlem için konsolide sistem-içi KPI snapshot'ı."""
    seferler = await _scalar(db, "SELECT COUNT(*) FROM seferler")
    predicted = await _scalar(
        db, "SELECT COUNT(*) FROM seferler WHERE tahmini_tuketim IS NOT NULL"
    )
    araclar = await _scalar(db, "SELECT COUNT(*) FROM araclar")
    soforler = await _scalar(db, "SELECT COUNT(*) FROM soforler")
    yakit = await _scalar(db, "SELECT COUNT(*) FROM yakit_alimlari")

    anom_open = await _scalar(
        db,
        "SELECT COUNT(*) FROM anomalies "
        "WHERE acknowledged_at IS NULL AND resolved_at IS NULL",
    )
    anom_ack = await _scalar(
        db,
        "SELECT COUNT(*) FROM anomalies "
        "WHERE acknowledged_at IS NOT NULL AND resolved_at IS NULL",
    )
    anom_resolved = await _scalar(
        db, "SELECT COUNT(*) FROM anomalies WHERE resolved_at IS NOT NULL"
    )

    coverage = round(predicted / seferler * 100.0, 1) if seferler else 0.0

    return PilotStatus(
        data_volume={
            "seferler": seferler,
            "araclar": araclar,
            "soforler": soforler,
            "yakit_alimlari": yakit,
        },
        prediction_coverage_pct=coverage,
        anomalies={
            "open": anom_open,
            "acknowledged": anom_ack,
            "resolved": anom_resolved,
        },
        external_surfaces={
            "sentry": "de.sentry.io (EU) — kritik hata sayısı",
            "open_meteo_429": "backend logları / Prometheus",
            "feedback": "Telegram OPS kanalı (POST /feedback)",
        },
    )
