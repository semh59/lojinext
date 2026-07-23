"""Trip'in ``POST /trips/upload`` (sefer Excel yükleme) canlı yolu.

Her satır ``SeferCreate`` ile tam Pydantic validasyonundan (XSS sanitize,
net_kg/ağırlık, durum normalize) geçer, sonra ``bulk_add_sefer``.

NOT (ARCH-002): admin generic bulk import + rollback için ayrı akış
``application/execute_import.py`` kullanır — iş akışları kasıtlı olarak
ayrıdır (job/rollback vs trip-validation). İkisi de durum için canonical
sabiti kullanmalıdır (drift = BUG-002).

B.1: eski ``SeferImportService`` sınıfının constructor'ı ``arac_repo``/
``sofor_repo``/``dorse_repo``/``lokasyon_repo`` alıyordu ama hiçbiri
kullanılmıyordu (metod gövdesi kendi ``UnitOfWork()``'ünü açıyor) — free
function'a geçişte bu ölü parametreler kaldırıldı, yalnız gerçekten
kullanılan ``bulk_add_sefer`` (trip modülü, dalga 14 — artık
``v2.modules.trip.public`` üzerinden doğrudan) korundu.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from v2.modules.import_excel.infrastructure.parsers import parse_sefer_excel
from v2.modules.platform_infra.public import get_logger
from v2.modules.shared_kernel.infrastructure.unit_of_work import UnitOfWork
from v2.modules.trip.public import SeferCreate

logger = get_logger(__name__)


def _clean_plaka(plaka: Any) -> str:
    if not plaka:
        return ""
    return str(plaka).replace(" ", "").upper()


def _build_lookup(master_list: List[Any], field: str) -> dict[str, Optional[int]]:
    """Build normalised-value → id lookup in O(m); None marks ambiguous duplicates."""
    lookup: dict[str, Optional[int]] = {}
    for item in master_list:
        val = (
            str(
                getattr(item, field, "")
                if hasattr(item, field)
                else item.get(field, "")
            )
            .strip()
            .upper()
        )
        if not val:
            continue
        item_id = item.id if hasattr(item, "id") else item.get("id")
        lookup[val] = None if val in lookup else item_id
    return lookup


def _resolve_route_id(
    cikis_yeri: str, varis_yeri: str, routes: List[Any]
) -> Optional[int]:
    cikis_norm = str(cikis_yeri or "").strip().upper()
    varis_norm = str(varis_yeri or "").strip().upper()
    if not cikis_norm or not varis_norm:
        return None

    for route in routes:
        route_cikis = (
            str(
                getattr(route, "cikis_yeri", "")
                if hasattr(route, "cikis_yeri")
                else route.get("cikis_yeri", "")
            )
            .strip()
            .upper()
        )
        route_varis = (
            str(
                getattr(route, "varis_yeri", "")
                if hasattr(route, "varis_yeri")
                else route.get("varis_yeri", "")
            )
            .strip()
            .upper()
        )
        if route_cikis == cikis_norm and route_varis == varis_norm:
            return route.id if hasattr(route, "id") else route.get("id")
    return None


async def import_sefer_excel_upload(
    content: bytes, current_user_id: int
) -> Tuple[int, List[Dict[str, Any]]]:
    """Excel verisini işler ve Sefer modellerini oluşturur."""
    try:
        # Excel'i parse et
        items = await parse_sefer_excel(content)
        if not items:
            return 0, [
                {"row": 0, "reason": "Excel dosyasında geçerli veri bulunamadı."}
            ]

        errors = []
        valid_sefers = []

        # Master listeleri UoW context'inde çek — singleton repo'lar
        # session'sız raw SQL atınca crash ediyor. UoW her repo'ya canlı
        # session enjekte ediyor.
        async with UnitOfWork() as uow:
            vehicles = await uow.arac_repo.get_all(sadece_aktif=False)
            drivers = await uow.sofor_repo.get_all(sadece_aktif=False)
            # DorseRepository.get_all yok → base'in include_inactive parametresi
            trailers = await uow.dorse_repo.get_all(include_inactive=True)
            routes = await uow.lokasyon_repo.get_all(include_inactive=True)

        # O(n×m) → O(n+m): build lookup dicts once, look up in O(1) per row
        vehicle_lookup = _build_lookup(vehicles, "plaka")
        driver_lookup = _build_lookup(drivers, "ad_soyad")
        trailer_lookup = _build_lookup(trailers, "plaka")

        for idx, item in enumerate(items, 1):
            try:
                # 1. Araç Çözümleme — zorunlu
                plaka = _clean_plaka(item.get("plaka"))
                arac_id = vehicle_lookup.get(plaka)
                if not arac_id:
                    raise ValueError(
                        f"Araç bulunamadı: '{plaka}'. Önce araç kayıt edin."
                    )

                # 2. Şoför Çözümleme — zorunlu
                sofor_id = None
                sofor_adi = item.get("sofor_adi")
                if sofor_adi:
                    sofor_id = driver_lookup.get(str(sofor_adi).strip().upper())
                if not sofor_id:
                    raise ValueError(
                        f"Şoför bulunamadı: '{sofor_adi or 'Bilinmiyor'}'. "
                        "Önce şoför kayıt edin (ad-soyad birebir eşleşir)."
                    )

                cikis_yeri = str(item.get("cikis_yeri") or "").strip()
                varis_yeri = str(item.get("varis_yeri") or "").strip()
                if len(cikis_yeri) < 2 or len(varis_yeri) < 2:
                    raise ValueError(
                        "cikis_yeri ve varis_yeri en az 2 karakter olmalı."
                    )
                # Güzergah opsiyonel — yoksa bulk_add_sefer fuzzy match
                # yapacak, yine yoksa None bırakılır (sefer guzergah_id
                # nullable).
                guzergah_id = _resolve_route_id(cikis_yeri, varis_yeri, routes)

                # 3. Dorse Çözümleme — opsiyonel
                dorse_id = None
                dorse_plaka = _clean_plaka(item.get("dorse_plakasi"))
                if dorse_plaka:
                    dorse_id = trailer_lookup.get(dorse_plaka)

                # 4. Tarih — zorunlu (excel'den parse edilmiş olmalı).
                # Eski davranış datetime.now() default → geçmiş veriler
                # bugün olarak kaydediliyordu; bu production-aykırı.
                tarih = item.get("tarih")
                if tarih is None:
                    raise ValueError(
                        "Tarih boş — geçmiş seferler için tarih sütunu zorunlu."
                    )

                # 5. Durum — Excel'de varsa kullan; yoksa SeferCreate default
                # (canonical 'Planned'). Tamamlanmış geçmiş seferler için
                # Excel'de 'Tamamlandı' yazılmalı (import sırasında 'Completed'e
                # normalize edilir).
                durum_raw = item.get("durum")

                # 6. SeferCreate Pydantic objesi (bulk_add_sefer attribute
                # erişimi yapar; dict göndermek runtime AttributeError verir).
                sefer_kwargs: Dict[str, Any] = {
                    "tarih": tarih,
                    "arac_id": arac_id,
                    "sofor_id": sofor_id,
                    "cikis_yeri": cikis_yeri,
                    "varis_yeri": varis_yeri,
                    "mesafe_km": float(item.get("mesafe_km") or 0),
                    "net_kg": float(item.get("net_kg") or 0),
                    "notlar": (
                        item.get("notlar")
                        or f"Excel Import - {datetime.now().strftime('%Y-%m-%d %H:%M')}"
                    ),
                }
                if guzergah_id:
                    sefer_kwargs["guzergah_id"] = guzergah_id
                if dorse_id:
                    sefer_kwargs["dorse_id"] = dorse_id
                if durum_raw:
                    sefer_kwargs["durum"] = str(durum_raw).strip()
                # GPS rotası alanları (varsa Excel'den geliyor)
                for gps_field in ("ascent_m", "descent_m", "flat_distance_km"):
                    if item.get(gps_field) is not None:
                        try:
                            sefer_kwargs[gps_field] = float(item[gps_field])
                        except (TypeError, ValueError):
                            pass
                # Sefer numarası (varsa)
                if item.get("sefer_no"):
                    sefer_kwargs["sefer_no"] = str(item["sefer_no"])

                valid_sefers.append(SeferCreate(**sefer_kwargs))

            except Exception as e:
                errors.append({"row": idx + 1, "reason": str(e)})

        # 7. Toplu Ekleme
        if valid_sefers:
            from v2.modules.trip.public import bulk_add_sefer

            try:
                count = await bulk_add_sefer(valid_sefers)
            except Exception as e:
                logger.error(f"bulk_add_sefer hatası: {e}", exc_info=True)
                errors.append({"row": 0, "reason": f"Toplu ekleme hatası: {str(e)}"})
                return 0, errors
            return count, errors

        return 0, errors

    except Exception as e:
        logger.error(f"sefer_upload_importer Error: {e}", exc_info=True)
        return 0, [{"row": 0, "reason": f"Sistem hatası: {str(e)}"}]
