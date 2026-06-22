import inspect
from decimal import Decimal

import pytest

from app.core.services.excel_service import ExcelService


@pytest.mark.asyncio
async def test_export_data_returns_bytes_not_coroutine():
    data = [{"plaka": "06ABC123", "marka": "Mercedes"}]
    result = await ExcelService.export_data(data, type="arac_listesi")
    assert isinstance(result, bytes), f"bytes beklendi, geldi: {type(result)}"
    assert len(result) > 100, "coroutine değil gerçek bytes olmalı"
    assert result[:4] == b"PK\x03\x04", "geçerli XLSX magic bytes olmalı"


@pytest.mark.asyncio
async def test_generate_template_returns_bytes_not_coroutine():
    result = await ExcelService.generate_template("arac")
    assert isinstance(result, bytes), f"bytes beklendi, geldi: {type(result)}"
    assert len(result) > 100
    assert result[:4] == b"PK\x03\x04"


def test_export_data_without_await_returns_coroutine():
    """Documents the bug — calling without await returns coroutine."""
    data = [{"plaka": "06ABC123"}]
    result = ExcelService.export_data(data, type="arac_listesi")
    assert inspect.iscoroutine(result), "await olmadan coroutine dönmeli (bug kanıtı)"
    result.close()


@pytest.mark.asyncio
async def test_export_data_handles_decimal_values():
    """Decimal tipler float'a çevrilmeli, xlsxwriter patlatmamalı."""
    data = [
        {
            "plaka": "06ABC",
            "maliyet": Decimal("1234.56"),
            "verimlilik": Decimal("28.750"),
        }
    ]
    result = await ExcelService.export_data(data, type="generic")
    assert isinstance(result, bytes)
    assert result[:4] == b"PK\x03\x04"


@pytest.mark.asyncio
async def test_export_data_handles_dict_values():
    """Dict tipler string'e çevrilmeli, xlsxwriter patlatmamalı."""
    data = [
        {
            "plaka": "06ABC",
            "meta": {"filo": "A", "grup": 3},
        }
    ]
    result = await ExcelService.export_data(data, type="generic")
    assert isinstance(result, bytes)
    assert result[:4] == b"PK\x03\x04"


@pytest.mark.asyncio
async def test_export_data_handles_mixed_special_types():
    """Decimal + dict + timezone datetime birlikte olunca da çalışmalı."""
    from datetime import datetime, timezone

    data = [
        {
            "tarih": datetime(2024, 1, 15, 12, 0, tzinfo=timezone.utc),
            "maliyet": Decimal("999.99"),
            "bilgi": {"kaynak": "gps"},
        }
    ]
    result = await ExcelService.export_data(data, type="generic")
    assert isinstance(result, bytes)
    assert result[:4] == b"PK\x03\x04"


@pytest.mark.asyncio
async def test_dorse_service_export_returns_bytes():
    """dorse_service export_all_trailers coroutine değil bytes dönmeli."""
    from unittest.mock import AsyncMock, MagicMock

    from app.core.services.dorse_service import DorseService

    mock_repo = AsyncMock()
    mock_repo.get_all = AsyncMock(
        return_value=[
            {
                "plaka": "34ABC001",
                "marka": "Schmitz",
                "model": "SCS",
                "yil": 2020,
                "tipi": "Tenteli",
                "bos_agirlik_kg": 7500,
                "lastik_sayisi": 12,
                "aktif": True,
            }
        ]
    )

    mock_event_bus = MagicMock()
    service = DorseService(repo=mock_repo, event_bus=mock_event_bus)
    result = await service.export_all_trailers()
    assert isinstance(result, bytes), f"bytes beklendi, geldi: {type(result)}"
    assert result[:4] == b"PK\x03\x04", "geçerli XLSX magic bytes olmalı"


@pytest.mark.asyncio
async def test_dorse_service_get_template_returns_bytes():
    """dorse_service get_template coroutine değil bytes dönmeli."""
    from unittest.mock import AsyncMock, MagicMock

    from app.core.services.dorse_service import DorseService

    service = DorseService(repo=AsyncMock(), event_bus=MagicMock())
    result = await service.get_template()
    assert isinstance(result, bytes), f"bytes beklendi, geldi: {type(result)}"
    assert result[:4] == b"PK\x03\x04", "geçerli XLSX magic bytes olmalı"
