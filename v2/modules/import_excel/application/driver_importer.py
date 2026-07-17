"""Şoför Excel import (driver modülünün ``bulk_add_sofor`` yolu)."""

from typing import Tuple

from v2.modules.import_excel.infrastructure.monitoring_bridge import (
    report_infra_failure,
)
from v2.modules.import_excel.infrastructure.parsers import parse_driver_excel


async def process_driver_import(content: bytes) -> Tuple[int, list]:
    """Processes driver import."""
    try:
        from v2.modules.driver.public import bulk_add_sofor

        items = await parse_driver_excel(content)
        if not items:
            return 0, ["Excel dosyasında veri bulunamadı."]

        errors: list[str] = []
        count = await bulk_add_sofor(items)
        return count, errors
    except Exception as e:
        await report_infra_failure("process_driver_import", e)
        return 0, [f"Sistem hatası: {str(e)}"]
