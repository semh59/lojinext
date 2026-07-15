"""
Excel dışa aktarma ve şablon oluşturma işlemleri.
"""

import asyncio
import io
import math
from datetime import date, datetime, timezone
from typing import Any, Dict, List

import numpy as np
import pandas as pd

from app.infrastructure.logging.logger import get_logger

logger = get_logger(__name__)


# =========================================================================
# EXPORT ENGINE (Phase 2 - Advanced Export)
# =========================================================================


async def export_data(data: List[Dict[str, Any]], type: str = "generic") -> bytes:
    """
    Verilen veri listesini kurumsal formatta Excel'e çevirir (non-blocking).
    LojiNext Design System renkleri ve profesyonel formatlama uygulanır.
    """
    return await asyncio.to_thread(_export_data_sync, data, type)


def _export_data_sync(data: List[Dict[str, Any]], type: str = "generic") -> bytes:
    """
    Senkron dışa aktarma işlemi. export_data() tarafından asyncio.to_thread ile çağrılır.
    """
    if not data:
        # Boş veri için boş bir Excel döndür
        df = pd.DataFrame()
    else:
        # Strip timezone from datetime values and replace NaN/Inf floats
        # before handing the data to pandas/xlsxwriter.
        def _clean_value(v: Any) -> Any:
            from decimal import (
                Decimal as _Decimal,  # local import avoids Python 3.14 closure issue with to_thread
            )

            if isinstance(v, datetime) and v.tzinfo is not None:
                return v.replace(tzinfo=None)
            if isinstance(v, float) and (math.isnan(v) or math.isinf(v)):
                return None
            if isinstance(v, _Decimal):
                return float(v)
            if isinstance(v, dict):
                return str(v)
            return v

        data = [{k: _clean_value(val) for k, val in row.items()} for row in data]
        df = pd.DataFrame(data)

    # Tip bazlı kolon başlıkları ve sıralama (Opsiyonel)
    if type == "arac_listesi":
        # Map columns for Turkish report
        df = df.rename(
            columns={
                "plaka": "Plaka",
                "marka": "Marka",
                "model": "Model",
                "yil": "Model Yılı",
                "tank_kapasitesi": "Tank Kapasitesi (LT)",
                "bos_agirlik_kg": "Boş Ağırlık (KG)",
                "motor_verimliligi": "Motor Verimliliği",
            }
        )
    elif type == "dorse_listesi":
        df = df.rename(
            columns={
                "plaka": "Plaka",
                "marka": "Marka",
                "model": "Model",
                "yil": "Model Yılı",
                "dorse_tipi": "Dorse Tipi",
                "bos_agirlik_kg": "Boş Ağırlık (KG)",
                "lastik_sayisi": "Lastik Sayısı",
                "aktif": "Durum",
            }
        )
        if "Durum" in df.columns:
            df["Durum"] = df["Durum"].map({True: "Aktif", False: "Pasif"})
    elif type == "sefer_listesi":
        # Map columns for Turkish report
        df = df.rename(
            columns={
                "tarih": "Tarih",
                "saat": "Saat",
                "cikis_yeri": "Çıkış Yeri",
                "varis_yeri": "Varış Yeri",
                "mesafe_km": "Mesafe (KM)",
                "net_kg": "Yük (KG)",
                "plaka": "Plaka",
                "sofor": "Şoför",
                "durum": "Durum",
                "tahmini_yakit_lt": "Tahm. Yakıt (LT)",
            }
        )
        # Filter only useful columns if any exist
        cols = [
            "Tarih",
            "Saat",
            "Çıkış Yeri",
            "Varış Yeri",
            "Mesafe (KM)",
            "Yük (KG)",
            "Plaka",
            "Şoför",
            "Durum",
            "Tahm. Yakıt (LT)",
        ]
        df = df[[c for c in cols if c in df.columns]]
    elif type == "yakit_listesi":
        # Map columns for Turkish report
        df = df.rename(
            columns={
                "tarih": "Tarih",
                "plaka": "Plaka",
                "istasyon": "İstasyon",
                "fiyat_tl": "Birim Fiyat (TL)",
                "litre": "Litre",
                "km_sayac": "KM Sayacı",
                "fis_no": "Fiş No",
                "toplam_tutar": "Toplam Tutar (TL)",
                "depo_durumu": "Depo Durumu",
            }
        )
        cols = [
            "Tarih",
            "Plaka",
            "İstasyon",
            "Birim Fiyat (TL)",
            "Litre",
            "Toplam Tutar (TL)",
            "KM Sayacı",
            "Fiş No",
            "Depo Durumu",
        ]
        df = df[[c for c in cols if c in df.columns]]
    elif type == "lokasyon_listesi":
        df = df.rename(
            columns={
                "cikis_yeri": "Çıkış Yeri",
                "varis_yeri": "Varış Yeri",
                "mesafe_km": "Mesafe (KM)",
                "tahmini_sure_saat": "Tahmini Süre (Saat)",
                "zorluk": "Zorluk",
                "otoban_mesafe_km": "Otoban (KM)",
                "sehir_ici_mesafe_km": "Şehiriçi (KM)",
                "flat_distance_km": "Düz Yol (KM)",
                "notlar": "Notlar",
                "aktif": "Durum",
            }
        )
        cols = [
            "Çıkış Yeri",
            "Varış Yeri",
            "Mesafe (KM)",
            "Tahmini Süre (Saat)",
            "Zorluk",
            "Otoban (KM)",
            "Şehiriçi (KM)",
            "Düz Yol (KM)",
            "Durum",
            "Notlar",
        ]
        df = df[[c for c in cols if c in df.columns]]
        # Durum kolonunu True/False yerine Aktif/Pasif yapalım
        if "Durum" in df.columns:
            df["Durum"] = df["Durum"].map({True: "Aktif", False: "Pasif"})
    else:
        # Kolon isimlerini baş harfi büyük yap ve alt çizgileri boşluğa çevir
        df.columns = [str(c).replace("_", " ").title() for c in df.columns]

    output = io.BytesIO()
    # strings_to_formulas=False: prevents CSV/Excel formula injection — a cell
    # value starting with =/+/-/@ (e.g. a malicious "notlar" field imported
    # from a prior Excel upload) is written as literal text instead of being
    # auto-converted into an executable formula when the export is reopened.
    writer = pd.ExcelWriter(
        output,
        engine="xlsxwriter",
        engine_kwargs={"options": {"strings_to_formulas": False}},
    )
    sheet_name = "Rapor"

    df.to_excel(
        writer, index=False, sheet_name=sheet_name, startrow=1
    )  # Başlık için 1 satır boşluk

    workbook = writer.book
    worksheet = writer.sheets[sheet_name]

    # -------------------------------------------------------------------------
    # LOJINEXT STYLING
    # -------------------------------------------------------------------------

    # Renk Paleti
    PRIMARY_COLOR = "#3B82F6"  # Blue 500
    HEADER_BG = "#1E293B"  # Slate 800
    HEADER_TEXT = "#FFFFFF"  # White
    BORDER_COLOR = "#CBD5E1"  # Slate 300

    # Formatlar
    header_format = workbook.add_format(
        {
            "bold": True,
            "text_wrap": False,
            "valign": "vcenter",
            "fg_color": HEADER_BG,
            "font_color": HEADER_TEXT,
            "border": 1,
            "border_color": BORDER_COLOR,
            "font_size": 11,
            "font_name": "Calibri",
        }
    )

    cell_format = workbook.add_format(
        {
            "border": 1,
            "border_color": BORDER_COLOR,
            "valign": "vcenter",
            "font_size": 10,
            "font_name": "Calibri",
        }
    )

    date_format = workbook.add_format(
        {
            "border": 1,
            "border_color": BORDER_COLOR,
            "num_format": "dd.mm.yyyy",
            "valign": "vcenter",
            "font_size": 10,
            "font_name": "Calibri",
        }
    )

    number_format = workbook.add_format(
        {
            "border": 1,
            "border_color": BORDER_COLOR,
            "num_format": "#,##0.00",
            "valign": "vcenter",
            "font_size": 10,
            "font_name": "Calibri",
        }
    )

    title_format = workbook.add_format(
        {
            "bold": True,
            "font_size": 14,
            "font_name": "Calibri",
            "font_color": PRIMARY_COLOR,
        }
    )

    # -------------------------------------------------------------------------
    # UYGULAMA
    # -------------------------------------------------------------------------

    # Rapor Başlığı
    title = f"{type.upper()} RAPORU - {datetime.now(timezone.utc).strftime('%d.%m.%Y %H:%M')}"
    worksheet.write(0, 0, title, title_format)

    # Kolon Başlıklarını Elle Yaz (Pandas'ınkini eziyoruz stil için)
    for col_num, value in enumerate(df.columns.values):
        worksheet.write(1, col_num, value, header_format)

    # Veri Satırları
    if not df.empty:
        for row_num, row_data in enumerate(df.values):
            for col_num, cell_value in enumerate(row_data):
                # Format belirle
                fmt = cell_format

                if isinstance(cell_value, np.datetime64):
                    # pandas df.values, bazı numpy versiyonlarında tz-aware
                    # datetime'ı numpy.datetime64'e çevirir → xlsxwriter yazamaz.
                    # tz-naive python datetime'a normalize et.
                    cell_value = pd.Timestamp(cell_value).to_pydatetime()
                    fmt = date_format
                elif isinstance(cell_value, (date, datetime, pd.Timestamp)):
                    # Strip timezone so xlsxwriter can serialise the value
                    if (
                        isinstance(cell_value, datetime)
                        and cell_value.tzinfo is not None
                    ):
                        cell_value = cell_value.replace(tzinfo=None)
                    elif (
                        isinstance(cell_value, pd.Timestamp)
                        and cell_value.tzinfo is not None
                    ):
                        cell_value = cell_value.tz_localize(None).to_pydatetime()
                    fmt = date_format
                elif isinstance(cell_value, float):
                    if math.isnan(cell_value) or math.isinf(cell_value):
                        cell_value = None
                        fmt = cell_format
                    else:
                        fmt = number_format
                elif isinstance(cell_value, int):
                    fmt = number_format
                elif isinstance(cell_value, (dict, list)):
                    import json as _json
                    from decimal import Decimal

                    cell_value = _json.dumps(
                        cell_value,
                        ensure_ascii=False,
                        default=lambda o: (
                            float(o) if isinstance(o, Decimal) else str(o)
                        ),
                    )
                    fmt = cell_format

                if isinstance(cell_value, str):
                    worksheet.write_string(row_num + 2, col_num, cell_value, fmt)
                else:
                    worksheet.write(row_num + 2, col_num, cell_value, fmt)

        # Sütun Genişliklerini Otomatik Ayarla
        for i, col in enumerate(df.columns):
            # Başlık uzunluğu
            max_len = len(str(col)) + 4

            # Veri uzunluğu (ilk 50 satırı kontrol et performans için)
            column_data = df.iloc[:50, i]
            for val in column_data:
                if val is not None:
                    max_len = max(max_len, len(str(val)))

            # Limitler
            max_len = min(max_len, 50)  # Max 50 char
            worksheet.set_column(i, i, max_len)

    # Auto-Filter Ekle
    if not df.empty:
        (max_row, max_col) = df.shape
        worksheet.autofilter(1, 0, max_row + 1, max_col - 1)

    writer.close()
    return output.getvalue()


# =========================================================================
# TEMPLATE GENERATOR
# =========================================================================


async def generate_template(type: str) -> bytes:
    """Şablon Excel dosyası oluşturur (non-blocking)."""
    return await asyncio.to_thread(_generate_template_sync, type)


def _generate_template_sync(type: str) -> bytes:
    """
    Senkron şablon oluşturma işlemi. generate_template() tarafından asyncio.to_thread ile çağrılır.
    """
    output = io.BytesIO()
    # strings_to_formulas=False: prevents CSV/Excel formula injection — a cell
    # value starting with =/+/-/@ (e.g. a malicious "notlar" field imported
    # from a prior Excel upload) is written as literal text instead of being
    # auto-converted into an executable formula when the export is reopened.
    writer = pd.ExcelWriter(
        output,
        engine="xlsxwriter",
        engine_kwargs={"options": {"strings_to_formulas": False}},
    )

    if type == "sefer":
        columns = [
            "Tarih",
            "Saat",
            "Çıkış Yeri",
            "Varış Yeri",
            "Mesafe (KM)",
            "Yük (KG)",
            "Plaka",
            "Dorse Plakası",
            "Şoför Adı",
            "Durum",
            # GPS ile gelen rotalar için (opsiyonel ama ML için faydalı)
            "Tırmanış (m)",
            "İniş (m)",
            "Düz Mesafe (KM)",
            # Geçmiş sefer numarası referansı (opsiyonel)
            "Sefer No",
            # Serbest metin not
            "Notlar",
        ]
        data = [
            [
                "2026-01-01",
                "09:00",
                "Istanbul",
                "Ankara",
                450,
                15000,
                "34ABC01",
                "34XYZ99",
                "Ahmet Yilmaz",
                "Tamamlandı",
                320,
                180,
                300,
                "SEF-2026-001",
                "Soğuk zincir yük",
            ],
            [
                "YYYY-MM-DD (zorunlu)",
                "HH:MM (opsiyonel)",
                "Çıkış şehri/şubesi (zorunlu)",
                "Varış şehri/şubesi (zorunlu)",
                "Number (zorunlu, >0)",
                "Number (kg)",
                "Sistemdeki plaka birebir (zorunlu)",
                "Dorse plaka (varsa)",
                "Ad Soyad birebir (zorunlu)",
                "Tamamlandı/Planlandı/İptal/Yolda/Atandı",
                "Number (m, GPS varsa)",
                "Number (m, GPS varsa)",
                "Number (km, GPS varsa)",
                "Text (varsa)",
                "Text (varsa)",
            ],
        ]
    elif type == "yakit":
        columns = [
            "Tarih",
            "Plaka",
            "İstasyon",
            "Litre",
            "Fiyat",
            "Toplam Tutar",
            "KM Sayacı",
            "Fiş No",
            "Depo Durumu",
        ]
        data = [
            [
                "2026-02-10",
                "34 ABC 123",
                "Shell Maslak",
                500,
                42.50,
                21250,
                120500,
                "FIS-001",
                "Doldu",
            ],
            [
                "YYYY-MM-DD (zorunlu)",
                "Birebir araç plakası (zorunlu)",
                "Text (varsa, default 'Bilinmiyor')",
                "Number (L, zorunlu > 0)",
                "Number (₺/L, zorunlu > 0)",
                "Number (₺) — boş bırakırsan litre×fiyat'tan hesaplanır",
                "Number (km, monoton artan) — periyot hesabı için kritik",
                "Text (fiş referansı)",
                "Doldu/Dolu/Kısmi/Bilinmiyor",
            ],
        ]
    elif type == "arac":
        columns = [
            "Plaka",
            "Marka",
            "Model",
            "Yil",
            "Tank_Kapasitesi",
            "Bos_Agirlik_KG",
            "Maks_Yuk_Kapasitesi_KG",
            "Dingil_Sayisi",
            "Motor_Verimliligi",
            "Hava_Direnc_Katsayisi",
            "On_Kesit_Alani_m2",
            "Lastik_Direnc_Katsayisi",
            "Hedef_Tuketim",
            "Yakit_Tipi",
            "Muayene_Tarihi",
            "Notlar",
        ]
        data = [
            [
                "34 ABC 001",
                "Mercedes",
                "Actros 2645",
                2022,
                600,  # tank L
                8200,  # bos kg
                26000,  # maks yuk kg
                2,  # dingil
                0.38,  # motor verim
                0.7,  # Cx
                8.5,  # frontal area m2
                0.007,  # lastik direnç
                32.0,  # hedef L/100km
                "DIZEL",
                "2027-06-15",
                "Soğutmalı tertibatlı",
            ],
            [
                "Plaka (zorunlu, birebir Excel'de yazılır)",
                "Text",
                "Text",
                "Yıl (1990-2100)",
                "Number (L, default 600)",
                "Number (kg)",
                "Number (kg)",
                "Number (1-8)",
                "Float 0..1 (default 0.38)",
                "Float (default 0.7)",
                "Float (m², default 8.5)",
                "Float (default 0.007)",
                "Float (L/100km, default 32)",
                "DIZEL/BENZIN/LPG/ELEKTRIK",
                "YYYY-MM-DD veya boş",
                "Serbest text",
            ],
        ]
    elif type == "sofor":
        columns = [
            "Ad_Soyad",
            "Telefon",
            "Ise_Baslama",
            "Ehliyet_Sinifi",
            "Telegram_ID",
            "Notlar",
        ]
        data = [
            [
                "Ahmet Yılmaz",
                "0555 123 45 67",
                "2023-01-01",
                "CE",
                "",
                "İstanbul-Ankara hattı düzenli",
            ],
            [
                "Ad Soyad (zorunlu, sefer Excel'inde birebir yazılır)",
                "Text (telefon)",
                "YYYY-MM-DD",
                "B/C/D/E/CE",
                "Telegram chat ID (push bildirim için, opsiyonel)",
                "Serbest text",
            ],
        ]
    elif type == "guzergah":
        columns = [
            "Çıkış Yeri",
            "Varış Yeri",
            "Çıkış Lat",
            "Çıkış Lon",
            "Varış Lat",
            "Varış Lon",
            "Mesafe (KM)",
            "Tahmini Süre (saat)",
            "Tırmanış (m)",
            "İniş (m)",
            "Düz Mesafe (KM)",
            "Otoban Mesafe (KM)",
            "Şehir İçi Mesafe (KM)",
            "Tahmini Yakıt (L)",
            "Zorluk",
            "Notlar",
        ]
        data = [
            [
                "İstanbul Kadıköy",
                "Ankara Sincan",
                40.9924,
                29.0271,  # cikis_lat, cikis_lon
                39.9709,
                32.5816,  # varis_lat, varis_lon
                450,  # mesafe
                5.5,  # tahmini_sure
                320,
                180,  # ascent, descent
                420,
                380,
                70,  # flat, otoban, sehir_ici
                145,  # tahmini_yakit
                "Normal",
                "E-90 üzerinden standart rota",
            ],
            [
                "Text (zorunlu)",
                "Text (zorunlu)",
                "Decimal (-90..+90)",
                "Decimal (-180..+180)",
                "Decimal",
                "Decimal",
                "Number > 0 (zorunlu)",
                "Number (saat)",
                "Number (m, opsiyonel — GPS yoksa 0)",
                "Number (m, opsiyonel — GPS yoksa 0)",
                "Number",
                "Number",
                "Number",
                "Number (L)",
                "Kolay/Normal/Zor",
                "Serbest text",
            ],
        ]
    elif type == "dorse":
        columns = [
            "Plaka",
            "Marka",
            "Model",
            "Yil",
            "Dorse_Tipi",
            "Bos_Agirlik_KG",
            "Lastik_Sayisi",
            "Rolling_Resistance",
            "Drag_Coefficient",
        ]
        data = [["34XYZ99", "Tirsan", "Frigo", 2023, "Tenteli", 7200, 6, 0.006, 0.75]]
    else:
        return b""

    df = pd.DataFrame(data, columns=columns)
    df.to_excel(writer, index=False, sheet_name="Sablon")

    # Sütun genişliklerini ayarla
    worksheet = writer.sheets["Sablon"]
    for i, col in enumerate(columns):
        worksheet.set_column(i, i, 20)

    writer.close()
    return output.getvalue()
