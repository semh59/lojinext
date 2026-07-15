"""Use-case'ler: Feature B.2 yakıt hırsızlığı soruşturma yaşam döngüsü.

B.1/katman-disiplini düzeltmesi (2026-07-15, dalga-1-6+8 dedektif
denetiminde bulundu): ``api/investigation_routes.py``'nin TÜM endpoint'leri
`application/` katmanını atlayıp doğrudan
``get_investigation_repo(db)``/``get_anomaly_repo(session=db)`` çağırıyordu
— diğer modüllerdeki (fleet/notification/driver/auth_rbac) aynı dalgada
düzeltilen ihlalin dokümante edilmemiş bir tekrarı. Mekanik taşıma,
davranış değişikliği yok.

KRİTİK: bu dosyadaki fonksiyonlar çağıranın (route'un) ``SessionDep``
session'ını parametre olarak alır, kendi ``UnitOfWork``'ünü AÇMAZ —
``lock_investigation_for_update``'in ``SELECT ... FOR UPDATE`` kilidi ile
onu izleyen ``update_investigation_fields``/``db.commit()`` AYNI
transaction'da kalmalı (FOR-UPDATE invaryantı, bkz.
``v2/modules/anomaly/infrastructure/investigation_repository.py`` başlığı).
Commit/rollback çağrıları — pre-migration route'taki sırayla birebir
korunarak — burada, çağıranın session'ı üzerinde yapılır.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import Anomaly
from v2.modules.anomaly.application.classify_theft import get_fuel_theft_classifier
from v2.modules.anomaly.infrastructure.anomaly_repository import get_anomaly_repo
from v2.modules.anomaly.infrastructure.investigation_repository import (
    get_investigation_repo,
)
from v2.modules.anomaly.schemas import TheftClassification

_TERMINAL_STATUSES = {"closed"}


async def get_patterns(
    db: AsyncSession, days: int, min_count: int, limit: int
) -> List[Dict[str, Any]]:
    """Aynı (sofor, arac) için son N gün ≥min_count soruşturma → pattern."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    inv_repo = get_investigation_repo(db)
    return await inv_repo.get_investigation_patterns(cutoff, min_count, limit)


async def list_investigations(
    db: AsyncSession,
    days: int,
    limit: int,
    status: Optional[str] = None,
    suspicion_level: Optional[str] = None,
    assigned_to_user_id: Optional[int] = None,
) -> List[Dict[str, Any]]:
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    inv_repo = get_investigation_repo(db)
    return await inv_repo.list_investigations(
        cutoff,
        limit,
        status=status,
        suspicion_level=suspicion_level,
        assigned_to_user_id=assigned_to_user_id,
    )


async def get_investigation_detail(
    db: AsyncSession, inv_id: int
) -> Optional[Dict[str, Any]]:
    inv_repo = get_investigation_repo(db)
    return await inv_repo.get_investigation_detail(inv_id)


async def resolve_alarm_context(
    db: AsyncSession, anomaly: Anomaly
) -> Tuple[Optional[str], Optional[str]]:
    """Anomaly → (plaka, sofor_adi). Yoksa (None, None)."""
    inv_repo = get_investigation_repo(db)
    return await inv_repo.get_anomaly_alarm_context(int(anomaly.id))


async def create_investigation(
    db: AsyncSession,
    *,
    anomaly_id: int,
    initial_notes: Optional[str],
    creator_id: Optional[int],
) -> Tuple[Dict[str, Any], TheftClassification, Anomaly]:
    """Yeni soruşturma + auto-classify. Raises 404/409 HTTPException.

    Döner: (JOIN'li detay dict, classification, anomaly ORM nesnesi) —
    çağıran (route) classification+anomaly'yi OPS Telegram alarmı için
    kullanır.
    """
    anomaly_repo = get_anomaly_repo(session=db)
    inv_repo = get_investigation_repo(db)

    anomaly = await anomaly_repo.get_anomaly_by_id(anomaly_id)
    if not anomaly:
        raise HTTPException(status_code=404, detail="Anomali bulunamadı")
    existing = await inv_repo.get_investigation_by_anomaly_id(anomaly_id)
    if existing:
        raise HTTPException(
            status_code=409,
            detail="Bu anomali için zaten bir soruşturma var",
        )

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

    try:
        inv = await inv_repo.create_investigation_row(
            anomaly_id=anomaly_id,
            status="open",
            suspicion_score=classification.suspicion_score,
            suspicion_level=classification.suspicion_level,
            notes=initial_notes,
            creator_id=creator_id,
        )
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(
            status_code=409,
            detail="Bu anomali için zaten bir soruşturma var",
        ) from exc

    row = await inv_repo.get_investigation_detail(int(inv.id))
    if row is None:
        raise HTTPException(
            status_code=500, detail="Soruşturma oluşturuldu ama okunamadı"
        )
    return row, classification, anomaly


async def update_investigation(
    db: AsyncSession, inv_id: int, payload
) -> Tuple[Dict[str, Any], Dict[str, Any], Dict[str, Any]]:
    """PATCH iş kuralları. Raises 404/409 HTTPException.

    Döner: (güncel detay dict, old_value dict, new_value/values dict) —
    çağıran audit-log için old/new değerleri kullanır.
    """
    inv_repo = get_investigation_repo(db)
    # 2026-07-01 prod-grade denetimi P1 (Dalga 4 madde 18): SELECT ... FOR
    # UPDATE ile satır kilitlenir — eskiden kilitsiz okunuyordu (TOCTOU),
    # eşzamanlı iki PATCH'te geç kalan istek ilkinin commit'inden ÖNCE
    # okunan stale bir status'a göre karar verip diğerinin sonucunu sessizce
    # eziyordu.
    inv = await inv_repo.lock_investigation_for_update(inv_id)
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
        row = await inv_repo.get_investigation_detail(inv_id)
        if row is None:
            raise HTTPException(status_code=404, detail="Soruşturma bulunamadı")
        return row, old_value, values

    await inv_repo.update_investigation_fields(inv_id, values)
    await db.commit()

    row = await inv_repo.get_investigation_detail(inv_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Soruşturma bulunamadı")
    return row, old_value, values


async def soft_delete_investigation(db: AsyncSession, inv_id: int) -> bool:
    """Soruşturmayı 'closed' durumuna alır. Raises 404. Döner: idempotent mi (True=zaten kapalıydı)."""
    inv_repo = get_investigation_repo(db)
    inv = await inv_repo.get_investigation_by_id(inv_id)
    if not inv:
        raise HTTPException(status_code=404, detail="Soruşturma bulunamadı")
    if inv.status == "closed":
        return True  # idempotent, hiçbir şey yapmaya gerek yok

    await inv_repo.close_investigation(inv_id, datetime.now(timezone.utc))
    await db.commit()
    return False


async def reclassify_investigation(
    db: AsyncSession, inv_id: int
) -> TheftClassification:
    """Re-run classifier. Raises 404 HTTPException."""
    inv_repo = get_investigation_repo(db)
    anomaly_repo = get_anomaly_repo(session=db)
    inv = await inv_repo.get_investigation_by_id(inv_id)
    if not inv:
        raise HTTPException(status_code=404, detail="Soruşturma bulunamadı")
    anomaly = await anomaly_repo.get_anomaly_by_id(inv.anomaly_id)
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
    await inv_repo.update_investigation_classification(
        inv_id,
        classification.suspicion_score,
        classification.suspicion_level,
    )
    await db.commit()
    return classification
