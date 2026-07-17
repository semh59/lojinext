"""
TIR Yakıt Takip - Lokasyon Repository
Lokasyon/güzergah CRUD operasyonları
"""

import difflib
import threading
from typing import Any, Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database.base_repository import BaseRepository
from app.database.models import Lokasyon
from app.infrastructure.logging.logger import get_logger

logger = get_logger(__name__)


class LokasyonRepository(BaseRepository[Lokasyon]):
    """Lokasyon/güzergah veritabanı operasyonları (Async)"""

    model = Lokasyon
    search_columns = ["cikis_yeri", "varis_yeri", "notlar"]

    async def get_all(self, **kwargs) -> List[Dict]:  # type: ignore[override]
        """Tüm lokasyonları getir"""
        order_by = kwargs.pop("order_by", "cikis_yeri asc, varis_yeri asc")
        limit = kwargs.pop("limit", 200)
        include_inactive = kwargs.pop("include_inactive", True)

        return await super().get_all(
            order_by=order_by, limit=limit, include_inactive=include_inactive, **kwargs
        )

    async def get_by_route(self, cikis: str, varis: str) -> Optional[Dict]:
        """Çıkış ve varış noktasına göre güzergah getir (Case Insensitive)"""
        session = self.session
        from sqlalchemy import func

        # Neutralize dotted/dotless i for Turkish resilience
        def neutralize_sql(col):
            return func.replace(func.replace(func.lower(col), "İ", "i"), "ı", "i")

        stmt = select(self.model).where(
            neutralize_sql(self.model.cikis_yeri) == neutralize_sql(cikis),
            neutralize_sql(self.model.varis_yeri) == neutralize_sql(varis),
        )
        result = await session.execute(stmt)
        obj = result.scalar_one_or_none()
        return self._to_dict(obj)

    async def get_all_route_keys(self) -> List[Dict]:
        """Tüm güzergahların id/aktif/çıkış-varış'ını TEK sorguda döner.

        N+1 önleme (Sentry LOJINEXT-17A): ``import_routes`` toplu Excel
        akışı, her satır için ayrı ``get_by_route`` SELECT'i atmak yerine
        bunu bir kez çağırıp bellek-içi index kurar.
        """
        stmt = select(
            self.model.id,
            self.model.aktif,
            self.model.cikis_yeri,
            self.model.varis_yeri,
        )
        result = await self.session.execute(stmt)
        return [
            {
                "id": row.id,
                "aktif": row.aktif,
                "cikis_yeri": row.cikis_yeri,
                "varis_yeri": row.varis_yeri,
            }
            for row in result
        ]

    async def get_benzersiz_lokasyonlar(
        self, limit: int = 1000, offset: int = 0
    ) -> List[str]:
        """Benzersiz lokasyon isimlerini getir (çıkış + varış)."""
        limit = max(1, min(int(limit or 1000), 5000))
        offset = max(0, int(offset or 0))
        query = """
            SELECT DISTINCT cikis_yeri as yer FROM lokasyonlar
            UNION
            SELECT DISTINCT varis_yeri as yer FROM lokasyonlar
            ORDER BY yer
            LIMIT :limit OFFSET :offset
        """
        rows = await self.execute_query(query, {"limit": limit, "offset": offset})
        return [row["yer"] for row in rows]

    async def add(
        self,
        cikis_yeri: str,
        varis_yeri: str,
        mesafe_km: int,
        tahmini_sure_saat: float = None,
        zorluk: str = "Normal",
        notlar: str = "",
        cikis_lat: float = None,
        cikis_lon: float = None,
        varis_lat: float = None,
        varis_lon: float = None,
        api_mesafe_km: float = None,
        api_sure_saat: float = None,
        ascent_m: float = None,
        descent_m: float = None,
        flat_distance_km: float = 0.0,
        otoban_mesafe_km: float = None,
        sehir_ici_mesafe_km: float = None,
        aktif: bool = True,
        # Phase 3.4: kullanıcı verdiği takma isim
        ad: str = None,
    ) -> int:
        """Yeni güzergah ekle"""
        return await self.create(
            cikis_yeri=cikis_yeri,
            varis_yeri=varis_yeri,
            mesafe_km=mesafe_km,
            tahmini_sure_saat=tahmini_sure_saat,
            zorluk=zorluk,
            notlar=notlar,
            cikis_lat=cikis_lat,
            cikis_lon=cikis_lon,
            varis_lat=varis_lat,
            varis_lon=varis_lon,
            api_mesafe_km=api_mesafe_km,
            api_sure_saat=api_sure_saat,
            ascent_m=ascent_m,
            descent_m=descent_m,
            flat_distance_km=flat_distance_km,
            otoban_mesafe_km=otoban_mesafe_km,
            sehir_ici_mesafe_km=sehir_ici_mesafe_km,
            aktif=aktif,
            ad=ad,
        )

    async def find_closest_match(
        self,
        input_name: str,
        threshold: float = 0.6,
        pre_fetched_names: List[str] = None,
    ) -> Optional[str]:
        """
        Akıllı İsim Eşleme (Fuzzy Matching).
        Bulk işlemlerde pre_fetched_names verilerek N+1 sorgu önlenir.
        """
        if not input_name:
            return None

        all_names = pre_fetched_names
        if all_names is None:
            all_names = await self.get_benzersiz_lokasyonlar()

        if not all_names:
            return None

        # Büyük/küçük harf duyarsız eşleme
        input_name = input_name.upper().strip()
        matches = difflib.get_close_matches(
            input_name, [n.upper() for n in all_names], n=1, cutoff=threshold
        )

        if matches:
            # Orijinal ismi bul (all_names içinden)
            idx = [n.upper() for n in all_names].index(matches[0])
            return all_names[idx]

        return None

    async def get_location_stats(self) -> Dict[str, Any]:
        """Fleet-wide location statistics for KPI cards (Tier F madde 35)."""
        query = """
            SELECT
                COUNT(*) FILTER (WHERE aktif = TRUE AND is_deleted = FALSE)          AS total,
                COUNT(*) FILTER (WHERE aktif = TRUE AND is_deleted = FALSE
                                 AND route_analysis IS NOT NULL)                      AS analyzed,
                COUNT(*) FILTER (WHERE aktif = TRUE AND is_deleted = FALSE
                                 AND (last_api_call IS NULL
                                      OR last_api_call < NOW() - INTERVAL '90 days')) AS stale,
                ROUND(AVG(mesafe_km) FILTER (WHERE aktif = TRUE AND is_deleted = FALSE)::numeric, 1)
                                                                                      AS avg_distance_km,
                COUNT(*) FILTER (WHERE aktif = TRUE AND is_deleted = FALSE
                                 AND zorluk = 'Zor')                                  AS high_difficulty
            FROM lokasyonlar
        """
        rows = await self.execute_query(query)
        row = rows[0]
        return {
            "total": row["total"] or 0,
            "analyzed": row["analyzed"] or 0,
            "stale": row["stale"] or 0,
            "avg_distance_km": float(row["avg_distance_km"] or 0),
            "high_difficulty": row["high_difficulty"] or 0,
        }

    async def get_stale_locations(self, days: int) -> List[Dict[str, Any]]:
        """Locations not analyzed in the last N days (or never analyzed)."""
        query = """
            SELECT id, cikis_yeri, varis_yeri, mesafe_km, zorluk, last_api_call
            FROM lokasyonlar
            WHERE aktif = TRUE AND is_deleted = FALSE
              AND (last_api_call IS NULL OR last_api_call < NOW() - INTERVAL '1 day' * :days)
            ORDER BY last_api_call ASC NULLS FIRST
            LIMIT 20
        """
        return await self.execute_query(query, {"days": days})

    async def search_by_route_names(self, cikis: str, varis: str) -> List[Lokasyon]:
        """Search locations by start/destination names (ILIKE, ORM objects)."""
        safe_cikis = cikis.replace("%", "\\%").replace("_", "\\_")
        safe_varis = varis.replace("%", "\\%").replace("_", "\\_")
        stmt = select(self.model).where(
            self.model.cikis_yeri.ilike(f"%{safe_cikis}%"),
            self.model.varis_yeri.ilike(f"%{safe_varis}%"),
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_with_segments(self, lokasyon_id: int) -> Optional[Lokasyon]:
        """Fetch a location with its hydrated route segments eagerly loaded."""
        stmt = (
            select(self.model)
            .where(self.model.id == lokasyon_id)
            .options(selectinload(self.model.segments))
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()


# Thread-safe Singleton
_lokasyon_repo_lock = threading.Lock()
_lokasyon_repo: Optional[LokasyonRepository] = None


def get_lokasyon_repo(session: Optional[AsyncSession] = None) -> LokasyonRepository:
    """LokasyonRepo Provider. Eğer session verilirse yeni instance döner (UoW için)."""
    global _lokasyon_repo
    if session:
        return LokasyonRepository(session=session)
    with _lokasyon_repo_lock:
        if _lokasyon_repo is None:
            _lokasyon_repo = LokasyonRepository()
    return _lokasyon_repo
