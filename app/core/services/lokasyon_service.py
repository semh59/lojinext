from datetime import datetime, timezone
from typing import Optional

from app.config import settings
from app.database.repositories.lokasyon_repo import get_lokasyon_repo
from app.infrastructure.events.event_bus import EventType, get_event_bus, publishes
from app.infrastructure.logging.logger import get_logger
from app.infrastructure.monitoring.external_api_probe import get_monitored_client
from app.schemas.lokasyon import LokasyonCreate, LokasyonResponse, LokasyonUpdate

logger = get_logger(__name__)


class LokasyonService:
    """Lokasyon/Güzergah iş mantığı servisi

    TYPE: PER-REQUEST
    SCOPE: Transaction-scoped (UnitOfWork ile oluşturulur)
    DEPENDS_ON: UoW.lokasyon_repo
    CREATED_BY: app/api/deps.py::deps.get_lokasyon_service()
    """

    def __init__(self, repo=None, event_bus=None):
        self.repo = repo or get_lokasyon_repo()
        self.event_bus = event_bus or get_event_bus()

    async def geocode_query(self, q: str, limit: int = 5) -> list[dict]:
        query = (q or "").strip()
        if len(query) < 2:
            return []

        ors_results = await self._geocode_with_openroute(query, limit=limit)
        if ors_results:
            return ors_results

        nominatim_results = await self._geocode_with_nominatim(query, limit=limit)
        if nominatim_results:
            return nominatim_results

        return self._geocode_offline(query)

    async def _geocode_with_openroute(self, q: str, limit: int = 5) -> list[dict]:
        from urllib.parse import urlsplit, urlunsplit

        from app.core.services.openroute_service import get_openroute_service

        openroute_service = get_openroute_service()
        if not openroute_service.is_configured():
            return []

        try:
            client = await openroute_service._get_client()
            # BUG (found via 0-mock epiği real-network test): geocode lives
            # at the host root, not under /v2 — appending "/geocode/search"
            # directly to base_url (which includes /v2) built a 404'ing URL
            # in real production. Derive the origin instead, matching
            # OpenRouteClient's geocode_url derivation.
            _origin = urlsplit(openroute_service.base_url)
            geocode_url = urlunsplit(
                (_origin.scheme, _origin.netloc, "/geocode/search", "", "")
            )
            response = await client.get(
                geocode_url,
                params={
                    "api_key": openroute_service.api_key,
                    "text": q,
                    "size": limit,
                    "boundary.country": "TR",
                },
            )
            if response.status_code != 200:
                logger.warning(
                    "ORS geocode failed with status %s", response.status_code
                )
                return []

            features = response.json().get("features", [])
            suggestions = []
            for feature in features[:limit]:
                coords = feature.get("geometry", {}).get("coordinates", [])
                if len(coords) < 2:
                    continue
                label = (
                    feature.get("properties", {}).get("label")
                    or feature.get("properties", {}).get("name")
                    or q
                )
                suggestions.append(
                    {
                        "lat": float(coords[1]),
                        "lon": float(coords[0]),
                        "label": str(label),
                        "source": "ors",
                    }
                )
            return self._dedupe_geocode_results(suggestions)
        except Exception as exc:
            logger.warning("ORS geocode error: %s", exc)
            return []

    async def _geocode_with_nominatim(self, q: str, limit: int = 5) -> list[dict]:
        try:
            async with get_monitored_client(
                timeout=10.0,
                headers={"User-Agent": f"{settings.PROJECT_NAME}/geocode"},
            ) as client:
                response = await client.get(
                    "https://nominatim.openstreetmap.org/search",
                    params={
                        "q": q,
                        "format": "jsonv2",
                        "addressdetails": 1,
                        "limit": limit,
                        "countrycodes": "tr",
                    },
                )

            if response.status_code != 200:
                logger.warning(
                    "Nominatim geocode failed with status %s", response.status_code
                )
                return []

            suggestions = []
            for item in response.json()[:limit]:
                lat = item.get("lat")
                lon = item.get("lon")
                if lat is None or lon is None:
                    continue
                suggestions.append(
                    {
                        "lat": float(lat),
                        "lon": float(lon),
                        "label": str(item.get("display_name") or q),
                        "source": "nominatim",
                    }
                )
            return self._dedupe_geocode_results(suggestions)
        except Exception as exc:
            logger.warning("Nominatim geocode error: %s", exc)
            return []

    def _geocode_offline(self, q: str) -> list[dict]:
        from app.core.services.openroute_service import get_openroute_service

        coords = get_openroute_service().geocode_offline(q)
        if not coords:
            return []
        lon, lat = coords
        return [{"lat": float(lat), "lon": float(lon), "label": q, "source": "offline"}]

    @staticmethod
    def _dedupe_geocode_results(results: list[dict]) -> list[dict]:
        seen = set()
        deduped = []
        for result in results:
            key = (
                round(float(result["lat"]), 6),
                round(float(result["lon"]), 6),
                str(result["label"]).strip().lower(),
            )
            if key in seen:
                continue
            seen.add(key)
            deduped.append(result)
        return deduped

    @publishes(EventType.LOKASYON_ADDED)
    async def add_lokasyon(self, data: LokasyonCreate) -> int:
        """
        Yeni lokasyon/güzergah ekle.
        """

        # Normalize names to prevent duplicates (e.g., Istanbul vs İstanbul)
        # Turkish-aware title case: 'i' → 'İ' (not 'I') at word start.
        # BUG (found via 0-mock epiği real-DB test): str.lower() decomposes
        # 'İ' (U+0130) into 'i' + a combining dot above (U+0307) — that
        # stray combining mark then leaked into w[1:], corrupting every
        # word starting with capital İ (e.g. "İstanbul" -> "İ̇stanbul",
        # double-dotted). Neutralize İ to plain 'i' BEFORE lower() so the
        # decomposition never happens.
        def _tr_title(s: str) -> str:
            return " ".join(
                ("İ" if w[0] == "i" else "I" if w[0] == "ı" else w[0].upper())
                + w[1:].lower()
                for w in s.strip().replace("İ", "i").lower().split()
                if w
            )

        data.cikis_yeri = _tr_title(data.cikis_yeri)
        data.varis_yeri = _tr_title(data.varis_yeri)

        # We use consistent normalization for checking existing records
        # in the repository (which now handles it in SQL)
        existing = await self.repo.get_by_route(data.cikis_yeri, data.varis_yeri)
        if existing:
            if existing.get("aktif"):
                raise ValueError(
                    f"Bu güzergah zaten mevcut: {data.cikis_yeri} -> {data.varis_yeri}"
                )
            else:
                # Pasif ise geri getir ve güncelle
                logger.info(
                    f"Pasif lokasyon tekrar aktifleştiriliyor: {data.cikis_yeri} -> {data.varis_yeri}"
                )
                await self.repo.update(
                    existing["id"], aktif=True, **data.model_dump(exclude_unset=True)
                )
                return existing["id"]

        # Exclude schema fields that are not accepted by the repo layer
        _REPO_EXCLUDE = {"route_analysis", "source"}
        lokasyon_id = await self.repo.add(**data.model_dump(exclude=_REPO_EXCLUDE))
        logger.info(f"Yeni güzergah eklendi: ID {lokasyon_id}")

        # Rota analizi yap (Opsiyonel - eğer koordinatlar varsa veya sadece isimden bulmaya çalışıyorsak)
        # Şimdilik sadece koordinat varsa veya isimlerden bulmaya çalışıyorsak tetikleyebiliriz.
        # create_guzergah mantığını buraya taşıyoruz:
        payload = data.model_dump()
        if all(
            [
                payload.get("cikis_lat"),
                payload.get("cikis_lon"),
                payload.get("varis_lat"),
                payload.get("varis_lon"),
            ]
        ):
            try:
                # Arka planda analiz başlatılabilir veya senkron yapılabilir.
                # create_guzergah senkron yapıyordu, biz de öyle yapalım şimdilik.
                await self.analyze_route(lokasyon_id)
            except Exception as e:
                logger.warning(
                    f"Otomatik rota analizi başarısız (ID: {lokasyon_id}): {e}"
                )

        return lokasyon_id

    @publishes(EventType.LOKASYON_UPDATED)
    async def update_lokasyon(self, lokasyon_id: int, data: LokasyonUpdate) -> bool:
        """Güzergah güncelle"""
        success = await self.repo.update(
            lokasyon_id, **data.model_dump(exclude_unset=True)
        )
        if success:
            logger.info(f"Güzergah güncellendi: ID {lokasyon_id}")
        return success

    @publishes(EventType.LOKASYON_DELETED)
    async def delete_lokasyon(self, lokasyon_id: int) -> bool:
        """Güzergah sil (Smart Delete: Aktif->Pasif, Pasif->Hard)"""
        try:
            # include_inactive=True: smart-delete state machine, ikinci
            # çağrıda (aktif=False → hard-delete) zaten pasif kaydı görmesi
            # gerekiyor.
            current = await self.repo.get_by_id(lokasyon_id, include_inactive=True)
            if not current:
                return False

            if current.get("aktif"):
                # Soft Delete
                success = await self.repo.update(lokasyon_id, aktif=False)
                if success:
                    logger.info(
                        f"Güzergah pasife alındı (Soft Deleted): ID {lokasyon_id}"
                    )
                return success
            else:
                # Hard Delete
                try:
                    success = await self.repo.hard_delete(lokasyon_id)
                    if success:
                        logger.info(
                            f"Güzergah tamamen silindi (Hard Deleted): ID {lokasyon_id}"
                        )
                    return success
                except Exception as e:
                    logger.warning(f"Hard delete engellendi: {e}")
                    raise ValueError(
                        "Bu güzergah silinemez (bağımlı veriler olabilir)."
                    )
        except ValueError:
            raise
        except Exception as e:
            logger.error(f"Lokasyon silme hatasi: {e}")
            raise ValueError("Silme işlemi sırasında bir hata oluştu.")

    async def get_all_paged(
        self,
        skip: int = 0,
        limit: int = 100,
        aktif_only: bool = True,
        zorluk: Optional[str] = None,
        search: Optional[str] = None,
    ) -> dict:
        """Sayfalı ve filtreli lokasyon listesi + Toplam Sayı"""
        filters = {}
        if zorluk:
            filters["zorluk"] = zorluk
        if search:
            filters["search"] = search

        # Get records
        records = await self.repo.get_all(
            offset=skip, limit=limit, include_inactive=not aktif_only, filters=filters
        )

        # Get total count (new repo method needed or generic count)
        total = await self.repo.count(filters=filters, include_inactive=not aktif_only)

        items = []
        skipped = 0
        for r in records:
            try:
                items.append(LokasyonResponse.model_validate(dict(r)))
            except Exception as e:
                logger.error(f"Lokasyon validasyon hatasi (ID {r.get('id')}): {e}")
                skipped += 1

        # Adjust total downward by skipped records on this page so the frontend
        # doesn't navigate to pages that would return 0 items.
        return {"items": items, "total": max(0, total - skipped)}

    async def analyze_route(self, lokasyon_id: int) -> dict:
        """Hibrit RouteService kullanarak güzergahı analiz et ve güncelle"""
        # Centralized logic via RouteService (Hybrid + Validation support)
        from app.services.route_service import get_route_service

        # 1. Lokasyon bilgilerini getir
        loc = await self.repo.get_by_id(lokasyon_id)
        if not loc or not all(
            [
                loc.get("cikis_lat"),
                loc.get("cikis_lon"),
                loc.get("varis_lat"),
                loc.get("varis_lon"),
            ]
        ):
            raise ValueError(f"Lokasyon {lokasyon_id} koordinat bilgileri eksik.")

        # 2. RouteService üzerinden analiz yap (Hybrid: ORS -> Validator -> Mapbox Fallback)
        route_service = get_route_service()
        # RouteService accepts (lon, lat) tuples
        start_coords = (loc["cikis_lon"], loc["cikis_lat"])
        end_coords = (loc["varis_lon"], loc["varis_lat"])

        # use_cache=False because we want fresh analysis/correction
        result = await route_service.get_route_details(
            start_coords, end_coords, use_cache=False
        )

        if "error" in result:
            raise ValueError(f"Analiz hatası: {result['error']}")

        # 3. Sonuçları veritabanına yansıt
        await self.repo.update(
            lokasyon_id,
            mesafe_km=result["distance_km"],
            tahmini_sure_saat=round(result["duration_min"] / 60, 2),
            api_mesafe_km=result["distance_km"],
            api_sure_saat=round(result["duration_min"] / 60, 2),
            ascent_m=result["ascent_m"],
            descent_m=result["descent_m"],
            flat_distance_km=result["flat_distance_km"],
            otoban_mesafe_km=result.get("otoban_mesafe_km"),
            sehir_ici_mesafe_km=result.get("sehir_ici_mesafe_km"),
            zorluk=result.get("difficulty", loc.get("zorluk", "Normal")),
            source=result.get("source"),
            is_corrected=result.get("is_corrected", False),
            correction_reason=result.get("correction_reason"),
            route_analysis=result.get("route_analysis"),
            distributions=result.get("distributions"),
            last_api_call=datetime.now(timezone.utc),
        )

        logger.info(
            f"Güzergah {lokasyon_id} hibrit servis ile güncellendi. Kaynak: {result.get('source')}"
        )

        # Baseline yakıt tahmini (standart TIR, 13t yük — güzergah kartında göstermek için)
        try:
            import asyncio

            from app.core.ml.physics_fuel_predictor import (
                PhysicsBasedFuelPredictor,
                RouteConditions,
            )

            predictor = PhysicsBasedFuelPredictor()
            route_conds = RouteConditions(
                distance_km=result["distance_km"],
                load_ton=13.0,
                ascent_m=result.get("ascent_m", 0) or 0,
                descent_m=result.get("descent_m", 0) or 0,
                flat_distance_km=result.get("flat_distance_km", 0) or 0,
                route_analysis=result.get("route_analysis"),
            )
            fuel_pred = await asyncio.to_thread(predictor.predict, route_conds)
            await self.repo.update(lokasyon_id, tahmini_yakit_lt=fuel_pred.total_liters)
            result["tahmini_yakit_lt"] = fuel_pred.total_liters
        except Exception as e:
            logger.warning(f"Baseline yakıt tahmini başarısız (ID: {lokasyon_id}): {e}")

        return result


def get_lokasyon_service() -> LokasyonService:
    from app.core.container import get_container

    return get_container().lokasyon_service
