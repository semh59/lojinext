"""Dönüş seferi (round-trip) oluşturma akışı.

NOT: task dosyası (``TASKS/modules/trip.md`` madde 5) bu kümeyi
``domain/return_trip.py`` olarak planlamıştı; gerçek kod DB I/O
(``uow.sefer_repo``/``uow.lokasyon_repo``) ve cross-module çağrı
(``v2.modules.prediction_ml.public.get_prediction_service``) yapıyor —
domain saflığı kuralını ihlal ederdi. ``application/``'a taşındı (aynı
sapma prediction_ml dalgasında da yaşandı).
"""

from datetime import date
from typing import Any, Dict, Optional

from pydantic import ValidationError

from v2.modules.platform_infra.public import get_logger
from v2.modules.shared_kernel.infrastructure.unit_of_work import UnitOfWork
from v2.modules.trip.application.trip_prediction_enrichment import (
    build_prediction_quality_flags,
    build_prediction_route_analysis,
    extract_prediction_values,
)
from v2.modules.trip.domain.trip_validation import safe_durum
from v2.modules.trip.schemas import SeferCreate
from v2.modules.trip.sefer_status import SEFER_STATUS_PLANLANDI

logger = get_logger(__name__)


def get_uow() -> UnitOfWork:
    """Module-level UnitOfWork factory — patchable in unit tests."""
    return UnitOfWork()


async def build_return_trip(
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
            from v2.modules.prediction_ml.public import get_prediction_service

            pred_service = get_prediction_service()
            prediction_quality = build_prediction_quality_flags(
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
                route_analysis=build_prediction_route_analysis(
                    route_details=route_details,
                    weather_factor=weather_factor,
                ),
            )
            return_tahmini, return_tahmin_meta = extract_prediction_values(
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
        durum=safe_durum(data.durum),
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


async def handle_round_trip_on_update(
    uow: UnitOfWork,
    sefer_id: int,
    update_data: Dict[str, Any],
) -> None:
    """Update sırasında is_round_trip=True ise dönüş seferini oluşturur.

    Dönüş seferi oluşturma başarısız olursa exception'ı YUTMAZ — çağıranın
    kendi except/raise zincirine (bkz. update_trip.py) yeniden fırlatılır,
    böylece ana update işlemiyle atomik kalır. Önceki davranış (bare
    `except Exception: logger.error(...)`) hatayı sessizce yutuyordu; sonuç
    olarak `update_sefer` True dönüyor ve kullanıcı dönüş seferinin
    oluştuğunu sanıyordu, oysa hiç oluşmamış olabiliyordu (2026-07-01
    prod-grade denetimi P0 bulgusu).

    İstisna: mevcut sefer kaydının (current_full) kendisi yapısal olarak
    round-trip mirror'ı için geçersizse (ör. mesafe_km=0, tek karakterlik
    cikis_yeri — SeferCreate validasyonunu geçemeyen ESKİ/edge-case veri),
    bu durum "build_return_trip başarısız oldu" ile aynı kategori değildir —
    kaynak verinin kalitesi, kullanıcının şu anki işlemiyle ilgisizdir. Bu
    durumda dönüş seferi sessizce atlanır (ana update etkilenmez); yalnızca
    gerçek oluşturma hataları (build_return_trip içindeki) propagate edilir.
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
        await build_return_trip(uow, full_sefer_obj, full_sefer_obj.tarih, sefer_id)


async def create_return_trip(sefer_id: int, user_id: Optional[int] = None) -> int:
    """
    Mevcut seferden otomatik dönüş seferi oluşturur.
    Yerleri ve tırmanış/iniş değerlerini ters çevirerek boş sefer oluşturur.
    """
    from v2.modules.route_simulation.public import RouteValidator

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
