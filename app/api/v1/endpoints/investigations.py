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
from datetime import datetime, timedelta, timezone
from typing import Annotated, Any, Dict, List, Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.exc import IntegrityError

from app.api.deps import SessionDep, require_permissions
from app.config import settings
from app.core.ai.fuel_theft_classifier import get_fuel_theft_classifier
from app.database.models import Anomaly, Kullanici
from app.database.repositories.analiz_repo import get_analiz_repo
from app.infrastructure.audit.audit_logger import log_audit_event
from app.schemas.investigation import (
    InvestigationCreate,
    InvestigationResponse,
    InvestigationUpdate,
    PatternMatch,
    TheftClassification,
)

logger = logging.getLogger(__name__)

router = APIRouter()


def _ensure_enabled() -> None:
    if not settings.THEFT_INVESTIGATION_ENABLED:
        raise HTTPException(
            status_code=503,
            detail="Hırsızlık soruşturma modülü devre dışı",
        )


@router.get("/patterns", response_model=List[PatternMatch])
async def get_patterns(
    db: SessionDep,
    current_admin: Annotated[Kullanici, Depends(require_permissions("sefer:read"))],
    days: int = Query(30, ge=7, le=180),
    min_count: int = Query(2, ge=1, le=10),
    limit: int = Query(50, ge=1, le=200),
):
    """Aynı (sofor, arac) için son N gün ≥min_count soruşturma → pattern."""
    _ensure_enabled()
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    repo = get_analiz_repo(session=db)
    result_rows = await repo.get_investigation_patterns(cutoff, min_count, limit)
    return [PatternMatch(**d) for d in result_rows]


# ── Liste ───────────────────────────────────────────────────────────────


@router.get("", response_model=List[InvestigationResponse])
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
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    repo = get_analiz_repo(session=db)
    result_rows = await repo.list_investigations(
        cutoff,
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
    repo = get_analiz_repo(session=db)
    row = await repo.get_investigation_detail(inv_id)
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


async def _resolve_alarm_context(
    db, anomaly: Anomaly
) -> "tuple[Optional[str], Optional[str]]":
    """Anomaly → (plaka, sofor_adi). Yoksa (None, None)."""
    repo = get_analiz_repo(session=db)
    return await repo.get_anomaly_alarm_context(int(anomaly.id))


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

    plaka, sofor_adi = await _resolve_alarm_context(db, anomaly)
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
    repo = get_analiz_repo(session=db)
    # 1. Anomaly var mı?
    anomaly = await repo.get_anomaly_by_id(payload.anomaly_id)
    if not anomaly:
        raise HTTPException(status_code=404, detail="Anomali bulunamadı")
    # 2. Mevcut investigation var mı? (unique constraint da yakalar)
    existing = await repo.get_investigation_by_anomaly_id(payload.anomaly_id)
    if existing:
        raise HTTPException(
            status_code=409,
            detail="Bu anomali için zaten bir soruşturma var",
        )

    # 3. Classifier
    classification = await get_fuel_theft_classifier().classify(
        {
            "id": anomaly.id,
            "tip": anomaly.tip,
            "kaynak_id": anomaly.kaynak_id,
            "kaynak_tip": anomaly.kaynak_tip,
            "sapma_yuzde": anomaly.sapma_yuzde,
            "severity": anomaly.severity,
        }
    )

    # 4. INSERT (creator_id virtual super-admin=0 ise NULL)
    creator_id = current_admin.id if current_admin.id and current_admin.id > 0 else None
    try:
        inv = await repo.create_investigation_row(
            anomaly_id=payload.anomaly_id,
            status="open",
            suspicion_score=classification.suspicion_score,
            suspicion_level=classification.suspicion_level,
            notes=payload.initial_notes,
            creator_id=creator_id,
        )
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        # unique constraint çakışması (race)
        raise HTTPException(
            status_code=409,
            detail="Bu anomali için zaten bir soruşturma var",
        ) from exc

    await log_audit_event(
        module="theft",
        action="investigation_created",
        entity_id=str(inv.id),
        new_value={
            "anomaly_id": payload.anomaly_id,
            "suspicion_level": classification.suspicion_level,
            "suspicion_score": classification.suspicion_score,
        },
        user_id=current_admin.id,
    )

    # 5. High suspicion → OPS Telegram broadcast (B.5)
    await _maybe_broadcast_alarm(inv.id, classification, anomaly, db)

    # JOIN'li response
    row = await repo.get_investigation_detail(int(inv.id))
    if row is None:
        # Beklenmedik durum
        raise HTTPException(
            status_code=500, detail="Soruşturma oluşturuldu ama okunamadı"
        )
    return InvestigationResponse(**row)


# ── PATCH: güncelle ─────────────────────────────────────────────────────


_TERMINAL_STATUSES = {"closed"}


@router.patch("/{inv_id}", response_model=InvestigationResponse)
async def update_investigation(
    inv_id: int,
    payload: InvestigationUpdate,
    db: SessionDep,
    current_admin: Annotated[Kullanici, Depends(require_permissions("sefer:write"))],
):
    _ensure_enabled()
    repo = get_analiz_repo(session=db)
    # 2026-07-01 prod-grade denetimi P1 (Dalga 4 madde 18): SELECT ... FOR
    # UPDATE ile satır kilitlenir — eskiden kilitsiz okunuyordu (TOCTOU),
    # eşzamanlı iki PATCH'te geç kalan istek ilkinin commit'inden ÖNCE
    # okunan stale bir status'a göre karar verip diğerinin sonucunu sessizce
    # eziyordu.
    inv = await repo.lock_investigation_for_update(inv_id)
    if not inv:
        raise HTTPException(status_code=404, detail="Soruşturma bulunamadı")
    if inv.status in _TERMINAL_STATUSES:
        raise HTTPException(
            status_code=409,
            detail="Kapatılmış soruşturma değiştirilemez",
        )

    old_value: Dict[str, Any] = {
        "status": inv.status,
        "assigned_to_user_id": inv.assigned_to_user_id,
        "resolution_type": inv.resolution_type,
    }
    values: Dict[str, Any] = {}

    if payload.status is not None:
        values["status"] = payload.status
        if payload.status == "resolved" and inv.closed_at is None:
            values["closed_at"] = datetime.now(timezone.utc)
        elif payload.status == "closed":
            values["closed_at"] = datetime.now(timezone.utc)

    if payload.assigned_to_user_id is not None:
        values["assigned_to_user_id"] = payload.assigned_to_user_id
        # Atama yapılıyor + status hala open ise otomatik 'assigned'
        if inv.status == "open" and "status" not in values:
            values["status"] = "assigned"

    if payload.notes is not None:
        values["notes"] = payload.notes

    if payload.resolution_type is not None:
        values["resolution_type"] = payload.resolution_type
        # resolution set olunca status auto='resolved' + closed_at
        if "status" not in values:
            values["status"] = "resolved"
            values["closed_at"] = datetime.now(timezone.utc)

    if payload.evidence_files is not None:
        values["evidence_files"] = payload.evidence_files

    if not values:
        # No-op update — mevcut kaydı dön
        row = await repo.get_investigation_detail(inv_id)
        if row is None:
            raise HTTPException(status_code=404, detail="Soruşturma bulunamadı")
        return InvestigationResponse(**row)

    await repo.update_investigation_fields(inv_id, values)
    await db.commit()

    await log_audit_event(
        module="theft",
        action="investigation_updated",
        entity_id=str(inv_id),
        old_value=old_value,
        new_value=values,
        user_id=current_admin.id,
    )

    row = await repo.get_investigation_detail(inv_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Soruşturma bulunamadı")
    return InvestigationResponse(**row)


# ── DELETE: soft (status='closed') ──────────────────────────────────────


@router.delete("/{inv_id}", status_code=204)
async def soft_delete_investigation(
    inv_id: int,
    db: SessionDep,
    current_admin: Annotated[Kullanici, Depends(require_permissions("sefer:write"))],
):
    _ensure_enabled()
    repo = get_analiz_repo(session=db)
    inv = await repo.get_investigation_by_id(inv_id)
    if not inv:
        raise HTTPException(status_code=404, detail="Soruşturma bulunamadı")
    if inv.status == "closed":
        return  # idempotent

    await repo.close_investigation(inv_id, datetime.now(timezone.utc))
    await db.commit()
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
    repo = get_analiz_repo(session=db)
    inv = await repo.get_investigation_by_id(inv_id)
    if not inv:
        raise HTTPException(status_code=404, detail="Soruşturma bulunamadı")
    anomaly = await repo.get_anomaly_by_id(inv.anomaly_id)
    if not anomaly:
        raise HTTPException(status_code=404, detail="İlişkili anomali bulunamadı")

    classification = await get_fuel_theft_classifier().classify(
        {
            "id": anomaly.id,
            "tip": anomaly.tip,
            "kaynak_id": anomaly.kaynak_id,
            "kaynak_tip": anomaly.kaynak_tip,
            "sapma_yuzde": anomaly.sapma_yuzde,
            "severity": anomaly.severity,
        }
    )
    await repo.update_investigation_classification(
        inv_id,
        classification.suspicion_score,
        classification.suspicion_level,
    )
    await db.commit()

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
