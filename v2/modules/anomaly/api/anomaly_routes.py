from typing import Annotated, Any, Dict, List, Optional

from fastapi import APIRouter, Body, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from app.config import settings
from v2.modules.anomaly.application.detect_anomaly import (
    SeverityEnum,
    get_anomaly_detector,
)
from v2.modules.anomaly.application.generate_cluster_insight import (
    generate_cluster_insight,
)
from v2.modules.anomaly.application.get_fleet_insights import (
    get_fleet_insights as get_fleet_insights_usecase,
)
from v2.modules.anomaly.domain.clustering import cluster_anomalies
from v2.modules.auth_rbac.public import (
    Kullanici,
    get_current_active_user,
    require_permissions,
)
from v2.modules.platform_infra.audit.audit_logger import log_audit_event
from v2.modules.platform_infra.logging.logger import get_logger

logger = get_logger(__name__)

router = APIRouter()


@router.get("/clusters", response_model=Dict[str, Any])
async def get_anomaly_clusters(
    current_user: Annotated[Kullanici, Depends(get_current_active_user)],
    days: int = Query(30, ge=1, le=180),
) -> Dict[str, Any]:
    """Son `days` gün anomalilerini kümeleyip pattern listesi döndürür.

    LLM insight yalnız ANOMALY_CLUSTER_LLM_ENABLED açıkken ve best-effort;
    Groq kesintisi pattern listesini bloklamaz (insight=None).
    """
    detector = get_anomaly_detector()
    rows = await detector.get_recent_anomalies(days=days)
    clusters = cluster_anomalies(rows)
    for c in clusters:
        c["insight"] = None
        if settings.ANOMALY_CLUSTER_LLM_ENABLED:
            try:
                c["insight"] = await generate_cluster_insight(c)
            except Exception as exc:  # noqa: BLE001
                logger.warning("cluster insight (groq) başarısız: %s", exc)
    return {"clusters": clusters, "period_days": days}


@router.get("/fleet/insights", response_model=Dict[str, Any])
async def get_fleet_insights(
    current_user: Annotated[Kullanici, Depends(get_current_active_user)],
    days: int = Query(30, ge=2, le=90),
):
    """
    Filo analiz dashboard verilerini getirir.
    Maliyet kaçağı ve bakım adaylarını içerir.
    """
    return await get_fleet_insights_usecase(days)


@router.get("/", response_model=Dict[str, Any])
async def get_recent_anomalies(
    current_user: Annotated[Kullanici, Depends(get_current_active_user)],
    days: int = Query(30, ge=1, le=365),
    severity: Optional[str] = Query(None, pattern="^(low|medium|high|critical)$"),
    tip: Optional[str] = Query(None, pattern="^(tuketim|maliyet|sefer)$"),
    status: Optional[str] = Query(
        None,
        pattern="^(open|acknowledged|resolved)$",
        description="open=işlenmedi, acknowledged=onaylı ama çözülmedi, resolved=çözüldü",
    ),
    limit: int = Query(50, ge=1, le=200),
):
    """
    Geçmiş anomali kayıtlarını getirir.
    Filtreler: days, severity, tip, status. Her kayıtta plaka, şoför,
    RCA özeti ve eylem alanları (acknowledged_at/by, resolved_at/by,
    resolution_notes) döner.
    """
    detector = get_anomaly_detector()
    sev_enum = SeverityEnum(severity) if severity else None
    anomalies: List[Dict] = await detector.get_recent_anomalies(
        days=days, severity=sev_enum, status=status
    )

    if tip:
        anomalies = [a for a in anomalies if a.get("tip") == tip]

    anomalies = anomalies[:limit]

    return {
        "status": "success",
        "data": {
            "anomalies": anomalies,
            "total": len(anomalies),
            "filters": {
                "days": days,
                "severity": severity,
                "tip": tip,
                "status": status,
            },
        },
    }


class ResolveRequest(BaseModel):
    notes: Optional[str] = Field(None, max_length=2000)


@router.post("/{anomaly_id}/acknowledge", response_model=Dict[str, Any])
async def acknowledge_anomaly(
    anomaly_id: int,
    current_user: Annotated[Kullanici, Depends(require_permissions("anomali:yonet"))],
):
    """Anomaliyi acknowledge eder (acknowledged_at + acknowledged_by doldurulur).

    Anomali yönetimi (acknowledge/resolve) ``anomali:yonet`` yetkisi gerektirir;
    salt-okuma listeleme/insight endpoint'leri herhangi bir kimlikli kullanıcıya
    açıktır.
    """
    detector = get_anomaly_detector()
    try:
        result = await detector.acknowledge(anomaly_id, user_id=current_user.id)
        await log_audit_event(
            module="anomaly",
            action="acknowledge",
            entity_id=str(anomaly_id),
            user_id=current_user.id,
        )
        return result
    except ValueError as exc:
        raise HTTPException(
            status_code=404 if "bulunamadı" in str(exc) else 400, detail=str(exc)
        ) from exc


@router.post("/{anomaly_id}/resolve", response_model=Dict[str, Any])
async def resolve_anomaly(
    anomaly_id: int,
    current_user: Annotated[Kullanici, Depends(require_permissions("anomali:yonet"))],
    payload: ResolveRequest = Body(default_factory=ResolveRequest),  # type: ignore[arg-type]
):
    """Anomaliyi çözüldü olarak işaretler (``anomali:yonet`` yetkisi gerekir).

    Notes opsiyonel ama tavsiye edilir."""
    detector = get_anomaly_detector()
    try:
        result = await detector.resolve(
            anomaly_id, user_id=current_user.id, notes=payload.notes
        )
        await log_audit_event(
            module="anomaly",
            action="resolve",
            entity_id=str(anomaly_id),
            new_value={"notes": payload.notes},
            user_id=current_user.id,
        )
        return result
    except ValueError as exc:
        raise HTTPException(
            status_code=404 if "bulunamadı" in str(exc) else 400, detail=str(exc)
        ) from exc
