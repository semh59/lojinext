"""Anomaly CRUD repository — ``anomalies`` tablosunun tek sahibi.

dalga 8 taşıması: ``app/database/repositories/analiz_repo.py``'den
``bulk_create_anomalies``/``get_anomalies_filtered``/``get_anomaly_by_id``/
``update_anomaly`` metodları birebir taşındı (davranış değişikliği yok).
"""

import threading
from typing import Any, Dict, List, Optional

from sqlalchemy import text, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.base_repository import BaseRepository
from app.infrastructure.logging.logger import get_logger
from v2.modules.anomaly.infrastructure.models import Anomaly

logger = get_logger(__name__)


class AnomalyRepository(BaseRepository[Anomaly]):
    """``anomalies`` tablosu üzerinde CRUD (Async)."""

    model = Anomaly

    async def bulk_create_anomalies(self, payloads: List[Dict[str, Any]]) -> int:
        """AnomalyDetector'ın heuristic/ML anomali sonuçlarını toplu yazar.

        ``AnomalyDetector.save_anomalies`` için yazma tarafı — gerçek sayısal
        sapma (deger/beklenen_deger/sapma_yuzde) ve RCA alanları taşınır.
        Eklenen satır sayısını döner.
        """
        if not payloads:
            return 0
        try:
            await self.session.execute(insert(Anomaly), payloads)
            if self._session is None:
                await self.session.commit()
            return len(payloads)
        except Exception:
            if self._session is None:
                await self.session.rollback()
            raise

    async def get_anomalies_filtered(
        self,
        days: int,
        severity: Optional[str] = None,
        status: Optional[str] = None,
        sofor_id: Optional[int] = None,
    ) -> List[Dict]:
        """Sürücü/araç adı zenginleştirilmiş, filtrelenmiş anomali listesi.

        ``AnomalyDetector.get_anomalies`` (T7 anomali eylem akışı) için tek
        sorgu — kaynak_tip='sefer'/'arac' ayrımına göre sofor/arac join'i.
        """
        sql = """
            SELECT
                a.*,
                sf.sofor_id as sofor_id,
                COALESCE(s.ad_soyad, 'Bilinmiyor') as sofor_adi,
                COALESCE(v.plaka, 'Bilinmiyor') as plaka
            FROM anomalies a
            LEFT JOIN seferler sf ON a.kaynak_tip = 'sefer' AND a.kaynak_id = sf.id
            LEFT JOIN soforler s ON sf.sofor_id = s.id
            LEFT JOIN araclar v ON (a.kaynak_tip = 'arac' AND a.kaynak_id = v.id) OR (a.kaynak_tip = 'sefer' AND sf.arac_id = v.id)
            WHERE a.tarih >= CURRENT_DATE - (:days || ' days')::interval
        """  # noqa: E501
        params: Dict[str, Any] = {"days": str(days)}

        if severity:
            sql += " AND a.severity = :sev"
            params["sev"] = severity

        if status == "open":
            sql += " AND a.acknowledged_at IS NULL AND a.resolved_at IS NULL"
        elif status == "acknowledged":
            sql += " AND a.acknowledged_at IS NOT NULL AND a.resolved_at IS NULL"
        elif status == "resolved":
            sql += " AND a.resolved_at IS NOT NULL"

        if sofor_id is not None:
            sql += " AND sf.sofor_id = :sofor_id"
            params["sofor_id"] = sofor_id

        sql += " ORDER BY a.tarih DESC"

        from app.infrastructure.security.pii_encryption import decrypt_pii_or

        result = await self.session.execute(text(sql), params)
        rows = [dict(row._mapping) for row in result.fetchall()]
        for row in rows:
            row["sofor_adi"] = decrypt_pii_or(row.get("sofor_adi"))
        return rows

    async def get_anomaly_by_id(self, anomaly_id: int) -> Optional[Anomaly]:
        """Tek anomali kaydını ORM nesnesi olarak getirir (acknowledge/resolve için)."""
        return await self.session.get(Anomaly, anomaly_id)

    async def update_anomaly(self, anomaly_id: int, **values: Any) -> None:
        """Anomali satırını verilen alanlarla günceller (acknowledge/resolve)."""
        await self.session.execute(
            update(Anomaly).where(Anomaly.id == anomaly_id).values(**values)
        )


_anomaly_repo_lock = threading.Lock()
_anomaly_repo: Optional[AnomalyRepository] = None


def get_anomaly_repo(session: Optional[AsyncSession] = None) -> AnomalyRepository:
    """AnomalyRepo Provider. Eğer session verilirse yeni instance döner (UoW için)."""
    global _anomaly_repo
    if session:
        return AnomalyRepository(session=session)
    with _anomaly_repo_lock:
        if _anomaly_repo is None:
            _anomaly_repo = AnomalyRepository()
    return _anomaly_repo
