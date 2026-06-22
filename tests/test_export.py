import io

import pandas as pd
import pytest

from app.core.services.excel_service import ExcelService


@pytest.mark.asyncio
async def test_excel_export():
    data = [
        {
            "tarih": "2026-03-19",
            "saat": "10:30",
            "cikis_yeri": "Istanbul",
            "varis_yeri": "Ankara",
            "mesafe_km": 450,
            "net_kg": 22000,
            "plaka": "34 ABC 123",
            "sofor": "Ahmet Sofor",
            "durum": "Tamam",
            "tahmini_yakit_lt": 140.5,
        }
    ]

    content = await ExcelService.export_data(data, type="sefer_listesi")

    assert content
    df = pd.read_excel(io.BytesIO(content), header=1)
    columns = [str(col) for col in df.columns]
    assert any("Tarih" in col for col in columns)
    assert any("Plaka" in col for col in columns)
    assert any("Şof" in col or "Sof" in col for col in columns)
    assert df.iloc[0]["Plaka"] == "34 ABC 123"
