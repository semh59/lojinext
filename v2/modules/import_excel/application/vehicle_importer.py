"""Araç Excel import (fleet modülünün ``bulk_add_vehicles`` yolu)."""

from typing import Tuple

from app.database.unit_of_work import UnitOfWork
from v2.modules.import_excel.domain.field_validators import validate_plaka
from v2.modules.import_excel.infrastructure.monitoring_bridge import (
    report_infra_failure,
)
from v2.modules.import_excel.infrastructure.parsers import parse_vehicle_excel


async def process_vehicle_import(content: bytes) -> Tuple[int, list]:
    """Processes vehicle import."""
    try:
        items = await parse_vehicle_excel(content)
        if not items:
            return 0, ["Excel dosyasında veri bulunamadı."]

        from v2.modules.fleet.schemas import AracCreate

        errors: list[str] = []
        count = 0
        to_add: list[AracCreate] = []

        # Phase 1: read existing + reactivate in a short UoW.
        # Closed before bulk_add_arac opens its own UoW (avoid nested UoW).
        async with UnitOfWork() as uow:
            existing_vehicles = await uow.arac_repo.get_all(sadece_aktif=False)
            for idx, item in enumerate(items, 1):
                try:
                    plaka = validate_plaka(item.get("plaka"))

                    existing = next(
                        (
                            v
                            for v in existing_vehicles
                            if v["plaka"].replace(" ", "").upper() == plaka
                        ),
                        None,
                    )
                    if existing:
                        if not existing.get("aktif", True):
                            await uow.arac_repo.update(existing["id"], aktif=True)
                            errors.append(
                                f"Araç {plaka} zaten mevcuttu, aktifleştirildi."
                            )
                        continue

                    # Per-item Pydantic cast — bad rows become errors, batch continues.
                    try:
                        to_add.append(AracCreate(**item))
                    except Exception as cast_err:
                        errors.append(f"Satır {idx}: geçersiz alan — {cast_err}")

                except ValueError as ve:
                    errors.append(f"Satır {idx}: {str(ve)}")
            await uow.commit()

        # Phase 2: create new vehicles in bulk_add_vehicles's own UoW.
        if to_add:
            from v2.modules.fleet.application.bulk_add_vehicles import (
                bulk_add_vehicles,
            )

            count = await bulk_add_vehicles(to_add)

        return count, errors
    except Exception as e:
        await report_infra_failure("process_vehicle_import", e)
        return 0, [f"Sistem hatası: {str(e)}"]
