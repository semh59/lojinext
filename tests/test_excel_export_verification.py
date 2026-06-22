import io

import pandas as pd
import pytest

from app.core.services.excel_service import ExcelService


class TestExcelExportEngine:
    """Excel Export Engine Verification Tests"""

    @pytest.mark.asyncio
    async def test_export_data_generates_bytes(self):
        """Test that export_data returns bytes"""
        data = [{"col1": "val1", "col2": 123}]
        result = await ExcelService.export_data(data, type="test")
        assert isinstance(result, bytes)
        assert len(result) > 0

    @pytest.mark.asyncio
    async def test_export_data_content_integrity(self):
        """Test that exported data matches input when read back"""
        input_data = [
            {"ad_soyad": "Ahmet Yilmaz", "puan": 1.5, "tarih": "2024-01-01"},
            {"ad_soyad": "Mehmet Demir", "puan": 0.8, "tarih": "2024-01-02"},
        ]

        excel_bytes = await ExcelService.export_data(input_data, type="integrity_check")

        df = pd.read_excel(io.BytesIO(excel_bytes), header=1)

        assert "Ad Soyad" in df.columns
        assert "Puan" in df.columns
        assert "Tarih" in df.columns

        assert df.iloc[0]["Ad Soyad"] == "Ahmet Yilmaz"
        assert df.iloc[0]["Puan"] == 1.5
        assert "2024-01-01" in str(df.iloc[0]["Tarih"])

    @pytest.mark.asyncio
    async def test_empty_data_handling(self):
        """Test export with empty list"""
        result = await ExcelService.export_data([], type="empty")
        assert isinstance(result, bytes)
        df = pd.read_excel(io.BytesIO(result))
        assert df.empty

    @pytest.mark.asyncio
    async def test_styling_header_exists(self):
        """Test that the title row is present"""
        data = [{"a": 1}]
        excel_bytes = await ExcelService.export_data(data, type="styling_test")

        df = pd.read_excel(io.BytesIO(excel_bytes), header=None)
        title_cell = df.iloc[0, 0]
        assert "STYLING_TEST RAPORU" in str(title_cell)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
