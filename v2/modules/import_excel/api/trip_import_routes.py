"""Sefer (trip) Excel yükleme + asenkron görev durumu route'ları.

Dalga 14 — ``app/api/v1/endpoints/trips.py``'den taşındı; mantık zaten
``import_sefer_excel_upload`` (bu modülün ``public.py``'si) üzerinden
işliyordu. ``api.py``'de hâlâ ``prefix="/trips"`` ile mount edilir —
URL'ler DEĞİŞMEDİ.
"""

from typing import Annotated, Any, Dict

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile

from app.api.deps import get_background_job_manager, require_permissions
from app.database.models import Kullanici
from app.infrastructure.background.job_manager import (
    AsyncJobStatus,
    BackgroundJobManager,
)
from app.infrastructure.logging.logger import get_logger
from app.infrastructure.resilience.rate_limiter import RateLimiterDependency
from v2.modules.shared_kernel.schemas.api_responses import TaskStatusResponse

logger = get_logger(__name__)

router = APIRouter()


@router.post(
    "/upload",
    response_model=dict,
    dependencies=[
        # per_user=True — 2026-07-05 tespiti: global bucket çok-operatörlü
        # üretimde bir kullanıcının upload'ı diğerini 10 sn bloklar.
        Depends(
            RateLimiterDependency("upload_trips", rate=1.0, period=10.0, per_user=True)
        )
    ],
)
async def upload_sefer_excel(
    current_admin: Annotated[Kullanici, Depends(require_permissions("sefer:write"))],
    job_manager: Annotated[BackgroundJobManager, Depends(get_background_job_manager)],
    file: UploadFile = File(...),
    async_mode: bool = Query(
        False,
        description="True ise task_id döner; sonuç /trips/tasks/{id}/status ile alınır",
    ),
):
    """Excel import. Default sync (geriye uyumlu); ``async_mode=true`` ile task_id döner."""
    # MIME Type Validation
    ALLOWED_MIME_TYPES = {
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "application/vnd.ms-excel",
        "application/octet-stream",
    }
    if file.content_type and file.content_type not in ALLOWED_MIME_TYPES:
        raise HTTPException(
            status_code=400,
            detail="Sadece Excel dosyalari (.xlsx, .xls) kabul edilir.",
        )

    # File extension validation
    if file.filename and not file.filename.lower().endswith((".xlsx", ".xls")):
        raise HTTPException(
            status_code=400, detail="Dosya uzantisi .xlsx veya .xls olmali."
        )

    MAX_FILE_SIZE = 10 * 1024 * 1024

    # 1. Check Content-Length header (fast fail)
    if file.size and file.size > MAX_FILE_SIZE:
        raise HTTPException(status_code=413, detail="Dosya boyutu 10MB'i gecemez.")

    # 2. Secure Read (Chunked) protecting RAM
    content = bytearray()
    chunk_size = 1024 * 1024  # 1MB chunks

    while True:
        chunk = await file.read(chunk_size)
        if not chunk:
            break
        content.extend(chunk)
        if len(content) > MAX_FILE_SIZE:
            raise HTTPException(status_code=413, detail="Dosya boyutu 10MB'i gecemez.")

    from v2.modules.import_excel.public import import_sefer_excel_upload

    raw_bytes = bytes(content)
    user_id = current_admin.id

    async def _do_import() -> Dict[str, Any]:
        count, errors = await import_sefer_excel_upload(raw_bytes, user_id)
        failed_count = len(errors)
        return {
            "success": count > 0,
            "total_rows": count + failed_count,
            "success_count": count,
            "failed_count": failed_count,
            "errors": errors,
        }

    if async_mode:
        job_id = await job_manager.submit(_do_import)
        return {
            "status": AsyncJobStatus.PROCESSING.value,
            "task_id": job_id,
            "message": "İçe aktarma arka plana alındı. /trips/tasks/{task_id}/status ile takip edin.",
        }

    return await _do_import()


@router.get("/tasks/{task_id}/status", response_model=TaskStatusResponse)
async def get_task_status(
    task_id: str,
    current_user: Annotated[Kullanici, Depends(require_permissions("sefer:read"))],
    job_manager: BackgroundJobManager = Depends(get_background_job_manager),
):
    """
    Asenkron islem durumunu kontrol eden polling endpointi.
    """
    status_info = job_manager.get_status(task_id)

    if status_info["status"] == "unknown":
        raise HTTPException(
            status_code=404, detail=f"'{task_id}' ID'li gorev bulunamadi."
        )

    # Normalize status for frontend (PROCESSING, SUCCESS, FAILED)
    norm_status = AsyncJobStatus.PROCESSING.value
    if status_info["status"] == "completed":
        norm_status = AsyncJobStatus.SUCCESS.value
    elif status_info["status"] == "failed":
        norm_status = AsyncJobStatus.FAILED.value

    return {
        "task_id": task_id,
        "status": norm_status,
        "result": status_info.get("result"),
        "error": status_info.get("error"),
        "timestamp": status_info.get("timestamp"),
    }
