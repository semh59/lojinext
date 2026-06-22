from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from app.core.services.excel_service import ExcelService
from app.database.unit_of_work import UnitOfWork
from app.infrastructure.logging.logger import get_logger
from app.schemas.sefer import SeferCreate

logger = get_logger(__name__)


class SeferImportService:
    """Excel'den seferleri parse eden ve veritabanına işleyen özel servis.

    Trips endpoint'inin (``POST /trips/upload``) canlı sefer-import yolu:
    her satır ``SeferCreate`` ile tam Pydantic validasyonundan (XSS sanitize,
    net_kg/ağırlık, durum normalize) geçer, sonra ``bulk_add_sefer``.

    NOT (ARCH-002): admin generic bulk import + rollback için ayrı servis
    ``core/services/ImportService.execute_import`` kullanılır — iş akışları
    kasıtlı olarak ayrıdır (job/rollback vs trip-validation). İkisi de durum
    için canonical sabiti kullanmalıdır (drift = BUG-002)."""

    def __init__(
        self,
        sefer_service=None,
        arac_repo=None,
        sofor_repo=None,
        dorse_repo=None,
        lokasyon_repo=None,
    ):
        self.sefer_service = sefer_service
        self.arac_repo = arac_repo
        self.sofor_repo = sofor_repo
        self.dorse_repo = dorse_repo
        self.lokasyon_repo = lokasyon_repo

    async def process_excel_import(
        self, content: bytes, current_user_id: int
    ) -> Tuple[int, List[Dict[str, Any]]]:
        """Excel verisini işler ve Sefer modellerini oluşturur."""
        try:
            # Excel'i parse et
            items = await ExcelService.parse_sefer_excel(content)
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
            vehicle_lookup = self._build_lookup(vehicles, "plaka")
            driver_lookup = self._build_lookup(drivers, "ad_soyad")
            trailer_lookup = self._build_lookup(trailers, "plaka")

            for idx, item in enumerate(items, 1):
                try:
                    # 1. Araç Çözümleme — zorunlu
                    plaka = self._clean_plaka(item.get("plaka"))
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
                    guzergah_id = self._resolve_route_id(cikis_yeri, varis_yeri, routes)

                    # 3. Dorse Çözümleme — opsiyonel
                    dorse_id = None
                    dorse_plaka = self._clean_plaka(item.get("dorse_plakasi"))
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
                try:
                    count = await self.sefer_service.bulk_add_sefer(valid_sefers)
                except Exception as e:
                    logger.error(f"bulk_add_sefer hatası: {e}", exc_info=True)
                    errors.append(
                        {"row": 0, "reason": f"Toplu ekleme hatası: {str(e)}"}
                    )
                    return 0, errors
                return count, errors

            return 0, errors

        except Exception as e:
            logger.error(f"SeferImportService Error: {e}", exc_info=True)
            return 0, [{"row": 0, "reason": f"Sistem hatası: {str(e)}"}]

    def _clean_plaka(self, plaka: Any) -> str:
        if not plaka:
            return ""
        return str(plaka).replace(" ", "").upper()

    def _build_lookup(
        self, master_list: List[Any], field: str
    ) -> dict[str, Optional[int]]:
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

    def _resolve_master_id(
        self, search_val: str, master_list: List[Any], field: str
    ) -> Optional[int]:
        if not search_val:
            return None
        search_norm = str(search_val).strip().upper()
        matches = []
        for item in master_list:
            item_val = (
                str(
                    getattr(item, field, "")
                    if hasattr(item, field)
                    else item.get(field, "")
                )
                .strip()
                .upper()
            )
            if item_val == search_norm:
                matches.append(item.id if hasattr(item, "id") else item.get("id"))
        # Ambiguous (>1 match) → None prevents silent misassignment
        return matches[0] if len(matches) == 1 else None

    def _resolve_route_id(
        self, cikis_yeri: str, varis_yeri: str, routes: List[Any]
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


def get_sefer_import_service() -> SeferImportService:
    from app.core.container import get_container  # deferred — circular import önlenir

    container = get_container()
    return SeferImportService(
        sefer_service=container.sefer_service,
        arac_repo=container.arac_repo,
        sofor_repo=container.sofor_repo,
        dorse_repo=container.dorse_repo,
        lokasyon_repo=container.lokasyon_repo,
    )
