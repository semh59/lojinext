"""Lokasyon/güzergah Excel import.

Hedef: ``v2.modules.location.application.create_location`` — dict →
``LokasyonCreate`` Pydantic. Her satır kendi UoW'unda işlenir;
container.lokasyon_repo singleton'ı (session'sız) raw SQL atınca
crash ediyordu.
"""

from typing import Tuple

from v2.modules.import_excel.infrastructure.monitoring_bridge import (
    report_infra_failure,
)
from v2.modules.import_excel.infrastructure.parsers import parse_route_excel
from v2.modules.shared_kernel.infrastructure.unit_of_work import UnitOfWork


async def import_routes(content: bytes) -> Tuple[int, list]:
    from v2.modules.location.public import LokasyonCreate, create_location, route_key

    try:
        items = await parse_route_excel(content)
        if not items:
            return 0, ["Excel dosyası boş veya veri bulunamadı."]

        # N+1 önleme (Sentry LOJINEXT-17A): satır-başına ayrı get_by_route
        # SELECT'i atmak yerine mevcut tüm güzergahları TEK sorguyla
        # bellek-içi index'e çek; create_location bu index verildiğinde
        # kendi SELECT'ini atlar (aynı batch içi tekrarlar dahil,
        # index insert/reaktivasyon sonrası yerinde güncelleniyor).
        # route_key modül-seviyesinde serbest bir fonksiyon — testlerin
        # create_location'ı monkeypatch'lediği senaryolarda bile
        # (bkz. test_import_routes_valid) çağrılabilir kalması için.
        async with UnitOfWork() as index_uow:
            existing_rows = await index_uow.lokasyon_repo.get_all_route_keys()
        existing_index = {
            route_key(r["cikis_yeri"], r["varis_yeri"]): {
                "id": r["id"],
                "aktif": r["aktif"],
            }
            for r in existing_rows
        }

        errors: list[str] = []
        count = 0
        for idx, item in enumerate(items, 1):
            try:
                payload = LokasyonCreate(**item)
                async with UnitOfWork() as uow:
                    await create_location(
                        uow.lokasyon_repo, payload, existing_index=existing_index
                    )
                    await uow.commit()
                count += 1
            except Exception as e:
                errors.append(f"Satır {idx}: {str(e)}")
        return count, errors
    except Exception as e:
        await report_infra_failure("import_routes", e)
        return 0, [f"Sistem hatası: {str(e)}"]
