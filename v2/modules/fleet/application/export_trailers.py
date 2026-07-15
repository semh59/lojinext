"""Use-cases: trailer Excel export/import."""

from typing import Any, Dict

from v2.modules.fleet.infrastructure.trailer_repository import DorseRepository


async def export_all_trailers(repo: DorseRepository) -> bytes:
    """Tüm dorseleri Excel olarak dışa aktar."""
    from v2.modules.import_excel.public import export_data

    dorseler = await repo.get_all(limit=10000)
    data = [
        {
            "plaka": d.get("plaka") if isinstance(d, dict) else d.plaka,
            "marka": d.get("marka") if isinstance(d, dict) else d.marka,
            "model": d.get("model") if isinstance(d, dict) else d.model,
            "yil": d.get("yil") if isinstance(d, dict) else d.yil,
            "tipi": d.get("tipi") if isinstance(d, dict) else d.tipi,
            "bos_agirlik_kg": d.get("bos_agirlik_kg")
            if isinstance(d, dict)
            else d.bos_agirlik_kg,
            "lastik_sayisi": d.get("lastik_sayisi")
            if isinstance(d, dict)
            else d.lastik_sayisi,
            "aktif": d.get("aktif") if isinstance(d, dict) else d.aktif,
        }
        for d in dorseler
    ]

    return await export_data(data, type="dorse_listesi")


async def get_trailer_template() -> bytes:
    """Dorse yükleme şablonunu getir."""
    from v2.modules.import_excel.public import generate_template

    return await generate_template("dorse")


async def import_trailers(repo: DorseRepository, content: bytes) -> Dict[str, Any]:
    """Excel'den dorse aktarımı."""
    from v2.modules.fleet.application.create_trailer import create_trailer
    from v2.modules.import_excel.public import parse_dorse_excel

    parsed_data = await parse_dorse_excel(content)

    count = 0
    errors = []

    for item in parsed_data:
        try:
            # Plaka bazlı mükerrer kontrolü create_trailer içinde var
            await create_trailer(repo, **item)
            count += 1
        except Exception as e:
            errors.append({"plaka": item.get("plaka"), "error": str(e)})

    return {"imported": count, "errors": errors}
