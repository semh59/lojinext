from datetime import date
from typing import Annotated, Any, Optional

from fastapi import (
    APIRouter,
    Depends,
    File,
    Header,
    HTTPException,
    Query,
    Response,
    UploadFile,
)
from sqlalchemy import text

from app.api.deps import (
    SessionDep,
    UOWDep,
    get_current_active_admin,
    get_current_active_user,
    get_yakit_service,
    require_permissions,
)
from app.api.v1.endpoints.internal import (
    _ALLOWED_MIME_TYPES,
    _looks_like_allowed_image,
)
from app.api.v1.utils import parse_date_param
from app.config import settings
from app.core.exceptions import DomainError
from app.core.services.idempotency_service import (
    IdempotencyKeyConflictError,
    IdempotencyKeyInProgressError,
    finalize_response,
    release_reservation,
    reserve_or_get_cached,
)
from app.core.services.yakit_service import YakitService
from app.database.models import Kullanici, YakitAlimi
from app.infrastructure.audit.audit_logger import log_audit_event
from app.infrastructure.logging.logger import get_logger
from app.infrastructure.monitoring.external_api_probe import get_monitored_client
from app.infrastructure.resilience.rate_limiter import RateLimiterDependency
from app.schemas.api_responses import FuelStatsResponse
from app.schemas.yakit import (
    FuelDocumentItem,
    FuelDocumentList,
    OcrParsedFields,
    OcrPreviewResponse,
    YakitCreate,
    YakitListResponse,
    YakitResponse,
    YakitUpdate,
)

logger = get_logger(__name__)

router = APIRouter()


@router.get("/stats", response_model=FuelStatsResponse)
async def get_fuel_stats(
    current_user: Annotated[Kullanici, Depends(get_current_active_user)],
    service: YakitService = Depends(get_yakit_service),
    baslangic_tarih: Optional[str] = Query(None, description="YYYY-MM-DD"),
    bitis_tarih: Optional[str] = Query(None, description="YYYY-MM-DD"),
) -> FuelStatsResponse:
    """
    Yakıt istatistiklerini getir (Service Layer).
    """
    start_date = parse_date_param(baslangic_tarih, "baslangic_tarih")
    end_date = parse_date_param(bitis_tarih, "bitis_tarih")

    try:
        payload = await service.get_stats(
            baslangic_tarih=start_date, bitis_tarih=end_date
        )
        return FuelStatsResponse.model_validate(payload)
    except DomainError:
        raise
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting fuel stats: {e}")
        raise HTTPException(status_code=500, detail="İstatistikler alınamadı")


# read_yakit_alimlari wrapped in try/except


@router.get("/", response_model=YakitListResponse)
async def read_yakit_alimlari(
    db: SessionDep,
    current_user: Annotated[Kullanici, Depends(get_current_active_user)],
    service: YakitService = Depends(get_yakit_service),
    baslangic_tarih: Optional[str] = Query(None),
    bitis_tarih: Optional[str] = Query(None),
    arac_id: Optional[int] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=200),
) -> Any:
    """Yakıt alımlarını listele (Service Layer)."""
    try:
        # Service handles skip/limit/safety/validation internally
        return await service.get_all_paged(
            skip=skip,
            limit=limit,
            baslangic_tarih=baslangic_tarih,
            bitis_tarih=bitis_tarih,
            arac_id=arac_id,
        )
    except DomainError:
        raise
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error listing fuel via service: {e}")
        raise HTTPException(status_code=500, detail="Liste alınırken hata oluştu")


@router.post(
    "/",
    response_model=YakitResponse,
    status_code=201,
    dependencies=[Depends(RateLimiterDependency("create_fuel", rate=2.0, period=1.0))],
)
async def create_yakit(
    yakit: YakitCreate,
    current_admin: Annotated[Kullanici, Depends(get_current_active_admin)],
    uow: UOWDep,
    service: YakitService = Depends(get_yakit_service),
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
):
    """Yeni yakıt alımı ekle (Service Layer).

    2026-07-01 prod-grade denetimi P1 (Dalga 4 madde 19): client timeout+retry
    ile çift kayıt oluşmasını önlemek için opsiyonel `Idempotency-Key` header'ı
    desteklenir — aynı key + aynı gövde tekrar POST edilirse önbelleklenen
    yanıt aynen dönülür, gerçek bir ikinci kayıt oluşturulmaz.
    """
    _ENDPOINT = "POST /fuel"
    request_body = yakit.model_dump(mode="json")
    if idempotency_key:
        try:
            reservation = await reserve_or_get_cached(
                key=idempotency_key,
                endpoint=_ENDPOINT,
                request_body=request_body,
            )
        except IdempotencyKeyConflictError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        except IdempotencyKeyInProgressError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        if not reservation.reserved:
            _status_code, cached_body = reservation.cached
            return cached_body

    try:
        yakit_id = await service.add_yakit(yakit)
        created = await service.get_yakit_by_id(yakit_id)
        await log_audit_event(
            module="yakit",
            action="create",
            entity_id=str(yakit_id),
            new_value={"arac_id": yakit.arac_id, "litre": str(yakit.litre)},
            user_id=current_admin.id,
        )
        if idempotency_key:
            response_body = YakitResponse.model_validate(
                created, from_attributes=True
            ).model_dump(mode="json")
            await finalize_response(
                key=idempotency_key,
                endpoint=_ENDPOINT,
                status_code=201,
                response_body=response_body,
            )
        return created

    except ValueError as e:
        if idempotency_key:
            await release_reservation(key=idempotency_key, endpoint=_ENDPOINT)
        raise HTTPException(status_code=400, detail=str(e))
    except DomainError:
        if idempotency_key:
            await release_reservation(key=idempotency_key, endpoint=_ENDPOINT)
        raise
    except HTTPException:
        if idempotency_key:
            await release_reservation(key=idempotency_key, endpoint=_ENDPOINT)
        raise
    except Exception as e:
        if idempotency_key:
            await release_reservation(key=idempotency_key, endpoint=_ENDPOINT)
        logger.error(f"Error creating fuel: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Sunucu hatası")


@router.post("/ocr-preview", response_model=OcrPreviewResponse)
async def ocr_preview(
    file: UploadFile = File(...),
    _user: Kullanici = Depends(get_current_active_user),
) -> OcrPreviewResponse:
    """Fiş görselini OCR servisine iletip yapılandırılmış önizleme döndürür.

    DB'ye yazmaz — kullanıcı önizleyip onayladıktan sonra POST /fuel/ ile
    kayıt oluşturur. Görsel mime + magic-byte ile doğrulanır (ARCH-020).
    """
    content_type = file.content_type or ""
    if content_type not in _ALLOWED_MIME_TYPES:
        raise HTTPException(
            status_code=415, detail=f"Desteklenmeyen dosya türü: {content_type}"
        )
    content = await file.read()
    if not _looks_like_allowed_image(content):
        raise HTTPException(status_code=415, detail="Geçerli bir görsel dosyası değil")
    ocr_headers = {}
    if settings.OCR_SERVICE_API_KEY:
        ocr_headers["Authorization"] = f"Bearer {settings.OCR_SERVICE_API_KEY}"
    try:
        async with get_monitored_client(timeout=90) as client:
            resp = await client.post(
                f"{settings.OCR_SERVICE_URL}/ocr/process",
                files={"file": ("fis.jpg", content, content_type)},
                data={"belge_tipi": "yakit_fisi"},
                headers=ocr_headers,
            )
        resp.raise_for_status()
        result = resp.json()
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        logger.error("OCR servisi hatası (web preview): %s", exc)
        raise HTTPException(
            status_code=502, detail="OCR servisi şu an yanıt vermiyor"
        ) from exc
    yap = result.get("yapilandirilmis") or {}
    return OcrPreviewResponse(
        ham_metin=result.get("ham_metin"),
        yapilandirilmis=OcrParsedFields(
            litre=yap.get("litre"),
            tutar=yap.get("tutar"),
            km=yap.get("km"),
            tarih=yap.get("tarih"),
            istasyon=yap.get("istasyon"),
        ),
    )


@router.get("/documents", response_model=FuelDocumentList)
async def list_fuel_documents(
    db: SessionDep,
    _admin: Annotated[Kullanici, Depends(get_current_active_admin)],
    limit: int = Query(50, ge=1, le=200),
) -> FuelDocumentList:
    """Yakıt fişi belgelerinin arşiv listesi (en yeni → eski)."""
    rows = (
        (
            await db.execute(
                text(
                    "SELECT id, belge_tipi, ocr_durumu, sofor_id, sefer_id, "
                    "created_at FROM sefer_belgeler WHERE belge_tipi = 'yakit_fisi' "
                    "ORDER BY created_at DESC LIMIT :limit"
                ),
                {"limit": limit},
            )
        )
        .mappings()
        .all()
    )
    return FuelDocumentList(items=[FuelDocumentItem(**dict(r)) for r in rows])


@router.get("/{yakit_id}", response_model=YakitResponse)
async def read_yakit(
    yakit_id: int,
    current_user: Annotated[Kullanici, Depends(get_current_active_user)],
    service: YakitService = Depends(get_yakit_service),
):
    """Yakıt alımı detaylarını getir (Service Layer)."""
    yakit = await service.get_yakit_by_id(yakit_id)
    if not yakit:
        raise HTTPException(status_code=404, detail="Yakıt alımı bulunamadı")
    return yakit


@router.put("/{yakit_id}", response_model=YakitResponse)
async def update_yakit(
    yakit_id: int,
    yakit_in: YakitUpdate,
    current_admin: Annotated[Kullanici, Depends(get_current_active_admin)],
    service: YakitService = Depends(get_yakit_service),
):
    """Yakıt kaydı güncelle (Service Layer)."""
    try:
        success = await service.update_yakit(yakit_id, yakit_in)
        if not success:
            raise HTTPException(status_code=404, detail="Yakıt alımı bulunamadı")

        updated = await service.get_yakit_by_id(yakit_id)
        await log_audit_event(
            module="yakit",
            action="update",
            entity_id=str(yakit_id),
            new_value=yakit_in.model_dump(exclude_unset=True),
            user_id=current_admin.id,
        )
        return updated

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except DomainError:
        raise
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Update error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Güncelleme hatası")


@router.delete("/{yakit_id}", response_model=YakitResponse)
async def delete_yakit(
    yakit_id: int,
    response: Response,
    db: SessionDep,
    current_admin: Annotated[Kullanici, Depends(get_current_active_admin)],
    service: YakitService = Depends(get_yakit_service),
):
    """Yakıt alımı sil (Service: Smart Delete)."""

    current = await db.get(YakitAlimi, yakit_id)
    if not current:
        raise HTTPException(status_code=404, detail="Yakıt alımı bulunamadı")

    was_active = current.aktif

    try:
        success = await service.delete_yakit(yakit_id)
        if not success:
            raise HTTPException(status_code=404, detail="Silinemedi")

        await log_audit_event(
            module="yakit",
            action="delete",
            entity_id=str(yakit_id),
            new_value={"was_active": was_active},
            user_id=current_admin.id,
        )
        if was_active:
            updated = await db.get(YakitAlimi, yakit_id)
            return updated if updated is not None else current
        else:
            response.headers["X-Delete-Type"] = "Hard Delete"
            return current

    except DomainError:
        raise
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting fuel: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Silme hatası")


@router.get("/excel/export")
async def export_yakit_alimlari(
    db: SessionDep,
    current_admin: Annotated[Kullanici, Depends(get_current_active_admin)],
    service: YakitService = Depends(get_yakit_service),
    baslangic_tarih: Optional[str] = Query(None),
    bitis_tarih: Optional[str] = Query(None),
    arac_id: Optional[int] = Query(None),
):
    """Yakıt alımlarını Excel olarak dışa aktar."""
    try:
        # Get all matching records (not paged)
        data = await service.get_all_paged(
            skip=0,
            limit=10000,  # Large enough for export
            baslangic_tarih=baslangic_tarih,
            bitis_tarih=bitis_tarih,
            arac_id=arac_id,
        )

        # get_all_paged returns {"items": [...], "total": N}
        items = data.get("items", data) if isinstance(data, dict) else data
        clean_data = [
            d.model_dump() if hasattr(d, "model_dump") else dict(d) for d in items
        ]

        # Excel oluştur
        from app.core.services.excel_service import ExcelService

        content = await ExcelService.export_data(clean_data, type="yakit_listesi")

        filename = f"yakit_raporu_{date.today().isoformat()}.xlsx"
        return Response(
            content=content,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f"attachment; filename={filename}"},
        )
    except DomainError:
        raise
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error exporting fuel: {e}")
        raise HTTPException(status_code=500, detail="Excel oluşturulurken hata oluştu")


@router.get("/excel/template")
async def get_fuel_excel_template(
    current_admin: Annotated[Kullanici, Depends(get_current_active_admin)],
):
    """Yakıt yükleme şablonu indir."""
    from app.core.services.excel_service import ExcelService

    try:
        content = await ExcelService.generate_template("yakit")
        return Response(
            content=content,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={
                "Content-Disposition": "attachment; filename=yakit_yukleme_sablonu.xlsx"
            },
        )
    except DomainError:
        raise
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error generating fuel template: {e}")
        raise HTTPException(status_code=500, detail="Şablon oluşturulamadı")


@router.post(
    "/excel/upload",
    response_model=dict,
    dependencies=[Depends(RateLimiterDependency("upload_fuel", rate=1.0, period=10.0))],
)
async def upload_yakit_excel(
    current_admin: Annotated[Kullanici, Depends(require_permissions("yakit:write"))],
    file: UploadFile = File(...),
    async_mode: bool = Query(
        False,
        description="True ise task_id döner; sonuç /trips/tasks/{id}/status ile alınır",
    ),
):
    """Yakıt fişleri toplu Excel import (1000+ kayıt için async_mode önerilir).

    Şablon: GET /api/v1/fuel/excel/template (kolonlar: Tarih, Plaka,
    İstasyon, Litre, Fiyat, KM Sayacı, Toplam Tutar, Fiş No, Depo Durumu).

    Pipeline:
      1. Excel parse (plaka normalize, fuzzy column match)
      2. plaka → arac_id resolve; bulunamayan satır errors[]'a
      3. bulk_add_yakit (Pydantic YakitCreate listesi; tek transaction)
      4. Etkilenen her arac_id için recalculate_vehicle_periods çağrılır
         (km aralıklarından tüketim oranı türetilir; yakit_periyotlari tablosu)

    Rate limit: 1 dosya / 10 saniye.
    async_mode=True büyük dosyalar için (>200 satır) önerilir.
    """
    ALLOWED_MIME_TYPES = {
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "application/vnd.ms-excel",
        "application/octet-stream",
    }
    if file.content_type and file.content_type not in ALLOWED_MIME_TYPES:
        raise HTTPException(
            status_code=400,
            detail="Sadece Excel dosyaları (.xlsx, .xls) kabul edilir.",
        )
    if file.filename and not file.filename.lower().endswith((".xlsx", ".xls")):
        raise HTTPException(
            status_code=400, detail="Dosya uzantısı .xlsx veya .xls olmalı."
        )

    MAX_FILE_SIZE = 10 * 1024 * 1024
    if file.size and file.size > MAX_FILE_SIZE:
        raise HTTPException(status_code=413, detail="Dosya boyutu 10MB'ı geçemez.")

    content = bytearray()
    chunk_size = 1024 * 1024
    while True:
        chunk = await file.read(chunk_size)
        if not chunk:
            break
        content.extend(chunk)
        if len(content) > MAX_FILE_SIZE:
            raise HTTPException(status_code=413, detail="Dosya boyutu 10MB'ı geçemez.")

    raw_bytes = bytes(content)

    async def _do_import() -> dict:
        from app.core.services.import_service import get_import_service

        service = get_import_service()
        count, errors = await service.process_yakit_import(raw_bytes)
        return {
            "status": "success" if not errors else "partial_success",
            "processed": count + len(errors),
            "saved": count,
            "failed": len(errors),
            "errors": errors,
        }

    if async_mode:
        from app.infrastructure.background.job_manager import (
            get_job_manager,
        )

        job_manager = get_job_manager()
        job_id = await job_manager.submit(_do_import)
        return {
            "status": "PROCESSING",
            "task_id": job_id,
            "message": (
                "Yakıt içe aktarma arka plana alındı. "
                "/trips/tasks/{task_id}/status ile takip edin."
            ),
        }

    return await _do_import()
