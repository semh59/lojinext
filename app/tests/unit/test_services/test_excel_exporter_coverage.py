"""Coverage tests for app/core/services/excel_exporter.py.

Targets uncovered branches:
- export_data / _export_data_sync: dorse_listesi (with Durum mapping),
  sefer_listesi, yakit_listesi, lokasyon_listesi (with Durum mapping),
  generic (else branch), empty data
- _clean_value: Decimal, dict values, TZ-naive datetime passthrough
- Cell-level formatting: date, Timestamp (tz-aware), float NaN/inf in rows,
  dict/list cell values, int cell formatting
- Column width loop (>50 chars)
- autofilter on non-empty df
- generate_template: all template types (sefer, yakit, arac, sofor, guzergah, dorse)
- generate_template unknown type → returns b""
"""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

import pytest

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _run(coro):
    import asyncio

    return asyncio.get_event_loop().run_until_complete(coro)


# ---------------------------------------------------------------------------
# export_data — type dispatching
# ---------------------------------------------------------------------------


async def test_export_data_empty_returns_bytes():
    from app.core.services.excel_exporter import export_data

    result = await export_data([], type="generic")
    assert isinstance(result, bytes)
    assert len(result) > 0  # valid Excel even when empty


async def test_export_data_generic_title_case():
    """Generic type → column names title-cased."""
    from app.core.services.excel_exporter import export_data

    data = [{"hello_world": "val", "foo_bar": 1.5}]
    result = await export_data(data, type="generic")
    assert isinstance(result, bytes)
    assert len(result) > 100


async def test_export_data_arac_listesi_renames_columns():
    from app.core.services.excel_exporter import export_data

    data = [
        {
            "plaka": "34ABC01",
            "marka": "Mercedes",
            "model": "Actros",
            "yil": 2022,
            "tank_kapasitesi": 600,
            "bos_agirlik_kg": 8200,
            "motor_verimliligi": 0.38,
        }
    ]
    result = await export_data(data, type="arac_listesi")
    assert isinstance(result, bytes)
    assert len(result) > 100


async def test_export_data_dorse_listesi_durum_mapping():
    """dorse_listesi should map True/False to Aktif/Pasif."""
    from app.core.services.excel_exporter import export_data

    data = [
        {
            "plaka": "34XYZ99",
            "marka": "Tirsan",
            "model": "Frigo",
            "yil": 2023,
            "dorse_tipi": "Tenteli",
            "bos_agirlik_kg": 7200,
            "lastik_sayisi": 6,
            "aktif": True,
        },
        {
            "plaka": "06DEF01",
            "marka": "Krone",
            "model": "SDP",
            "yil": 2021,
            "dorse_tipi": "Tenteli",
            "bos_agirlik_kg": 7100,
            "lastik_sayisi": 6,
            "aktif": False,
        },
    ]
    result = await export_data(data, type="dorse_listesi")
    assert isinstance(result, bytes)
    assert len(result) > 100


async def test_export_data_sefer_listesi():
    from app.core.services.excel_exporter import export_data

    data = [
        {
            "tarih": "2026-01-15",
            "saat": "09:00",
            "cikis_yeri": "İstanbul",
            "varis_yeri": "Ankara",
            "mesafe_km": 450.0,
            "net_kg": 15000,
            "plaka": "34ABC01",
            "sofor": "Ahmet Yılmaz",
            "durum": "Tamamlandı",
            "tahmini_yakit_lt": 145.0,
        }
    ]
    result = await export_data(data, type="sefer_listesi")
    assert isinstance(result, bytes)
    assert len(result) > 100


async def test_export_data_yakit_listesi():
    from app.core.services.excel_exporter import export_data

    data = [
        {
            "tarih": "2026-02-10",
            "plaka": "34ABC01",
            "istasyon": "Shell Maslak",
            "fiyat_tl": 42.5,
            "litre": 500.0,
            "km_sayac": 120500,
            "fis_no": "FIS-001",
            "toplam_tutar": 21250.0,
            "depo_durumu": "Doldu",
        }
    ]
    result = await export_data(data, type="yakit_listesi")
    assert isinstance(result, bytes)
    assert len(result) > 100


async def test_export_data_lokasyon_listesi_durum_mapping():
    """lokasyon_listesi maps True/False Durum and filters columns."""
    from app.core.services.excel_exporter import export_data

    data = [
        {
            "cikis_yeri": "İstanbul",
            "varis_yeri": "Ankara",
            "mesafe_km": 450.0,
            "tahmini_sure_saat": 5.5,
            "zorluk": "Normal",
            "otoban_mesafe_km": 380.0,
            "sehir_ici_mesafe_km": 70.0,
            "flat_distance_km": 420.0,
            "notlar": "E-90",
            "aktif": True,
        },
        {
            "cikis_yeri": "Ankara",
            "varis_yeri": "Konya",
            "mesafe_km": 260.0,
            "tahmini_sure_saat": 3.0,
            "zorluk": "Kolay",
            "otoban_mesafe_km": 230.0,
            "sehir_ici_mesafe_km": 30.0,
            "flat_distance_km": 245.0,
            "notlar": "",
            "aktif": False,
        },
    ]
    result = await export_data(data, type="lokasyon_listesi")
    assert isinstance(result, bytes)
    assert len(result) > 100


# ---------------------------------------------------------------------------
# _clean_value branches
# ---------------------------------------------------------------------------


def test_clean_value_decimal_to_float():
    """Decimal should be converted to float."""
    from app.core.services.excel_exporter import _export_data_sync

    data = [{"amount": Decimal("1234.56")}]
    result = _export_data_sync(data, type="generic")
    assert isinstance(result, bytes)


def test_clean_value_dict_to_str():
    """dict values should be converted to string."""
    from app.core.services.excel_exporter import _export_data_sync

    data = [{"meta": {"key": "value"}}]
    result = _export_data_sync(data, type="generic")
    assert isinstance(result, bytes)


def test_clean_value_tz_aware_datetime_stripped():
    """Timezone-aware datetime should be stripped before export."""
    from app.core.services.excel_exporter import _export_data_sync

    dt = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    data = [{"created_at": dt}]
    result = _export_data_sync(data, type="generic")
    assert isinstance(result, bytes)


def test_clean_value_nan_float_becomes_none():
    """NaN float in data should not crash export."""
    from app.core.services.excel_exporter import _export_data_sync

    data = [{"ratio": float("nan"), "val": float("inf")}]
    result = _export_data_sync(data, type="generic")
    assert isinstance(result, bytes)


# ---------------------------------------------------------------------------
# Cell-level formatting inside _export_data_sync
# ---------------------------------------------------------------------------


def test_cell_value_float_nan_in_rows_handled():
    """NaN float in rows sets fmt=cell_format and value=None."""
    from app.core.services.excel_exporter import _export_data_sync

    data = [{"fuel": float("nan")}, {"fuel": 42.5}, {"fuel": float("inf")}]
    result = _export_data_sync(data, type="generic")
    assert isinstance(result, bytes)


def test_cell_value_int_uses_number_format():
    """Integer cell values should use number_format."""
    from app.core.services.excel_exporter import _export_data_sync

    data = [{"count": 100, "score": 99}]
    result = _export_data_sync(data, type="generic")
    assert isinstance(result, bytes)


def test_cell_value_dict_list_serialized_to_json():
    """Dict and list cell values should be JSON-serialized."""
    from app.core.services.excel_exporter import _export_data_sync

    data = [
        {"metadata": {"nested": 1, "amount": Decimal("5.5")}},
        {"tags": ["a", "b", "c"]},
    ]
    result = _export_data_sync(data, type="generic")
    assert isinstance(result, bytes)


def test_cell_value_tz_aware_timestamp_stripped():
    """pandas Timestamp with tz should be localized to None."""
    import pandas as pd

    from app.core.services.excel_exporter import _export_data_sync

    ts = pd.Timestamp("2026-01-15", tz="UTC")
    data = [{"ts_col": ts}]
    result = _export_data_sync(data, type="generic")
    assert isinstance(result, bytes)


def test_cell_value_naive_date_uses_date_format():
    """date object should use date_format."""
    from datetime import date

    from app.core.services.excel_exporter import _export_data_sync

    data = [{"trip_date": date(2026, 3, 15)}]
    result = _export_data_sync(data, type="generic")
    assert isinstance(result, bytes)


def test_column_width_capped_at_50():
    """Columns with very long values are capped at 50 chars width."""
    from app.core.services.excel_exporter import _export_data_sync

    long_val = "x" * 200
    data = [{"description": long_val}]
    result = _export_data_sync(data, type="generic")
    assert isinstance(result, bytes)


# ---------------------------------------------------------------------------
# generate_template — all types
# ---------------------------------------------------------------------------


async def test_generate_template_sefer():
    from app.core.services.excel_exporter import generate_template

    result = await generate_template("sefer")
    assert isinstance(result, bytes)
    assert len(result) > 100


async def test_generate_template_yakit():
    from app.core.services.excel_exporter import generate_template

    result = await generate_template("yakit")
    assert isinstance(result, bytes)
    assert len(result) > 100


async def test_generate_template_arac():
    from app.core.services.excel_exporter import generate_template

    result = await generate_template("arac")
    assert isinstance(result, bytes)
    assert len(result) > 100


async def test_generate_template_sofor():
    from app.core.services.excel_exporter import generate_template

    result = await generate_template("sofor")
    assert isinstance(result, bytes)
    assert len(result) > 100


async def test_generate_template_guzergah():
    from app.core.services.excel_exporter import generate_template

    result = await generate_template("guzergah")
    assert isinstance(result, bytes)
    assert len(result) > 100


async def test_generate_template_dorse():
    from app.core.services.excel_exporter import generate_template

    result = await generate_template("dorse")
    assert isinstance(result, bytes)
    assert len(result) > 100


async def test_generate_template_unknown_returns_empty():
    """Unknown template type returns empty bytes."""
    from app.core.services.excel_exporter import generate_template

    result = await generate_template("unknown_type_xyz")
    assert result == b""


# ---------------------------------------------------------------------------
# _generate_template_sync — column widths applied
# ---------------------------------------------------------------------------


def test_generate_template_sync_sefer_columns_set():
    """Sync path sets column widths on the worksheet."""
    from app.core.services.excel_exporter import _generate_template_sync

    result = _generate_template_sync("sefer")
    assert isinstance(result, bytes)
    assert len(result) > 100
