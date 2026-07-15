"""Sefer (trip) Excel import — domain endpoint'inin ``bulk_add_sefer`` yolu.

NOT (ARCH-002 — import_service.py'den taşındı, gerekçe korunuyor): prod'da
çağrılmıyor (test-covered legacy yol); canlı sefer importu
``application/sefer_upload_importer.py`` (trip'in ``upload_sefer_excel``
route'u) üzerinden yapılır. İkisi de durum için canonical
``SEFER_STATUS_PLANLANDI`` sabitini kullanır (drift = BUG-002).
"""

from typing import List, Tuple

from app.core.exceptions import ImportValidationError
from app.core.utils.sefer_status import SEFER_STATUS_PLANLANDI
from app.database.unit_of_work import UnitOfWork
from app.infrastructure.logging.logger import get_logger
from v2.modules.import_excel.domain.entity_resolvers import (
    resolve_arac_id,
    resolve_dorse_id,
    resolve_route_id,
    resolve_sofor_id,
)
from v2.modules.import_excel.domain.field_validators import (
    validate_name,
    validate_numeric,
    validate_plaka,
)
from v2.modules.import_excel.infrastructure.monitoring_bridge import (
    report_infra_failure,
)
from v2.modules.import_excel.infrastructure.parsers import parse_sefer_excel

logger = get_logger(__name__)


async def process_sefer_import(content: bytes) -> Tuple[int, list]:
    """Processes Excel import for trips (Seferler)."""
    try:
        items = await parse_sefer_excel(content)
        if not items:
            return 0, ["Excel dosyasında veri bulunamadı."]

        errors: List[object] = []
        sefer_list = []

        # Master listeleri UoW context'inde çek — singleton repo'da
        # session yok, raw SQL crash ediyor.
        async with UnitOfWork() as uow_ref:
            vehicles = await uow_ref.arac_repo.get_all(sadece_aktif=False)
            drivers = await uow_ref.sofor_repo.get_all(sadece_aktif=False)
            trailers = await uow_ref.dorse_repo.get_all(include_inactive=True)
            routes = await uow_ref.lokasyon_repo.get_all(include_inactive=True)

        for idx, item in enumerate(items, 1):
            try:
                # Validate and Resolve
                plaka = validate_plaka(item.get("plaka"))
                arac_id = resolve_arac_id(plaka, vehicles)

                name = validate_name(item.get("sofor_adi"))
                sofor_id = resolve_sofor_id(name, drivers)

                dorse_id = None
                if item.get("dorse_plakasi"):
                    d_plaka = validate_plaka(item.get("dorse_plakasi"))
                    dorse_id = resolve_dorse_id(d_plaka, trailers)

                cikis_yeri = str(item.get("cikis_yeri") or "").strip()
                varis_yeri = str(item.get("varis_yeri") or "").strip()
                guzergah_id = resolve_route_id(cikis_yeri, varis_yeri, routes)

                # Create Sefer Data
                sefer_data = {
                    "arac_id": arac_id,
                    "sofor_id": sofor_id,
                    "guzergah_id": guzergah_id,
                    "dorse_id": dorse_id,
                    "tarih": item.get("tarih"),
                    "baslangic_km": validate_numeric(
                        item.get("baslangic_km", 0), "Kilometre"
                    ),
                    "bitis_km": validate_numeric(item.get("bitis_km", 0), "Kilometre"),
                    "mesafe_km": validate_numeric(item.get("mesafe_km", 1.0), "Mesafe"),
                    "net_kg": validate_numeric(item.get("net_kg", 0), "Yük"),
                    "cikis_yeri": cikis_yeri or "Bilinmiyor",
                    "varis_yeri": varis_yeri or "Bilinmiyor",
                    "durum": SEFER_STATUS_PLANLANDI,
                }
                sefer_list.append(sefer_data)

            except ImportValidationError as ive:
                # ImportValidationError carries reason code — map to field name
                reason_code = ive.reason or ""
                if reason_code in ("ARAC_NOT_FOUND", "INVALID_PLAKA"):
                    field = "plaka"
                elif reason_code in ("SOFOR_NOT_FOUND", "INVALID_NAME"):
                    field = "sofor_adi"
                elif reason_code == "ROUTE_NOT_FOUND":
                    field = "guzergah"
                elif reason_code == "INVALID_NUMERIC":
                    field = "net_kg"
                else:
                    field = "genel"
                errors.append({"row": idx, "field": field, "reason": str(ive)})
            except ValueError as ve:
                # Eski ValueError path (diğer servislerden gelebilir)
                msg = str(ve)
                field = "Bilinmiyor"
                if "Plaka" in msg or "Araç" in msg:
                    field = "plaka"
                elif "Sofor" in msg or "Şoför" in msg:
                    field = "sofor_adi"
                elif "Guzergah" in msg:
                    field = "guzergah"
                elif "ay" in msg or "Yük" in msg:
                    field = "net_kg"
                errors.append({"row": idx, "field": field, "reason": msg})
            except Exception as e:
                errors.append(
                    {
                        "row": idx,
                        "field": "genel",
                        "reason": f"Beklenmedik hata: {str(e)}",
                    }
                )

        count = 0
        if sefer_list:
            # Delegate to SeferService for bulk processing (trip modülü,
            # henüz taşınmadı — container üzerinden geçici erişim).
            from app.core.container import get_container

            count = await get_container().sefer_service.bulk_add_sefer(sefer_list)

        return count, errors

    except Exception as e:
        await report_infra_failure("process_sefer_import", e)
        return 0, [f"Sistem hatası: {str(e)}"]
