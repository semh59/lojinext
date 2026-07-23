"""Yakıt fişleri Excel import + otomatik periyot hesabı.

Pipeline:
  1. Excel parse (tarih, plaka, litre, fiyat, km_sayac)
  2. Plaka → arac_id; bulunamayanlar errors[] satırına düşer
  3. bulk_add_yakit (Pydantic YakitCreate listesi)
  4. Etkilenen her arac için recalculate_vehicle_periods çağrılır
     (km aralıklarına göre tüketim periyotları hesaplanır)
"""

from decimal import Decimal
from typing import TYPE_CHECKING, Any, List, Tuple, cast

from v2.modules.import_excel.domain.entity_resolvers import resolve_arac_id
from v2.modules.import_excel.domain.field_validators import validate_numeric
from v2.modules.import_excel.infrastructure.monitoring_bridge import (
    report_infra_failure,
)
from v2.modules.import_excel.infrastructure.parsers import parse_yakit_excel
from v2.modules.platform_infra.public import get_logger
from v2.modules.shared_kernel.infrastructure.unit_of_work import UnitOfWork

if TYPE_CHECKING:
    from v2.modules.fuel.public import YakitAlimiCreate

logger = get_logger(__name__)


async def process_yakit_import(content: bytes) -> Tuple[int, list]:
    from v2.modules.fuel.public import YakitCreate

    try:
        items = await parse_yakit_excel(content)
        if not items:
            return 0, ["Excel dosyasında veri bulunamadı."]

        errors: List[str] = []
        yakit_list: List[YakitCreate] = []
        affected_arac_ids: set[int] = set()
        async with UnitOfWork() as uow_ref:
            vehicles = await uow_ref.arac_repo.get_all(sadece_aktif=False)

        for idx, item in enumerate(items, 1):
            try:
                # Plaka normalize: boşluk + büyük harf. Strict regex
                # araç ekleme'de yapılır; yakıt fişinde araç zaten
                # kayıtlı, sade normalize yeterli.
                plaka_raw = item.get("plaka") or ""
                plaka = str(plaka_raw).replace(" ", "").upper().strip()
                if not plaka:
                    raise ValueError("Plaka boş.")

                arac_id = resolve_arac_id(plaka, vehicles)
                if not arac_id:
                    raise ValueError(
                        f"Araç bulunamadı: '{plaka}'. Önce araç kaydı gerekli."
                    )

                tarih = item.get("tarih")
                if tarih is None:
                    raise ValueError("Tarih boş — fişler için tarih sütunu zorunlu.")

                # depo_durumu None ise Pydantic Literal reddediyor —
                # explicit default "Bilinmiyor".
                depo_durumu = item.get("depo_durumu") or "Bilinmiyor"

                yakit = YakitCreate(
                    arac_id=arac_id,
                    tarih=tarih,
                    istasyon=item.get("istasyon") or "Bilinmiyor",
                    litre=Decimal(str(validate_numeric(item.get("litre", 0), "Litre"))),
                    fiyat_tl=Decimal(
                        str(validate_numeric(item.get("fiyat_tl", 0), "Fiyat"))
                    ),
                    toplam_tutar=None,  # backend hesaplar (YakitCreate'de Optional)
                    km_sayac=int(
                        validate_numeric(item.get("km_sayac", 0), "Kilometre")
                    ),
                    fis_no=(str(item.get("fis_no")) if item.get("fis_no") else None),
                    depo_durumu=cast("Any", depo_durumu),
                    durum="Bekliyor",
                )
                yakit_list.append(yakit)
                affected_arac_ids.add(arac_id)
            except ValueError as ve:
                errors.append(f"Satır {idx}: {str(ve)}")
            except Exception as ex:  # Pydantic validation vs.
                errors.append(f"Satır {idx}: {str(ex)}")

        count = 0
        if yakit_list:
            from v2.modules.fuel.public import bulk_add_yakit

            # bulk_add_yakit's signature types its param as YakitAlimiCreate
            # (core/entities/models.py) — this pre-existing latent mismatch
            # (YakitCreate is structurally identical for every attribute
            # bulk_add_yakit reads: arac_id/tarih/istasyon/litre/fiyat_tl/
            # km_sayac/fis_no/depo_durumu) was invisible to mypy before this
            # migration because the old call site (self.yakit_service, an
            # untyped constructor param) had no static type. Now that the
            # call is a properly-typed free function, mypy correctly flags
            # the nominal type difference — cast() documents it's safe
            # rather than silently widening bulk_add_yakit's signature.
            count = await bulk_add_yakit(cast("List[YakitAlimiCreate]", yakit_list))

            # Periyot recalc — yakıt fişi km aralıklarından tüketim türetir.
            # YAKIT_ADDED event burada subscribe edilmiyor; bulk import'tan
            # sonra manuel çağrı tek seferde tetikleyici.
            try:
                from v2.modules.fuel.public import recalculate_vehicle_periods

                for arac_id in affected_arac_ids:
                    try:
                        await recalculate_vehicle_periods(arac_id)
                    except Exception as pe:
                        logger.warning(
                            "Period recalc failed for arac %s: %s",
                            arac_id,
                            pe,
                        )
            except Exception as exc:
                logger.warning("Period recalc skipped: %s", exc)

        return count, errors
    except Exception as e:
        await report_infra_failure("process_yakit_import", e)
        return 0, [f"Sistem hatası: {str(e)}"]
