"""Yeni sefer oluşturma use-case'i."""

from datetime import date
from typing import Any, Optional, cast

from v2.modules.platform_infra.public import (
    EventType,
    audit_log,
    get_logger,
    monitor_errors,
    publishes,
)
from v2.modules.route_simulation.public import RouteValidator
from v2.modules.shared_kernel.exceptions import RouteProcessingError
from v2.modules.shared_kernel.infrastructure.outbox import get_outbox_service
from v2.modules.shared_kernel.infrastructure.unit_of_work import UnitOfWork
from v2.modules.trip.application.return_trip import build_return_trip
from v2.modules.trip.application.stats_refresh import refresh_stats
from v2.modules.trip.application.trip_prediction_enrichment import (
    predict_outbound,
    resolve_route,
)
from v2.modules.trip.domain.trip_validation import (
    safe_durum,
    sync_weight_fields,
    validate_sefer_create,
)
from v2.modules.trip.schemas import SeferCreate, TripStatus

logger = get_logger(__name__)


@monitor_errors(category="sefer_write", severity="error")
@audit_log("CREATE", "sefer")
@publishes(EventType.SEFER_ADDED)
async def add_sefer(data: SeferCreate, user_id: Optional[int] = None) -> int:
    """Yeni bir sefer olusturur."""
    async with UnitOfWork() as uow:
        # State Machine: Initial Status
        if not data.durum:
            # SeferDurum (str Literal) alanına TripStatus str-enum atanıyor;
            # runtime'da eşdeğer ("Planned"), mypy Literal!=enum diyor.
            data.durum = cast(Any, TripStatus.PLANNED)

        # 1. Validation Logic
        # Parse date first (needed by validate_sefer_create)
        trip_date = (
            data.tarih
            if isinstance(data.tarih, date)
            else date.fromisoformat(str(data.tarih))
        )

        validate_sefer_create(data, trip_date)

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
        route_dict = await resolve_route(uow, data)

        # Validate and correct route data (Elevation anomalies check)
        temp_dict = data.model_dump()
        corrected = RouteValidator.validate_and_correct(temp_dict)
        if corrected.get("is_corrected"):
            data.ascent_m = corrected["ascent_m"]
            data.descent_m = corrected["descent_m"]
            logger.info(f"API Add: Corrected anomalous elevation to {data.ascent_m}m")

        # Ağırlık senkronizasyonu — tahmin ÖNCE yapılmalı: ton=0 tahmini önlemek
        # için bos/dolu/net/ton tutarlılığı prediction input'undan önce çözülmeli.
        sync_weight_fields(data, arac)

        # 3. YAKIT TAHMİNİ (Gidiş Leg)
        tahmini_tuk, tahmin_meta, route_sim_id = None, None, None
        if data.arac_id and data.mesafe_km:
            tahmini_tuk, tahmin_meta, route_sim_id = await predict_outbound(
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
            durum=safe_durum(data.durum),
            ascent_m=data.ascent_m or 0.0,
            descent_m=data.descent_m or 0.0,
            flat_distance_km=data.flat_distance_km or 0.0,
            tahmini_tuketim=tahmini_tuk,
            tahmin_meta=tahmin_meta,
            route_simulation_id=route_sim_id,
            rota_detay=route_dict.get("route_analysis") if route_dict else None,
            otoban_mesafe_km=route_dict.get("otoban_mesafe_km") if route_dict else None,
            sehir_ici_mesafe_km=route_dict.get("sehir_ici_mesafe_km")
            if route_dict
            else None,
            notlar=data.notlar,
            created_by_id=user_id or None,
        )

        # 5. ROUND-TRIP (Dönüş Seferi)
        if data.is_round_trip:
            await build_return_trip(
                uow,
                data,
                trip_date,
                sefer_id,
                route_details=route_dict,
                user_id=user_id,
            )

        # Phase 7: Atomic Outbox Persistence
        outbox = get_outbox_service()
        await outbox.save_event(
            event_type=EventType.SEFER_ADDED,
            payload={"sefer_id": int(sefer_id), "sefer_no": data.sefer_no},
            uow=uow,
        )

        # 6. Atomic Commit
        await uow.commit()
        # 7. Refresh Stats (Post-commit)
        await refresh_stats(uow)
        logger.info(f"Sefer(ler) başarıyla kaydedildi. ID: {sefer_id}")
        return int(sefer_id)
