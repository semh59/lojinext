"""
Excel servisi — facade.
Gerçek implementasyon excel_parser.py ve excel_exporter.py içindedir.
"""

from app.core.services.excel_column_map import (  # noqa: F401
    SafeColumnMapper,
    _parse_date_flexible,
)
from app.core.services.excel_exporter import export_data, generate_template
from app.core.services.excel_parser import (
    parse_dorse_excel,
    parse_driver_excel,
    parse_route_excel,
    parse_sefer_excel,
    parse_vehicle_excel,
    parse_yakit_excel,
)


class ExcelService:
    """Backward-compat facade. Yeni kod modülleri doğrudan import etmeli."""

    parse_sefer_excel = staticmethod(parse_sefer_excel)
    parse_yakit_excel = staticmethod(parse_yakit_excel)
    parse_route_excel = staticmethod(parse_route_excel)
    parse_vehicle_excel = staticmethod(parse_vehicle_excel)
    parse_driver_excel = staticmethod(parse_driver_excel)
    parse_dorse_excel = staticmethod(parse_dorse_excel)
    export_data = staticmethod(export_data)
    generate_template = staticmethod(generate_template)

    # Aliases for callers that use the legacy *_data names (bytes-based)
    parse_vehicle_data = staticmethod(parse_vehicle_excel)
    parse_driver_data = staticmethod(parse_driver_excel)
