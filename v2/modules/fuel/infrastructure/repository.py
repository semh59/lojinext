"""
TIR Yakıt Takip - Yakıt Repository
PostgreSQL CRUD + periyot yönetimi
"""

import threading
from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from typing import Any, Dict, List, Optional

from sqlalchemy import insert, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.base_repository import BaseRepository
from app.infrastructure.logging.logger import get_logger
from v2.modules.fuel.infrastructure.models import YakitAlimi, YakitPeriyot

logger = get_logger(__name__)


class YakitRepository(BaseRepository[YakitAlimi]):
    """Yakıt alımı veritabanı operasyonları (Async)"""

    model = YakitAlimi

    async def get_all(  # type: ignore[override]
        self,
        arac_id: Optional[int] = None,
        limit: int = 100,
        offset: int = 0,
        desc: bool = True,
        baslangic_tarih: Optional[date] = None,
        bitis_tarih: Optional[date] = None,
        include_inactive: bool = False,
        **filters: Any,
    ) -> Dict[str, Any]:
        """Yakıt alımlarını getir"""
        limit = max(1, min(int(limit or 100), self.MAX_LIMIT))
        offset = max(0, int(offset or 0))

        query = """
            SELECT ya.*, a.plaka
            FROM yakit_alimlari ya
            JOIN araclar a ON ya.arac_id = a.id
        """
        params: Dict[str, Any] = {}
        where_clauses = []

        if arac_id:
            where_clauses.append("ya.arac_id = :arac_id")
            params["arac_id"] = arac_id

        if not include_inactive:
            where_clauses.append("ya.aktif = TRUE")

        if baslangic_tarih:
            where_clauses.append("ya.tarih >= :baslangic_tarih")
            params["baslangic_tarih"] = baslangic_tarih

        if bitis_tarih:
            where_clauses.append("ya.tarih <= :bitis_tarih")
            params["bitis_tarih"] = bitis_tarih

        if where_clauses:
            query += " WHERE " + " AND ".join(where_clauses)

        # 2. Count Query (Total records for pagination)
        count_query = (
            "SELECT COUNT(*) FROM yakit_alimlari ya JOIN araclar a ON ya.arac_id = a.id"
        )
        if where_clauses:
            count_query += " WHERE " + " AND ".join(where_clauses)

        total_count = await self.execute_scalar(count_query, params)

        # 3. Data Query
        order_direction = "DESC" if desc else "ASC"
        assert order_direction in ("ASC", "DESC"), "Invalid order direction"
        query += f" ORDER BY ya.tarih {order_direction}, ya.km_sayac {order_direction} LIMIT :limit OFFSET :offset"
        params["limit"] = limit
        params["offset"] = offset

        records = await self.execute_query(query, params)
        return {"items": records, "total": total_count}

    async def add(
        self,
        tarih: date,
        arac_id: int,
        istasyon: Optional[str],
        fiyat: float,
        litre: float,
        km_sayac: int,
        fis_no: Optional[str] = None,
        depo_durumu: str = "Bilinmiyor",
        toplam_tutar: Optional[float] = None,
    ) -> int:
        """Yeni yakıt alımı ekle.

        Para hesabı (toplam = fiyat * litre) Decimal'de yapılır; float çarpımı
        ~7 işlemde 1'inde cent yuvarlama hatası verir (ör. 42.55 * 23.70 float'ta
        1008.43, Decimal'de 1008.44). Girdiler float ya da Decimal olabildiği
        için Decimal(str(...)) ile güvenli dönüştürülür.
        """
        # Eğer dışarıdan hesaplanmış geldiyse onu kullan, yoksa burada hesapla.
        toplam: Decimal = (
            Decimal(str(toplam_tutar))
            if toplam_tutar is not None and toplam_tutar > 0
            else (Decimal(str(fiyat)) * Decimal(str(litre))).quantize(
                Decimal("0.01"), rounding=ROUND_HALF_UP
            )
        )

        return await self.create(
            tarih=tarih,
            arac_id=arac_id,
            istasyon=istasyon,
            fiyat_tl=fiyat,
            litre=litre,
            toplam_tutar=toplam,
            km_sayac=km_sayac,
            fis_no=fis_no,
            depo_durumu=depo_durumu,
            durum="Bekliyor",
        )

    async def check_duplicate(self, arac_id: int, tarih: date, litre: float) -> bool:
        """Aynı araç, tarih ve miktar için kayıt var mı kontrol et"""
        query = """
            SELECT EXISTS(
                SELECT 1 FROM yakit_alimlari
                WHERE arac_id = :arac_id
                AND tarih = :tarih
                AND litre = :litre
                AND aktif = TRUE
            )
        """
        return bool(
            await self.execute_scalar(
                query, {"arac_id": arac_id, "tarih": tarih, "litre": litre}
            )
        )

    async def get_son_km(self, arac_id: int) -> Optional[int]:
        """Aracın son KM değerini getir"""
        query = """
            SELECT MAX(km_sayac) as son_km
            FROM yakit_alimlari
            WHERE arac_id = :arac_id AND aktif = TRUE
        """
        result = await self.execute_scalar(query, {"arac_id": arac_id})
        return int(result) if result is not None else None

    async def get_son_km_bulk(self, arac_ids: List[int]) -> Dict[int, int]:
        """Birden çok aracın son (MAX) KM değerini TEK sorguda getir.

        Toplu yakıt import'unda araç başına ``get_son_km`` çağırmak N+1 üretiyordu;
        bu metod tek GROUP BY sorgusuyla ``{arac_id: son_km}`` döner. Hiç (aktif)
        yakıt kaydı olmayan araç sözlükte yer almaz (çağıran ``.get(id, 0)`` ile
        okumalı).
        """
        if not arac_ids:
            return {}
        query = text(
            """
            SELECT arac_id, MAX(km_sayac) AS son_km
            FROM yakit_alimlari
            WHERE arac_id = ANY(:arac_ids) AND aktif = TRUE
            GROUP BY arac_id
            """
        )
        result = await self.session.execute(query, {"arac_ids": list(arac_ids)})
        return {
            row.arac_id: int(row.son_km)
            for row in result.fetchall()
            if row.son_km is not None
        }

    async def get_last_n_by_arac(
        self, arac_id: int, n: int = 5
    ) -> List[Dict[str, Any]]:
        """Aracın son N (aktif) yakıt kaydını km_sayac'a göre azalan sırayla getirir.

        Rolling outlier tespiti (``application/add_yakit.py``) için.
        """
        query = text(
            """
            SELECT litre, km_sayac FROM yakit_alimlari
            WHERE arac_id = :arac_id AND aktif = TRUE
            ORDER BY km_sayac DESC
            LIMIT :n
            """
        )
        result = await self.session.execute(query, {"arac_id": arac_id, "n": n})
        return [{"litre": r.litre, "km_sayac": r.km_sayac} for r in result.fetchall()]

    async def update_yakit(self, id: int, **kwargs: Any) -> bool:
        """Yakıt alımı güncelle"""
        allowed = [
            "tarih",
            "arac_id",
            "istasyon",
            "fiyat_tl",
            "litre",
            "km_sayac",
            "fis_no",
            "depo_durumu",
            "durum",
        ]

        updates = {k: v for k, v in kwargs.items() if k in allowed}

        # Recalculate toplam_tutar whenever fiyat_tl or litre changes.
        # Fetch missing value from DB so partial updates stay consistent.
        if "fiyat_tl" in updates or "litre" in updates:
            current = await self.get_by_id(id)
            cur_fiyat = current["fiyat_tl"] if current else 0
            cur_litre = current["litre"] if current else 0
            fiyat = Decimal(str(updates.get("fiyat_tl", cur_fiyat) or 0))
            litre = Decimal(str(updates.get("litre", cur_litre) or 0))
            updates["toplam_tutar"] = (fiyat * litre).quantize(
                Decimal("0.01"), rounding=ROUND_HALF_UP
            )

        return await self.update(id, **updates)

    # =========================================================================
    # YAKIT PERİYOTLARI
    # =========================================================================

    async def save_fuel_periods(
        self, periods: List[Any], clear_existing: bool = False
    ) -> int:
        """
        Yakıt periyotlarını toplu kaydet (Async).
        """
        if not periods:
            return 0

        session = self.session
        try:
            if clear_existing:
                arac_ids = set(p.arac_id for p in periods)
                for arac_id in arac_ids:
                    await session.execute(
                        text("DELETE FROM yakit_periyotlari WHERE arac_id = :arac_id"),
                        {"arac_id": arac_id},
                    )

            count = 0
            # Bulk Insert Data Preparation
            insert_data = []
            for p in periods:
                insert_data.append(
                    {
                        "arac_id": p.arac_id,
                        "alim1_id": p.alim1_id,
                        "alim2_id": p.alim2_id,
                        "alim1_tarih": p.alim1_tarih,
                        "alim2_tarih": p.alim2_tarih,
                        "alim1_km": p.alim1_km,
                        "alim2_km": p.alim2_km,
                        "alim1_litre": p.alim1_litre,
                        "ara_mesafe": p.ara_mesafe,
                        "toplam_yakit": p.toplam_yakit,
                        "ort_tuketim": p.ort_tuketim,
                        "durum": p.durum,
                    }
                )

            # Core Insert
            stmt = insert(YakitPeriyot).values(insert_data)

            # Execute Bulk Insert
            await session.execute(stmt)
            count = len(insert_data)

            logger.info(f"Saved {count} fuel periods (Bulk)")
            return count
        except Exception as e:
            raise e

    async def get_monthly_cost_trend(self, months: int = 12) -> List[Dict[str, Any]]:
        """Son N ay için aylık toplam yakıt maliyeti (ham TL toplamı).

        `ai_assistant/api/ai_routes.py::_fuel_trend_chart`'ın eski ham-SQL'i
        buraya taşındı (2026-07-17 dedektif denetimi — endpoint katmanı DB'ye
        doğrudan erişmemeli). Sorgu birebir aynı, davranış değişikliği yok.
        """
        query = """
            SELECT to_char(date_trunc('month', tarih), 'YYYY-MM') AS ay,
                   COALESCE(SUM(toplam_tutar), 0) AS tutar
            FROM yakit_alimlari
            WHERE tarih >= now() - make_interval(months => :months)
            GROUP BY 1 ORDER BY 1
        """
        return await self.execute_query(query, {"months": months})

    async def get_fuel_periods(
        self, arac_id: int, limit: int = 20
    ) -> List[Dict[str, Any]]:
        """Aracın yakıt periyotlarını getir"""
        query = """
            SELECT * FROM yakit_periyotlari
            WHERE arac_id = :arac_id
            ORDER BY alim2_tarih DESC
            LIMIT :limit
        """
        return await self.execute_query(query, {"arac_id": arac_id, "limit": limit})

    async def get_stats(
        self,
        baslangic_tarih: Optional[date] = None,
        bitis_tarih: Optional[date] = None,
    ) -> Dict[str, Any]:
        """Yakıt istatistiklerini getir (Gerçek L/100km Hesaplamalı)"""
        # 1. Toplam Yakıt ve Maliyet (YakitAlimi)
        fuel_query = """
            SELECT
                SUM(litre) as total_consumption,
                SUM(toplam_tutar) as total_cost,
                AVG(fiyat_tl) as avg_price
            FROM yakit_alimlari
            WHERE aktif = TRUE
        """
        params = {}
        if baslangic_tarih:
            fuel_query += " AND tarih >= :start"
            params["start"] = baslangic_tarih
        if bitis_tarih:
            fuel_query += " AND tarih <= :end"
            params["end"] = bitis_tarih

        fuel_rows = await self.execute_query(fuel_query, params)
        if fuel_rows and fuel_rows[0].get("total_consumption") is not None:
            fuel_stats = {
                "total_consumption": float(fuel_rows[0]["total_consumption"]),
                "total_cost": float(fuel_rows[0]["total_cost"]),
                "avg_price": float(fuel_rows[0]["avg_price"] or 0.0),
            }
        else:
            fuel_stats = {
                "total_consumption": 0.0,
                "total_cost": 0.0,
                "avg_price": 0.0,
            }

        # 2. Toplam Mesafe (Seferler) - L/100km için gerekli
        dist_query = "SELECT SUM(mesafe_km) as total_distance FROM seferler WHERE is_deleted = FALSE"
        dist_params = {}
        if baslangic_tarih:
            dist_query += " AND tarih >= :start"
            dist_params["start"] = baslangic_tarih
        if bitis_tarih:
            dist_query += " AND tarih <= :end"
            dist_params["end"] = bitis_tarih

        dist_rows = await self.execute_query(dist_query, dist_params)
        total_distance = (
            float(dist_rows[0].get("total_distance") or 0.0) if dist_rows else 0.0
        )

        # 3. L/100km Hesapla
        # Eğer mesafe 0 ise fallback olarak 0 döner.
        avg_consumption = 0.0
        if total_distance > 0:
            avg_consumption = (fuel_stats["total_consumption"] / total_distance) * 100

        return {
            "total_consumption": fuel_stats["total_consumption"],
            "total_cost": fuel_stats["total_cost"],
            "avg_consumption": avg_consumption,
            "avg_price": fuel_stats["avg_price"],
            "total_distance": total_distance,
        }

    async def get_by_date_range(
        self,
        start: Any,
        end: Any,
        arac_id: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """Tarih aralığına göre yakıt alımı listesi döner."""
        from datetime import date as _date

        def _to_date(v):
            return v if isinstance(v, _date) else _date.fromisoformat(str(v))

        params: Dict[str, Any] = {"start": _to_date(start), "end": _to_date(end)}
        where = "ya.tarih >= :start AND ya.tarih <= :end AND ya.aktif = TRUE"
        if arac_id is not None:
            where += " AND ya.arac_id = :arac_id"
            params["arac_id"] = arac_id
        sql = f"""
            SELECT ya.*, a.plaka
            FROM yakit_alimlari ya
            JOIN araclar a ON ya.arac_id = a.id
            WHERE {where}
            ORDER BY ya.tarih DESC
        """
        return await self.execute_query(sql, params)


_yakit_repo_lock = threading.Lock()
_yakit_repo: Optional[YakitRepository] = None


def get_yakit_repo(session: Optional[AsyncSession] = None) -> YakitRepository:
    """YakitRepo Provider. Eğer session verilirse yeni instance döner (UoW için)."""
    global _yakit_repo
    if session:
        return YakitRepository(session=session)
    with _yakit_repo_lock:
        if _yakit_repo is None:
            _yakit_repo = YakitRepository()
    return _yakit_repo
