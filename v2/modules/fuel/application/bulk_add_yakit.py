"""Use-case: bulk-create fuel entries (pre-fetch + batch insert)."""

from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from typing import List

from app.infrastructure.events.event_bus import EventType
from app.infrastructure.logging.logger import get_logger
from v2.modules.fuel.domain.entities import YakitAlimiCreate
from v2.modules.shared_kernel.infrastructure.outbox import save_outbox_event
from v2.modules.shared_kernel.infrastructure.unit_of_work import UnitOfWork

logger = get_logger(__name__)


async def bulk_add_yakit(yakit_list: List[YakitAlimiCreate]) -> int:
    """Bulk creates fuel entries (Pre-fetch & Batch Insert)."""
    if not yakit_list:
        return 0
    count = 0
    async with UnitOfWork() as uow:
        try:
            # Son KM'leri tek sorguda topla (araç başına get_son_km = N+1'di).
            # Kaydı olmayan araçlar sözlükte yok → aşağıda .get(id, 0) okunur.
            active_araclar = await uow.arac_repo.get_all(sadece_aktif=True)
            active_arac_ids = {a["id"] for a in active_araclar}
            last_km_cache = await uow.yakit_repo.get_son_km_bulk(list(active_arac_ids))

            today = date.today()
            sorted_list = sorted(yakit_list, key=lambda x: x.tarih)
            items_to_add = []
            for data in sorted_list:
                if data.arac_id not in active_arac_ids:
                    logger.warning(
                        f"Bulk skip: Vehicle {data.arac_id} is inactive or unknown"
                    )
                    continue
                if data.litre <= 0:
                    continue
                if data.fiyat_tl <= 0:
                    logger.warning(f"Bulk skip: Vehicle {data.arac_id} price <= 0")
                    continue
                entry_date = (
                    data.tarih
                    if isinstance(data.tarih, date)
                    else date.fromisoformat(str(data.tarih))
                )
                if entry_date > today:
                    logger.warning(
                        f"Bulk skip: Vehicle {data.arac_id} future date {entry_date}"
                    )
                    continue
                current_last_km = last_km_cache.get(data.arac_id, 0)
                if data.km_sayac < current_last_km:
                    logger.warning(
                        f"Odometer error (Skipped): Vehicle {data.arac_id}, Last {current_last_km}, Entered {data.km_sayac}"  # noqa: E501
                    )
                    continue

                fiyat_tl = float(data.fiyat_tl)
                litre = float(data.litre)
                items_to_add.append(
                    {
                        "tarih": data.tarih,
                        "arac_id": data.arac_id,
                        "istasyon": data.istasyon,
                        "fiyat_tl": fiyat_tl,
                        "litre": litre,
                        # Para çarpımı Decimal'de (float çarpımı cent hatası verir).
                        "toplam_tutar": (
                            Decimal(str(litre)) * Decimal(str(fiyat_tl))
                        ).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP),
                        "km_sayac": data.km_sayac,
                        "fis_no": data.fis_no,
                        # add_yakit.py'nin tekil yoluyla tutarlı fallback
                        # (2026-07-16 dedektif denetimi bulgusu).
                        "depo_durumu": data.depo_durumu or "Bilinmiyor",
                    }
                )
                last_km_cache[data.arac_id] = data.km_sayac

            if items_to_add:
                new_ids = await uow.yakit_repo.bulk_create(items_to_add)
                # add_yakit.py'nin tekil yolu her eklemede YAKIT_ADDED outbox
                # event'i yazıyor (arac_id ile — model_training_handler'ın
                # araç-başına ML-retrain sayacı buna bağlı); bulk yol bunu
                # hiç yapmıyordu — Excel'den toplu eklenen yakıt kayıtları
                # retrain sayacına hiç düşmüyordu (2026-07-16 dedektif
                # denetimi bulgusu). `bulk_create` id'leri `items_to_add`
                # sırasıyla aynı sırada döner.
                for yakit_id, item in zip(new_ids, items_to_add):
                    await save_outbox_event(
                        uow.session,
                        EventType.YAKIT_ADDED,
                        {"result": int(yakit_id), "arac_id": item["arac_id"]},
                    )
                await uow.commit()
                count = len(items_to_add)

        except Exception as e:
            logger.error(f"Bulk insert error: {e}")
            raise e

    if count > 0:
        logger.info(f"Bulk insert: {count} fuel transactions added")
    return count
