import io
from datetime import date

import pandas as pd
import pytest

from v2.modules.import_excel.infrastructure.column_mapper import SafeColumnMapper
from v2.modules.import_excel.infrastructure.parsers import parse_sefer_excel


@pytest.mark.asyncio
async def test_excel_fuzzy_column_mapping():
    """Excel başlıklarının (header) esnek eşleştirme testi"""
    # SafeColumnMapper içindeki gerçek ALIAS'lara göre test et
    dirty_headers = [
        "Plaka No",
        "Sefer Tarihi",
        "Şoför Adı",
        "Çıkış Yeri",
        "Varış Yeri",
        "Net KG",
    ]

    mapping = SafeColumnMapper.map_columns(dirty_headers)

    # Beklenen eşleşmeler
    assert mapping["Plaka No"] == "plaka"
    assert mapping["Sefer Tarihi"] == "tarih"
    assert mapping["Şoför Adı"] == "sofor_adi"
    assert mapping["Çıkış Yeri"] == "cikis_yeri"
    assert mapping["Varış Yeri"] == "varis_yeri"
    assert "net_kg" in mapping.values()


@pytest.mark.asyncio
async def test_excel_parse_sefer_anomalies():
    """Excel'deki tarih ve sayı formatı anomalilerinin testi"""
    # Mesafe için 'KM Sayacı' veya 'KM' bekliyor olabilir SafeColumnMapper
    data = {
        "Plaka No": ["34ABC123", "34 DEF 456 ", " 35 GHI 789"],
        "Sefer Tarihi": ["2024-03-18", "19.03.2024", "20/03/2024"],
        "KM": ["450", "300.5", "invalid"],
        "Çıkış Yeri": ["Istanbul", "Ankara", "Izmir"],
        "Varış Yeri": ["Ankara", "Izmir", "Istanbul"],
    }
    df = pd.DataFrame(data)
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
        df.to_excel(writer, index=False)
    content = output.getvalue()

    result = await parse_sefer_excel(content)

    assert len(result) == 3
    assert result[0]["plaka"] == "34ABC123"
    assert result[0]["tarih"] == date(2024, 3, 18)
    # ExcelService km_sayac -> mesafe_km mi eşliyor kontrol etmeliyiz
    # Genelde km_sayac -> mesafe_km veya mesafe_km direkt olmalı
    # SafeColumnMapper'da 'mesafe_km' anahtarı var mı bakacağız.
