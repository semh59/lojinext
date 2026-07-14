import json
from typing import Dict, List

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    Request,
    UploadFile,
)
from pydantic import BaseModel

from app.api.deps import get_current_active_user
from app.api.middleware.rate_limiter import limiter
from app.core.exceptions import DomainError
from app.core.services.import_service import ImportService, get_import_service
from app.database.models import Kullanici
from app.database.unit_of_work import UnitOfWork
from app.infrastructure.audit.audit_logger import log_audit_event
from app.schemas.api_responses import (
    ImportCommitResponse,
    ImportHistoryItem,
    ImportPreviewResponse,
    SuccessCountResponse,
)
from v2.modules.auth_rbac.domain.permission_checker import require_yetki

router = APIRouter()
# Removed global instantiation to support proper DI


class MappingData(BaseModel):
    mapping: Dict[str, str]


@router.post(
    "/preview",
    summary="İçeri Aktarım Önizleme",
    dependencies=[Depends(require_yetki("import_goruntule"))],
    response_model=ImportPreviewResponse,
)
async def preview_import(
    file: UploadFile = File(...),
    aktarim_tipi: str = Form(...),
    current_user: Kullanici = Depends(get_current_active_user),
    import_service: ImportService = Depends(get_import_service),
):
    """Excel veya CSV dosyasının başlıklarını okur ve 5 satırlık önizleme sunar."""
    try:
        return await import_service.parse_and_preview(file, aktarim_tipi)
    except DomainError:
        raise
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post(
    "/commit",
    summary="İçeri Aktarım İşlemini Başlat",
    dependencies=[Depends(require_yetki(["import_rollback", "all", "*"]))],
    response_model=ImportCommitResponse,
)
async def commit_import(
    file: UploadFile = File(...),
    aktarim_tipi: str = Form(...),
    mapping_str: str = Form(...),  # JSON string
    current_user: Kullanici = Depends(get_current_active_user),
    import_service: ImportService = Depends(get_import_service),
):
    """
    Eşleştirilen alanlara göre veri tabanına bulk insert yapar.
    Oluşturulan track_id (islem_haritasi) geri alımı mümkün kılar.
    """
    try:
        mapping = json.loads(mapping_str)
        result = await import_service.execute_import(
            file, aktarim_tipi, current_user.id, mapping
        )
        await log_audit_event(
            module="import",
            action="commit",
            entity_id=str(result.get("job_id") if isinstance(result, dict) else None),
            new_value={"aktarim_tipi": aktarim_tipi},
            user_id=current_user.id,
        )
        return result
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Geçersiz mapping formatı.")
    except DomainError:
        raise
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Aktarım Hatası: {str(e)}")


@router.post(
    "/{job_id}/rollback",
    summary="Aktarım İşlemini Geri Al",
    dependencies=[Depends(require_yetki(["import_rollback", "all", "*"]))],
    response_model=SuccessCountResponse,
)
@limiter.limit("10/day")
async def rollback_import(
    job_id: int,
    request: Request,
    current_user: Kullanici = Depends(get_current_active_user),
    import_service: ImportService = Depends(get_import_service),
):
    """
    Geçmiş bir işlemi transaction içerisinde geri alır.
    """
    try:
        success = await import_service.rollback_import(job_id, current_user.id)
        await log_audit_event(
            module="import",
            action="rollback",
            entity_id=str(job_id),
            new_value={"success": success},
            user_id=current_user.id,
        )
        return {"success": success, "message": "Geri alma işlemi başarıyla tamamlandı."}
    except DomainError:
        raise
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get(
    "/history",
    response_model=List[ImportHistoryItem],
    summary="Geçmiş Aktarımlar",
    dependencies=[Depends(require_yetki("import_goruntule"))],
)
async def import_history(
    limit: int = Query(50, ge=1, le=200),
    current_user: Kullanici = Depends(get_current_active_user),
) -> List[ImportHistoryItem]:
    """
    Geçmişe dönük yükleme loglarını getirir.
    """
    async with UnitOfWork() as uow:
        jobs = await uow.import_repo.get_recent_jobs(limit=limit)
        return [
            ImportHistoryItem(
                id=job.id,
                dosya_adi=job.dosya_adi,
                aktarim_tipi=job.aktarim_tipi,
                durum=job.durum,
                toplam=job.toplam_kayit,
                basarili=job.basarili_kayit,
                hatali=job.hatali_kayit,
                baslama_zamani=job.baslama_zamani,
                yukleyen_id=job.yukleyen_id,
            )
            for job in jobs
        ]
