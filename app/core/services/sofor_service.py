"""
LOJINEXT Fuel Tracking - Driver Service
Business logic layer: Driver CRUD operations (English).

TYPE: PER-REQUEST
SCOPE: Transaction-scoped (UnitOfWork ile oluşturulur)
DEPENDS_ON: UoW.sofor_repo
CREATED_BY: app/api/deps.py::deps.get_sofor_service()
"""

from datetime import date
from typing import Any, Dict, List, Optional

from app.database.repositories.sofor_repo import SoforRepository, get_sofor_repo
from app.database.unit_of_work import UnitOfWork
from app.infrastructure.events.event_bus import (
    EventBus,
    EventType,
    get_event_bus,
    publishes,
)
from app.infrastructure.logging.logger import get_logger

logger = get_logger(__name__)


class SoforService:
    """
    Driver business logic service.
    Acts as a bridge between UI and DB.
    """

    def __init__(
        self,
        repo: Optional["SoforRepository"] = None,
        event_bus: Optional[EventBus] = None,
    ):
        import asyncio

        self.repo = repo or get_sofor_repo()
        self.event_bus = event_bus or get_event_bus()
        self._lock = asyncio.Lock()

    @publishes(EventType.SOFOR_ADDED)
    async def add_sofor(
        self,
        ad_soyad: str,
        telefon: str = "",
        ehliyet_sinifi: str = "E",
        ise_baslama: Optional[date] = None,
        manual_score: float = 1.0,
        notlar: str = "",
    ) -> int:
        """
        Adds a new driver (UoW & Atomic Check).
        """
        async with UnitOfWork() as uow:
            async with self._lock:  # Local Lock (Secondary Guard)
                # Business Rules
                if not ad_soyad or len(ad_soyad.strip()) < 3:
                    raise ValueError("Ad soyad en az 3 karakter olmalıdır.")

                # Title Case formatting
                ad_soyad_clean = " ".join(
                    word.capitalize() for word in ad_soyad.strip().split()
                )

                existing = await uow.sofor_repo.get_by_name(
                    ad_soyad_clean, for_update=True
                )
                if existing:
                    if existing.get("aktif"):
                        raise ValueError(
                            f"An active driver with this name already exists: {ad_soyad_clean}"
                        )
                    else:
                        # Re-activate passive driver
                        logger.info(
                            f"Re-activating passive driver (ID: {existing['id']})"
                        )
                        await uow.sofor_repo.update(existing["id"], aktif=True)
                        await uow.commit()
                        return existing["id"]

                # DB Insert
                sofor_id = await uow.sofor_repo.add(
                    ad_soyad=ad_soyad_clean,
                    telefon=telefon,
                    ehliyet_sinifi=ehliyet_sinifi,
                    ise_baslama=ise_baslama,
                    manual_score=manual_score,
                    score=manual_score,  # Initial score is manual
                    notlar=notlar,
                )

                logger.info(f"New driver added: {ad_soyad_clean} (ID: {sofor_id})")
                await uow.commit()
                return int(sofor_id)

    async def get_all_paged(
        self,
        skip: int = 0,
        limit: int = 100,
        aktif_only: bool = True,
        search: Optional[str] = None,
        ehliyet_sinifi: Optional[str] = None,
        min_score: Optional[float] = None,
        max_score: Optional[float] = None,
    ) -> Dict[str, Any]:
        """Returns paged and filtered driver list."""
        filters: Dict[str, Any] = {}
        if ehliyet_sinifi:
            filters["ehliyet_sinifi"] = ehliyet_sinifi
        if min_score is not None:
            filters["score_ge"] = min_score
        if max_score is not None:
            filters["score_le"] = max_score

        async with UnitOfWork() as uow:
            items = await uow.sofor_repo.get_all(
                offset=skip,
                limit=limit,
                sadece_aktif=aktif_only,
                search=search,
                filters=filters,
            )
            total = await uow.sofor_repo.count_all(
                sadece_aktif=aktif_only,
                search=search,
                filters=filters,
            )

        return {"items": items, "total": total}

    async def get_by_id(self, sofor_id: int) -> Optional[Dict[str, Any]]:
        """Retrieves a driver by ID."""
        async with UnitOfWork() as uow:
            return await uow.sofor_repo.get_by_id(sofor_id)

    @publishes(EventType.SOFOR_UPDATED)
    async def update_sofor(self, sofor_id: int, **kwargs: Any) -> bool:
        """Updates driver details (UoW & Safe Name Change)."""
        async with UnitOfWork() as uow:
            # Title Case if ad_soyad is provided
            if kwargs.get("ad_soyad"):
                ad_soyad = " ".join(
                    word.capitalize() for word in kwargs["ad_soyad"].strip().split()
                )
                kwargs["ad_soyad"] = ad_soyad

                async with self._lock:
                    existing = await uow.sofor_repo.get_by_name(ad_soyad)
                    if existing and existing["id"] != sofor_id:
                        raise ValueError("This name belongs to another driver.")

            # Recalculate hybrid score if manual_score is updated
            if "manual_score" in kwargs:
                current = await uow.sofor_repo.get_by_id(sofor_id)
                if current:
                    new_score = await self.calculate_hybrid_score(
                        sofor_id, kwargs["manual_score"], uow=uow
                    )
                    kwargs["score"] = new_score

            success = await uow.sofor_repo.update(sofor_id, **kwargs)
            if success:
                logger.info(f"Driver updated: ID {sofor_id}")
                await uow.commit()
            return bool(success)

    @publishes(EventType.SOFOR_DELETED)
    async def delete_sofor(self, sofor_id: int) -> bool:
        """Deletes a driver (Soft Delete Standard)."""
        async with UnitOfWork() as uow:
            success = await self._delete_sofor_uow(uow, sofor_id)
            if success:
                await uow.commit()
            return success

    async def _delete_sofor_uow(self, uow: UnitOfWork, sofor_id: int) -> bool:
        """Transactional soft delete logic (Shared UoW)."""
        current = await uow.sofor_repo.get_by_id(sofor_id, for_update=True)
        if not current or current.get("is_deleted"):
            return False

        # Soft Delete (is_deleted=True, aktif=False)
        success = await uow.sofor_repo.update(sofor_id, is_deleted=True, aktif=False)
        if success:
            logger.info(f"Driver soft-deleted: ID {sofor_id}")
        return bool(success)

    async def bulk_delete(self, ids: List[int]) -> Dict[str, Any]:
        """Bulk delete drivers (Transaction isolated)."""
        if not ids:
            return {"deleted": 0, "errors": []}

        async with UnitOfWork() as uow:
            count = await uow.sofor_repo.bulk_soft_delete(ids)
            await uow.commit()

            logger.info(f"Bulk drivers deleted: {count} entries")
            return {"deleted": count, "total": len(ids), "status": "success"}

    async def update_score(self, sofor_id: int, score: float) -> bool:
        """Updates driver manual score and recalculates hybrid score."""
        if score < 0.1 or score > 2.0:
            raise ValueError("Score must be between 0.1 and 2.0")

        try:
            async with UnitOfWork() as uow:
                async with self._lock:
                    current = await uow.sofor_repo.get_by_id(sofor_id)
                    if not current:
                        raise ValueError("Driver not found")

                    # Recalculate hybrid score based on performance
                    hybrid_score = await self.calculate_hybrid_score(
                        sofor_id, score, uow=uow
                    )

                    success = await uow.sofor_repo.update(
                        sofor_id, manual_score=score, score=hybrid_score
                    )
                    if success:
                        await uow.commit()
                        logger.info(
                            f"Driver scores updated: ID {sofor_id} | Manual: {score}, Hybrid: {hybrid_score}"
                        )
            return bool(success)
        except Exception as e:
            logger.error(f"Score update error: {e}")
            raise

    async def calculate_hybrid_score(
        self,
        sofor_id: int,
        manual_score: float,
        uow: Optional[UnitOfWork] = None,
    ) -> float:
        """Hybrid ML correction factor stored as `soforer.score`.

        Scale: 0.1–2.0 (multiplicative factor, NOT a percentage).
        Interpretation: 1.0 = average driver (30 L/100km reference), >1.0 = more
        efficient, <1.0 = less efficient. Used by the ML pipeline to adjust
        per-driver fuel predictions. Formula: 60% perf_factor + 40% manual_score.

        NOT comparable to the 0-100 elite/fleet scores — different scale and purpose.
        Pass an existing `uow` to avoid nested UoW when called from a transaction.
        """
        try:
            if uow is not None:
                stats_list = await uow.sofor_repo.get_sefer_stats(sofor_id=sofor_id)
            else:
                async with UnitOfWork() as _uow:
                    stats_list = await _uow.sofor_repo.get_sefer_stats(
                        sofor_id=sofor_id
                    )
            if not stats_list or len(stats_list) == 0:
                return float(manual_score)

            stats = stats_list[0]
            avg_consumption = float(stats.get("ort_tuketim") or 0)

            if avg_consumption <= 0:
                return float(manual_score)

            # Performance scoring baseline
            target_reference = 30.0
            perf_factor = target_reference / avg_consumption

            perf_score = max(0.1, min(2.0, perf_factor))

            # Hybrid Calculation
            hybrid = (float(perf_score) * 0.6) + (float(manual_score) * 0.4)
            return round(float(hybrid), 2)

        except Exception as e:
            logger.error(f"Hybrid score calculation error: {e}")
            return float(manual_score)

    async def get_score_breakdown(self, sofor_id: int) -> Dict[str, Any]:
        """XAI: hybrid score kırılımı.

        Aynı `calculate_hybrid_score` mantığını paylaşır ama hesaplamadaki
        her bileşeni (manual, auto, ağırlıklar, ortalama tüketim, sefer
        sayısı, referans) ayrı ayrı döner. Frontend bunları görsel formüle
        çevirir.
        """
        sofor = await self.repo.get_by_id(sofor_id)
        if not sofor:
            raise ValueError("Driver not found")

        manual = float(sofor.get("manual_score") or sofor.get("score") or 1.0)
        manual = max(0.1, min(2.0, manual))

        target_reference = 30.0
        manual_weight = 0.4
        auto_weight = 0.6
        avg_consumption = 0.0
        trip_count = 0
        has_trips = False
        auto = manual  # fallback

        try:
            async with UnitOfWork() as uow:
                stats_list = await uow.sofor_repo.get_sefer_stats(sofor_id=sofor_id)
            if stats_list:
                stats = stats_list[0]
                trip_count = int(stats.get("toplam_sefer") or 0)
                avg_consumption = float(stats.get("ort_tuketim") or 0)
                if avg_consumption > 0 and trip_count > 0:
                    perf_factor = target_reference / avg_consumption
                    auto = max(0.1, min(2.0, perf_factor))
                    has_trips = True
        except Exception as e:
            logger.error(f"Score breakdown stats fetch error: {e}")
            # has_trips False kalsın → frontend "henüz yeterli veri yok" göstersin.

        total = round(manual * manual_weight + auto * auto_weight, 2)

        return {
            "sofor_id": sofor_id,
            "ad_soyad": sofor.get("ad_soyad") or "",
            "manual": round(manual, 2),
            "manual_weight": manual_weight,
            "auto": round(auto, 2),
            "auto_weight": auto_weight,
            "total": total,
            "trip_count": trip_count,
            "avg_consumption": round(avg_consumption, 2),
            "target_reference": target_reference,
            "has_trips": has_trips,
        }

    async def get_route_profile(
        self, sofor_id: int, min_trips_for_best: int = 5
    ) -> Dict[str, Any]:
        """Şoför × güzergah tipi profili.

        Her route_type için ortalama gerçek/tahmini tüketim ve sapma yüzdesini
        döndürür. ``best_route_type`` en az ``min_trips_for_best`` seferi olan
        ve sapma_pct'si en düşük (= tahminden en iyi performans) profili
        seçer; aday yoksa None döner.
        """
        from app.core.ml.driver_route_profile import ROUTE_TYPES, classify_route

        # Şoför var mı?
        sofor = await self.repo.get_by_id(sofor_id)
        if not sofor:
            raise ValueError("Driver not found")

        async with UnitOfWork() as uow:
            trips = await uow.sefer_repo.get_driver_trips_with_route_analysis(
                sofor_id=sofor_id, limit=300, days=365
            )

        # route_type → list of {gercek, tahmini}
        buckets: Dict[str, List[Dict[str, float]]] = {rt: [] for rt in ROUTE_TYPES}
        for t in trips:
            rota = t.get("rota_detay") or {}
            route_analysis = rota.get("route_analysis") or rota
            try:
                rtype = classify_route(
                    route_analysis if isinstance(route_analysis, dict) else {}
                )
            except Exception as e:
                logger.warning(f"classify_route failed for trip {t.get('id')}: {e}")
                continue
            if rtype not in buckets:
                continue
            actual = t.get("gercek_tuketim") or 0
            predicted = t.get("tahmini_tuketim") or 0
            if actual > 0 and predicted > 0:
                buckets[rtype].append({"actual": actual, "predicted": predicted})

        labels = {
            "highway_dominant": "Otoyol Ağırlıklı",
            "mountain": "Dağlık",
            "urban": "Şehir İçi",
            "mixed": "Karışık",
        }

        profiles: List[Dict[str, Any]] = []
        for rt in ROUTE_TYPES:
            samples = buckets[rt]
            count = len(samples)
            if count == 0:
                profiles.append(
                    {
                        "route_type": rt,
                        "label": labels[rt],
                        "trip_count": 0,
                        "avg_actual": 0.0,
                        "avg_predicted": 0.0,
                        "deviation_pct": 0.0,
                    }
                )
                continue
            avg_actual = sum(s["actual"] for s in samples) / count
            avg_predicted = sum(s["predicted"] for s in samples) / count
            deviation_pct = (
                ((avg_actual - avg_predicted) / avg_predicted * 100.0)
                if avg_predicted > 0
                else 0.0
            )
            profiles.append(
                {
                    "route_type": rt,
                    "label": labels[rt],
                    "trip_count": count,
                    "avg_actual": round(avg_actual, 2),
                    "avg_predicted": round(avg_predicted, 2),
                    "deviation_pct": round(deviation_pct, 2),
                }
            )

        # En iyi tip: yeterli sefer + en düşük deviation_pct (negatif = tahminden iyi)
        candidates = [p for p in profiles if p["trip_count"] >= min_trips_for_best]
        best_route_type: Optional[str] = None
        if candidates:
            best = min(candidates, key=lambda p: p["deviation_pct"])
            best_route_type = best["route_type"]

        return {
            "sofor_id": sofor_id,
            "ad_soyad": sofor.get("ad_soyad") or "",
            "profiles": profiles,
            "best_route_type": best_route_type,
            "min_trips_for_best": min_trips_for_best,
        }

    async def bulk_add_sofor(self, data_list: List[Any]) -> int:
        """Bulk creates drivers (UoW & performance optimized)."""
        if not data_list:
            return 0

        async with UnitOfWork() as uow:
            existing_names = await uow.sofor_repo.get_aktif_isimler()
            existing_set = set(existing_names)

            to_add = []
            for data in data_list:
                if hasattr(data, "model_dump"):
                    d = data.model_dump()
                elif hasattr(data, "dict"):
                    d = data.dict()
                else:
                    d = data

                ad_soyad = d.get("ad_soyad", "").strip()
                if not ad_soyad or len(ad_soyad) < 3:
                    continue

                ad_soyad = " ".join(word.capitalize() for word in ad_soyad.split())

                if ad_soyad in existing_set:
                    continue

                to_add.append(
                    {
                        "ad_soyad": ad_soyad,
                        "telefon": d.get("telefon", ""),
                        "ise_baslama": d.get("ise_baslama") or None,
                        "ehliyet_sinifi": d.get("ehliyet_sinifi", "E"),
                        "notlar": d.get("notlar", ""),
                        "aktif": True,
                        "score": 1.0,
                    }
                )

            if to_add:
                ids = await uow.sofor_repo.bulk_create(to_add)
                logger.info(f"Bulk drivers added: {len(ids)} entries")
                await uow.commit()
                return len(ids)

        return 0

    async def get_performance_details(self, sofor_id: int) -> Dict[str, Any]:
        """Calculates driver performance details (AI & Stats Analysis)."""
        async with UnitOfWork() as uow:
            # 1. Trip Stats
            stats_list = await uow.sofor_repo.get_sefer_stats(sofor_id=sofor_id)
            stats = stats_list[0] if stats_list else {}

            total_km = float(stats.get("toplam_km") or 0)
            total_trips = int(stats.get("toplam_sefer") or 0)
            avg_consumption = float(stats.get("ort_tuketim") or 0)

            # 2. Anomaly Analysis (Last 30 days)
            anomalies = await uow.sofor_repo.get_driver_anomalies_count(
                sofor_id, days=30
            )

        # 3. Composite score calculation
        deduction = (
            (anomalies.get("critical", 0) * 10)
            + (anomalies.get("high", 0) * 5)
            + (anomalies.get("medium", 0) * 2)
        )

        safety_score = max(0.0, 100.0 - deduction)

        # Eco score
        target = 30.0
        if avg_consumption > 0:
            deviation_pct = ((avg_consumption - target) / target) * 100
            if deviation_pct > 0:
                eco_score = max(0.0, 100.0 - deviation_pct)
            else:
                eco_score = min(100.0, 100.0 + (abs(deviation_pct) * 0.5))
        else:
            eco_score = 90.0

        # Compliance score
        compliance_deduction = (
            (anomalies.get("critical", 0) * 6)
            + (anomalies.get("high", 0) * 3)
            + (anomalies.get("medium", 0) * 1.5)
            + (anomalies.get("low", 0) * 0.5)
        )
        compliance_score = max(0.0, 100.0 - compliance_deduction)

        # Weighted total score
        total_score = (
            (safety_score * 0.4) + (eco_score * 0.4) + (compliance_score * 0.2)
        )

        # Trend mapping
        trend = "stable"
        if total_score > 90:
            trend = "increasing"
        elif total_score < 70:
            trend = "decreasing"

        return {
            "safety_score": round(safety_score, 1),
            "eco_score": round(eco_score, 1),
            "compliance_score": round(compliance_score, 1),
            "total_score": round(total_score, 1),
            "trend": trend,
            "total_km": round(total_km, 1),
            "total_trips": total_trips,
        }


def get_sofor_service() -> SoforService:
    from app.core.container import get_container

    return get_container().sofor_service
