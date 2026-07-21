"""Investigation repository — ``fuel_investigations`` tablosunun tek sahibi.

dalga 8 taşıması: ``app/database/repositories/analiz_repo.py``'den 11
soruşturma metodu birebir taşındı (davranış değişikliği yok).

KRİTİK İNVARYANT (görev dosyası TASKS/modules/anomaly.md madde 6):
``lock_investigation_for_update`` + ``update_investigation_fields`` +
``close_investigation`` AYNI dosyada, taşımadan önceki sırayla kalmalı —
FOR-UPDATE satır kilidi bir transaction sınırıdır, bu üç metodun scope'u
bölünürse eşzamanlı PATCH/DELETE arasındaki TOCTOU koruması (2026-07-01
prod-grade denetimi P1, dalga 4 madde 18) kırılır.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import select, text, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.base_repository import BaseRepository
from v2.modules.anomaly.infrastructure.models import FuelInvestigation

_INVESTIGATION_JOIN_SQL = """
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


class InvestigationRepository(BaseRepository[FuelInvestigation]):
    """``fuel_investigations`` tablosu üzerinde CRUD + FOR-UPDATE akışı (Async)."""

    model = FuelInvestigation

    async def get_investigation_detail(self, inv_id: int) -> Optional[Dict[str, Any]]:
        """Tek soruşturma kaydı, plaka/şoför JOIN'li (decrypt edilmiş)."""
        from app.infrastructure.security.pii_encryption import decrypt_pii_or

        sql = _INVESTIGATION_JOIN_SQL + " AND fi.id = :id LIMIT 1"
        row = (
            (await self.session.execute(text(sql), {"id": inv_id}))
            .mappings()
            .one_or_none()
        )
        if row is None:
            return None
        result = dict(row)
        result["sofor_adi"] = decrypt_pii_or(result.get("sofor_adi"))
        return result

    async def get_investigation_patterns(
        self, cutoff: datetime, min_count: int, limit: int
    ) -> List[Dict[str, Any]]:
        """Aynı (sofor, arac) için tekrarlayan yüksek şüpheli olay pattern'i."""
        from app.infrastructure.security.pii_encryption import decrypt_pii_or

        sql = """
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
        rows = (
            (
                await self.session.execute(
                    text(sql),
                    {"cutoff": cutoff, "min_count": min_count, "limit": limit},
                )
            )
            .mappings()
            .all()
        )
        result_rows = []
        for r in rows:
            d = dict(r)
            d["sofor_adi"] = decrypt_pii_or(d.get("sofor_adi"))
            result_rows.append(d)
        return result_rows

    async def list_investigations(
        self,
        cutoff: datetime,
        limit: int,
        status: Optional[str] = None,
        suspicion_level: Optional[str] = None,
        assigned_to_user_id: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """Filtrelenmiş soruşturma listesi, plaka/şoför JOIN'li (decrypt edilmiş)."""
        from app.infrastructure.security.pii_encryption import decrypt_pii_or

        sql = _INVESTIGATION_JOIN_SQL
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

        rows = (await self.session.execute(text(sql), params)).mappings().all()
        result_rows = []
        for r in rows:
            d = dict(r)
            d["sofor_adi"] = decrypt_pii_or(d.get("sofor_adi"))
            result_rows.append(d)
        return result_rows

    async def get_anomaly_alarm_context(
        self, anomaly_id: int
    ) -> "tuple[Optional[str], Optional[str]]":
        """Anomaly -> (plaka, sofor_adi) OPS alarm bildirimi için. Yoksa (None, None)."""
        from app.infrastructure.security.pii_encryption import decrypt_pii_or

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
            (await self.session.execute(text(sql), {"aid": int(anomaly_id)}))
            .mappings()
            .one_or_none()
        )
        if row is None:
            return None, None
        return row.get("plaka"), decrypt_pii_or(row.get("sofor_adi"))

    async def get_investigation_by_anomaly_id(
        self, anomaly_id: int
    ) -> Optional[FuelInvestigation]:
        """Bir anomaliye ait mevcut soruşturmayı getirir (varsa)."""
        result = await self.session.execute(
            select(FuelInvestigation).where(FuelInvestigation.anomaly_id == anomaly_id)
        )
        return result.scalar_one_or_none()

    async def create_investigation_row(
        self,
        *,
        anomaly_id: int,
        status: str,
        suspicion_score: float,
        suspicion_level: str,
        notes: Optional[str],
        creator_id: Optional[int],
    ) -> FuelInvestigation:
        """Yeni FuelInvestigation ekler + flush/refresh eder.

        Commit/rollback çağıranın sorumluluğunda (unique-constraint
        IntegrityError'ı flush anında fırlatır, çağıran yakalayıp
        rollback + 409 döner).
        """
        inv = FuelInvestigation(
            anomaly_id=anomaly_id,
            status=status,
            suspicion_score=suspicion_score,
            suspicion_level=suspicion_level,
            notes=notes,
            created_by_user_id=creator_id,
            evidence_files=[],
        )
        self.session.add(inv)
        await self.session.flush()
        await self.session.refresh(inv)
        return inv

    async def lock_investigation_for_update(
        self, inv_id: int
    ) -> Optional[FuelInvestigation]:
        """FuelInvestigation'ı ``SELECT ... FOR UPDATE`` ile satır kilidiyle getirir.

        2026-07-01 prod-grade denetimi P1 (Dalga 4 madde 18): eskiden
        kilitsiz okunuyordu (TOCTOU) — eşzamanlı iki PATCH'te geç kalan
        istek ilkinin commit'inden ÖNCE okunan stale bir status'a göre
        karar verip diğerinin sonucunu sessizce eziyordu.
        """
        result = await self.session.execute(
            select(FuelInvestigation)
            .where(FuelInvestigation.id == inv_id)
            .with_for_update()
        )
        return result.scalar_one_or_none()

    async def get_investigation_by_id(self, inv_id: int) -> Optional[FuelInvestigation]:
        """Tek FuelInvestigation kaydını ORM nesnesi olarak getirir."""
        return await self.session.get(FuelInvestigation, inv_id)

    async def update_investigation_fields(
        self, inv_id: int, values: Dict[str, Any]
    ) -> None:
        """FuelInvestigation satırını verilen alanlarla günceller (PATCH)."""
        await self.session.execute(
            update(FuelInvestigation)
            .where(FuelInvestigation.id == inv_id)
            .values(**values)
        )

    async def close_investigation(self, inv_id: int, closed_at: datetime) -> None:
        """Soruşturmayı 'closed' durumuna alır (soft delete)."""
        await self.session.execute(
            update(FuelInvestigation)
            .where(FuelInvestigation.id == inv_id)
            .values(status="closed", closed_at=closed_at)
        )

    async def update_investigation_classification(
        self, inv_id: int, suspicion_score: float, suspicion_level: str
    ) -> None:
        """Yeniden sınıflandırma sonucu skor/seviyeyi günceller."""
        await self.session.execute(
            update(FuelInvestigation)
            .where(FuelInvestigation.id == inv_id)
            .values(suspicion_score=suspicion_score, suspicion_level=suspicion_level)
        )


def get_investigation_repo(session: AsyncSession) -> InvestigationRepository:
    """InvestigationRepo Provider. Her zaman request-scoped session ister.

    (analiz_repo'daki `get_analiz_repo`'nun tersine burada session-parametresi
    OPSİYONEL DEĞİL — investigations.py endpoint'lerinin tamamı zaten
    ``SessionDep``'ten gelen bir session ile çağırıyordu, singleton fallback'e
    hiç ihtiyaç yok; sessizce yanlış bir global session'a düşme riski taşımaz.)
    """
    return InvestigationRepository(session=session)
