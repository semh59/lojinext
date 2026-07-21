"""
TIR Yakıt Takip - Araç Repository
PostgreSQL CRUD operasyonları
"""

import threading
from typing import Any, Dict, List, Optional, cast

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.base_repository import BaseRepository
from app.infrastructure.logging.logger import get_logger
from v2.modules.fleet.infrastructure.models import Arac

logger = get_logger(__name__)


class AracRepository(BaseRepository[Arac]):
    """Araç veritabanı operasyonları (Async)"""

    model = Arac
    search_columns = ["plaka", "marka", "model"]

    async def get_all(  # type: ignore[override]
        self,
        sadece_aktif: bool = True,
        limit: int = 100,
        offset: int = 0,
        search: Optional[str] = None,
        filters: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Tüm araçları getir (Arama ve Sayfalama destekli).
        """
        _filters = filters.copy() if filters else {}
        if search:
            _filters["search"] = search

        return await self.get_all_with_stats_paged(
            limit=limit,
            offset=offset,
            search=search,
            filters=_filters,
            sadece_aktif=sadece_aktif,
        )

    async def count_all(
        self,
        sadece_aktif: bool = True,
        search: Optional[str] = None,
        filters: Optional[Dict[str, Any]] = None,
    ) -> int:
        """Filtrelere uyan toplam araç sayısını getir"""
        query = "SELECT COUNT(*) FROM araclar a WHERE 1=1 AND a.is_deleted = false"
        params = {}

        if sadece_aktif:
            query += " AND a.aktif = true"

        if search:
            query += " AND (a.plaka ILIKE :search OR a.marka ILIKE :search)"
            params["search"] = f"%{search}%"

        if filters:
            if "marka" in filters:
                query += " AND a.marka = :marka"
                params["marka"] = filters["marka"]
            if "model" in filters:
                query += " AND a.model = :model"
                params["model"] = filters["model"]
            if "yil_ge" in filters:
                query += " AND a.yil >= :yil_ge"
                params["yil_ge"] = filters["yil_ge"]
            if "yil_le" in filters:
                query += " AND a.yil <= :yil_le"
                params["yil_le"] = filters["yil_le"]

        return await self.execute_scalar(query, params) or 0

    async def count_active(self) -> int:
        """Aktif (soft-delete edilmemiş) araç sayısı."""
        query = "SELECT COUNT(*) FROM araclar WHERE aktif = TRUE AND is_deleted = FALSE"
        return await self.execute_scalar(query) or 0

    async def get_all_with_stats_paged(
        self,
        limit: int = 100,
        offset: int = 0,
        search: Optional[str] = None,
        filters: Optional[Dict[str, Any]] = None,
        sadece_aktif: bool = True,
    ) -> List[Dict[str, Any]]:
        """
        Araçları istatistikleriyle (KM, Tüketim) beraber getirir.
        N+1 problemini çözer.
        """
        # Base Query
        query = """
            SELECT
                a.*,
                COALESCE(SUM(s.mesafe_km), 0) as toplam_km,
                COUNT(s.id) as toplam_sefer,
                COALESCE(AVG(s.tuketim), 0.0) as ort_tuketim,
                (SELECT COUNT(*) FROM arac_bakimlari b
                 WHERE b.arac_id = a.id AND b.tamamlandi = false
                   AND b.bakim_tipi IN ('ARIZA', 'ACIL')) as acik_ariza
            FROM araclar a
            LEFT JOIN seferler s ON a.id = s.arac_id AND s.tuketim IS NOT NULL
            WHERE 1=1
        """

        params: Dict[str, Any] = {}

        # Soft-delete filter — always exclude logically deleted vehicles
        query += " AND a.is_deleted = false"

        # Filters
        if sadece_aktif:
            query += " AND a.aktif = true"

        if search:
            query += " AND (a.plaka ILIKE :search OR a.marka ILIKE :search)"
            params["search"] = f"%{search}%"

        if filters:
            if "marka" in filters:
                query += " AND a.marka = :marka"
                params["marka"] = filters["marka"]
            if "model" in filters:
                query += " AND a.model = :model"
                params["model"] = filters["model"]
            if "yil_ge" in filters:
                query += " AND a.yil >= :yil_ge"
                params["yil_ge"] = filters["yil_ge"]
            if "yil_le" in filters:
                query += " AND a.yil <= :yil_le"
                params["yil_le"] = filters["yil_le"]

        # Group By & Order & Limit
        query += """
            GROUP BY a.id
            ORDER BY a.plaka ASC
            LIMIT :limit OFFSET :offset
        """

        params["limit"] = limit
        params["offset"] = offset

        return await self.execute_query(query, params)

    async def get_by_plaka(
        self, plaka: str, for_update: bool = False
    ) -> Optional[Dict[str, Any]]:
        """Plaka ile araç getir"""
        session = self.session
        stmt = select(self.model).where(self.model.plaka == plaka)
        if for_update:
            stmt = stmt.with_for_update()
        result = await session.execute(stmt)
        obj = result.scalar_one_or_none()
        if not obj:
            return None
        d = obj.__dict__.copy()
        d.pop("_sa_instance_state", None)
        return d

    async def add(
        self,
        plaka: str,
        marka: str,
        model: str = "",
        yil: int = 2020,
        tank_kapasitesi: int = 600,
        hedef_tuketim: float = 32.0,
        bos_agirlik_kg: float = 8000.0,
        hava_direnc_katsayisi: float = 0.7,
        on_kesit_alani_m2: float = 8.5,
        motor_verimliligi: float = 0.38,
        lastik_direnc_katsayisi: float = 0.007,
        maks_yuk_kapasitesi_kg: int = 26000,
        notlar: str = "",
        muayene_tarihi: Optional[Any] = None,
        sigorta_tarihi: Optional[Any] = None,
        motor_no: Optional[str] = None,
        sasi_no: Optional[str] = None,
        aktif: bool = True,
    ) -> Arac:
        """Yeni araç ekle.

        Duplicate'e karşı GERÇEK guard ``UNIQUE(plaka)`` constraint'idir:
        eşzamanlı iki insert'te kaybeden ``IntegrityError`` alır (endpoint 400'e
        map'ler). Aşağıdaki ``SELECT ... FOR UPDATE`` yalnızca yaygın (sıralı)
        durumda dostça erken hata veren bir fast-path'tir — satır henüz YOKKEN
        kilitleyecek bir şey olmadığından phantom-insert race'ini TEK BAŞINA
        önlemez.
        """
        session = self.session
        logger.debug(f"[AracRepository.add] Using session {id(session)}")
        # Fast-path: kayıt zaten varsa dostça hata. Mevcut satırı kilitler;
        # yoksa no-op (asıl koruma UNIQUE constraint'te).
        stmt = select(self.model).where(self.model.plaka == plaka).with_for_update()
        result = await session.execute(stmt)
        if result.scalar_one_or_none():
            logger.warning(f"TOCTOU Alert: Araç zaten mevcut ({plaka})")
            raise ValueError(f"Bu plaka ile araç zaten kayıtlı: {plaka}")

        # 2. Kaydı oluştur (ORM implementation for visibility)
        new_arac = self.model(
            plaka=plaka,
            marka=marka,
            model=model,
            yil=yil,
            tank_kapasitesi=tank_kapasitesi,
            hedef_tuketim=hedef_tuketim,
            bos_agirlik_kg=bos_agirlik_kg,
            hava_direnc_katsayisi=hava_direnc_katsayisi,
            on_kesit_alani_m2=on_kesit_alani_m2,
            motor_verimliligi=motor_verimliligi,
            lastik_direnc_katsayisi=lastik_direnc_katsayisi,
            maks_yuk_kapasitesi_kg=maks_yuk_kapasitesi_kg,
            notlar=notlar,
            aktif=aktif,
            muayene_tarihi=muayene_tarihi,
            sigorta_tarihi=sigorta_tarihi,
            motor_no=motor_no,
            sasi_no=sasi_no,
        )
        session.add(new_arac)
        await session.flush()
        return new_arac

    async def get_arac_with_stats(self, arac_id: int) -> Optional[Dict[str, Any]]:
        """Araç bilgisi + istatistikler"""
        query = """
            SELECT
                a.id as arac_id,
                a.plaka,
                a.marka,
                a.model,
                a.yil,
                a.aktif,
                COUNT(s.id) as toplam_sefer,
                COALESCE(SUM(s.mesafe_km), 0) as toplam_km,
                COALESCE(SUM(s.tuketim), 0) as toplam_yakit,
                COALESCE(AVG(s.tuketim), 0.0) as ort_tuketim
            FROM araclar a
            LEFT JOIN seferler s ON a.id = s.arac_id AND s.tuketim IS NOT NULL
                AND s.is_deleted = False
            WHERE a.id = :arac_id
            GROUP BY a.id, a.plaka, a.marka, a.model, a.yil, a.aktif
        """
        rows = await self.execute_query(query, {"arac_id": arac_id})
        return rows[0] if rows else None

    async def get_aktif_plakalar(self) -> List[str]:
        """Aktif araç plakalarını getir"""
        query = "SELECT plaka FROM araclar WHERE aktif = true ORDER BY plaka"
        rows = await self.execute_query(query)
        return [str(row["plaka"]) for row in rows]

    async def get_plaka_id_map(self) -> dict[str, tuple[int, bool]]:
        """Tüm araçlar (aktif+pasif) için {plaka: (id, aktif)} haritası döner.

        bulk_add_vehicles'ta reaktivasyon kararı için kullanılır.
        """
        query = "SELECT id, plaka, aktif FROM araclar WHERE is_deleted = FALSE"
        rows = await self.execute_query(query)
        return {str(r["plaka"]): (int(r["id"]), bool(r["aktif"])) for r in rows}

    async def get_maintenance_candidates(self) -> Dict[str, Any]:
        """
        Bakım ihtiyacı olan araçları getir (Çok kriterli, kural tabanlı).
        Kriterler:
        1. Araç yaşı > 15 yıl
        2. Ort. tüketim > 35 L/100km
        3. Toplam sefer km > 500,000
        4. Son bakım > 365 gün önce (veya hiç bakım kaydı yok)
        Severity: 3+ kriter = critical, 2 = high, 1 = medium

        Her aday'ın "reason_codes" alanı [{"code": str, "params": dict}, ...]
        şeklinde döner (önceden tek bir önceden-Türkçeleştirilmiş "reason"
        string'iydi) — frontend'in her dile göre kendi formatlayıp
        birleştirmesi için. code değerleri: old_vehicle, high_consumption,
        high_mileage, no_maintenance_record, overdue_maintenance.
        """
        query = """
            SELECT
                a.id,
                a.plaka,
                a.marka,
                a.model,
                a.yil,
                COALESCE(AVG(s.tuketim), 0.0)   AS ort_tuketim,
                COALESCE(SUM(s.mesafe_km), 0)   AS toplam_km,
                MAX(b.bakim_tarihi)              AS son_bakim
            FROM araclar a
            LEFT JOIN seferler s  ON a.id = s.arac_id  AND s.is_deleted = FALSE
            LEFT JOIN arac_bakimlari b ON a.id = b.arac_id AND b.tamamlandi = TRUE  -- sadece tamamlanmış bakımlar
            WHERE a.aktif = TRUE AND a.is_deleted = FALSE
            GROUP BY a.id, a.plaka, a.marka, a.model, a.yil
            HAVING
                (EXTRACT(YEAR FROM NOW()) - a.yil) > 15
                OR AVG(s.tuketim) > 35
                OR COALESCE(SUM(s.mesafe_km), 0) > 500000
                OR MAX(b.bakim_tarihi) < NOW() - INTERVAL '365 days'
                OR (
                    MAX(b.bakim_tarihi) IS NULL
                    AND (EXTRACT(YEAR FROM NOW()) - a.yil) >= 1
                )
            ORDER BY ort_tuketim DESC
            LIMIT 10
        """
        rows = await self.execute_query(query)

        from datetime import date as _date
        from datetime import datetime as _datetime
        from datetime import timezone as _tz

        current_year = _date.today().year
        now = _datetime.now(_tz.utc)

        candidates = []
        for row in rows:
            # Structured (code, params) instead of a pre-formatted Turkish
            # sentence — lets the frontend translate/format per the active
            # UI language instead of always showing Turkish text.
            reason_codes: List[Dict[str, Any]] = []
            age = current_year - (row["yil"] or current_year)

            if age > 15:
                reason_codes.append({"code": "old_vehicle", "params": {"age": age}})
            if row["ort_tuketim"] > 35:
                reason_codes.append(
                    {
                        "code": "high_consumption",
                        "params": {"value": round(float(row["ort_tuketim"]), 1)},
                    }
                )
            if row["toplam_km"] > 500_000:
                reason_codes.append(
                    {"code": "high_mileage", "params": {"km": int(row["toplam_km"])}}
                )

            son_bakim = row["son_bakim"]
            if son_bakim is None:
                # 1 yıldan taze araçlar için "hiç bakım kaydı yok" henüz
                # anlamlı bir sinyal değil — ilk periyodik bakım vadesi
                # (overdue_maintenance ile aynı 365 gün eşiği) daha
                # dolmamış olabilir. Eşiksiz haliyle sıfır km'li yepyeni
                # bir araç bile sürekli "bakım adayı" görünüyordu.
                if age >= 1:
                    reason_codes.append({"code": "no_maintenance_record", "params": {}})
            elif hasattr(son_bakim, "tzinfo"):
                if son_bakim.tzinfo is None:
                    son_bakim = son_bakim.replace(tzinfo=_tz.utc)
                days_since = (now - son_bakim).days
                if days_since > 365:
                    reason_codes.append(
                        {
                            "code": "overdue_maintenance",
                            "params": {"days": days_since},
                        }
                    )

            if not reason_codes:
                continue

            criterion_count = len(reason_codes)
            if criterion_count >= 3:
                severity = "critical"
            elif criterion_count == 2:
                severity = "high"
            else:
                severity = "medium"

            candidates.append(
                {
                    "id": row["id"],
                    "plaka": row["plaka"],
                    "reason_codes": reason_codes,
                    "severity": severity,
                    "toplam_km": int(row["toplam_km"]),
                    "ort_tuketim": round(float(row["ort_tuketim"]), 1),
                }
            )

        urgent_count = sum(
            1 for c in candidates if c["severity"] in ("high", "critical")
        )
        warning_count = len(candidates) - urgent_count

        return {
            "urgent_count": urgent_count,
            "warning_count": warning_count,
            "vehicles": candidates,
        }

    async def get_eligible_for_planning(
        self, *, trip_date, limit: int = 10
    ) -> List[Dict[str, Any]]:
        """Feature C — sefer planlama wizard'ı için uygun araç adayları.

        Hard filter:
          - aktif=TRUE, is_deleted=FALSE
          - muayene_tarihi NULL veya >= trip_date
          - Aynı tarihte 'Planned' (açık) sefer yok (çakışma)
        Ek alanlar:
          - has_open_maintenance_alert: arac_bakimlari WHERE tamamlandi=FALSE
          - recent_trip_count: son 7 günde başlayan/devam eden sefer sayısı

        Sıralama: önce az kullanılanlar (recent_trip_count ASC).
        """
        query = """
            SELECT
                a.id,
                a.plaka,
                a.marka,
                a.model,
                a.yil,
                EXISTS (
                    SELECT 1 FROM arac_bakimlari ab
                    WHERE ab.arac_id = a.id AND ab.tamamlandi = FALSE
                ) AS has_open_maintenance_alert,
                (
                    SELECT COUNT(*)::int FROM seferler s2
                    WHERE s2.arac_id = a.id
                      AND s2.is_deleted = FALSE
                      AND s2.tarih >= (CAST(:trip_date AS DATE) - INTERVAL '7 days')
                      AND s2.tarih <= CAST(:trip_date AS DATE)
                ) AS recent_trip_count
            FROM araclar a
            WHERE a.aktif = TRUE
              AND a.is_deleted = FALSE
              AND (a.muayene_tarihi IS NULL OR a.muayene_tarihi >= CAST(:trip_date AS DATE))
              AND NOT EXISTS (
                  SELECT 1 FROM seferler s
                  WHERE s.arac_id = a.id
                    AND s.is_deleted = FALSE
                    AND s.tarih = CAST(:trip_date AS DATE)
                    AND s.durum IN ('Planned')
              )
            ORDER BY recent_trip_count ASC, a.id DESC
            LIMIT :limit
        """
        return await self.execute_query(
            query, {"trip_date": trip_date, "limit": int(limit)}
        )

    async def hard_delete_all(self) -> int:
        """Tüm araçları tamamen sil (Tehlikeli!)"""
        session = self.session
        try:
            stmt = delete(self.model)
            result = await session.execute(stmt)
            await session.flush()
            return int(cast("Any", result).rowcount)
        except Exception as e:
            logger.error(f"Bulk delete error for vehicles: {e}")
            raise e

    async def get_fleet_stats(self) -> Dict[str, Any]:
        """Araç filosu genel istatistikleri (toplam, aktif, muayene uyarısı)."""
        query = """
            SELECT
                COUNT(*)                                                                              AS total,
                COUNT(*) FILTER (WHERE aktif = true)                                                  AS active,
                COUNT(*) FILTER (WHERE muayene_tarihi IS NOT NULL
                                    AND muayene_tarihi >= CURRENT_DATE
                                    AND muayene_tarihi <= CURRENT_DATE + INTERVAL '30 days')          AS inspection_expiring,
                COUNT(*) FILTER (WHERE muayene_tarihi IS NOT NULL
                                    AND muayene_tarihi < CURRENT_DATE)                                AS inspection_overdue
            FROM araclar
        """  # noqa: E501
        rows = await self.execute_query(query)
        return dict(rows[0]) if rows else {}

    async def get_inspection_alerts(
        self, within_days: int
    ) -> Dict[str, List[Dict[str, Any]]]:
        """Muayenesi yaklaşan (``expiring``) veya geçmiş (``overdue``) araçlar."""
        query = """
            SELECT
                id,
                plaka,
                marka,
                model,
                yil,
                muayene_tarihi,
                CASE
                    WHEN muayene_tarihi < CURRENT_DATE THEN 'overdue'
                    ELSE 'expiring'
                END AS bucket,
                (muayene_tarihi - CURRENT_DATE) AS days_remaining
            FROM araclar
            WHERE aktif = TRUE
              AND is_deleted = FALSE
              AND muayene_tarihi IS NOT NULL
              AND (
                  muayene_tarihi < CURRENT_DATE
                  OR muayene_tarihi <= CURRENT_DATE + (:within_days || ' days')::interval
              )
            ORDER BY muayene_tarihi ASC
        """
        rows = await self.execute_query(query, {"within_days": str(within_days)})

        expiring: List[Dict[str, Any]] = []
        overdue: List[Dict[str, Any]] = []
        for row in rows:
            item = {
                "id": row["id"],
                "plaka": row["plaka"],
                "marka": row["marka"],
                "model": row["model"],
                "yil": row["yil"],
                "muayene_tarihi": row["muayene_tarihi"].isoformat()
                if row["muayene_tarihi"]
                else None,
                "days_remaining": int(row["days_remaining"])
                if row["days_remaining"] is not None
                else None,
            }
            (overdue if row["bucket"] == "overdue" else expiring).append(item)
        return {"expiring": expiring, "overdue": overdue}

    async def get_vehicle_events(
        self, arac_id: int, limit: int = 20
    ) -> List[Dict[str, Any]]:
        """Araç olay geçmişini getir (son N kayıt), `vehicle_event_log`'dan."""
        query = """
            SELECT id, arac_id, event_type, old_status, new_status, triggered_by, details, created_at
            FROM vehicle_event_log
            WHERE arac_id = :arac_id
            ORDER BY created_at DESC
            LIMIT :limit
        """  # noqa: E501
        rows = await self.execute_query(query, {"arac_id": arac_id, "limit": limit})
        return [
            {
                "id": row["id"],
                "event_type": row["event_type"],
                "old_status": row["old_status"],
                "new_status": row["new_status"],
                "triggered_by": row["triggered_by"],
                "details": row["details"],
                "created_at": row["created_at"].isoformat()
                if row["created_at"]
                else None,
            }
            for row in rows
        ]

    async def get_by_ids(self, ids: List[int]) -> Dict[int, Arac]:
        """Fetch multiple vehicles by IDs in a single query (N+1 optimization)."""
        if not ids:
            return {}
        query = select(Arac).where(Arac.id.in_(ids)).where(~Arac.is_deleted)
        result = await self.session.execute(query)
        vehicles = result.scalars().all()
        return {v.id: v for v in vehicles}


_arac_repo_lock = threading.Lock()
_arac_repo: Optional[AracRepository] = None


def get_arac_repo(session: Optional[AsyncSession] = None) -> AracRepository:
    """AracRepo Provider. Eğer session verilirse yeni instance döner (UoW için)."""
    global _arac_repo
    if session:
        return AracRepository(session=session)
    with _arac_repo_lock:
        if _arac_repo is None:
            _arac_repo = AracRepository()
    return _arac_repo
