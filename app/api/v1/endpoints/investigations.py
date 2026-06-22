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
from sqlalchemy import select, text, update
from sqlalchemy.exc import IntegrityError

from app.api.deps import SessionDep, require_permissions
from app.config import settings
from app.core.ai.fuel_theft_classifier import get_fuel_theft_classifier
from app.database.models import Anomaly, FuelInvestigation, Kullanici
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


_LIST_SQL_BASE = """
    SELECT
        fi.id,
        fi.anomaly_id,
        fi.status,
        fi.suspicion_score,
        fi.suspicion_level,
        fi.assigned_to_user_id,
        fi.notes,
        fi.resolution_type,
        fi.evidence_files,
        fi.created_at,
        fi.updated_at,
        fi.closed_at,
        a.sapma_yuzde,
        COALESCE(s.ad_soyad, NULL) AS sofor_adi,
        COALESCE(v.plaka, NULL) AS plaka
    FROM fuel_investigations fi
    JOIN anomalies a ON fi.anomaly_id = a.id
    LEFT JOIN seferler sf ON a.kaynak_tip = 'sefer' AND a.kaynak_id = sf.id
    LEFT JOIN soforler s ON sf.sofor_id = s.id
    LEFT JOIN araclar v ON (a.kaynak_tip = 'arac' AND a.kaynak_id = v.id)
                        OR (a.kaynak_tip = 'sefer' AND sf.arac_id = v.id)
    WHERE 1=1
"""


async def _fetch_investigation_dict(db, inv_id: int) -> Optional[Dict[str, Any]]:
    sql = _LIST_SQL_BASE + " AND fi.id = :id LIMIT 1"
    row = (await db.execute(text(sql), {"id": inv_id})).mappings().one_or_none()
    if row is None:
        return None
    return dict(row)


# ── Pattern detection (B.3 ile birleşik — route {id}'den önce) ───────────


_PATTERN_SQL = """
    WITH inv_data AS (
        SELECT
            fi.suspicion_score,
            fi.created_at,
            COALESCE(sf.sofor_id, NULL) AS sofor_id,
            COALESCE(sf.arac_id, NULL) AS arac_id,
            COALESCE(s.ad_soyad, NULL) AS sofor_adi,
            COALESCE(v.plaka, NULL) AS plaka
        FROM fuel_investigations fi
        JOIN anomalies a ON fi.anomaly_id = a.id
        LEFT JOIN seferler sf ON a.kaynak_tip = 'sefer' AND a.kaynak_id = sf.id
        LEFT JOIN soforler s ON sf.sofor_id = s.id
        LEFT JOIN araclar v ON (a.kaynak_tip = 'arac' AND a.kaynak_id = v.id)
                            OR (a.kaynak_tip = 'sefer' AND sf.arac_id = v.id)
        WHERE fi.created_at >= :cutoff
          AND fi.suspicion_score IS NOT NULL
    )
    SELECT
        sofor_id, sofor_adi, arac_id, plaka,
        COUNT(*)::int AS occurrence_count,
        AVG(suspicion_score)::float AS avg_suspicion_score,
        MAX(created_at) AS last_seen
    FROM inv_data
    WHERE sofor_id IS NOT NULL OR arac_id IS NOT NULL
    GROUP BY sofor_id, sofor_adi, arac_id, plaka
    HAVING COUNT(*) >= :min_count
    ORDER BY avg_suspicion_score DESC NULLS LAST
    LIMIT :limit
"""


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
    rows = (
        (
            await db.execute(
                text(_PATTERN_SQL),
                {"cutoff": cutoff, "min_count": min_count, "limit": limit},
            )
        )
        .mappings()
        .all()
    )
    return [PatternMatch(**dict(r)) for r in rows]


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

    sql = _LIST_SQL_BASE
    params: Dict[str, Any] = {"cutoff": cutoff, "limit": limit}
    sql += " AND fi.created_at >= :cutoff"
    if status:
        sql += " AND fi.status = :status"
        params["status"] = status
    if suspicion_level:
        sql += " AND fi.suspicion_level = :sl"
        params["sl"] = suspicion_level
    if assigned_to_user_id:
        sql += " AND fi.assigned_to_user_id = :assigned"
        params["assigned"] = assigned_to_user_id
    sql += " ORDER BY fi.created_at DESC LIMIT :limit"

    rows = (await db.execute(text(sql), params)).mappings().all()
    return [InvestigationResponse(**dict(r)) for r in rows]


# ── Tek kayıt ───────────────────────────────────────────────────────────


@router.get("/{inv_id}", response_model=InvestigationResponse)
async def get_investigation(
    inv_id: int,
    db: SessionDep,
    current_admin: Annotated[Kullanici, Depends(require_permissions("sefer:read"))],
):
    _ensure_enabled()
    row = await _fetch_investigation_dict(db, inv_id)
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
) -> tuple[Optional[str], Optional[str]]:
    """Anomaly → (plaka, sofor_adi). Yoksa (None, None)."""
    sql = """
        SELECT
            COALESCE(s.ad_soyad, NULL) AS sofor_adi,
            COALESCE(v.plaka, NULL) AS plaka
        FROM anomalies a
        LEFT JOIN seferler sf ON a.kaynak_tip = 'sefer' AND a.kaynak_id = sf.id
        LEFT JOIN soforler s ON sf.sofor_id = s.id
        LEFT JOIN araclar v ON (a.kaynak_tip = 'arac' AND a.kaynak_id = v.id)
                            OR (a.kaynak_tip = 'sefer' AND sf.arac_id = v.id)
        WHERE a.id = :aid
        LIMIT 1
    """
    row = (
        (await db.execute(text(sql), {"aid": int(anomaly.id)})).mappings().one_or_none()
    )
    if row is None:
        return None, None
    return row.get("plaka"), row.get("sofor_adi")


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
                f"https://api.telegram.org/bot{bot_token}/sendMessage",
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
    # 1. Anomaly var mı?
    anomaly = await db.get(Anomaly, payload.anomaly_id)
    if not anomaly:
        raise HTTPException(status_code=404, detail="Anomali bulunamadı")
    # 2. Mevcut investigation var mı? (unique constraint da yakalar)
    existing = (
        await db.execute(
            select(FuelInvestigation).where(
                FuelInvestigation.anomaly_id == payload.anomaly_id
            )
        )
    ).scalar_one_or_none()
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
    inv = FuelInvestigation(
        anomaly_id=payload.anomaly_id,
        status="open",
        suspicion_score=classification.suspicion_score,
        suspicion_level=classification.suspicion_level,
        notes=payload.initial_notes,
        created_by_user_id=creator_id,
        evidence_files=[],
    )
    db.add(inv)
    try:
        await db.flush()
        await db.refresh(inv)
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
    row = await _fetch_investigation_dict(db, int(inv.id))
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
    inv = await db.get(FuelInvestigation, inv_id)
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
        row = await _fetch_investigation_dict(db, inv_id)
        if row is None:
            raise HTTPException(status_code=404, detail="Soruşturma bulunamadı")
        return InvestigationResponse(**row)

    await db.execute(
        update(FuelInvestigation).where(FuelInvestigation.id == inv_id).values(**values)
    )
    await db.commit()

    await log_audit_event(
        module="theft",
        action="investigation_updated",
        entity_id=str(inv_id),
        old_value=old_value,
        new_value=values,
        user_id=current_admin.id,
    )

    row = await _fetch_investigation_dict(db, inv_id)
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
    inv = await db.get(FuelInvestigation, inv_id)
    if not inv:
        raise HTTPException(status_code=404, detail="Soruşturma bulunamadı")
    if inv.status == "closed":
        return  # idempotent

    await db.execute(
        update(FuelInvestigation)
        .where(FuelInvestigation.id == inv_id)
        .values(status="closed", closed_at=datetime.now(timezone.utc))
    )
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
    inv = await db.get(FuelInvestigation, inv_id)
    if not inv:
        raise HTTPException(status_code=404, detail="Soruşturma bulunamadı")
    anomaly = await db.get(Anomaly, inv.anomaly_id)
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
    await db.execute(
        update(FuelInvestigation)
        .where(FuelInvestigation.id == inv_id)
        .values(
            suspicion_score=classification.suspicion_score,
            suspicion_level=classification.suspicion_level,
        )
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
