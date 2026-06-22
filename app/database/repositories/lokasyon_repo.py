"""
TIR Yakıt Takip - Lokasyon Repository
Lokasyon/güzergah CRUD operasyonları
"""

import difflib
import threading
from typing import Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

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

    async def get_mesafe(self, cikis: str, varis: str) -> Optional[int]:
        """Lokasyonlar arası mesafeyi getir"""
        loc = await self.get_by_route(cikis, varis)
        return loc.get("mesafe_km") if loc else None

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

    async def get_with_elevation(self, lokasyon_id: int) -> Optional[Dict]:
        """Yükseklik bilgisi ile lokasyon getir"""
        # BaseRepo get_by_id returns all cols including ascent_m/descent_m
        loc = await self.get_by_id(lokasyon_id)
        if loc:
            # Add alias keys if frontend expects them
            loc["ascent"] = loc.get("ascent_m") or 0
            loc["descent"] = loc.get("descent_m") or 0
        return loc

    async def get_route_for_prediction(self, cikis: str, varis: str) -> Dict:
        """Tahmin için rota bilgilerini getir"""
        loc = await self.get_by_route(cikis, varis)
        if loc:
            return {
                "mesafe_km": loc.get("mesafe_km", 0),
                "ascent_m": loc.get("ascent_m") or 0,
                "descent_m": loc.get("descent_m") or 0,
                "zorluk": loc.get("zorluk", "Normal"),
            }
        return {"mesafe_km": 0, "ascent_m": 0, "descent_m": 0, "zorluk": "Normal"}

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
