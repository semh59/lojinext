"""``execute_import``'un satır-bazlı doğrulama dispatcher'ı.

Eskiden tek bir ``_validate_import_rows`` metodu 4 ``aktarim_tipi``'ne
(arac/surucu/sefer/yakit) dallanıyordu. Burada her tip kendi fonksiyonuna
bölündü (B.1), AMA prefetch edilen master listeler (``vehicles``/``drivers``/
``trailers``/``routes``) **tek seferde çekilip parametre olarak paylaşılıyor**
— her split'in kendi SELECT'ini atması N+1 regresyonu olurdu (görev
dosyasının açık uyarısı). Kanıt:
``app/tests/unit/test_services/test_import_service_coverage.py::
TestExecuteImportSeferPath::test_sefer_execute_import_avoids_n_plus_one`` —
3 satırlı bir sefer Excel'i ile `arac_repo`/`sofor_repo`/`dorse_repo`/
`lokasyon_repo.get_all`'ların satır sayısından bağımsız TAM 1 kez
çağrıldığını sorgu-sayımıyla kanıtlar (`import_routes`/güzergah yolu için
ayrıca `test_import_routes_avoids_n_plus_one` var).
"""

from typing import Any, Dict, List, Tuple

from v2.modules.import_excel.domain.entity_resolvers import (
    resolve_arac_id,
    resolve_dorse_id,
    resolve_route_id,
    resolve_sofor_id,
)
from v2.modules.import_excel.domain.field_validators import (
    parse_date_flexible,
    validate_numeric,
)


def validate_arac_row(row: Dict[str, Any], mapping: Dict[str, str]) -> Dict[str, Any]:
    from v2.modules.shared_kernel.exceptions import ImportValidationError

    plaka = row.get(mapping.get("plaka", "plaka"))
    if not plaka:
        raise ImportValidationError(["Plaka alanı zorunludur."])
    return {"plaka": plaka}


def validate_surucu_row(row: Dict[str, Any], mapping: Dict[str, str]) -> Dict[str, Any]:
    from v2.modules.shared_kernel.exceptions import ImportValidationError

    ad_soyad = row.get(mapping.get("ad_soyad", "ad_soyad"))
    if not ad_soyad:
        # Diğer 3 kardeşle (arac/sefer/yakit) tutarlı: eksik zorunlu alan
        # temiz bir ImportValidationError olarak yükselmeli, aksi halde
        # execute_import.py'nin ham SQL INSERT'i (PII şifreleme/NOT NULL)
        # opak bir hata ile patlıyordu (2026-07-16 dedektif denetimi
        # bulgusu).
        raise ImportValidationError(["Ad Soyad alanı zorunludur."])
    ehliyet_key = mapping.get("ehliyet_sinifi", "ehliyet_sinifi")
    ehliyet_sinifi = row.get(ehliyet_key)
    telefon = row.get(mapping.get("telefon", "telefon"))
    return {"ad_soyad": ad_soyad, "ehliyet": ehliyet_sinifi, "tel": telefon}


def validate_sefer_row(
    row: Dict[str, Any],
    mapping: Dict[str, str],
    vehicles: List[Dict[str, Any]],
    drivers: List[Dict[str, Any]],
    trailers: List[Dict[str, Any]],
    routes: List[Dict[str, Any]],
) -> Dict[str, Any]:
    from v2.modules.shared_kernel.exceptions import ImportValidationError

    plaka = row.get(mapping.get("plaka", "plaka"))
    sofor_ad = row.get(mapping.get("sofor_ad", "sofor_ad"))
    dorse_plaka = row.get(mapping.get("dorse_plakasi", "dorse_plakasi"))
    cikis_yeri = str(row.get(mapping.get("cikis_yeri", "cikis_yeri")) or "").strip()
    varis_yeri = str(row.get(mapping.get("varis_yeri", "varis_yeri")) or "").strip()
    tarih = parse_date_flexible(row.get(mapping.get("tarih", "tarih")))
    mesafe = validate_numeric(
        row.get(mapping.get("mesafe_km", "mesafe_km"), 0), "Mesafe"
    )
    ton_raw = validate_numeric(row.get(mapping.get("ton", "ton"), 0), "Yük")

    # "Yük" kolonu kg cinsinden beklenir. 200'den küçük değer büyük
    # ihtimalle ton cinsinden girilmiş (örn. 20 ton yerine 20000 kg
    # yazılmalıydı). 1000 ile çarp ve uyar.
    if 0 < ton_raw < 200:
        from app.infrastructure.logging.logger import get_logger

        get_logger(__name__).warning(
            "Yük=%s küçük — ton olarak yorumlandı, kg'a çevrildi (%s kg). "
            "Excel şablonuna kg giriniz.",
            ton_raw,
            int(ton_raw * 1000),
        )
        net_kg = int(round(ton_raw * 1000))
    else:
        net_kg = int(round(ton_raw))
    ton = round(net_kg / 1000.0, 2)

    # Araç boş ağırlığını master listeden al → dolu = bos + net
    arac_id = resolve_arac_id(plaka, vehicles)
    bos_agirlik_kg = 0
    if arac_id is not None:
        _arac = next((v for v in vehicles if v["id"] == arac_id), None)
        bos_agirlik_kg = int(_arac.get("bos_agirlik_kg") or 0) if _arac else 0
    dolu_agirlik_kg = bos_agirlik_kg + net_kg

    if not cikis_yeri or not varis_yeri:
        raise ImportValidationError(
            ["Çıkış veya varış yeri eksik"], reason="ROUTE_NOT_FOUND"
        )

    sofor_id = resolve_sofor_id(str(sofor_ad or "").strip(), drivers)
    guzergah_id = resolve_route_id(cikis_yeri, varis_yeri, routes)

    dorse_id = None
    if dorse_plaka:
        dorse_id = resolve_dorse_id(dorse_plaka, trailers)

    return {
        "arac_id": arac_id,
        "sofor_id": sofor_id,
        "dorse_id": dorse_id,
        "guzergah_id": guzergah_id,
        "tarih": tarih,
        "mesafe": mesafe,
        "net_kg": net_kg,
        "ton": ton,
        "bos_agirlik_kg": bos_agirlik_kg,
        "dolu_agirlik_kg": dolu_agirlik_kg,
        "cikis_yeri": cikis_yeri,
        "varis_yeri": varis_yeri,
    }


def validate_yakit_row(
    row: Dict[str, Any],
    mapping: Dict[str, str],
    vehicles: List[Dict[str, Any]],
) -> Dict[str, Any]:
    plaka = row.get(mapping.get("plaka", "plaka"))
    tarih = parse_date_flexible(row.get(mapping.get("tarih", "tarih")))
    litre = validate_numeric(row.get(mapping.get("litre", "litre"), 0), "Litre")
    tutar = validate_numeric(
        row.get(mapping.get("toplam_tutar", "toplam_tutar"), 0), "Tutar"
    )
    km = validate_numeric(row.get(mapping.get("km_sayac", "km_sayac"), 0), "Kilometre")
    arac_id = resolve_arac_id(plaka, vehicles)
    return {
        "arac_id": arac_id,
        "tarih": tarih,
        "litre": litre,
        "tutar": tutar,
        "km": km,
    }


def validate_import_rows(
    rows: List[Dict[str, Any]],
    aktarim_tipi: str,
    mapping: Dict[str, str],
    vehicles: List[Dict[str, Any]],
    drivers: List[Dict[str, Any]],
    trailers: List[Dict[str, Any]],
    routes: List[Dict[str, Any]],
) -> Tuple[List[Dict[str, Any]], Dict[str, str]]:
    """
    Her satırı doğrular ve gerekli alanları çözer.
    (geçerli_satırlar, hata_mesajları_dict) döner.
    Geçerli satırlar insert için hazır parametre dict'leri içerir.

    ``vehicles``/``drivers``/``trailers``/``routes`` çağıran tarafından TEK
    seferde (aktarim_tipi'ne bakılmaksızın) prefetch edilip buraya geçirilir
    — her satır için ayrı sorgu atmak N+1 regresyonu olurdu.
    """
    valid: List[Dict[str, Any]] = []
    errors: Dict[str, str] = {}

    for index, row in enumerate(rows):
        try:
            if aktarim_tipi == "arac":
                result = validate_arac_row(row, mapping)
            elif aktarim_tipi == "surucu":
                result = validate_surucu_row(row, mapping)
            elif aktarim_tipi == "sefer":
                result = validate_sefer_row(
                    row, mapping, vehicles, drivers, trailers, routes
                )
            elif aktarim_tipi == "yakit":
                result = validate_yakit_row(row, mapping, vehicles)
            else:
                continue
            result["_index"] = index
            valid.append(result)
        except Exception as e:
            errors[str(index)] = str(e)

    return valid, errors
