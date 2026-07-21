"""Master-liste üzerinden plaka/isim/güzergah → id çözümleyicileri.

Excel import satırlarının referans verdiği araç/şoför/dorse/güzergahı,
UoW içinde önceden çekilmiş master listeler (``vehicles``/``drivers``/
``trailers``/``routes``) üzerinde arar. Repository'lere DOĞRUDAN erişmez —
çağıran (``application/``) master listeyi bir kez UoW ile çekip buraya
parametre olarak geçirir (N+1 önleme, importer'lar arası paylaşılan sözleşme).
"""

from typing import Any, Dict, List, Optional

from v2.modules.shared_kernel.exceptions import ImportValidationError


def resolve_arac_id(
    plaka: Optional[str], vehicles: List[Dict[str, Any]]
) -> Optional[int]:
    if not plaka:
        return None
    search_p = plaka.replace(" ", "").upper()
    for v in vehicles:
        if v["plaka"].replace(" ", "").upper() == search_p:
            return v["id"]
    raise ImportValidationError(["Araç bulunamadı"], reason="ARAC_NOT_FOUND")


def resolve_sofor_id(name: Optional[str], drivers: List[Dict[str, Any]]) -> int:
    if not name:
        raise ImportValidationError(["Şoför adı boş"], reason="SOFOR_NOT_FOUND")
    search_n = name.strip().upper()
    for d in drivers:
        if d["ad_soyad"].strip().upper() == search_n:
            return d["id"]
    raise ImportValidationError([f"Şoför bulunamadı: {name}"], reason="SOFOR_NOT_FOUND")


def resolve_route_id(
    cikis_yeri: Optional[str],
    varis_yeri: Optional[str],
    routes: List[Dict[str, Any]],
) -> int:
    from v2.modules.import_excel.domain.field_validators import normalize_text

    cikis_norm = normalize_text(cikis_yeri)
    varis_norm = normalize_text(varis_yeri)
    if not cikis_norm or not varis_norm:
        raise ImportValidationError(["Çıkış/varış yeri boş"], reason="ROUTE_NOT_FOUND")

    for route in routes:
        route_cikis = normalize_text(route.get("cikis_yeri", ""))
        route_varis = normalize_text(route.get("varis_yeri", ""))
        if route_cikis == cikis_norm and route_varis == varis_norm:
            return route["id"]

    raise ImportValidationError(
        [f"Güzergah bulunamadı: {cikis_yeri} → {varis_yeri}"],
        reason="ROUTE_NOT_FOUND",
    )


def resolve_dorse_id(
    plaka: Optional[str], trailers: List[Dict[str, Any]]
) -> Optional[int]:
    if not plaka:
        return None
    search_p = plaka.replace(" ", "").upper()
    for t in trailers:
        if t["plaka"].replace(" ", "").upper() == search_p:
            return t["id"]
    return None
