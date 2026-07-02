"""
TIR Yakıt Takip Sistemi - Sefer Yazma Servisi
Command-Query Separation (CQS) prensibi gereği yazma (Create/Update/Delete) işlemlerini yönetir.
"""

from datetime import date, timedelta
from typing import Any, Dict, List, Optional, cast

from pydantic import ValidationError

from app.core.exceptions import RouteProcessingError
from app.core.utils.type_helpers import safe_float
from app.database.unit_of_work import UnitOfWork
from app.schemas.sefer import SeferCreate, SeferUpdate, TripStatus


def get_uow():
    """Module-level UnitOfWork factory — patchable in unit tests."""
    return UnitOfWork()


from app.core.services.route_validator import RouteValidator  # noqa: E402
from app.core.utils.sefer_status import (  # noqa: E402
    SEFER_STATUS_IPTAL,
    SEFER_STATUS_PLANLANDI,
    SEFER_STATUS_TAMAMLANDI,
    ensure_canonical_sefer_status,
)
from app.database.repositories.sefer_repo import (  # noqa: E402
    SeferRepository,
    get_sefer_repo,
)
from app.infrastructure.audit import audit_log  # noqa: E402
from app.infrastructure.events.event_bus import (  # noqa: E402
    Event,
    EventBus,
    EventType,
    get_event_bus,
    publishes,
)
from app.infrastructure.events.outbox_service import get_outbox_service  # noqa: E402
from app.infrastructure.logging.logger import get_logger  # noqa: E402
from app.infrastructure.monitoring.service_probe import monitor_errors  # noqa: E402

logger = get_logger(__name__)

# 2026-07-02 prod-grade denetimi P2 (Tier B madde 8): aynı literal 3 yerde
# tekrarlanmıştı (_predict_via_estimator, _predict_outbound legacy yolu,
# bulk_add_sefer) — biri güncellenip diğerleri unutulursa coverage_pct
# sessizce sapabilirdi. Mapbox+Open-Meteo zincirinde cache hit sub-saniye,
# miss ~2sn sürüyor; 2.5s emniyetli tampon.
_PREDICTION_TIMEOUT_SECONDS = 2.5


def _safe_durum(value: object) -> str:
    """Coerce a sefer durum to a canonical value (Planned/Completed/Cancelled).

    Folds Turkish/legacy values; for empty or unmappable input falls back to
    Planned instead of inserting a raw value that violates the DB durum-enum
    CHECK constraint (Sentry LOJINEXT-19G/19H on bulk Excel import).
    """
    try:
        return (
            ensure_canonical_sefer_status(value, allow_none=False)
            or SEFER_STATUS_PLANLANDI
        )
    except ValueError:
        return SEFER_STATUS_PLANLANDI


class SeferWriteService:
    """
    Sefer yazma işlemleri (Create, Update, Delete).
    """

    # --- PHASE 6: PROD-READY ENFORCEMENT ---
    # Yalnızca canonical durumlar (Planned/Completed/Cancelled) — DB CHECK ile
    # birebir. ASSIGNED/IN_PROGRESS DB'de yok (ensure_canonical_sefer_status
    # reddeder) ve eski geçiş tanımları ölü koddu (ARCH-003).
    ALLOWED_TRANSITIONS = {
        TripStatus.PLANNED: [
            TripStatus.COMPLETED,
            TripStatus.CANCELLED,
        ],
        TripStatus.COMPLETED: [],  # Terminal
        TripStatus.CANCELLED: [
            TripStatus.PLANNED
        ],  # Allow re-planning after cancellation
    }
    # Alias kept for backward-compat with tests and external references
    VALID_STATUS_TRANSITIONS = ALLOWED_TRANSITIONS

    def __init__(
        self,
        repo: Optional[SeferRepository] = None,
        event_bus: Optional[EventBus] = None,
    ):
        self.repo = repo or get_sefer_repo()
        self.event_bus = event_bus or get_event_bus()

    @staticmethod
    def _build_route_details_snapshot(
        source: Optional[Dict[str, Any]],
    ) -> Optional[Dict[str, Any]]:
        if not isinstance(source, dict):
            return None

        route_analysis = source.get("route_analysis")
        if not isinstance(route_analysis, dict):
            route_analysis = source.get("rota_detay")

        snapshot: Dict[str, Any] = {}
        if isinstance(route_analysis, dict):
            snapshot["route_analysis"] = dict(route_analysis)

        for key in ("otoban_mesafe_km", "sehir_ici_mesafe_km"):
            if source.get(key) is not None:
                snapshot[key] = source.get(key)

        return snapshot or None

    @staticmethod
    def _build_prediction_quality_flags(
        route_details: Optional[Dict[str, Any]] = None,
        weather_factor: Optional[float] = None,
    ) -> Dict[str, Any]:
        route_analysis = (
            route_details.get("route_analysis")
            if isinstance(route_details, dict)
            else None
        )
        return {
            "canonical_prediction": True,
            "route_available": bool(route_details),
            "route_analysis_available": isinstance(route_analysis, dict),
            "weather_factor_applied": weather_factor is not None,
        }

    @staticmethod
    def _build_prediction_route_analysis(
        route_details: Optional[Dict[str, Any]] = None,
        weather_factor: Optional[float] = None,
    ) -> Optional[Dict[str, Any]]:
        analysis: Dict[str, Any] = {}
        if isinstance(route_details, dict):
            route_analysis = route_details.get("route_analysis")
            if isinstance(route_analysis, dict):
                analysis.update(route_analysis)
            # Also carry the standalone distributions column (may differ from
            # route_analysis["distributions"] if route_analysis was never stored)
            distributions = route_details.get("distributions")
            if isinstance(distributions, dict) and "distributions" not in analysis:
                analysis["distributions"] = distributions
        if weather_factor is not None:
            analysis["weather_factor"] = float(weather_factor)
        return analysis or None

    @classmethod
    def _extract_prediction_values(
        cls,
        prediction: Optional[Dict[str, Any]],
        quality_flags: Optional[Dict[str, Any]] = None,
    ) -> tuple[Optional[float], Optional[Dict[str, Any]]]:
        if not isinstance(prediction, dict):
            return None, None

        canonical_value = safe_float(prediction.get("tahmini_tuketim"))
        if canonical_value is None:
            return None, None

        meta: Dict[str, Any] = {
            "input_quality": {
                "canonical_prediction": True,
                **(quality_flags or {}),
            }
        }

        tahmini_litre = safe_float(prediction.get("tahmini_litre"))
        if tahmini_litre is None:
            tahmini_litre = safe_float(prediction.get("prediction_liters"))
        if tahmini_litre is not None:
            meta["tahmini_litre"] = round(tahmini_litre, 1)

        for key in (
            "model_used",
            "model_version",
            "status",
            "warning_level",
            "insight",
            "explanation_summary",
        ):
            if prediction.get(key) is not None:
                meta[key] = prediction.get(key)

        for key in ("confidence_score", "confidence_low", "confidence_high"):
            numeric_value = safe_float(prediction.get(key))
            if numeric_value is not None:
                meta[key] = numeric_value

        if prediction.get("fallback_triggered") is not None:
            meta["fallback_triggered"] = bool(prediction.get("fallback_triggered"))

        faktorler = prediction.get("faktorler")
        if isinstance(faktorler, dict):
            meta["faktorler"] = faktorler

        return canonical_value, meta

    @staticmethod
    def _validate_sefer_create(data: "SeferCreate", trip_date: date) -> None:
        """Temel sefer oluşturma validasyonları."""
        if data.cikis_yeri == data.varis_yeri:
            raise RouteProcessingError(
                "Çıkış ve varış yeri aynı olamaz",
                field_name="cikis_yeri",
                reason="SAME_ORIGIN_DESTINATION",
            )
        if data.mesafe_km <= 0:
            raise RouteProcessingError(
                "Mesafe 0'dan büyük olmalıdır",
                field_name="mesafe_km",
                reason="INVALID_DISTANCE",
            )
        if trip_date > date.today() + timedelta(days=365):
            raise RouteProcessingError(
                "Sefer tarihi 1 yıldan daha ileri bir tarih olamaz",
                field_name="tarih",
                reason="DATE_TOO_FAR",
            )

    @staticmethod
    def _check_reprediction_needed(update_data: Dict[str, Any]) -> bool:
        """Tahmin etkileyen alan değişikliği var mı kontrol eder."""
        repredict_fields = {
            "guzergah_id",
            "arac_id",
            "sofor_id",
            "net_kg",
            "ton",
            "tarih",
            "bos_sefer",
            "dorse_id",
        }
        return any(field in update_data for field in repredict_fields)

    async def _repredikt_for_update(
        self,
        uow: Any,
        current_sefer: Dict[str, Any],
        update_data: Dict[str, Any],
    ) -> None:
        """Update sırasında gerektiğinde tahmini yeniler.

        update_data'yı in-place günceller.
        """
        # Build prediction parameters (merging old and new data)
        pred_arac_id = update_data.get("arac_id", current_sefer.get("arac_id"))
        pred_sofor_id = update_data.get("sofor_id", current_sefer.get("sofor_id"))
        pred_tarih = update_data.get("tarih", current_sefer.get("tarih"))
        pred_bos_sefer = update_data.get("bos_sefer", current_sefer.get("bos_sefer"))
        pred_dorse_id = update_data.get("dorse_id", current_sefer.get("dorse_id"))

        # Tonaj logic (Standardized)
        pred_ton = update_data.get("ton")
        if pred_ton is None:
            pred_net_kg = update_data.get("net_kg", current_sefer.get("net_kg", 0))
            pred_ton = float(pred_net_kg) / 1000.0 if pred_net_kg else 0.0

        # If it's an empty return (bos_sefer), ton is essentially 0
        if pred_bos_sefer:
            pred_ton = 0.0

        # Get route info if available
        pred_mesafe = update_data.get("mesafe_km", current_sefer.get("mesafe_km", 0.0))
        pred_ascent = update_data.get("ascent_m", current_sefer.get("ascent_m", 0.0))
        pred_descent = update_data.get("descent_m", current_sefer.get("descent_m", 0.0))
        pred_flat = update_data.get(
            "flat_distance_km", current_sefer.get("flat_distance_km", 0.0)
        )
        prediction_route_details = self._build_route_details_snapshot(
            {
                "route_analysis": current_sefer.get("rota_detay"),
                "otoban_mesafe_km": current_sefer.get("otoban_mesafe_km"),
                "sehir_ici_mesafe_km": current_sefer.get("sehir_ici_mesafe_km"),
            }
        )

        # Enrich from NEW route if changed
        if "guzergah_id" in update_data and update_data["guzergah_id"]:
            route_dict = await uow.lokasyon_repo.get_by_id(update_data["guzergah_id"])
            if route_dict:
                prediction_route_details = self._build_route_details_snapshot(
                    route_dict
                )
                pred_mesafe = route_dict.get("mesafe_km", pred_mesafe)
                pred_ascent = route_dict.get("ascent_m", pred_ascent)
                pred_descent = route_dict.get("descent_m", pred_descent)
                pred_flat = route_dict.get("flat_distance_km", pred_flat)
                # Actually apply these to update_data as well
                update_data["mesafe_km"] = pred_mesafe
                update_data["ascent_m"] = pred_ascent
                update_data["descent_m"] = pred_descent
                update_data["flat_distance_km"] = pred_flat

                # Enhanced Route Data
                if "route_analysis" in route_dict:
                    update_data["rota_detay"] = route_dict["route_analysis"]
                if "otoban_mesafe_km" in route_dict:
                    update_data["otoban_mesafe_km"] = route_dict["otoban_mesafe_km"]
                if "sehir_ici_mesafe_km" in route_dict:
                    update_data["sehir_ici_mesafe_km"] = route_dict[
                        "sehir_ici_mesafe_km"
                    ]

        # Trigger Prediction
        try:
            logger.info(
                "Triggering PREDICTION: Arac=%s, Mesafe=%s, Ton=%s, Empty=%s",
                pred_arac_id,
                pred_mesafe,
                pred_ton,
                pred_bos_sefer,
            )
            from app.services.prediction_service import get_prediction_service

            pred_service = get_prediction_service()

            prediction = await pred_service.predict_consumption(
                arac_id=pred_arac_id,
                mesafe_km=pred_mesafe,
                ton=pred_ton,
                ascent_m=pred_ascent,
                descent_m=pred_descent,
                flat_distance_km=pred_flat,
                sofor_id=pred_sofor_id,
                target_date=pred_tarih
                if isinstance(pred_tarih, date)
                else date.fromisoformat(str(pred_tarih)),
                bos_sefer=pred_bos_sefer,
                dorse_id=pred_dorse_id,
                route_analysis=self._build_prediction_route_analysis(
                    route_details=prediction_route_details
                ),
            )
            tahmini_tuketim, tahmin_meta = self._extract_prediction_values(
                prediction,
                quality_flags=self._build_prediction_quality_flags(
                    route_details=prediction_route_details
                ),
            )
            if tahmini_tuketim is not None:
                update_data["tahmini_tuketim"] = tahmini_tuketim
            if tahmin_meta is not None:
                update_data["tahmin_meta"] = tahmin_meta
            if tahmini_tuketim is not None:
                logger.info(
                    "Re-prediction SUCCESS: %s L",
                    update_data["tahmini_tuketim"],
                )
        except Exception as pe:
            logger.error(f"Re-prediction error: {pe}", exc_info=True)

    # MV refresh için arka plan task'ları GC'den korumak adına sınıf bazlı set.
    # Aksi halde task.add_done_callback hiç çalışmayabilir.
    _bg_stats_tasks: set = set()

    async def _refresh_stats(self, uow: UnitOfWork) -> None:
        """İstatistik MV'sini arka planda yenile.

        Önceki davranış: sync REFRESH MATERIALIZED VIEW tüm POST'u 4-10 sn
        bloke ediyordu (PostgreSQL MV refresh O(N), her sefer ekleme/güncelleme
        sonrası tetikleniyor). Production'da yeni AsyncSession üzerinden
        fire-and-forget; test ortamında concurrent session ile çakışmamak
        için sync (UoW içinde) refresh tercih edilir.
        """
        import os

        # pytest fixture session'ları ile çakışmamak için test ortamında
        # mevcut UoW üzerinden sync refresh.
        if os.getenv("PYTEST_CURRENT_TEST"):
            try:
                await uow.sefer_repo.refresh_stats_mv()
            except Exception as e:
                logger.debug(f"Test sync stats refresh skipped: {e}")
            return

        async def _refresh_in_bg() -> None:
            from app.database.connection import AsyncSessionLocal
            from app.database.repositories.sefer_repo import SeferRepository

            try:
                async with AsyncSessionLocal() as session:
                    repo = SeferRepository(session=session)
                    await repo.refresh_stats_mv()
                    await session.commit()
            except Exception as e:
                logger.warning(f"Post-write stats refresh (bg) failed: {e}")

        import asyncio

        task = asyncio.create_task(_refresh_in_bg())
        self._bg_stats_tasks.add(task)
        task.add_done_callback(self._bg_stats_tasks.discard)

    async def _resolve_route(
        self, uow: Any, data: "SeferCreate"
    ) -> Optional[Dict[str, Any]]:
        """Güzergah metadata'sını çeker ve data'ya elevation alanlarını yazar."""
        if not data.guzergah_id:
            return None
        route_dict = await uow.lokasyon_repo.get_by_id(data.guzergah_id)
        if not route_dict:
            return None
        if not data.mesafe_km:
            data.mesafe_km = route_dict.get("mesafe_km", 0.0)
        if not data.ascent_m:
            data.ascent_m = route_dict.get("ascent_m", 0.0)
        if not data.descent_m:
            data.descent_m = route_dict.get("descent_m", 0.0)
        return route_dict

    async def _predict_via_estimator(
        self,
        uow: Any,
        data: "SeferCreate",
        trip_date: date,
        route_dict: Optional[Dict[str, Any]],
    ) -> tuple:
        """Phase 4.4: SeferFuelEstimator ile yeni tahmin akışı.

        ``settings.USE_SEFER_FUEL_ESTIMATOR=True`` ise ``_predict_outbound``
        en başta bunu çağırır. Mapbox + Open-Meteo elevation + weather +
        physics + adjustment factors birleşimi (Phase 4.3).

        Returns:
            (tuketim, meta, simulation_id) — meta dict'ine simulation_id
            de inject edilir (debug için). Mevcut helper'lar uyumlu kalır.
        """
        try:
            from app.core.services.sefer_fuel_estimator import (
                SeferFuelInput,
                get_sefer_fuel_estimator,
            )

            estimator = get_sefer_fuel_estimator()
            ton = float(data.ton or (data.net_kg / 1000.0 if data.net_kg else 0.0))

            cikis_lat = cikis_lon = varis_lat = varis_lon = None
            if route_dict:
                cikis_lat = route_dict.get("cikis_lat")
                cikis_lon = route_dict.get("cikis_lon")
                varis_lat = route_dict.get("varis_lat")
                varis_lon = route_dict.get("varis_lon")

            inp = SeferFuelInput(
                arac_id=data.arac_id,
                sofor_id=data.sofor_id,
                dorse_id=data.dorse_id,
                ton=ton,
                target_date=trip_date,
                bos_sefer=bool(data.bos_sefer),
                lokasyon_id=data.guzergah_id,
                cikis_lat=cikis_lat,
                cikis_lon=cikis_lon,
                varis_lat=varis_lat,
                varis_lon=varis_lon,
            )

            import asyncio as _asyncio

            try:
                estimate = await _asyncio.wait_for(
                    estimator.predict(inp, persist=True, session=uow.session),
                    timeout=_PREDICTION_TIMEOUT_SECONDS,
                )
            except _asyncio.TimeoutError:
                logger.warning(
                    "SeferFuelEstimator timeout (>%ss) for arac=%s — "
                    "sefer kaydı tahmin olmadan kaydedilecek.",
                    _PREDICTION_TIMEOUT_SECONDS,
                    data.arac_id,
                )
                from app.infrastructure.monitoring.silent_fallback_probe import (
                    record_silent_fallback,
                )

                record_silent_fallback("sefer_estimator_timeout", arac_id=data.arac_id)
                return None, None, None

            if estimate is None:
                return None, None, None

            legacy = estimate.to_legacy_prediction_dict()
            tuketim, meta = self._extract_prediction_values(
                legacy,
                quality_flags=self._build_prediction_quality_flags(
                    route_details=route_dict
                ),
            )
            if meta is not None:
                meta["simulation_id"] = estimate.simulation_id
                meta["estimator_source"] = "SeferFuelEstimator"
            return tuketim, meta, estimate.simulation_id
        except Exception as exc:
            logger.error("SeferFuelEstimator path failed: %s", exc)
            return None, None, None

    async def _predict_outbound(
        self,
        uow: Any,
        data: "SeferCreate",
        trip_date: date,
        route_dict: Optional[Dict[str, Any]],
    ) -> tuple:
        """Gidiş seferi için yakıt tahmini çalıştırır.

        Phase 4.4 (USE_SEFER_FUEL_ESTIMATOR feature flag):
        - True: yeni SeferFuelEstimator pipeline kullanılır → tuple-3
          (tuketim, meta, simulation_id) döner
        - False (default): eski predict_consumption akışı → tuple-3'ün
          son elemanı None
        """
        from app.config import settings

        if settings.USE_SEFER_FUEL_ESTIMATOR:
            return await self._predict_via_estimator(uow, data, trip_date, route_dict)
        try:
            from app.core.services.weather_service import get_weather_service
            from app.services.prediction_service import get_prediction_service

            pred_service = get_prediction_service()
            weather_service = get_weather_service()
            weather_factor: Optional[float] = None

            if data.guzergah_id and route_dict:
                try:
                    c_lat = route_dict.get("cikis_lat")
                    c_lon = route_dict.get("cikis_lon")
                    v_lat = route_dict.get("varis_lat")
                    v_lon = route_dict.get("varis_lon")
                    if c_lat and v_lat:
                        w_res = await weather_service.get_trip_impact_analysis(
                            cikis_lat=c_lat,
                            cikis_lon=c_lon,
                            varis_lat=v_lat,
                            varis_lon=v_lon,
                        )
                        if (
                            w_res.get("success")
                            and w_res.get("fuel_impact_factor") is not None
                        ):
                            weather_factor = w_res["fuel_impact_factor"]
                except Exception as we:
                    logger.warning(f"Weather failed: {we}")

            prediction_quality = self._build_prediction_quality_flags(
                route_details=route_dict,
                weather_factor=weather_factor,
            )
            # ML cold-start veya schema mismatch senaryolarında sefer kaydı
            # response'u 10sn beklemesin — timeout durumunda physics fallback.
            import asyncio as _asyncio

            try:
                prediction = await _asyncio.wait_for(
                    pred_service.predict_consumption(
                        arac_id=data.arac_id,
                        mesafe_km=data.mesafe_km,
                        ton=data.ton or round(data.net_kg / 1000, 2),
                        ascent_m=data.ascent_m or 0.0,
                        descent_m=data.descent_m or 0.0,
                        flat_distance_km=data.flat_distance_km or 0.0,
                        sofor_id=data.sofor_id,
                        target_date=trip_date,
                        bos_sefer=data.bos_sefer,
                        dorse_id=data.dorse_id,
                        route_analysis=self._build_prediction_route_analysis(
                            route_details=route_dict,
                            weather_factor=weather_factor,
                        ),
                    ),
                    timeout=_PREDICTION_TIMEOUT_SECONDS,
                )
            except _asyncio.TimeoutError:
                logger.warning(
                    "Prediction timeout (>%ss) for arac=%s — sefer kaydı "
                    "tahmin olmadan kaydedilecek.",
                    _PREDICTION_TIMEOUT_SECONDS,
                    data.arac_id,
                )
                from app.infrastructure.monitoring.silent_fallback_probe import (
                    record_silent_fallback,
                )

                record_silent_fallback("legacy_predict_timeout", arac_id=data.arac_id)
                return None, None, None
            tuk, meta = self._extract_prediction_values(
                prediction, quality_flags=prediction_quality
            )
            # Phase 4.4: tuple-3 — eski path simulation_id YOK
            return tuk, meta, None
        except Exception as pe:
            logger.error(f"Tahmin servisi hatası: {pe}")
            return None, None, None

    @staticmethod
    def _sync_weight_fields(data: "SeferCreate", arac: Dict[str, Any]) -> None:
        """bos/dolu/net ağırlık tutarlılığını in-place sağlar."""
        b_kg = data.bos_agirlik_kg or arac.get("bos_agirlik_kg", 0)
        n_kg = data.net_kg or 0
        d_kg = data.dolu_agirlik_kg or (b_kg + n_kg)
        if data.dolu_agirlik_kg:
            n_kg = d_kg - b_kg
        else:
            d_kg = b_kg + n_kg
        # Negatif net kargo fiziksel olarak imkânsız. Schema her alanı tek tek
        # ge=0 doğruluyor ama dolu<bos ilişkisini görmüyor; DB CHECK ise yalnız
        # ``net = dolu - bos`` aritmetiğini sağladığından negatif net'i kabul
        # eder (örn. net=-2000 = 3000-5000). Negatif ton tahmini de bozar —
        # burada erken ve dostça reddet (endpoint → 400).
        if n_kg < 0:
            raise ValueError(
                "Dolu ağırlık boş ağırlıktan küçük olamaz "
                f"(boş={b_kg} kg, dolu={d_kg} kg → net={n_kg} kg)."
            )
        data.bos_agirlik_kg = b_kg
        data.dolu_agirlik_kg = d_kg
        data.net_kg = n_kg
        data.ton = round(n_kg / 1000.0, 2)

    async def _check_sla_delay(
        self,
        uow: UnitOfWork,
        sefer_id: int,
        target_arac_id: Optional[int],
        current_sefer: Dict[str, Any],
    ) -> None:
        """Tamamlanan seferin SLA gecikmesini hesaplar ve outbox'a yazar."""
        try:
            current_full = await uow.sefer_repo.get_by_id(sefer_id)
            if not current_full:
                return
            actual_duration = current_full.get("duration_min")
            planned_duration_min = 0
            if current_full.get("guzergah_id"):
                route = await uow.lokasyon_repo.get_by_id(current_full["guzergah_id"])
                if route and route.get("tahmini_sure_saat"):
                    planned_duration_min = int(route["tahmini_sure_saat"] * 60)
            if planned_duration_min > 0 and actual_duration:
                delay_min = actual_duration - planned_duration_min
                outbox = get_outbox_service()
                await outbox.save_event(
                    event_type=EventType.SLA_DELAY,
                    payload={
                        "sefer_id": sefer_id,
                        "arac_id": target_arac_id or current_sefer.get("arac_id"),
                        "planned_min": planned_duration_min,
                        "actual_min": actual_duration,
                        "delay_min": delay_min,
                    },
                    uow=uow,
                )
        except Exception as sla_err:
            logger.error(f"SLA Check fail: {sla_err}")

    async def _handle_round_trip_on_update(
        self,
        uow: UnitOfWork,
        sefer_id: int,
        update_data: Dict[str, Any],
    ) -> None:
        """Update sırasında is_round_trip=True ise dönüş seferini oluşturur.

        Dönüş seferi oluşturma başarısız olursa exception'ı YUTMAZ — çağıranın
        kendi except/raise zincirine (bkz. _update_sefer_uow) yeniden fırlatılır,
        böylece ana update işlemiyle atomik kalır. Önceki davranış (bare
        `except Exception: logger.error(...)`) hatayı sessizce yutuyordu; sonuç
        olarak `update_sefer` True dönüyor ve kullanıcı dönüş seferinin
        oluştuğunu sanıyordu, oysa hiç oluşmamış olabiliyordu (2026-07-01
        prod-grade denetimi P0 bulgusu).

        İstisna: mevcut sefer kaydının (current_full) kendisi yapısal olarak
        round-trip mirror'ı için geçersizse (ör. mesafe_km=0, tek karakterlik
        cikis_yeri — SeferCreate validasyonunu geçemeyen ESKİ/edge-case veri),
        bu durum "_create_return_trip başarısız oldu" ile aynı kategori
        değildir — kaynak verinin kalitesi, kullanıcının şu anki işlemiyle
        ilgisizdir. Bu durumda dönüş seferi sessizce atlanır (ana update
        etkilenmez); yalnızca gerçek oluşturma hataları (_create_return_trip
        içindeki) propagate edilir.
        """
        current_full = await uow.sefer_repo.get_by_id(sefer_id)
        if not current_full:
            return

        try:
            full_sefer_obj = SeferCreate(  # type: ignore[call-arg]
                **{
                    "sefer_no": current_full.get("sefer_no"),
                    "tarih": current_full.get("tarih"),
                    "saat": current_full.get("saat"),
                    "arac_id": current_full.get("arac_id"),
                    "sofor_id": current_full.get("sofor_id"),
                    "guzergah_id": current_full.get("guzergah_id"),
                    "cikis_yeri": current_full.get("cikis_yeri"),
                    "varis_yeri": current_full.get("varis_yeri"),
                    "mesafe_km": current_full.get("mesafe_km"),
                    "bos_agirlik_kg": current_full.get("bos_agirlik_kg"),
                    "dolu_agirlik_kg": current_full.get("dolu_agirlik_kg"),
                    "net_kg": current_full.get("net_kg"),
                    "bos_sefer": current_full.get("bos_sefer"),
                    "durum": current_full.get("durum"),
                    "is_round_trip": True,
                    "return_net_kg": update_data.get("return_net_kg", 0),
                    "return_sefer_no": update_data.get("return_sefer_no"),
                    "ascent_m": current_full.get("ascent_m"),
                    "descent_m": current_full.get("descent_m"),
                    "flat_distance_km": current_full.get("flat_distance_km"),
                }
            )
        except ValidationError as ve:
            logger.warning(
                "Round-trip mirror verisi geçersiz (sefer %s), dönüş seferi "
                "atlanıyor: %s",
                sefer_id,
                ve,
            )
            return

        potential_return_no = f"{full_sefer_obj.sefer_no}-D"
        existing_return = await uow.sefer_repo.get_by_sefer_no(potential_return_no)
        if not existing_return:
            await self._create_return_trip(
                uow, full_sefer_obj, full_sefer_obj.tarih, sefer_id
            )

    async def _create_return_trip(
        self,
        uow: Any,
        data: SeferCreate,
        trip_date: date,
        ref_sefer_id: int,
        weather_factor: Optional[float] = None,
        route_details: Optional[Dict] = None,
        user_id: Optional[int] = None,
    ) -> None:
        """Helper to create return trip logic (Atomicity support)"""
        return_kg = data.return_net_kg or 0

        is_empty = return_kg == 0

        # Guard: Ensure return_sefer_no has suffix and swap logic is sound
        base_sn = data.sefer_no
        return_sn = data.return_sefer_no
        if not return_sn and base_sn:
            if not base_sn.endswith("-D"):
                return_sn = f"{base_sn}-D"
            else:
                return_sn = f"{base_sn}-R"  # Rare case: return of a return?

        return_tahmini = None
        return_tahmin_meta = None
        if data.arac_id and data.mesafe_km:
            try:
                from app.services.prediction_service import get_prediction_service

                pred_service = get_prediction_service()
                prediction_quality = self._build_prediction_quality_flags(
                    route_details=route_details,
                    weather_factor=weather_factor,
                )

                logger.info(
                    f"Predicting Return Trip: {data.varis_yeri} -> {data.cikis_yeri}, {return_kg}kg"
                )

                return_prediction = await pred_service.predict_consumption(
                    arac_id=data.arac_id,
                    mesafe_km=data.mesafe_km,
                    ton=round(return_kg / 1000, 2),
                    ascent_m=data.descent_m or 0.0,
                    descent_m=data.ascent_m or 0.0,
                    flat_distance_km=data.flat_distance_km or 0.0,
                    sofor_id=data.sofor_id,
                    target_date=trip_date,
                    bos_sefer=is_empty,
                    route_analysis=self._build_prediction_route_analysis(
                        route_details=route_details,
                        weather_factor=weather_factor,
                    ),
                )
                return_tahmini, return_tahmin_meta = self._extract_prediction_values(
                    return_prediction,
                    quality_flags=prediction_quality,
                )
            except Exception as rpe:
                logger.warning(f"Return prediction failed: {rpe}")

        await uow.sefer_repo.add(
            tarih=trip_date,
            arac_id=data.arac_id,
            sofor_id=data.sofor_id,
            guzergah_id=data.guzergah_id,
            mesafe_km=data.mesafe_km,
            net_kg=return_kg,
            sefer_no=return_sn,
            bos_agirlik_kg=data.bos_agirlik_kg,
            dolu_agirlik_kg=0,
            cikis_yeri=data.varis_yeri,
            varis_yeri=data.cikis_yeri,
            saat=data.saat or "",
            bos_sefer=is_empty,
            durum=_safe_durum(data.durum),
            ascent_m=data.descent_m or 0.0,
            descent_m=data.ascent_m or 0.0,
            flat_distance_km=data.flat_distance_km or 0.0,
            tahmini_tuketim=return_tahmini,
            tahmin_meta=return_tahmin_meta,
            rota_detay=route_details.get("route_analysis") if route_details else None,
            otoban_mesafe_km=route_details.get("otoban_mesafe_km")
            if route_details
            else None,
            sehir_ici_mesafe_km=route_details.get("sehir_ici_mesafe_km")
            if route_details
            else None,
            notlar=f"Dönüş seferi (Ref: #{ref_sefer_id})",
            created_by_id=user_id or None,
        )

    @monitor_errors(category="sefer_write", severity="error")
    @audit_log("CREATE", "sefer")
    @publishes(EventType.SEFER_ADDED)
    async def add_sefer(self, data: SeferCreate, user_id: Optional[int] = None) -> int:
        """Yeni bir sefer olusturur."""
        async with UnitOfWork() as uow:
            # State Machine: Initial Status
            if not data.durum:
                # SeferDurum (str Literal) alanına TripStatus str-enum atanıyor;
                # runtime'da eşdeğer ("Planned"), mypy Literal!=enum diyor.
                data.durum = cast("Any", TripStatus.PLANNED)

            # 1. Validation Logic
            # Parse date first (needed by _validate_sefer_create)
            trip_date = (
                data.tarih
                if isinstance(data.tarih, date)
                else date.fromisoformat(str(data.tarih))
            )

            self._validate_sefer_create(data, trip_date)

            # Normalize names
            data.cikis_yeri = data.cikis_yeri.strip().title()
            data.varis_yeri = data.varis_yeri.strip().title()

            # Sefer No duplicate check
            if data.sefer_no:
                existing_sn = await uow.sefer_repo.get_by_sefer_no(data.sefer_no)
                if existing_sn:
                    raise RouteProcessingError(
                        f"Bu sefer numarası zaten kullanımda: {data.sefer_no}",
                        field_name="sefer_no",
                        reason="DUPLICATE_SEFER_NO",
                    )

            # 2. Database Checks
            arac = await uow.arac_repo.get_by_id(data.arac_id)
            if not arac or not arac.get("aktif"):
                raise RouteProcessingError(
                    "Seçilen araç bulunamadı veya pasif.",
                    field_name="arac_id",
                    entity_id=data.arac_id,
                    reason="ARAC_NOT_FOUND",
                )

            sofor = await uow.sofor_repo.get_by_id(data.sofor_id)
            if not sofor or not sofor.get("aktif"):
                raise RouteProcessingError(
                    "Seçilen şoför bulunamadı veya pasif.",
                    field_name="sofor_id",
                    entity_id=data.sofor_id,
                    reason="SOFOR_NOT_FOUND",
                )

            # 2b. Güzergah metadata kalıtımı
            route_dict = await self._resolve_route(uow, data)

            # Validate and correct route data (Elevation anomalies check)
            temp_dict = data.model_dump()
            corrected = RouteValidator.validate_and_correct(temp_dict)
            if corrected.get("is_corrected"):
                data.ascent_m = corrected["ascent_m"]
                data.descent_m = corrected["descent_m"]
                logger.info(
                    f"API Add: Corrected anomalous elevation to {data.ascent_m}m"
                )

            # Ağırlık senkronizasyonu — tahmin ÖNCE yapılmalı: ton=0 tahmini önlemek
            # için bos/dolu/net/ton tutarlılığı prediction input'undan önce çözülmeli.
            self._sync_weight_fields(data, arac)

            # 3. YAKIT TAHMİNİ (Gidiş Leg)
            tahmini_tuk, tahmin_meta, route_sim_id = None, None, None
            if data.arac_id and data.mesafe_km:
                tahmini_tuk, tahmin_meta, route_sim_id = await self._predict_outbound(
                    uow, data, trip_date, route_dict
                )

            # 4. DB Insert (Gidiş)
            sefer_id = await uow.sefer_repo.add(
                tarih=trip_date,
                arac_id=data.arac_id,
                sofor_id=data.sofor_id,
                dorse_id=data.dorse_id,
                guzergah_id=data.guzergah_id,
                route_pair_id=getattr(data, "route_pair_id", None),
                mesafe_km=data.mesafe_km,
                net_kg=data.net_kg,
                sefer_no=data.sefer_no,
                bos_agirlik_kg=data.bos_agirlik_kg,
                dolu_agirlik_kg=data.dolu_agirlik_kg,
                cikis_yeri=data.cikis_yeri,
                varis_yeri=data.varis_yeri,
                saat=data.saat or "",
                bos_sefer=data.bos_sefer,
                durum=_safe_durum(data.durum),
                ascent_m=data.ascent_m or 0.0,
                descent_m=data.descent_m or 0.0,
                flat_distance_km=data.flat_distance_km or 0.0,
                tahmini_tuketim=tahmini_tuk,
                tahmin_meta=tahmin_meta,
                route_simulation_id=route_sim_id,
                rota_detay=route_dict.get("route_analysis") if route_dict else None,
                otoban_mesafe_km=route_dict.get("otoban_mesafe_km")
                if route_dict
                else None,
                sehir_ici_mesafe_km=route_dict.get("sehir_ici_mesafe_km")
                if route_dict
                else None,
                notlar=data.notlar,
                created_by_id=user_id or None,
            )

            # 5. ROUND-TRIP (Dönüş Seferi)
            if data.is_round_trip:
                await self._create_return_trip(
                    uow,
                    data,
                    trip_date,
                    sefer_id,
                    route_details=route_dict,
                    user_id=user_id,
                )

            # Phase 7: Atomic Outbox Persistence
            from app.infrastructure.events.outbox_service import get_outbox_service

            outbox = get_outbox_service()
            await outbox.save_event(
                event_type=EventType.SEFER_ADDED,
                payload={"sefer_id": int(sefer_id), "sefer_no": data.sefer_no},
                uow=uow,
            )

            # 6. Atomic Commit
            await uow.commit()
            # 7. Refresh Stats (Post-commit)
            await self._refresh_stats(uow)
            logger.info(f"Sefer(ler) başarıyla kaydedildi. ID: {sefer_id}")
            return int(sefer_id)

    @monitor_errors(category="sefer_write", severity="error")
    async def update_sefer(
        self, sefer_id: int, data: SeferUpdate, user_id: Optional[int] = None
    ) -> bool:
        """Sefer gunceller."""
        async with UnitOfWork() as uow:
            success = await self._update_sefer_uow(uow, sefer_id, data, user_id)
            if success:
                await uow.commit()
                await self._refresh_stats(uow)
            return success

    async def _update_sefer_uow(
        self,
        uow: UnitOfWork,
        sefer_id: int,
        data: SeferUpdate,
        user_id: Optional[int] = None,
    ) -> bool:
        """Sefer güncelleme mantığı (Paylaşımlı UoW destekli)."""
        # Status Transition Matrix
        # Defines which statuses can move to which
        VALID_TRANSITIONS = self.ALLOWED_TRANSITIONS

        try:
            # Fetch current state for transition check
            current_sefer = await uow.sefer_repo.get_by_id(sefer_id, for_update=True)
            if not current_sefer:
                raise RouteProcessingError(
                    f"Sefer bulunamadı: {sefer_id}",
                    entity_id=sefer_id,
                    reason="SEFER_NOT_FOUND",
                )

            # mode='json' serializes enums to their .value strings so DB writes and
            # comparisons always see plain strings, not TripStatus.X repr.
            update_data = data.model_dump(exclude_unset=True, mode="json")
            if not update_data:
                return True  # Nothing to update

            if "tarih" in update_data and isinstance(update_data["tarih"], str):
                update_data["tarih"] = date.fromisoformat(update_data["tarih"])

            # B-004: Optimistic Locking version check
            if "version" in update_data and update_data["version"] is not None:
                current_version = current_sefer.get("version", 1)
                if current_version != update_data["version"]:
                    from fastapi import HTTPException

                    raise HTTPException(
                        status_code=409,
                        detail="Bu kayıt başka biri tarafından güncellenmiş. Lütfen sayfayı yenileyin.",
                    )
                # Increment version locally.
                update_data["version"] = current_version + 1

            # Status Transition Validation
            new_status = update_data.get("durum")
            if new_status:
                old_status = ensure_canonical_sefer_status(
                    current_sefer.get("durum", SEFER_STATUS_PLANLANDI),
                    field_name="durum",
                    allow_none=False,
                )
                if old_status != new_status:
                    # ALLOWED_TRANSITIONS TripStatus str-enum ile key'li; old_status
                    # canonical str — runtime'da eşit hash, mypy key tipini ayırıyor.
                    allowed = VALID_TRANSITIONS.get(cast("Any", old_status), [])
                    if new_status not in allowed:
                        raise ValueError(
                            f"Geçersiz durum geçişi: '{old_status}' -> '{new_status}'"
                        )

            if user_id:
                update_data["updated_by_id"] = user_id

            # Sefer No duplicate check for update
            if "sefer_no" in update_data and update_data["sefer_no"]:
                if current_sefer.get("sefer_no") != update_data["sefer_no"]:
                    existing = await uow.sefer_repo.get_by_sefer_no(
                        update_data["sefer_no"]
                    )
                    if existing:
                        raise ValueError(
                            f"Bu sefer numarası zaten kullanımda: {update_data['sefer_no']}"
                        )

            # Active Trip Check for Update
            target_arac_id = update_data.get("arac_id")

            # RE-PREDICTION LOGIC
            # Check if fields affecting fuel prediction are changed
            if self._check_reprediction_needed(update_data):
                await self._repredikt_for_update(uow, current_sefer, update_data)

            # Validate and correct route data before final database write
            update_data = RouteValidator.validate_and_correct(update_data)

            # Ağırlık senkronizasyonu
            # dolu - bos = net kısıtının bozulmaması için tüm alanlar güncellenir.
            if any(
                k in update_data
                for k in ["net_kg", "bos_agirlik_kg", "dolu_agirlik_kg"]
            ):
                # Değerleri al (yeni yoksa mevcut olanı kullan)
                b_kg = update_data.get(
                    "bos_agirlik_kg", current_sefer.get("bos_agirlik_kg", 0)
                )
                d_kg = update_data.get(
                    "dolu_agirlik_kg", current_sefer.get("dolu_agirlik_kg", 0)
                )
                n_kg = update_data.get("net_kg", current_sefer.get("net_kg", 0))

                # Öncelik sırasına göre hesapla
                if "dolu_agirlik_kg" in update_data or "bos_agirlik_kg" in update_data:
                    # Dolu veya Boş değiştiyse Net'i güncelle
                    n_kg = d_kg - b_kg
                    update_data["net_kg"] = n_kg
                elif "net_kg" in update_data:
                    # Sadece Net değiştiyse Dolu'yu güncelle
                    d_kg = b_kg + n_kg
                    update_data["dolu_agirlik_kg"] = d_kg

                # Tonajı her durumda güncelle
                update_data["ton"] = round(n_kg / 1000.0, 2)

            success = await uow.sefer_repo.update_sefer(id=sefer_id, **update_data)

            if success:
                # ROUTE EVENTS
                if new_status:
                    if new_status == SEFER_STATUS_TAMAMLANDI:
                        await self.event_bus.publish_async(
                            Event(
                                type=EventType.ROUTE_COMPLETED,
                                data={
                                    "sefer_id": sefer_id,
                                    "arac_id": target_arac_id
                                    or current_sefer.get("arac_id"),
                                },
                                source="SeferWriteService.update_sefer",
                            )
                        )
                        await self._check_sla_delay(
                            uow, sefer_id, target_arac_id, current_sefer
                        )

                # ROUND-TRIP CHECK
                if update_data.get("is_round_trip"):
                    await self._handle_round_trip_on_update(uow, sefer_id, update_data)

            return bool(success)

        except Exception as e:
            logger.error(f"Sefer guncelleme hatasi (UoW): {e}")
            raise

    @monitor_errors(category="sefer_write", severity="error")
    @audit_log("DELETE", "sefer")
    @publishes(EventType.SEFER_DELETED)
    async def delete_sefer(self, sefer_id: int) -> bool:
        """Sefer sil (Soft Delete - Atomik)."""
        async with UnitOfWork() as uow:
            success = await self._delete_sefer_uow(uow, sefer_id)
            if success:
                await uow.commit()
                await self._refresh_stats(uow)
            return success

    async def _delete_sefer_uow(self, uow: UnitOfWork, sefer_id: int) -> bool:
        """Sefer silme mantığı (Paylaşımlı UoW destekli)."""
        try:
            # Soft delete by default, as per audit result
            success = await uow.sefer_repo.delete(sefer_id)
            if success:
                logger.info(f"Sefer silindi (Soft Deleted): ID {sefer_id}")
            return bool(success)
        except Exception as e:
            logger.error(f"Sefer silme hatasi (UoW): {e}")
            raise

    async def bulk_update_status(
        self, sefer_ids: List[int], new_status: str, user_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Birden fazla seferin durumunu toplu güncelle.
        N+1 Transaction sorunu giderildi (Tek UoW).
        """
        normalized_status = ensure_canonical_sefer_status(
            new_status, field_name="new_status", allow_none=False
        )
        if normalized_status == SEFER_STATUS_IPTAL:
            raise ValueError(
                "Toplu durum güncelleme iptal kabul etmez. İptal için bulk_cancel kullanın."
            )

        success_count = 0
        failed = []

        async with UnitOfWork() as uow:
            for sid in sefer_ids:
                try:
                    success = await self._update_sefer_uow(
                        uow,
                        sid,
                        # SeferUpdate alanları tümü optional; pydantic.mypy plugin
                        # olmadığı için mypy Field() default'larını görmez (call-arg
                        # false-positive) ve str->TripStatus runtime coercion'ını
                        # bilmez (arg-type). ARCH-005 partial-update kontratı.
                        SeferUpdate(durum=normalized_status),  # type: ignore[call-arg, arg-type]
                        user_id=user_id,
                    )
                    if success:
                        success_count += 1
                    else:
                        failed.append(
                            {"id": sid, "reason": "Bulunamadı veya güncellenemedi"}
                        )
                except Exception as e:
                    logger.error(f"Bulk status update error for sid {sid}: {e}")
                    failed.append({"id": sid, "reason": str(e)})

            if success_count > 0:
                await uow.commit()
                await self._refresh_stats(uow)

        return {
            "success_count": success_count,
            "failed_count": len(failed),
            "failed": failed,
        }

    async def bulk_cancel(
        self,
        sefer_ids: List[int],
        iptal_nedeni: str,
        user_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Birden fazla seferi toplu iptal et.
        N+1 Transaction sorunu giderildi.
        """
        success_count = 0
        failed = []

        async with UnitOfWork() as uow:
            for sid in sefer_ids:
                try:
                    success = await self._update_sefer_uow(
                        uow,
                        sid,
                        # Bkz. bulk_update_status: pydantic.mypy plugin yok (ARCH-005).
                        SeferUpdate(  # type: ignore[call-arg]
                            durum=cast("Any", SEFER_STATUS_IPTAL),
                            iptal_nedeni=iptal_nedeni,
                        ),
                        user_id=user_id,
                    )
                    if success:
                        success_count += 1
                    else:
                        failed.append(
                            {"id": sid, "reason": "Bulunamadı veya iptal edilemedi"}
                        )
                except Exception as e:
                    logger.error(f"Bulk cancel error for sid {sid}: {e}")
                    failed.append({"id": sid, "reason": str(e)})

            if success_count > 0:
                await uow.commit()
                await self._refresh_stats(uow)

        return {
            "success_count": success_count,
            "failed_count": len(failed),
            "failed": failed,
        }

    async def bulk_delete(self, sefer_ids: List[int]) -> Dict[str, Any]:
        """
        Birden fazla seferi toplu sil.
        N+1 Transaction sorunu giderildi (Tek UoW).
        """
        success_count = 0
        failed = []

        async with UnitOfWork() as uow:
            for sid in sefer_ids:
                try:
                    success = await self._delete_sefer_uow(uow, sid)
                    if success:
                        success_count += 1
                    else:
                        failed.append(
                            {"id": sid, "reason": "Bulunamadı veya silinemedi"}
                        )
                except Exception as e:
                    logger.error(f"Bulk delete error for sid {sid}: {e}")
                    failed.append({"id": sid, "reason": str(e)})

            if success_count > 0:
                await uow.commit()
                await self._refresh_stats(uow)

        return {
            "success_count": success_count,
            "failed_count": len(failed),
            "failed": failed,
        }

    @monitor_errors(category="sefer_write", severity="error")
    @audit_log("BULK_CREATE", "sefer", log_params=True)
    async def bulk_add_sefer(self, sefer_list: List[SeferCreate]) -> int:
        """Toplu sefer ekle (Batch Insert & Smart Enrichment)"""
        if not sefer_list:
            return 0

        count = 0
        from app.services.prediction_service import get_prediction_service

        pred_service = get_prediction_service()

        async with UnitOfWork() as uow:
            try:
                # 1. Pre-fetch Logic
                sorted_list = sorted(sefer_list, key=lambda x: (x.tarih, x.saat or ""))
                all_loc_names = await uow.lokasyon_repo.get_benzersiz_lokasyonlar()

                # Araç boş ağırlığı pre-fetch — check constraint
                # ``net_kg = dolu_agirlik_kg - bos_agirlik_kg`` zorunluluğunda
                # tek SeferCreate'in tek tek arac master sorgusu yerine batch.
                arac_ids = {s.arac_id for s in sorted_list if s.arac_id}
                arac_bos_map: Dict[int, float] = {}
                active_arac_ids: set[int] = set()
                if arac_ids:
                    araclar = await uow.arac_repo.get_all(sadece_aktif=False)
                    for a in araclar:
                        if a["id"] in arac_ids:
                            arac_bos_map[a["id"]] = float(a.get("bos_agirlik_kg") or 0)
                            if a.get("aktif"):
                                active_arac_ids.add(a["id"])

                # N+1 optimization: pre-fetch all arac/sofor objects before prediction loop
                # predict_consumption opens new UoW for each call; batch loading here reduces queries
                arac_objs = await uow.arac_repo.get_by_ids(list(arac_ids))
                sofor_ids = {s.sofor_id for s in sorted_list if s.sofor_id}
                sofor_objs = await uow.sofor_repo.get_by_ids(list(sofor_ids))

                # Active sofor set for validation
                active_sofor_ids: set[int] = set()
                if sofor_ids:
                    soforler = await uow.sofor_repo.get_all(sadece_aktif=False)
                    for sf in soforler:
                        if sf["id"] in sofor_ids and sf.get("aktif"):
                            active_sofor_ids.add(sf["id"])

                # sefer_no uniqueness: within-batch dedup + existing DB check
                batch_sefer_nos = {s.sefer_no for s in sorted_list if s.sefer_no}
                existing_sefer_nos: set[
                    str
                ] = await uow.sefer_repo.get_existing_sefer_nos(list(batch_sefer_nos))
                seen_sefer_nos: set[str] = set()  # within-batch dedup

                all_routes = await uow.lokasyon_repo.get_all(limit=1000)
                route_map = {
                    (
                        r["cikis_yeri"].upper().strip(),
                        r["varis_yeri"].upper().strip(),
                    ): r
                    for r in all_routes
                }

                items_to_add: List[Dict[str, Any]] = []

                for data in sorted_list:
                    if data.mesafe_km <= 0:
                        continue

                    # Arac aktif kontrolü
                    if data.arac_id and data.arac_id not in active_arac_ids:
                        logger.warning(
                            "bulk_add_sefer: arac_id=%s aktif değil, satır atlandı",
                            data.arac_id,
                        )
                        continue

                    # Sofor aktif kontrolü (sofor_id opsiyonel)
                    if data.sofor_id and data.sofor_id not in active_sofor_ids:
                        logger.warning(
                            "bulk_add_sefer: sofor_id=%s aktif değil, satır atlandı",
                            data.sofor_id,
                        )
                        continue

                    # sefer_no tekrar kontrolü
                    if data.sefer_no:
                        if data.sefer_no in existing_sefer_nos:
                            logger.warning(
                                "bulk_add_sefer: sefer_no=%s zaten DB'de var, atlandı",
                                data.sefer_no,
                            )
                            continue
                        if data.sefer_no in seen_sefer_nos:
                            logger.warning(
                                "bulk_add_sefer: sefer_no=%s batch içinde tekrar, atlandı",
                                data.sefer_no,
                            )
                            continue
                        seen_sefer_nos.add(data.sefer_no)

                    matched_cikis = await uow.lokasyon_repo.find_closest_match(
                        data.cikis_yeri, pre_fetched_names=all_loc_names
                    )
                    if matched_cikis:
                        data.cikis_yeri = matched_cikis

                    matched_varis = await uow.lokasyon_repo.find_closest_match(
                        data.varis_yeri, pre_fetched_names=all_loc_names
                    )
                    if matched_varis:
                        data.varis_yeri = matched_varis

                    if data.cikis_yeri.lower() == data.varis_yeri.lower():
                        continue

                    route_key = (
                        data.cikis_yeri.upper().strip(),
                        data.varis_yeri.upper().strip(),
                    )
                    route_metadata = route_map.get(route_key)

                    if route_metadata:
                        if not data.ascent_m:
                            data.ascent_m = route_metadata.get("ascent_m", 0.0)
                        if not data.descent_m:
                            data.descent_m = route_metadata.get("descent_m", 0.0)
                        if not data.flat_distance_km:
                            data.flat_distance_km = route_metadata.get(
                                "flat_distance_km", 0.0
                            )
                        if not data.guzergah_id:
                            data.guzergah_id = route_metadata.get("id")

                    # Bulk ML prediction: her sefer için predict_consumption
                    # 5 fresh DB fetch yapıyor (araclar, soforler,
                    # arac_bakimlari, sofor stat, AVG tuketim) → N+1 pattern.
                    # 20+ sefer'lik batch'te DB sorgu sayısı 5N'e çıkıyor.
                    # Geçmiş veri import'unda gerçek tüketim zaten kayıtlı,
                    # prediction değer katmaz; tek tek sefer create
                    # (POST /trips/) yolunda ise predict_consumption hala
                    # çalışır. Threshold 20: detector eşiğinden hemen önce.
                    tahmini_tuk = None
                    tahmin_meta = None
                    skip_prediction = len(sefer_list) > 20
                    if skip_prediction:
                        logger.info(
                            "bulk_add_sefer: batch size %d > 20, ML prediction skipped for all rows",
                            len(sefer_list),
                        )
                    if not skip_prediction:
                        import asyncio as _asyncio

                        try:
                            tonaj = data.ton or (
                                data.net_kg / 1000.0 if data.net_kg else 0.0
                            )
                            prediction = await _asyncio.wait_for(
                                pred_service.predict_consumption(
                                    arac_id=data.arac_id,
                                    mesafe_km=data.mesafe_km,
                                    ton=tonaj,
                                    ascent_m=data.ascent_m or 0.0,
                                    descent_m=data.descent_m or 0.0,
                                    flat_distance_km=data.flat_distance_km or 0.0,
                                    sofor_id=data.sofor_id,
                                    dorse_id=data.dorse_id,
                                    target_date=data.tarih
                                    if isinstance(data.tarih, date)
                                    else date.fromisoformat(data.tarih),
                                    route_analysis=self._build_prediction_route_analysis(
                                        route_details=route_metadata
                                    ),
                                    _arac_obj=arac_objs.get(data.arac_id),
                                    _sofor_obj=sofor_objs.get(data.sofor_id)
                                    if data.sofor_id
                                    else None,
                                ),
                                timeout=_PREDICTION_TIMEOUT_SECONDS,
                            )
                            tahmini_tuk, tahmin_meta = self._extract_prediction_values(
                                prediction,
                                quality_flags=self._build_prediction_quality_flags(
                                    route_details=route_metadata
                                ),
                            )
                        except _asyncio.TimeoutError:
                            logger.debug(
                                "Bulk prediction timeout (arac=%s) skipped",
                                data.arac_id,
                            )
                        except Exception as pe:
                            logger.error(f"Bulk Prediction Error: {pe}")

                    # Ağırlık enrichment — DB check constraint:
                    # ``net_kg = dolu_agirlik_kg - bos_agirlik_kg``. Excel'den
                    # gelen SeferCreate sadece ``net_kg`` taşıyor; bos/dolu
                    # boş kalırsa constraint patlar. Arac master'dan bos al,
                    # dolu = bos + net.
                    bos_kg = float(
                        data.bos_agirlik_kg or arac_bos_map.get(data.arac_id, 0) or 0
                    )
                    net_kg = float(data.net_kg or 0)
                    dolu_kg = float(data.dolu_agirlik_kg or (bos_kg + net_kg))
                    # CHECK: net_kg = dolu_agirlik_kg - bos_agirlik_kg.
                    # Clamp dolu first so dolu >= bos, then derive net exactly.
                    dolu_kg = max(dolu_kg, bos_kg)
                    net_kg = dolu_kg - bos_kg

                    items_to_add.append(
                        {
                            "tarih": data.tarih,
                            "saat": data.saat or "",
                            "arac_id": data.arac_id,
                            "dorse_id": data.dorse_id,
                            "sofor_id": data.sofor_id,
                            "guzergah_id": data.guzergah_id,
                            "net_kg": net_kg,
                            "ton": data.ton or round(net_kg / 1000, 2),
                            "bos_agirlik_kg": bos_kg,
                            "dolu_agirlik_kg": dolu_kg,
                            "cikis_yeri": data.cikis_yeri,
                            "varis_yeri": data.varis_yeri,
                            "mesafe_km": data.mesafe_km,
                            "bos_sefer": data.bos_sefer,
                            "ascent_m": data.ascent_m or 0.0,
                            "descent_m": data.descent_m or 0.0,
                            "flat_distance_km": data.flat_distance_km or 0.0,
                            "tahmini_tuketim": tahmini_tuk,
                            "tahmin_meta": tahmin_meta,
                            "durum": _safe_durum(data.durum),
                            "notlar": data.notlar,
                            "sefer_no": data.sefer_no,
                        }
                    )

                if items_to_add:
                    await uow.sefer_repo.bulk_create(items_to_add)
                    count = len(items_to_add)
                    await uow.commit()
                    await self._refresh_stats(uow)

            except Exception as e:
                logger.error(f"Bulk insert hatası (Sefer): {e}")
                await uow.rollback()
                raise e

        return count

    @monitor_errors(category="sefer_write", severity="error")
    @audit_log("CREATE_RETURN", "sefer")
    async def create_return_trip(
        self, sefer_id: int, user_id: Optional[int] = None
    ) -> int:
        """
        Mevcut seferden otomatik dönüş seferi oluşturur.
        Yerleri ve tırmanış/iniş değerlerini ters çevirerek boş sefer oluşturur.
        """
        try:
            async with get_uow() as uow:
                ref_sefer = await uow.sefer_repo.get_by_id(sefer_id)
                if not ref_sefer:
                    raise ValueError("Referans sefer bulunamadı")

                # Prevent '-D-D' double-suffix
                base_sefer_no = ref_sefer.get("sefer_no")
                if base_sefer_no:
                    if base_sefer_no.endswith("-D"):
                        base_sefer_no = base_sefer_no[:-2]
                    return_sefer_no = f"{base_sefer_no}-D"
                else:
                    return_sefer_no = None

                # Build reversed trip dict (locations and elevation swapped)
                trip_dict = {
                    "tarih": date.today(),
                    "arac_id": ref_sefer.get("arac_id"),
                    "sofor_id": ref_sefer.get("sofor_id"),
                    "dorse_id": ref_sefer.get("dorse_id"),
                    "guzergah_id": ref_sefer.get("guzergah_id"),
                    "cikis_yeri": ref_sefer.get("varis_yeri"),  # reversed
                    "varis_yeri": ref_sefer.get("cikis_yeri"),  # reversed
                    "mesafe_km": ref_sefer.get("mesafe_km", 1.0),
                    "sefer_no": return_sefer_no,
                    "bos_agirlik_kg": ref_sefer.get("bos_agirlik_kg", 0),
                    "dolu_agirlik_kg": ref_sefer.get("bos_agirlik_kg", 0),
                    "net_kg": 0,
                    "ton": 0.0,
                    "bos_sefer": True,
                    "durum": SEFER_STATUS_PLANLANDI,
                    "ascent_m": ref_sefer.get("descent_m", 0.0),  # reversed
                    "descent_m": ref_sefer.get("ascent_m", 0.0),  # reversed
                    "flat_distance_km": ref_sefer.get("flat_distance_km", 0.0),
                    "notlar": f"Dönüş seferi (Ref: #{sefer_id})",
                    "is_real": ref_sefer.get("is_real", False),
                    "created_by_id": user_id or None,
                }

                # Validate and correct elevation anomalies
                corrected = RouteValidator.validate_and_correct(trip_dict)
                trip_dict.update(corrected)

                # Direct insert — bypass add_sefer to avoid sefer_no duplicate check
                new_id = await uow.sefer_repo.add(**trip_dict)
                await uow.commit()
                logger.info(f"Dönüş seferi oluşturuldu: ID {new_id}, Ref #{sefer_id}")
                return int(new_id)

        except Exception as e:
            logger.error(f"Dönüş seferi oluşturma hatası: {e}")
            raise
