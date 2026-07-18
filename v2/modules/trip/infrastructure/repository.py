from datetime import date, timedelta
from typing import Any, Dict, List, Optional

from sqlalchemy import asc as sql_asc
from sqlalchemy import case, func, or_, select, text, update
from sqlalchemy import desc as sql_desc
from sqlalchemy.orm import joinedload

from app.database.base_repository import BaseRepository
from app.database.models import Arac, Sefer
from app.infrastructure.logging.logger import get_logger
from v2.modules.trip.sefer_status import (
    CANONICAL_SEFER_STATUS_SET,
    SEFER_STATUS_IPTAL,
    SEFER_STATUS_TAMAMLANDI,
    ensure_canonical_sefer_status,
    normalize_sefer_status,
)

logger = get_logger(__name__)


class SeferRepository(BaseRepository[Sefer]):
    """
    Asynchronous repository for Trip (Sefer) operations.
    Handles complex joins for vehicle, driver, and route analysis data.

    NOT: Şofore özel 6 sorgu (``get_by_sofor_id``, ``get_with_route_analysis``,
    ``get_driver_trips_with_route_analysis``, ``get_driver_trips_by_route_type``,
    ``get_recent_trips_batch``, ``_search_driver_ids_by_name``) buradan
    ``v2/modules/driver/infrastructure/driver_trip_queries.py``'ye taşındı
    (task dosyası madde 1/4 kararı). ``get_all``'ın genel arama özelliği artık
    ``v2.modules.driver.public.search_driver_ids_by_name``'i çağırıyor.
    """

    model = Sefer

    @staticmethod
    def _with_relations(stmt):
        """3 kopya ``joinedload(arac,sofor,dorse,guzergah)`` zincirini tek
        yerde toplar (models.py bölünmesinden ÖNCEKİ ara adım — D.1/1
        riskinin mitigasyonu, task dosyası madde 5.5)."""
        return stmt.options(
            joinedload(Sefer.arac),
            joinedload(Sefer.sofor),
            joinedload(Sefer.dorse),
            joinedload(Sefer.guzergah),
        )

    @staticmethod
    def _row_to_dict(s: Sefer) -> Dict[str, Any]:
        d = s.__dict__.copy()
        d.pop("_sa_instance_state", None)
        d["plaka"] = s.arac.plaka if s.arac else None
        d["sofor_adi"] = s.sofor.ad_soyad if s.sofor else None
        d["dorse_plakasi"] = s.dorse.plaka if s.dorse else None
        if s.guzergah:
            d["guzergah_adi"] = f"{s.guzergah.cikis_yeri} - {s.guzergah.varis_yeri}"
        else:
            d["guzergah_adi"] = f"{s.cikis_yeri} - {s.varis_yeri}"
        return d

    async def get_all(  # type: ignore[override]
        self,
        tarih: Optional[date] = None,
        baslangic_tarih: Optional[date] = None,
        bitis_tarih: Optional[date] = None,
        arac_id: Optional[int] = None,
        sofor_id: Optional[int] = None,
        durum: Optional[str] = None,
        search: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
        desc: bool = True,
        include_inactive: bool = False,
        filters: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ) -> List[Dict[str, Any]]:
        """
        Retrieves trips with joined details.
        Standardizes output for frontend consumption.
        """
        onay_durumu: Optional[str] = None
        if filters:
            tarih = filters.get("tarih", tarih)
            baslangic_tarih = filters.get("baslangic_tarih", baslangic_tarih)
            bitis_tarih = filters.get("bitis_tarih", bitis_tarih)
            arac_id = filters.get("arac_id", arac_id)
            sofor_id = filters.get("sofor_id", sofor_id)
            durum = filters.get("durum", durum)
            search = filters.get("search", search)
            include_inactive = filters.get("include_inactive", include_inactive)
            onay_durumu = filters.get("onay_durumu", None)

        # Type normalization
        if isinstance(tarih, str):
            tarih = date.fromisoformat(tarih)
        if isinstance(baslangic_tarih, str):
            baslangic_tarih = date.fromisoformat(baslangic_tarih)
        if isinstance(bitis_tarih, str):
            bitis_tarih = date.fromisoformat(bitis_tarih)

        if arac_id is not None:
            arac_id = int(arac_id)
        if sofor_id is not None:
            sofor_id = int(sofor_id)

        limit = max(1, min(int(limit or 100), self.MAX_LIMIT))
        offset = max(0, int(offset or 0))

        # Build Query
        stmt = self._with_relations(select(Sefer)).where(
            Sefer.is_deleted == False  # noqa: E712  [Integrity] Soft delete check
        )

        # Apply Filters
        if tarih:
            stmt = stmt.where(Sefer.tarih == tarih)
        if baslangic_tarih:
            stmt = stmt.where(Sefer.tarih >= baslangic_tarih)
        if bitis_tarih:
            stmt = stmt.where(Sefer.tarih <= bitis_tarih)
        if arac_id:
            stmt = stmt.where(Sefer.arac_id == arac_id)
        if sofor_id:
            stmt = stmt.where(Sefer.sofor_id == sofor_id)

        if durum:
            durum = ensure_canonical_sefer_status(
                durum, field_name="durum", allow_none=False
            )
            stmt = stmt.where(Sefer.durum == durum)
        elif not include_inactive:
            stmt = stmt.where(Sefer.durum != SEFER_STATUS_IPTAL)

        if search:
            from v2.modules.driver.public import search_driver_ids_by_name

            search_like = f"%{search}%"
            driver_ids = await search_driver_ids_by_name(search)
            stmt = stmt.where(
                or_(
                    Sefer.arac.has(Arac.plaka.ilike(search_like)),
                    Sefer.sofor_id.in_(driver_ids),
                    Sefer.cikis_yeri.ilike(search_like),
                    Sefer.varis_yeri.ilike(search_like),
                    Sefer.sefer_no.ilike(search_like),
                )
            )

        if onay_durumu:
            stmt = stmt.where(Sefer.onay_durumu == onay_durumu)

        # Ordering
        if desc:
            stmt = stmt.order_by(sql_desc(Sefer.tarih), sql_desc(Sefer.id))
        else:
            stmt = stmt.order_by(sql_asc(Sefer.tarih), sql_asc(Sefer.id))

        stmt = stmt.limit(limit).offset(offset)
        result = await self.session.execute(stmt)
        trips = result.scalars().unique().all()

        return [self._row_to_dict(s) for s in trips]

    async def get_for_training(self, arac_id: int, limit: int = 200) -> List[Dict]:
        """
        [v2.1] Returns enriched trip data for ML model training.
        Uses FK join on guzergah_id (not text-match) for reliable route enrichment.
        Includes Road Analysis and Trailer (Dorse) features.
        """
        query = """
            SELECT
                s.mesafe_km,
                s.net_kg / 1000.0 AS ton,
                s.tuketim,
                s.sofor_id,
                s.tarih,
                s.arac_id,
                COALESCE(s.ascent_m, l.ascent_m, 0.0) AS ascent_m,
                COALESCE(s.descent_m, l.descent_m, 0.0) AS descent_m,
                COALESCE(s.flat_distance_km, l.flat_distance_km, 0.0) AS flat_distance_km,
                COALESCE(l.zorluk, 'Normal') AS zorluk,
                COALESCE(s.rota_detay, l.route_analysis) AS rota_detay,
                COALESCE(s.otoban_mesafe_km, l.otoban_mesafe_km, 0.0) AS otoban_mesafe_km,
                COALESCE(s.sehir_ici_mesafe_km, l.sehir_ici_mesafe_km, 0.0) AS sehir_ici_mesafe_km,
                COALESCE(d.bos_agirlik_kg, 6500.0) AS dorse_bos_agirlik,
                COALESCE(d.lastik_sayisi, 6) AS dorse_lastik_sayisi
            FROM seferler s
            LEFT JOIN lokasyonlar l ON s.guzergah_id = l.id
            LEFT JOIN dorseler d ON s.dorse_id = d.id
            WHERE s.arac_id = :arac_id
              AND s.is_deleted = False
              AND s.tuketim IS NOT NULL
              AND s.tuketim > 0
              AND s.durum = :completed_status
            ORDER BY s.tarih DESC
            LIMIT :limit
        """
        return await self.execute_query(
            query,
            {
                "arac_id": arac_id,
                "limit": limit,
                "completed_status": SEFER_STATUS_TAMAMLANDI,
            },
        )

    async def get_cost_leakage_stats(
        self,
        days: int = 30,
        avg_fuel_price: float = 42.0,
        est_km_cost: float = 13.5,
    ) -> dict:
        """
        Son X gündeki maliyet kaçaklarını hesapla (Rota Sapması ve Yakıt Farkı).
        Uses _get_session() so it works both inside and outside a UoW context.
        """
        start_date = date.today() - timedelta(days=max(1, int(days or 30)))

        route_query = """
            SELECT COALESCE(SUM(s.mesafe_km - l.mesafe_km), 0)
            FROM seferler s
            JOIN lokasyonlar l ON (
                LOWER(s.cikis_yeri) = LOWER(l.cikis_yeri)
                AND LOWER(s.varis_yeri) = LOWER(l.varis_yeri)
            )
            WHERE s.tarih >= :start_date
              AND s.mesafe_km > l.mesafe_km * 1.1
              AND s.is_deleted = FALSE
              AND s.durum = 'Completed'
        """

        # Separate queries avoid the Cartesian product that the old JOIN produced
        # (arac_id-only join ⟹ N×M rows ⟹ both litre and mesafe_km inflated).
        actual_fuel_query = """
            SELECT COALESCE(SUM(ya.litre), 0)
            FROM yakit_alimlari ya
            WHERE ya.tarih >= :start_date
        """

        expected_fuel_query = """
            SELECT COALESCE(SUM(s.mesafe_km * :est_litre_per_km / 100.0), 0)
            FROM seferler s
            WHERE s.tarih >= :start_date
              AND s.is_deleted = FALSE
              AND s.durum = 'Completed'
        """

        async with self._get_session() as session:
            route_result = await session.execute(
                text(route_query), {"start_date": start_date}
            )
            actual_result = await session.execute(
                text(actual_fuel_query), {"start_date": start_date}
            )
            expected_result = await session.execute(
                text(expected_fuel_query),
                {"start_date": start_date, "est_litre_per_km": 30.0},
            )
            dev_km = route_result.scalar() or 0
            # actual = SUM(litre) → NUMERIC → Decimal; expected = float arithmetic
            # (the `/100.0` makes it double precision). Cast both to float before the
            # subtraction, else `Decimal - float` raises TypeError once real data exists
            # (empty DB returned int 0 via COALESCE, masking this).
            fuel_gap = float(actual_result.scalar() or 0) - float(
                expected_result.scalar() or 0
            )

        return {
            "route_deviation_km": round(float(dev_km), 1),
            "route_deviation_cost": round(float(dev_km) * est_km_cost, 2),
            "fuel_gap_liters": round(float(fuel_gap), 1),
            "fuel_gap_cost": round(float(fuel_gap) * avg_fuel_price, 2),
            "total_leakage_cost": round(
                (float(dev_km) * est_km_cost) + (float(fuel_gap) * avg_fuel_price),
                2,
            ),
        }

    async def get_by_id(
        self,
        sefer_id: int,
        for_update: bool = False,
        include_inactive: bool = False,
    ) -> dict | None:
        """ID ile sefer getir (dict olarak).

        ``include_inactive=True``: soft-deleted (``is_deleted=True``) bir
        seferi de görmek gereken kasıtlı akışlar için (ör. çift-silme
        guard'ı) filtreyi bypass eder — bkz. BaseRepository.get_by_id ile
        aynı sözleşme.
        """
        conditions = [Sefer.id == sefer_id]
        if not include_inactive:
            conditions.append(Sefer.is_deleted == False)  # noqa: E712
        stmt = self._with_relations(select(Sefer)).where(*conditions)
        result = await self.session.execute(stmt)
        s = result.scalars().first()
        if not s:
            return None
        return self._row_to_dict(s)

    # Alias used by sefer_read_service
    async def get_by_id_with_details(self, sefer_id: int) -> dict | None:
        return await self.get_by_id(sefer_id)

    async def count_all(
        self,
        include_inactive: bool = False,
        filters: Optional[Dict[str, Any]] = None,
    ) -> int:
        """Return total trip count matching the same filters used by get_all."""
        from sqlalchemy import func as sa_func
        from sqlalchemy import select as sa_select

        stmt = sa_select(sa_func.count()).select_from(Sefer)
        stmt = stmt.where(Sefer.is_deleted == False)  # noqa: E712

        durum: Optional[str] = None
        if filters:
            tarih = filters.get("tarih")
            baslangic_tarih = filters.get("baslangic_tarih")
            bitis_tarih = filters.get("bitis_tarih")
            arac_id = filters.get("arac_id")
            sofor_id = filters.get("sofor_id")
            durum = filters.get("durum")
            onay_durumu = filters.get("onay_durumu")
            include_inactive = filters.get("include_inactive", include_inactive)

            if isinstance(tarih, str):
                tarih = date.fromisoformat(tarih)
            if isinstance(baslangic_tarih, str):
                baslangic_tarih = date.fromisoformat(baslangic_tarih)
            if isinstance(bitis_tarih, str):
                bitis_tarih = date.fromisoformat(bitis_tarih)

            if tarih:
                stmt = stmt.where(Sefer.tarih == tarih)
            if baslangic_tarih:
                stmt = stmt.where(Sefer.tarih >= baslangic_tarih)
            if bitis_tarih:
                stmt = stmt.where(Sefer.tarih <= bitis_tarih)
            if arac_id:
                stmt = stmt.where(Sefer.arac_id == int(arac_id))
            if sofor_id:
                stmt = stmt.where(Sefer.sofor_id == int(sofor_id))
            if durum:
                durum = ensure_canonical_sefer_status(
                    durum, field_name="durum", allow_none=False
                )
                stmt = stmt.where(Sefer.durum == durum)
            if onay_durumu:
                stmt = stmt.where(Sefer.onay_durumu == onay_durumu)

        if not durum and not include_inactive:
            stmt = stmt.where(Sefer.durum != SEFER_STATUS_IPTAL)

        result = await self.session.execute(stmt)
        return result.scalar() or 0

    async def count_today(self, today: Optional[date] = None) -> int:
        """Bugünün sefer sayısı (soft-delete edilmemiş, iptal hariç)."""
        target = today or date.today()
        stmt = (
            select(func.count())
            .select_from(Sefer)
            .where(
                Sefer.tarih == target,
                Sefer.is_deleted == False,  # noqa: E712
                Sefer.durum != SEFER_STATUS_IPTAL,
            )
        )
        result = await self.session.execute(stmt)
        return int(result.scalar() or 0)

    async def update_sefer(self, id: int, **kwargs) -> bool:
        """Alias used by update_trip.py::update_sefer_uow."""
        return await self.update(id, **kwargs)

    async def delete(self, id: int) -> bool:
        """Soft delete: is_deleted=True set eder, kayıt kalıcı silinmez."""
        return await self.update(id, is_deleted=True)

    async def update_trips_fuel_data(self, trips: List[Any]) -> int:
        """Periyot dağıtımı sonrası seferlerin yakıt alanlarını
        (``dagitilan_yakit``, ``tuketim``, ``periyot_id``) PK bazında toplu
        günceller.

        ``trips`` başka bir context'te fetch edilip yakıt dağıtımıyla
        değiştirilmiş Sefer nesneleridir (ORM ya da core.entities Pydantic —
        ikisinde de id/dagitilan_yakit/tuketim/periyot_id alanları var); bu
        yüzden tip ``Any`` (katman ayrımı: repo core.entities'i import etmez).
        Değerleri okuyup mevcut session'da tek bir bulk UPDATE ile yazarız.
        Etkilenen sefer sayısını döner.
        """
        rows = [
            {
                "id": t.id,
                "dagitilan_yakit": t.dagitilan_yakit,
                "tuketim": t.tuketim,
                "periyot_id": t.periyot_id,
            }
            for t in trips
            if t.id is not None
        ]
        if not rows:
            return 0
        await self.session.execute(update(Sefer), rows)
        return len(rows)

    async def add(self, data: dict = None, **kwargs) -> int:
        """Yeni sefer ekle, ID döner. Accepts positional dict or keyword args."""
        import enum as _enum

        raw = {**(data or {}), **kwargs}
        allowed = {
            "tarih",
            "arac_id",
            "sofor_id",
            "dorse_id",
            "guzergah_id",
            "cikis_yeri",
            "varis_yeri",
            "mesafe_km",
            "sefer_no",
            "bos_agirlik_kg",
            "dolu_agirlik_kg",
            "net_kg",
            "ton",
            "bos_sefer",
            "durum",
            "ascent_m",
            "descent_m",
            "flat_distance_km",
            "notlar",
            "created_by_id",
            "tuketim",
            "is_deleted",
            "route_pair_id",
            "saat",
            "otoban_mesafe_km",
            "sehir_ici_mesafe_km",
            # Phase 4.4: SeferFuelEstimator bağı (opsiyonel FK)
            "route_simulation_id",
            # Tahmin alanları (mevcut akışta whitelist'te yoktu — silent drop
            # riskini önlemek için eklendi)
            "tahmini_tuketim",
            "tahmin_meta",
            "rota_detay",
        }
        # Python 3.11+: str(MyStrEnum.X) returns "MyStrEnum.X", not the value.
        # Coerce enums to their .value so asyncpg sends the correct string.
        filtered = {
            k: (v.value if isinstance(v, _enum.Enum) else v)
            for k, v in raw.items()
            if k in allowed
        }
        from sqlalchemy.exc import IntegrityError

        sefer = Sefer(**filtered)
        self.session.add(sefer)
        try:
            await self.session.flush()
        except IntegrityError as exc:
            if "sefer_no" in str(exc.orig).lower() or "unique" in str(exc.orig).lower():
                raise ValueError(
                    f"Bu sefer numarası zaten kullanımda: {filtered.get('sefer_no')}"
                ) from exc
            raise
        return sefer.id

    async def get_by_sefer_no(self, sefer_no: str) -> dict | None:
        """Sefer numarasına göre getir."""
        stmt = select(Sefer).where(
            Sefer.sefer_no == sefer_no,
            Sefer.is_deleted == False,  # noqa: E712
        )
        result = await self.session.execute(stmt)
        s = result.scalars().first()
        if not s:
            return None
        d = s.__dict__.copy()
        d.pop("_sa_instance_state", None)
        return d

    async def get_existing_sefer_nos(self, nos: List[str]) -> set[str]:
        """Verilen sefer_no listesinden DB'de zaten var olanları döner (soft-delete hariç).

        ``bulk_add_sefer``'in toplu-import benzersizlik kontrolü için — N ayrı
        ``get_by_sefer_no`` yerine tek sorgu.
        """
        if not nos:
            return set()
        stmt = select(Sefer.sefer_no).where(
            Sefer.sefer_no.in_(nos),
            Sefer.is_deleted == False,  # noqa: E712
        )
        result = await self.session.execute(stmt)
        return {row[0] for row in result.fetchall()}

    async def get_bugunun_seferleri(self) -> List[Dict[str, Any]]:
        """Bugünün seferlerini döner (iptal hariç, soft-delete hariç).

        Interface: ISeferRepository.get_bugunun_seferleri()
        """
        return await self.get_all(tarih=date.today(), include_inactive=False)

    async def get_ids_missing_prediction(self, limit: int = 50) -> List[int]:
        """tahmini_tuketim NULL olan, silinmemiş seferlerin id'leri (eski->yeni).

        Sefer create yolundaki 2.5s timeout fallback'i bu satırları NULL
        bırakıyor (bkz CLAUDE.md SeferFuelEstimator). Faz 1 backfill job
        bunları timeout'suz estimator ile doldurur.
        """
        stmt = (
            select(Sefer.id)
            .where(Sefer.tahmini_tuketim.is_(None))
            .where(Sefer.is_deleted.is_(False))
            .order_by(Sefer.id.asc())
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return [int(r) for r in result.scalars().all()]

    # Canonical durum set (Planned/Completed/Cancelled). Legacy Türkçe/ASCII
    # girişler get_trip_stats içinde normalize_sefer_status ile bu sete çevrilir.
    _VALID_DURUM = set(CANONICAL_SEFER_STATUS_SET)

    async def get_trip_stats(
        self,
        durum: Optional[str] = None,
        baslangic_tarih: Optional[date] = None,
        bitis_tarih: Optional[date] = None,
    ) -> Dict[str, Any]:
        """Aggregate trip statistics. Raises ValueError for unknown durum values."""
        # Legacy Türkçe/ASCII durum girişlerini canonical İngilizceye çevir.
        if durum:
            durum = normalize_sefer_status(durum)
        if durum and durum not in self._VALID_DURUM:
            raise ValueError(
                f"Geçersiz durum: {durum!r}. Geçerli değerler: {self._VALID_DURUM}"
            )

        stats_q = select(
            func.count().label("total_count"),
            func.sum(
                case(
                    (Sefer.durum == "Completed", 1),
                    else_=0,
                )
            ).label("completed_count"),
            func.sum(
                case(
                    (Sefer.durum == "Cancelled", 1),
                    else_=0,
                )
            ).label("cancelled_count"),
            func.sum(
                case(
                    (Sefer.durum == "Planned", 1),
                    else_=0,
                )
            ).label("planned_count"),
            func.sum(
                case(
                    (Sefer.durum == "InProgress", 1),
                    else_=0,
                )
            ).label("in_progress_count"),
            func.coalesce(func.sum(Sefer.mesafe_km), 0).label("total_distance_km"),
            func.coalesce(func.avg(Sefer.tuketim), 0.0).label("avg_consumption"),
        ).where(
            Sefer.is_deleted == False,  # noqa: E712
            *([Sefer.tarih >= baslangic_tarih] if baslangic_tarih else []),
            *([Sefer.tarih <= bitis_tarih] if bitis_tarih else []),
            *([Sefer.durum == durum] if durum else []),
        )

        result = await self.session.execute(stats_q)
        row = result.one()

        return {
            "total_count": row.total_count or 0,
            "completed_count": row.completed_count or 0,
            "cancelled_count": row.cancelled_count or 0,
            "planned_count": row.planned_count or 0,
            "in_progress_count": row.in_progress_count or 0,
            "total_distance_km": float(row.total_distance_km or 0),
            "avg_consumption": float(row.avg_consumption or 0),
        }

    async def get_fuel_performance_analytics(
        self,
        durum: Optional[str] = None,
        baslangic_tarih: Optional[date] = None,
        bitis_tarih: Optional[date] = None,
        arac_id: Optional[int] = None,
        sofor_id: Optional[int] = None,
        search: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Fuel performance analytics: KPIs, trend, distribution, outliers.

        Returns the predicted-vs-actual comparison for trips that have both
        ``tahmini_tuketim`` (AI prediction) and ``tuketim`` (actual consumption).
        """
        import math

        # Legacy Türkçe/ASCII durum girişlerini canonical İngilizceye çevir.
        if durum:
            durum = normalize_sefer_status(durum)
        if durum and durum not in self._VALID_DURUM:
            raise ValueError(f"Geçersiz durum: {durum!r}")

        base_where = [Sefer.is_deleted == False]  # noqa: E712
        if durum:
            base_where.append(Sefer.durum == durum)
        if baslangic_tarih:
            base_where.append(Sefer.tarih >= baslangic_tarih)
        if bitis_tarih:
            base_where.append(Sefer.tarih <= bitis_tarih)
        if arac_id:
            base_where.append(Sefer.arac_id == arac_id)
        if sofor_id:
            base_where.append(Sefer.sofor_id == sofor_id)

        # ── 1. Trips with both predicted and actual consumption ──────────────
        paired_stmt = select(
            Sefer.id,
            Sefer.tarih,
            Sefer.tuketim,
            Sefer.tahmini_tuketim,
            Sefer.mesafe_km,
        ).where(
            *base_where,
            Sefer.tuketim.isnot(None),
            Sefer.tuketim > 0,
            Sefer.tahmini_tuketim.isnot(None),
            Sefer.tahmini_tuketim > 0,
        )
        paired_result = await self.session.execute(paired_stmt)
        paired_rows = paired_result.fetchall()

        total_compared = len(paired_rows)
        mae = 0.0
        rmse = 0.0
        outliers: List[Dict[str, Any]] = []
        HIGH_DEVIATION_PCT = 0.20  # 20% deviation threshold

        if total_compared > 0:
            abs_errors = [
                abs(float(r.tuketim) - float(r.tahmini_tuketim)) for r in paired_rows
            ]
            sq_errors = [e * e for e in abs_errors]
            mae = sum(abs_errors) / total_compared
            rmse = math.sqrt(sum(sq_errors) / total_compared)

            high_count = 0
            for r, err in zip(paired_rows, abs_errors):
                actual = float(r.tuketim)
                if actual > 0 and (err / actual) > HIGH_DEVIATION_PCT:
                    high_count += 1
                    if len(outliers) < 20:
                        outliers.append(
                            {
                                "sefer_id": r.id,
                                "tarih": r.tarih.isoformat() if r.tarih else None,
                                "actual": round(actual, 2),
                                "predicted": round(float(r.tahmini_tuketim), 2),
                                "deviation_pct": round((err / actual) * 100, 1),
                            }
                        )

            high_deviation_ratio = high_count / total_compared
        else:
            high_deviation_ratio = 0.0

        # ── 2. Trend: weekly avg actual consumption (last 12 weeks) ─────────
        trend_start = (baslangic_tarih or date.today()) - timedelta(weeks=12)
        trend_stmt = select(
            Sefer.tarih,
            Sefer.tuketim,
        ).where(
            Sefer.is_deleted == False,  # noqa: E712
            Sefer.tuketim.isnot(None),
            Sefer.tuketim > 0,
            Sefer.tarih >= trend_start,
        )
        trend_result = await self.session.execute(trend_stmt)
        trend_rows = trend_result.fetchall()

        # Bucket by ISO week
        from collections import defaultdict

        week_buckets: Dict[str, List[float]] = defaultdict(list)
        for tr in trend_rows:
            if tr.tarih:
                week_key = tr.tarih.strftime("%Y-W%W")
                week_buckets[week_key].append(float(tr.tuketim))

        trend = [
            {"week": k, "avg_consumption": round(sum(v) / len(v), 2), "count": len(v)}
            for k, v in sorted(week_buckets.items())
        ]

        # ── 3. Distribution: consumption histogram (buckets of 5 L/100km) ───
        dist_stmt = select(Sefer.tuketim).where(
            *base_where,
            Sefer.tuketim.isnot(None),
            Sefer.tuketim > 0,
            Sefer.tuketim <= 200,
        )
        dist_result = await self.session.execute(dist_stmt)
        dist_rows = [float(r.tuketim) for r in dist_result.fetchall()]

        bucket_size = 5.0
        dist_map: Dict[str, int] = {}
        for val in dist_rows:
            bucket_label = f"{int(val // bucket_size) * int(bucket_size)}-{int(val // bucket_size) * int(bucket_size) + int(bucket_size)}"  # noqa: E501
            dist_map[bucket_label] = dist_map.get(bucket_label, 0) + 1
        distribution = [{"range": k, "count": v} for k, v in sorted(dist_map.items())]

        return {
            "kpis": {
                "mae": round(mae, 4),
                "rmse": round(rmse, 4),
                "total_compared": total_compared,
                "high_deviation_ratio": round(high_deviation_ratio, 4),
            },
            "trend": trend,
            "distribution": distribution,
            "outliers": outliers,
            "low_data": total_compared < 5,
        }

    async def refresh_stats_mv(self) -> None:
        """Materialized view'i CONCURRENTLY yenile; yoksa sessizce geç.

        CONCURRENTLY transaction dışında çalışması gerekir.  SQLAlchemy 2.0'da
        text().execution_options(autocommit=True) asyncpg üzerinde etkisizdir;
        gerçek autocommit için engine düzeyinde isolation_level='AUTOCOMMIT'
        ile açılan bağımsız bir bağlantı kullanılır.

        NOT: Bu metot mantıken sistem-geneli (yalnız trip'e özel değil) —
        task dosyası ``shared_kernel/infrastructure/mv_refresh.py``'ye
        taşınmasını öneriyordu ama shared_kernel modülü (dalga 16) henüz
        oluşturulmadı. O dalga gelene kadar burada kalıyor (bkz.
        ``application/stats_refresh.py``'nin docstring'i).
        """
        from app.database.connection import engine

        try:
            async with engine.execution_options(
                isolation_level="AUTOCOMMIT"
            ).connect() as conn:
                await conn.execute(
                    text("REFRESH MATERIALIZED VIEW CONCURRENTLY sefer_istatistik_mv")
                )
        except Exception as exc:
            # CONCURRENTLY desteklenmiyorsa veya MV yoksa blocking fallback.
            try:
                async with engine.execution_options(
                    isolation_level="AUTOCOMMIT"
                ).connect() as conn:
                    await conn.execute(
                        text("REFRESH MATERIALIZED VIEW sefer_istatistik_mv")
                    )
            except Exception:
                logger.debug("MV refresh skipped: %s", exc)

    async def get_by_date_range(
        self,
        start: Any,
        end: Any,
        arac_id: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """Tarih aralığına göre sefer listesi döner."""
        from datetime import date as _date

        def _to_date(v):
            return v if isinstance(v, _date) else _date.fromisoformat(str(v))

        params: Dict[str, Any] = {"start": _to_date(start), "end": _to_date(end)}
        where = "s.tarih >= :start AND s.tarih <= :end AND s.is_deleted = FALSE"
        if arac_id is not None:
            where += " AND s.arac_id = :arac_id"
            params["arac_id"] = arac_id
        sql = f"""
            SELECT s.*, a.plaka, so.ad_soyad AS sofor_adi
            FROM seferler s
            LEFT JOIN araclar a ON s.arac_id = a.id
            LEFT JOIN soforler so ON s.sofor_id = so.id
            WHERE {where}
            ORDER BY s.tarih DESC
        """
        from app.infrastructure.security.pii_encryption import decrypt_pii_or

        rows = await self.execute_query(sql, params)
        for row in rows:
            row["sofor_adi"] = decrypt_pii_or(row.get("sofor_adi"))
        return rows

    async def set_onay_durumu(
        self,
        sefer_id: int,
        yeni_durum: str,
        onay_notu: Optional[str] = None,
        onaylayan_id: Optional[int] = None,
    ) -> Optional[Dict[str, Any]]:
        """Sefer onay durumunu FOR UPDATE ile günceller (race-condition safe)."""
        async with self._get_session() as session:
            stmt = (
                select(Sefer)
                .where(Sefer.id == sefer_id, ~Sefer.is_deleted)
                .with_for_update()
            )
            result = await session.execute(stmt)
            sefer = result.scalar_one_or_none()
            if sefer is None:
                return None
            if sefer.onay_durumu == yeni_durum:
                return self._to_dict(sefer)
            sefer.onay_durumu = yeni_durum
            if onaylayan_id is not None:
                sefer.onaylayan_id = onaylayan_id
            if onay_notu:
                sefer.notlar = (
                    sefer.notlar or ""
                ) + f"\n[{yeni_durum.upper()}] {onay_notu}"
            if self._session is None:
                await session.commit()
            return self._to_dict(sefer)

    async def get_by_onay_durumu(
        self,
        onay_durumu: str,
        skip: int = 0,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """Onay durumuna göre sefer listesi (en yeni önce)."""
        async with self._get_session() as session:
            stmt = (
                self._with_relations(select(Sefer))
                .where(Sefer.onay_durumu == onay_durumu, ~Sefer.is_deleted)
                .order_by(Sefer.created_at.desc())
                .offset(skip)
                .limit(min(limit, self.MAX_LIMIT))
            )
            result = await session.execute(stmt)
            return [self._row_to_dict(s) for s in result.unique().scalars().all()]


def get_sefer_repo(session=None) -> "SeferRepository":
    """SeferRepo provider. Always returns a new repository instance."""
    return SeferRepository(session=session)
