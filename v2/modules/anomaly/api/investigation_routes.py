"""Feature B.2 — Yakıt Hırsızlığı Soruşturmaları endpoint'leri.

Tüm endpoint'ler `THEFT_INVESTIGATION_ENABLED` flag'ine bakar; False → 503.

Endpoint listesi:
  POST   /admin/investigations            — yeni soruşturma + auto-classify
  GET    /admin/investigations            — liste (filter + JOIN ile plaka/şoför)
  GET    /admin/investigations/patterns   — son N gün pattern tarama (B.3)
  GET    /admin/investigations/{id}       — tek kayıt
  PATCH  /admin/investigations/{id}       — status / assigned / notes / resolution
  DELETE /admin/investigations/{id}       — soft delete (status='closed')
  POST   /admin/investigations/{id}/classify — re-run classifier

NOT: patterns route'u {id} catch-all'dan önce gelmeli (route ordering).
"""

from __future__ import annotations

import html
import logging
from typing import Annotated, Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.deps import SessionDep, require_permissions
from app.config import settings
from app.infrastructure.audit.audit_logger import log_audit_event
from v2.modules.anomaly.application.manage_investigations import (
    create_investigation as create_investigation_uc,
)
from v2.modules.anomaly.application.manage_investigations import (
    get_investigation_detail,
    resolve_alarm_context,
)
from v2.modules.anomaly.application.manage_investigations import (
    get_patterns as get_patterns_uc,
)
from v2.modules.anomaly.application.manage_investigations import (
    list_investigations as list_investigations_uc,
)
from v2.modules.anomaly.application.manage_investigations import (
    reclassify_investigation as reclassify_investigation_uc,
)
from v2.modules.anomaly.application.manage_investigations import (
    soft_delete_investigation as soft_delete_investigation_uc,
)
from v2.modules.anomaly.application.manage_investigations import (
    update_investigation as update_investigation_uc,
)
from v2.modules.anomaly.infrastructure.models import Anomaly
from v2.modules.anomaly.schemas import (
    InvestigationCreate,
    InvestigationResponse,
    InvestigationUpdate,
    PatternMatch,
    TheftClassification,
)
from v2.modules.auth_rbac.public import Kullanici

logger = logging.getLogger(__name__)

router = APIRouter()


def _ensure_enabled() -> None:
    if not settings.THEFT_INVESTIGATION_ENABLED:
        raise HTTPException(
            status_code=503,
            detail="Hırsızlık soruşturma modülü devre dışı",
        )


@router.get("/patterns", response_model=list[PatternMatch])
async def get_patterns(
    db: SessionDep,
    current_admin: Annotated[Kullanici, Depends(require_permissions("sefer:read"))],
    days: int = Query(30, ge=7, le=180),
    min_count: int = Query(2, ge=1, le=10),
    limit: int = Query(50, ge=1, le=200),
):
    """Aynı (sofor, arac) için son N gün ≥min_count soruşturma → pattern."""
    _ensure_enabled()
    result_rows = await get_patterns_uc(db, days, min_count, limit)
    return [PatternMatch(**d) for d in result_rows]


# ── Liste ───────────────────────────────────────────────────────────────


@router.get("", response_model=list[InvestigationResponse])
async def list_investigations(
    db: SessionDep,
    current_admin: Annotated[Kullanici, Depends(require_permissions("sefer:read"))],
    status: Optional[str] = Query(
        None, pattern="^(open|assigned|investigating|resolved|closed)$"
    ),
    suspicion_level: Optional[str] = Query(None, pattern="^(low|medium|high|unknown)$"),
    assigned_to_user_id: Optional[int] = Query(None, ge=1),
    days: int = Query(30, ge=1, le=180),
    limit: int = Query(100, ge=1, le=500),
):
    _ensure_enabled()
    result_rows = await list_investigations_uc(
        db,
        days,
        limit,
        status=status,
        suspicion_level=suspicion_level,
        assigned_to_user_id=assigned_to_user_id,
    )
    return [InvestigationResponse(**d) for d in result_rows]


# ── Tek kayıt ───────────────────────────────────────────────────────────


@router.get("/{inv_id}", response_model=InvestigationResponse)
async def get_investigation(
    inv_id: int,
    db: SessionDep,
    current_admin: Annotated[Kullanici, Depends(require_permissions("sefer:read"))],
):
    _ensure_enabled()
    row = await get_investigation_detail(db, inv_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Soruşturma bulunamadı")
    return InvestigationResponse(**row)


# ── POST: yeni soruşturma + auto-classify ───────────────────────────────


def _build_theft_alarm_text(
    inv_id: int,
    classification: TheftClassification,
    anomaly: Anomaly,
    plaka: Optional[str],
    sofor_adi: Optional[str],
) -> str:
    """OPS için HTML-escaped şüpheli yakıt hırsızlığı bildirimi.

    Parse mode HTML — Markdown legacy escape sorunlarından kaçınır.
    Plan Q1: OPS broadcast'i insanlar okur, plaka/şoför adı dahildir
    (LLM PII politikası burayı kapsamaz).
    """
    sapma = anomaly.sapma_yuzde
    sapma_s = f"{sapma:+.1f}%" if sapma is not None else "—"
    score_s = f"{classification.suspicion_score:.2f}"
    plaka_s = html.escape(plaka) if plaka else "—"
    sofor_s = html.escape(sofor_adi) if sofor_adi else "—"
    return (
        "🚨 <b>Yüksek Şüpheli Yakıt Olayı</b>\n\n"
        f"Soruşturma #{inv_id} · Anomali #{anomaly.id}\n"
        f"<b>Plaka:</b> {plaka_s}\n"
        f"<b>Şoför:</b> {sofor_s}\n"
        f"<b>Sapma:</b> {sapma_s}\n"
        f"<b>Skor:</b> {score_s} (high)"
    )


async def _maybe_broadcast_alarm(
    inv_id: int,
    classification: TheftClassification,
    anomaly: Anomaly,
    db,
) -> None:
    """OPS Telegram kanalına yüksek şüpheli hırsızlık olayını yayınla.

    - Yalnız `suspicion_level='high'` için çalışır.
    - `THEFT_ALARM_ENABLED=False` ise no-op.
    - OPS token + chat_id eksikse 502 yerine sessiz log (akış kırılmasın).
    - OPS bot tanımlı değilse driver bot'a fallback (single-bot setup'larda).
    - Telegram başarısızlığı yine sessiz log → soruşturma yaratımı bloklamaz.
    """
    if classification.suspicion_level != "high":
        return
    if not settings.THEFT_ALARM_ENABLED:
        return

    bot_token = settings.TELEGRAM_OPS_BOT_TOKEN or settings.TELEGRAM_DRIVER_BOT_TOKEN
    chat_id = settings.TELEGRAM_OPS_CHAT_ID
    if not bot_token or not chat_id:
        logger.warning(
            "THEFT_ALARM skipped: OPS Telegram yapılandırması eksik (inv=%s)",
            inv_id,
        )
        return

    plaka, sofor_adi = await resolve_alarm_context(db, anomaly)
    text_body = _build_theft_alarm_text(
        inv_id, classification, anomaly, plaka, sofor_adi
    )

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(
                f"{settings.TELEGRAM_API_BASE_URL}/bot{bot_token}/sendMessage",
                json={
                    "chat_id": chat_id,
                    "text": text_body,
                    "parse_mode": "HTML",
                },
            )
            resp.raise_for_status()
        logger.info(
            "THEFT_ALARM sent: inv=%s anomaly=%s score=%.2f",
            inv_id,
            anomaly.id,
            classification.suspicion_score,
        )
    except httpx.HTTPError as exc:
        # Akış bloklanmasın — sadece log + audit
        logger.error(
            "THEFT_ALARM Telegram send failed: inv=%s err=%s",
            inv_id,
            exc,
        )
        try:
            await log_audit_event(
                module="theft",
                action="alarm_send_failed",
                entity_id=str(inv_id),
                new_value={"error": str(exc)},
            )
        except Exception:  # pragma: no cover
            pass


@router.post("", response_model=InvestigationResponse, status_code=201)
async def create_investigation(
    payload: InvestigationCreate,
    db: SessionDep,
    current_admin: Annotated[Kullanici, Depends(require_permissions("sefer:write"))],
):
    _ensure_enabled()
    creator_id = current_admin.id if current_admin.id and current_admin.id > 0 else None
    row, classification, anomaly = await create_investigation_uc(
        db,
        anomaly_id=payload.anomaly_id,
        initial_notes=payload.initial_notes,
        creator_id=creator_id,
    )

    await log_audit_event(
        module="theft",
        action="investigation_created",
        entity_id=str(row["id"]),
        new_value={
            "anomaly_id": payload.anomaly_id,
            "suspicion_level": classification.suspicion_level,
            "suspicion_score": classification.suspicion_score,
        },
        user_id=current_admin.id,
    )

    # High suspicion → OPS Telegram broadcast (B.5)
    await _maybe_broadcast_alarm(row["id"], classification, anomaly, db)

    return InvestigationResponse(**row)


# ── PATCH: güncelle ─────────────────────────────────────────────────────


@router.patch("/{inv_id}", response_model=InvestigationResponse)
async def update_investigation(
    inv_id: int,
    payload: InvestigationUpdate,
    db: SessionDep,
    current_admin: Annotated[Kullanici, Depends(require_permissions("sefer:write"))],
):
    _ensure_enabled()
    row, old_value, values = await update_investigation_uc(db, inv_id, payload)

    if values:
        await log_audit_event(
            module="theft",
            action="investigation_updated",
            entity_id=str(inv_id),
            old_value=old_value,
            new_value=values,
            user_id=current_admin.id,
        )

    return InvestigationResponse(**row)


# ── DELETE: soft (status='closed') ──────────────────────────────────────


@router.delete("/{inv_id}", status_code=204)
async def soft_delete_investigation(
    inv_id: int,
    db: SessionDep,
    current_admin: Annotated[Kullanici, Depends(require_permissions("sefer:write"))],
):
    _ensure_enabled()
    was_already_closed = await soft_delete_investigation_uc(db, inv_id)
    if was_already_closed:
        return  # idempotent
    await log_audit_event(
        module="theft",
        action="investigation_closed",
        entity_id=str(inv_id),
        user_id=current_admin.id,
    )


# ── POST /{id}/classify: re-run classifier ──────────────────────────────


@router.post("/{inv_id}/classify", response_model=TheftClassification)
async def reclassify_investigation(
    inv_id: int,
    db: SessionDep,
    current_admin: Annotated[Kullanici, Depends(require_permissions("sefer:write"))],
):
    _ensure_enabled()
    classification = await reclassify_investigation_uc(db, inv_id)

    await log_audit_event(
        module="theft",
        action="investigation_reclassified",
        entity_id=str(inv_id),
        new_value={
            "suspicion_level": classification.suspicion_level,
            "suspicion_score": classification.suspicion_score,
        },
        user_id=current_admin.id,
    )

    return classification
