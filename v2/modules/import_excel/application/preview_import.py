"""Excel/CSV önizleme — DB'ye yazmadan başlık + ilk 5 satır mapping preview'ı."""

import io
from typing import Any, Dict, List

import pandas as pd
from fastapi import HTTPException, UploadFile

from v2.modules.import_excel.domain.constants import SUPPORTED_TYPES
from v2.modules.import_excel.infrastructure.parsers import MAX_EXCEL_ROWS
from v2.modules.platform_infra.public import get_logger
from v2.modules.shared_kernel.exceptions import ExcelExportError

logger = get_logger(__name__)


async def parse_and_preview(file: UploadFile, aktarim_tipi: str) -> Dict[str, Any]:
    """Reads Excel/CSV file and provides a mapping preview without writing to DB."""
    if aktarim_tipi not in SUPPORTED_TYPES:
        raise HTTPException(
            status_code=400, detail=f"Desteklenmeyen aktarım tipi: {aktarim_tipi}"
        )

    content = await file.read()
    try:
        if file.filename.endswith(".csv"):
            df = pd.read_csv(io.BytesIO(content))
        else:
            df = pd.read_excel(io.BytesIO(content))
    except Exception as e:
        logger.error(f"Dosya okuma hatası: {e}")
        raise HTTPException(status_code=400, detail="Dosya formatı geçersiz.")

    if len(df) > MAX_EXCEL_ROWS:
        raise HTTPException(
            status_code=413,
            detail=(
                f"Dosya satır sayısı ({len(df)}) izin verilen üst sınırı "
                f"({MAX_EXCEL_ROWS}) aşıyor. Dosyayı bölüp tekrar deneyin."
            ),
        )

    df = df.fillna("")
    headers = df.columns.tolist()
    total_rows = len(df)
    preview_data = df.head(5).to_dict(orient="records")

    return {
        "filename": file.filename,
        "aktarim_tipi": aktarim_tipi,
        "headers": headers,
        "total_rows": total_rows,
        "preview": preview_data,
    }


async def parse_import_file(filename: str, content: bytes) -> List[Dict[str, Any]]:
    """Dosyayı türüne göre okur; pandas DataFrame'den sözlük listesi döner."""
    if filename.endswith(".csv"):
        df = pd.read_csv(io.BytesIO(content))
    else:
        df = pd.read_excel(io.BytesIO(content))
    if len(df) > MAX_EXCEL_ROWS:
        raise ExcelExportError(
            f"Dosya satır sayısı ({len(df)}) izin verilen üst sınırı "
            f"({MAX_EXCEL_ROWS}) aşıyor. Dosyayı bölüp tekrar deneyin."
        )
    df = df.fillna("")
    return df.to_dict(orient="records")
