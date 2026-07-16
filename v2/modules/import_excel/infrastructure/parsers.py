"""
Excel parse işlemleri — yalnızca okuma, hiç yazma yok.
"""

import asyncio
import io
from typing import Any, Dict, List

import pandas as pd

from app.core.exceptions import ExcelExportError
from app.infrastructure.logging.logger import get_logger
from v2.modules.import_excel.domain.field_validators import (
    parse_date_flexible as _parse_date_flexible,
)
from v2.modules.import_excel.infrastructure.column_mapper import SafeColumnMapper

logger = get_logger(__name__)


# 2026-07-02 prod-grade denetimi Tier B madde 15: Excel import'ta satır
# sayısı üst sınırı yoktu — `.xlsx` sıkıştırılmış bir zip arşivi olduğu
# için 10MB'lık HTTP boyut sınırını (endpoint'lerdeki `_MAX_UPLOAD_BYTES`)
# geçen küçük bir dosya, açıldığında yüz binlerce/milyonlarca tekrarlı
# satıra "şişebilir" (zip-bomb benzeri amplifikasyon) — pandas TÜMÜNÜ
# belleğe okur, sonra her satır Python dict'ine çevrilir. Bu, HTTP boyut
# sınırından TAMAMEN bağımsız bir DoS riski.
MAX_EXCEL_ROWS = 20_000


def _enforce_row_limit(df: pd.DataFrame, source: str) -> None:
    if len(df) > MAX_EXCEL_ROWS:
        raise ExcelExportError(
            f"{source}: satır sayısı ({len(df)}) izin verilen üst sınırı "
            f"({MAX_EXCEL_ROWS}) aşıyor. Dosyayı bölüp tekrar deneyin."
        )


_FORMULA_PREFIX_CHARS = ("=", "+", "-", "@")


def _sanitize_formula_prefix(val: Any) -> Any:
    """Excel/CSV formula injection koruması.

    Bir hücre metni '=', '+', '-' veya '@' ile başlıyorsa, bu değer daha sonra
    bir export'ta (ör. excel_exporter.py) veya kullanıcının kendi Excel'inde
    çalıştırılabilir bir formüle dönüşebilir (ör. import edilen bir "notlar"
    alanına "=HYPERLINK(...)" girilip sonra export edilip tekrar açılması).
    Lider karaktere bir apostrof (') ekleyerek Excel'in bunu her zaman düz
    metin olarak yorumlamasını sağlarız — apostrof Excel'de görünmez
    (force-text işareti), görünen değer değişmez.
    """
    if not isinstance(val, str) or not val:
        return val
    if val.startswith(_FORMULA_PREFIX_CHARS):
        return f"'{val}"
    return val


def _parse_float_tr(val: Any) -> float:
    """Parse numeric string, handling Turkish/German decimal comma (e.g. '43,5' → 43.5).

    Determines decimal separator by which appears last: if comma is last it's the
    decimal (Turkish/German); if dot is last it's the decimal (English).
    """
    if isinstance(val, str):
        s = val.strip()
        last_comma = s.rfind(",")
        last_dot = s.rfind(".")
        if last_comma > last_dot:
            s = s.replace(".", "").replace(",", ".")
        elif last_dot > last_comma:
            s = s.replace(",", "")
        return float(s)
    return float(val)


async def parse_sefer_excel(content: bytes) -> List[Dict[str, Any]]:
    """Seferler Excel dosyasını (bytes) parse et (Async & Non-blocking)."""
    return await asyncio.to_thread(_parse_sefer_excel_sync, content)


def _parse_sefer_excel_sync(content: bytes) -> List[Dict[str, Any]]:
    try:
        df = pd.read_excel(io.BytesIO(content), engine="openpyxl")
        _enforce_row_limit(df, "Sefer Excel")

        # Dynamic Column Mapping
        column_map = SafeColumnMapper.map_columns(df.columns.tolist())
        logger.info(f"Sefer Excel Map: {column_map}")

        result = []
        for idx, (_, row) in enumerate(df.iterrows(), start=2):
            item = {}
            for excel_col, model_field in column_map.items():
                val = row[excel_col]
                if model_field == "tarih":
                    val = _parse_date_flexible(val)
                if pd.isna(val):
                    val = None

                # FAZ 2.2: Güvenli tip dönüşümü (Safe Cast)
                if model_field == "mesafe_km" and val:
                    try:
                        val = _parse_float_tr(val)
                    except (ValueError, TypeError):
                        val = 0.0
                if model_field == "net_kg" and val:
                    try:
                        val = _parse_float_tr(val)
                    except (ValueError, TypeError):
                        val = 0.0

                item[model_field] = val

            plaka_val = item.get("plaka")
            if not plaka_val:
                logger.warning("Sefer Excel satır %d: plaka eksik, atlandı", idx)
                continue
            item["plaka"] = str(plaka_val).upper().replace(" ", "")
            if not item.get("tarih"):
                logger.warning(
                    "Sefer Excel satır %d (plaka=%s): tarih eksik, atlandı",
                    idx,
                    item["plaka"],
                )
                continue
            result.append(item)
        return result
    except (ValueError, OSError, KeyError, AttributeError) as e:
        logger.error(f"Sync sefer excel error: {e}")
        raise ExcelExportError(f"Excel okuma hatası: {e!s}") from e


async def parse_yakit_excel(content: bytes) -> List[Dict[str, Any]]:
    """Yakıt Excel dosyasını (bytes) parse et (Async & Non-blocking)."""
    return await asyncio.to_thread(_parse_yakit_excel_sync, content)


def _parse_yakit_excel_sync(content: bytes) -> List[Dict[str, Any]]:
    try:
        df = pd.read_excel(io.BytesIO(content), engine="openpyxl")
        _enforce_row_limit(df, "Yakıt Excel")

        column_map = SafeColumnMapper.map_columns(df.columns.tolist())
        logger.info(f"Yakit Excel Map: {column_map}")

        result = []
        for idx, (_, row) in enumerate(df.iterrows(), start=2):
            item = {}
            for excel_col, model_field in column_map.items():
                val = row[excel_col]
                if model_field == "tarih":
                    val = _parse_date_flexible(val)
                if pd.isna(val):
                    val = None

                # FAZ 2.2: Güvenli tip dönüşümü (Safe Cast)
                # YakitCreate Pydantic schema Decimal max 2 ondalık dayatır;
                # POS/Excel'den 3+ ondalık gelirse validation reject. Parser
                # round'lar — kullanıcıya saydam (43.4567 → 43.46).
                try:
                    if model_field == "litre" and val:
                        val = round(_parse_float_tr(val), 2)
                    if model_field == "fiyat_tl" and val:
                        val = round(_parse_float_tr(val), 2)
                    if model_field == "toplam_tutar" and val:
                        val = round(_parse_float_tr(val), 2)
                    if model_field == "km_sayac" and val:
                        val = int(_parse_float_tr(val))
                except (ValueError, TypeError):
                    val = 0

                item[model_field] = val

            if not item.get("plaka"):
                logger.warning("Yakıt Excel satır %d: plaka eksik, atlandı", idx)
                continue
            if not item.get("tarih"):
                logger.warning(
                    "Yakıt Excel satır %d (plaka=%s): tarih eksik, atlandı",
                    idx,
                    item.get("plaka"),
                )
                continue
            result.append(item)
        return result
    except (ValueError, OSError, KeyError, AttributeError) as e:
        logger.error(f"Sync yakit excel error: {e}")
        raise ExcelExportError(f"Excel okuma hatası: {e!s}") from e


async def parse_route_excel(content: bytes) -> List[Dict[str, Any]]:
    """Güzergahlar Excel dosyasını (bytes) parse et (Async & Non-blocking)."""
    return await asyncio.to_thread(_parse_route_excel_sync, content)


def _parse_route_excel_sync(content: bytes) -> List[Dict[str, Any]]:
    try:
        df = pd.read_excel(io.BytesIO(content), engine="openpyxl")
        _enforce_row_limit(df, "Güzergah Excel")
        column_map = SafeColumnMapper.map_columns(df.columns.tolist())
        logger.info(f"Route Excel Map: {column_map}")

        result = []
        for idx, (_, row) in enumerate(df.iterrows(), start=2):
            item = {}
            for excel_col, model_field in column_map.items():
                val = row[excel_col]
                if pd.isna(val):
                    val = None

                if model_field == "mesafe_km" and val:
                    try:
                        val = float(val)
                    except (ValueError, TypeError):
                        val = 0.0

                item[model_field] = val

            if not item.get("cikis_yeri"):
                logger.warning(
                    "Güzergah Excel satır %d: çıkış yeri eksik, atlandı", idx
                )
                continue
            if not item.get("varis_yeri"):
                logger.warning(
                    "Güzergah Excel satır %d (cikis=%s): varış yeri eksik, atlandı",
                    idx,
                    item.get("cikis_yeri"),
                )
                continue
            result.append(item)
        return result
    except (ValueError, OSError, KeyError, AttributeError) as e:
        logger.error(f"Sync route excel error: {e}")
        raise ExcelExportError(f"Excel okuma hatası: {e!s}") from e


async def parse_vehicle_excel(content: bytes) -> List[Dict[str, Any]]:
    """Araç Excel dosyasını (bytes) parse et."""
    return await asyncio.to_thread(_parse_vehicle_excel_sync, content)


def _parse_vehicle_excel_sync(content: bytes) -> List[Dict[str, Any]]:
    try:
        df = pd.read_excel(io.BytesIO(content), engine="openpyxl")
        _enforce_row_limit(df, "Vehicle Excel")
        column_map = SafeColumnMapper.map_columns(df.columns.tolist())
        logger.info(f"Vehicle Excel Map: {column_map}")

        result = []
        for index, row in df.iterrows():
            try:

                def safe_float(v, default=0.0):
                    try:
                        return float(v) if v is not None else default
                    except (ValueError, TypeError):
                        return default

                def safe_int(v, default=0):
                    try:
                        return int(float(v)) if v is not None else default
                    except (ValueError, TypeError):
                        return default

                item = {}
                for excel_col, model_field in column_map.items():
                    val = row[excel_col]
                    if model_field == "plaka":
                        val = str(val).upper().replace(" ", "") if val else None
                    elif model_field in ["marka", "model", "notlar"]:
                        val = _sanitize_formula_prefix(str(val)) if val else None
                    elif model_field in ["yil", "tank_kapasitesi"]:
                        val = safe_int(val, None if model_field == "yil" else 600)
                    elif model_field in [
                        "bos_agirlik_kg",
                        "motor_verimliligi",
                        "hedef_tuketim",
                    ]:
                        val = safe_float(val, None)

                    item[model_field] = val

                if not item.get("plaka"):
                    logger.warning(
                        "Vehicle Excel satır %d: plaka eksik, atlandı", index + 2
                    )
                    continue
                if not item.get("marka"):
                    logger.warning(
                        "Vehicle Excel satır %d (plaka=%s): marka eksik, atlandı",
                        index + 2,
                        item.get("plaka"),
                    )
                    continue
                result.append(item)
            except (KeyError, ValueError, TypeError, AttributeError) as row_err:
                logger.warning("Vehicle Excel satır %d hatası: %s", index + 2, row_err)
                continue
        return result
    except (ValueError, OSError, KeyError, AttributeError) as e:
        logger.error(f"Sync vehicle excel error: {e}")
        raise ExcelExportError(f"Excel okuma hatası: {e!s}") from e


async def parse_driver_excel(content: bytes) -> List[Dict[str, Any]]:
    """Şoför Excel dosyasını (bytes) parse et."""
    return await asyncio.to_thread(_parse_driver_excel_sync, content)


def _parse_driver_excel_sync(content: bytes) -> List[Dict[str, Any]]:
    try:
        df = pd.read_excel(io.BytesIO(content), engine="openpyxl")
        _enforce_row_limit(df, "Driver Excel")
        # prefer=["ad_soyad"]: "şoför adı"/"sofor adi" alias'ı sofor_adi ile
        # de çakışıyor (sefer Excel'inin sürücü-arama alanı) — sürücü
        # Excel'inde bu başlık her zaman ad_soyad'a gitmeli, aksi halde tüm
        # satırlar "ad_soyad eksik" ile sessizce atlanır (2026-07-16 bulgusu).
        column_map = SafeColumnMapper.map_columns(
            df.columns.tolist(), prefer=["ad_soyad"]
        )
        logger.info(f"Driver Excel Map: {column_map}")

        result = []
        for index, row in df.iterrows():
            try:
                item = {}
                for excel_col, model_field in column_map.items():
                    val = row[excel_col]
                    if model_field == "ad_soyad":
                        val = (
                            _sanitize_formula_prefix(str(val).strip().title())
                            if val
                            else None
                        )
                    elif model_field == "ise_baslama":
                        val = _parse_date_flexible(val)
                    elif model_field == "notlar":
                        val = _sanitize_formula_prefix(str(val)) if val else None
                    elif model_field in ["telefon", "ehliyet_sinifi"]:
                        # telefon/ehliyet_sinifi sanitize edilmez: Türk telefon
                        # numaraları rutin olarak "+90..." ile başlar —
                        # formula-prefix sanitizasyonu meşru veriyi
                        # "'+90..." olarak bozardı (2026-07-01 bağımsız
                        # review bulgusu). Bu alanlar export'ta zaten
                        # strings_to_formulas=False ile korunuyor.
                        val = str(val) if val else None

                    item[model_field] = val

                if not item.get("ad_soyad"):
                    logger.warning(
                        "Driver Excel satır %d: ad_soyad eksik, atlandı", index + 2
                    )
                    continue
                result.append(item)
            except (KeyError, ValueError, TypeError, AttributeError) as row_err:
                logger.warning("Driver Excel satır %d hatası: %s", index + 2, row_err)
                continue
        return result
    except (ValueError, OSError, KeyError, AttributeError) as e:
        logger.error(f"Sync driver excel error: {e}")
        raise ExcelExportError(f"Excel okuma hatası: {e!s}") from e


async def parse_dorse_excel(content: bytes) -> List[Dict[str, Any]]:
    """Dorse Excel dosyasını (bytes) parse et."""
    return await asyncio.to_thread(_parse_dorse_excel_sync, content)


def _parse_dorse_excel_sync(content: bytes) -> List[Dict[str, Any]]:
    try:
        df = pd.read_excel(io.BytesIO(content), engine="openpyxl")
        _enforce_row_limit(df, "Dorse Excel")
        column_map = SafeColumnMapper.map_columns(df.columns.tolist())
        logger.info(f"Dorse Excel Map: {column_map}")

        result = []
        for index, row in df.iterrows():
            try:

                def safe_float(v, default=0.0):
                    try:
                        return float(v) if v is not None else default
                    except (ValueError, TypeError):
                        return default

                def safe_int(v, default=0):
                    try:
                        return int(float(v)) if v is not None else default
                    except (ValueError, TypeError):
                        return default

                item = {}
                for excel_col, model_field in column_map.items():
                    val = row[excel_col]
                    if model_field == "plaka":
                        val = str(val).upper().replace(" ", "") if val else None
                    elif model_field in ["marka", "model", "dorse_tipi", "notlar"]:
                        val = _sanitize_formula_prefix(str(val)) if val else None
                    elif model_field in ["yil", "lastik_sayisi"]:
                        val = safe_int(val, None)
                    elif model_field in [
                        "bos_agirlik_kg",
                        "rolling_resistance",
                        "drag_coefficient",
                    ]:
                        val = safe_float(val, 0.0)

                    item[model_field] = val

                if item.get("plaka"):
                    result.append(item)
            except (KeyError, ValueError, TypeError, AttributeError) as row_err:
                logger.warning(f"Dorse row {index + 2} error: {row_err}")
                continue
        return result
    except (ValueError, OSError, KeyError, AttributeError) as e:
        logger.error(f"Sync dorse excel error: {e}")
        raise ExcelExportError(f"Excel okuma hatası: {e!s}") from e
