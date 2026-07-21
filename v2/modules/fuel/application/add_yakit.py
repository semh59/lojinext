"""Use-case: add a new fuel transaction (duplicate/odometer/rolling-outlier checks)."""

from datetime import date
from typing import Any

from app.database.unit_of_work import UnitOfWork
from app.infrastructure.events.event_bus import (
    Event,
    EventType,
    get_event_bus,
    publishes,
)
from app.infrastructure.events.outbox_service import save_outbox_event
from app.infrastructure.logging.logger import get_logger
from app.infrastructure.monitoring.service_probe import monitor_errors
from v2.modules.fuel.domain.entities import YakitAlimiCreate

logger = get_logger(__name__)


async def _check_rolling_outlier(
    arac_id: int, current_litre: float, current_km: int
) -> bool:
    """
    Rolling Outlier Check for Partial Fills (Last 5 Records).
    Examines the average of the last 5 entries instead of single records.
    """
    try:
        async with UnitOfWork() as uow:
            last_5 = await uow.yakit_repo.get_last_n_by_arac(arac_id, n=5)

        if not last_5:
            return False

        litres = [current_litre] + [float(r["litre"]) for r in last_5]
        kms = [current_km] + [int(r["km_sayac"]) for r in last_5]

        total_dist = max(kms) - min(kms)
        if len(kms) < 2 or total_dist <= 0:
            return False

        # Rolling Window Logic: the fuel of the earliest record is excluded
        # as it belongs to the period before that odometer reading.
        valid_fuel = sum(litres) - float(last_5[-1]["litre"])

        if valid_fuel <= 0:
            return False

        rolling_avg = (valid_fuel / total_dist) * 100

        # Smart Thresholds: 18-55 range is considered normal for Heavy Duty Trucks.
        if rolling_avg < 18 or rolling_avg > 55:
            logger.warning(
                f"Rolling Anomaly ({len(kms)} fills): Vehicle {arac_id}, {rolling_avg:.1f} L/100km (Dist: {total_dist})"  # noqa: E501
            )

            get_event_bus().publish(
                Event(
                    type=EventType.ANOMALY_DETECTED,
                    data={
                        "arac_id": arac_id,
                        "tip": "rolling_consumption",
                        "deger": rolling_avg,
                        "window_size": len(kms),
                        "total_dist": total_dist,
                    },
                )
            )
            return True

    except Exception as e:
        logger.error(f"Rolling outlier check error: {e}")

    return False


@monitor_errors(category="yakit_write", severity="error")
@publishes(EventType.YAKIT_ADDED)
async def add_yakit(data: YakitAlimiCreate) -> int:
    """Adds a new fuel transaction."""
    try:
        async with UnitOfWork() as uow:
            arac = await uow.arac_repo.get_by_id(data.arac_id)
            if not arac or not arac.get("aktif"):
                raise ValueError("Cannot enter fuel for a passive or invalid vehicle.")

            if data.litre <= 0:
                raise ValueError("Litres must be greater than zero")

            if data.fiyat_tl <= 0:
                raise ValueError("Price must be greater than zero")

            entry_date = (
                data.tarih
                if isinstance(data.tarih, date)
                else date.fromisoformat(data.tarih)
            )
            if entry_date > date.today():
                raise ValueError("İleri tarihli yakıt girişine izin verilmez")

            is_duplicate = await uow.yakit_repo.check_duplicate(
                data.arac_id, entry_date, float(data.litre)
            )
            if is_duplicate:
                logger.warning(
                    f"Duplicate fuel entry blocked: Vehicle {data.arac_id}, Date {entry_date}, Litre {data.litre}"
                )
                raise ValueError("This fuel record already exists (Duplicate Entry).")

            last_km = await uow.yakit_repo.get_son_km(data.arac_id)
            if last_km and data.km_sayac < last_km:
                raise ValueError(
                    f"KM Sayacı düşemez! (Son: {last_km}, Girilen: {data.km_sayac})"
                )

            if last_km:
                await _check_rolling_outlier(
                    data.arac_id, float(data.litre), data.km_sayac
                )

            yakit_id = await uow.yakit_repo.add(
                tarih=entry_date,
                arac_id=data.arac_id,
                istasyon=data.istasyon,
                fiyat=float(data.fiyat_tl),
                litre=float(data.litre),
                km_sayac=data.km_sayac,
                fis_no=data.fis_no,
                # "Unknown" (İngilizce) DepoDurumu Literal'inde YOK — kanonik
                # değer "Bilinmiyor" (bkz. v2/modules/fuel/schemas.py); yanlış
                # literal sync_create_fuel_periods'un "dolu"/"full" substring
                # eşleşmesini sessizce atlıyordu (2026-07-16 dedektif
                # denetimi bulgusu).
                depo_durumu=data.depo_durumu or "Bilinmiyor",
                # Verilmezse None geç; repo toplam'ı Decimal'de hesaplar.
                toplam_tutar=getattr(data, "toplam_tutar", None),
            )

            await save_outbox_event(
                uow.session,
                EventType.YAKIT_ADDED,
                {"result": int(yakit_id), "arac_id": data.arac_id},
            )
            await uow.commit()
            logger.info(f"Fuel entry added: ID {yakit_id}, Vehicle {data.arac_id}")
            return int(yakit_id)

    except Exception as e:
        logger.error(f"Fuel addition error: {e}", exc_info=True)
        raise


async def add_yakit_alimi(**kwargs: Any) -> int:
    """Alias for add_yakit (backward compatibility)."""
    if kwargs:
        try:
            data = YakitAlimiCreate(**kwargs)
            return await add_yakit(data)
        except Exception as e:
            logger.error(f"Fuel addition error (alias): {e}")
            raise
    raise ValueError("No data provided")
