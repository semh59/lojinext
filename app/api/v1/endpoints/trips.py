from datetime import date, datetime, timezone
from typing import Annotated, Any, Dict, List, Optional, cast

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Body,
    Depends,
    File,
    Header,
    HTTPException,
    Query,
    Response,
    UploadFile,
    status,
)
from fastapi.responses import StreamingResponse

from app.api.deps import (
    UOWDep,
    get_background_job_manager,
    get_current_active_user,
    get_sefer_service,
    require_permissions,
)
from app.core.exceptions import DomainError
from app.core.services.idempotency_service import (
    IdempotencyKeyConflictError,
    IdempotencyKeyInProgressError,
    finalize_response,
    release_reservation,
    reserve_or_get_cached,
)
from app.core.services.sefer_service import SeferService
from app.database.models import Kullanici
from app.infrastructure.audit.audit_logger import log_audit_event
from app.infrastructure.background.job_manager import (
    AsyncJobStatus,
    BackgroundJobManager,
)
from app.infrastructure.logging.logger import get_logger
from app.infrastructure.metrics import trip_approval_total
from app.infrastructure.resilience.rate_limiter import RateLimiterDependency
from app.schemas.api_responses import (
    EXCEL_XLSX_RESPONSES,
    FuelPerformanceAnalyticsResponse,
    TaskStatusResponse,
    TripTimelineResponse,
)
from app.schemas.sefer import (
    SeferBulkCancel,
    SeferBulkDelete,
    SeferBulkResponse,
    SeferBulkStatusUpdate,
    SeferCreate,
    SeferListResponse,
    SeferResponse,
    SeferStatsResponse,
    SeferUpdate,
)
from app.schemas.telegram import SeferOnayRequest
from v2.modules.ai_assistant.schemas import (
    DriverSuggestion,
    PlanWizardRequest,
    PlanWizardResponse,
    VehicleSuggestion,
)
from v2.modules.import_excel.public import export_data, generate_template

logger = get_logger(__name__)

router = APIRouter()


@router.get("/", response_model=SeferListResponse)
async def read_seferler(
    current_user: Annotated[Kullanici, Depends(require_permissions("sefer:read"))],
    service: SeferService = Depends(get_sefer_service),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    baslangic_tarih: Optional[str] = Query(None, description="YYYY-MM-DD"),
    bitis_tarih: Optional[str] = Query(None, description="YYYY-MM-DD"),
    arac_id: Optional[int] = Query(None),
    sofor_id: Optional[int] = Query(None),
    durum: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    onay_durumu: Optional[str] = Query(
        None, description="beklemede|onaylandi|reddedildi"
    ),
):
    """Seferleri listele (Service Layer)."""
    try:
        # Service handles skip/limit/safety/validation and ISOLATION internally
        # Returns Dict with "items", "total", "skip", "limit"
        return await service.get_all_paged(
            current_user=current_user,
            skip=skip,
            limit=limit,
            baslangic_tarih=baslangic_tarih,
            bitis_tarih=bitis_tarih,
            arac_id=arac_id,
            sofor_id=sofor_id,
            durum=durum,
            search=search,
            onay_durumu=onay_durumu,
        )
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except DomainError:
        raise
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error listing trips via service: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Liste alınırken hata oluştu")


@router.get("/today", response_model=SeferListResponse)
async def read_bugunun_seferleri(
    current_user: Annotated[Kullanici, Depends(require_permissions("sefer:read"))],
    service: SeferService = Depends(get_sefer_service),
):
    """Bugünün seferlerini listele."""
    try:
        from datetime import date

        return await service.get_all_paged(
            current_user=current_user,
            baslangic_tarih=date.today().isoformat(),
            bitis_tarih=date.today().isoformat(),
        )
    except DomainError:
        raise
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching today's trips: {e}")
        raise HTTPException(status_code=500, detail="Bugünkü seferler alınamadı")


@router.get(
    "/export",
    response_class=StreamingResponse,
    responses=EXCEL_XLSX_RESPONSES,
    response_model=None,
)
async def export_seferler(
    background_tasks: BackgroundTasks,
    current_user: Annotated[Kullanici, Depends(require_permissions("sefer:read"))],
    service: SeferService = Depends(get_sefer_service),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    baslangic_tarih: Optional[str] = Query(None, description="YYYY-MM-DD"),
    bitis_tarih: Optional[str] = Query(None, description="YYYY-MM-DD"),
    arac_id: Optional[int] = Query(None),
    sofor_id: Optional[int] = Query(None),
    durum: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
):
    """Sefer listesini Excel olarak dışa aktar (Filtreli ve Limitli)."""
    try:
        MAX_EXPORT_LIMIT = 5000

        # Seferleri getir (MAX_EXPORT_LIMIT uygulanmis hali)
        seferler = await service.get_all_paged(
            current_user=current_user,
            skip=0,
            limit=MAX_EXPORT_LIMIT,
            aktif_only=False,
            baslangic_tarih=baslangic_tarih,
            bitis_tarih=bitis_tarih,
            arac_id=arac_id,
            sofor_id=sofor_id,
            durum=durum,
            search=search,
        )

        items = seferler.get("items", [])
        total = int((seferler.get("meta") or {}).get("total") or len(items))

        if total > MAX_EXPORT_LIMIT:
            raise ValueError(
                f"{MAX_EXPORT_LIMIT} satir limitini astiniz, tarih araligini daraltin."
            )

        data = []
        for s in items:
            d = s.model_dump() if hasattr(s, "model_dump") else s
            if getattr(s, "tarih", None):
                d["tarih"] = s.tarih.strftime("%Y-%m-%d")
            else:
                d["tarih"] = d.get("tarih", "")

            d["durum"] = getattr(s, "durum", d.get("durum"))
            d["plaka"] = getattr(s, "plaka", d.get("plaka", ""))
            d["sofor"] = getattr(s, "sofor_adi", d.get("sofor", ""))
            data.append(d)

        # Excel oluştur
        content = await export_data(data, type="sefer_listesi")
        filename = (
            f"sefer_listesi_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M')}.xlsx"
        )
        import urllib.parse

        encoded_filename = urllib.parse.quote(filename)
        return Response(
            content=content,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={
                "Content-Disposition": f"attachment; filename*=UTF-8''{encoded_filename}",
                "Access-Control-Expose-Headers": "Content-Disposition",
            },
        )
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except DomainError:
        raise
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Excel export error: {e}", exc_info=True)
        raise HTTPException(
            status_code=500, detail="Excel dışa aktarım sırasında hata oluştu"
        )


@router.get("/stats", response_model=SeferStatsResponse)
async def get_trip_stats(
    current_user: Annotated[Kullanici, Depends(require_permissions("sefer:read"))],
    service: SeferService = Depends(get_sefer_service),
    durum: Optional[str] = Query(None, description="Filtrelemek istenen sefer durumu"),
    baslangic_tarih: Optional[str] = Query(None, description="YYYY-MM-DD"),
    bitis_tarih: Optional[str] = Query(None, description="YYYY-MM-DD"),
):
    """
    Sefer istatistiklerini sunar.
    Tarih filtresi varsa dinamik sorgu kosturur, yoksa materialized view kullanir.
    """
    try:
        start_date = date.fromisoformat(baslangic_tarih) if baslangic_tarih else None
        end_date = date.fromisoformat(bitis_tarih) if bitis_tarih else None
    except ValueError:
        raise HTTPException(status_code=422, detail="Tarih formati gecersiz.")

    try:
        stats = await service.get_trip_stats(
            durum=durum,
            baslangic_tarih=start_date,
            bitis_tarih=end_date,
        )
        return SeferStatsResponse(**stats)
    except ValueError:
        raise HTTPException(status_code=422, detail="Gecersiz durum degeri.")
    except DomainError:
        raise
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Sefer listesi alınırken hata: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Liste alınırken hata oluştu",
        )


@router.get(
    "/analytics/fuel-performance", response_model=FuelPerformanceAnalyticsResponse
)
async def get_fuel_performance_analytics(
    current_user: Annotated[Kullanici, Depends(require_permissions("sefer:read"))],
    service: SeferService = Depends(get_sefer_service),
    durum: Optional[str] = Query(None),
    baslangic_tarih: Optional[str] = Query(None, description="YYYY-MM-DD"),
    bitis_tarih: Optional[str] = Query(None, description="YYYY-MM-DD"),
    arac_id: Optional[int] = Query(None),
    sofor_id: Optional[int] = Query(None),
    search: Optional[str] = Query(None),
):
    """
    Sefer bazli yakit performans metriklerini kullanici odakli payload ile doner.
    """
    try:
        start_date = date.fromisoformat(baslangic_tarih) if baslangic_tarih else None
        end_date = date.fromisoformat(bitis_tarih) if bitis_tarih else None
    except ValueError:
        raise HTTPException(status_code=422, detail="Tarih formati gecersiz.")

    try:
        return await service.get_fuel_performance_analytics(
            durum=durum,
            baslangic_tarih=start_date,
            bitis_tarih=end_date,
            arac_id=arac_id,
            sofor_id=sofor_id,
            search=search,
        )
    except ValueError:
        raise HTTPException(status_code=422, detail="Gecersiz durum degeri.")
    except DomainError:
        raise
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Fuel performance analytics error: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Yakit performansi alinamadi")


@router.post(
    "/",
    response_model=SeferResponse,
    status_code=201,
)
async def create_sefer(
    _: Annotated[
        None, Depends(RateLimiterDependency("create_trip", rate=2.0, period=1.0))
    ],
    sefer: SeferCreate,
    current_admin: Annotated[Kullanici, Depends(require_permissions("sefer:write"))],
    uow: UOWDep,
    service: SeferService = Depends(get_sefer_service),
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
):
    """Yeni sefer oluştur (Service Layer).

    2026-07-01 prod-grade denetimi P1 (Dalga 4 madde 19): client timeout+retry
    ile çift kayıt oluşmasını önlemek için opsiyonel `Idempotency-Key` header'ı
    desteklenir — aynı key + aynı gövde tekrar POST edilirse önbelleklenen
    yanıt aynen dönülür, gerçek bir ikinci kayıt oluşturulmaz.
    """
    _ENDPOINT = "POST /trips"
    request_body = sefer.model_dump(mode="json")
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
        # Capture the actor id BEFORE the service commits — after commit the
        # ORM attribute is expired and re-reading it would trigger a sync lazy
        # load (MissingGreenlet) inside the later audit call.
        actor_id = current_admin.id
        logger.info(
            f"API: Creating trip with sefer_no: {sefer.sefer_no}, round_trip: {sefer.is_round_trip}"
        )
        sefer_id = await service.add_sefer(sefer, user_id=actor_id)
        logger.info(f"API: Service returned sefer_id: {sefer_id}")

        # Use service to get detailed object
        created_dict = await service.get_sefer_by_id(sefer_id)
        if not created_dict:
            logger.error(
                f"API: Created trip ID {sefer_id} could not be retrieved after creation"
            )
            raise HTTPException(
                status_code=500, detail="Oluşturulan kayıt geri okunamadı"
            )

        logger.info(f"API: Retrieved created trip dict for ID {sefer_id}")

        await log_audit_event(
            module="sefer",
            action="create",
            entity_id=str(sefer_id),
            new_value={"sefer_no": sefer.sefer_no},
            user_id=actor_id,
        )

        # Manually validate to SeferResponse to catch serialization errors
        from pydantic import ValidationError

        try:
            validated = SeferResponse.model_validate(created_dict)
            if idempotency_key:
                await finalize_response(
                    key=idempotency_key,
                    endpoint=_ENDPOINT,
                    status_code=201,
                    response_body=validated.model_dump(mode="json"),
                )
            return validated
        except ValidationError as ve:
            logger.error(
                f"API: Serialization error to SeferResponse for ID {sefer_id}: {ve}"
            )
            raise HTTPException(
                status_code=500,
                detail=f"Veri şema uyumsuzluğu (ID:{sefer_id}): {str(ve.errors()[0].get('msg'))}",
            )

    except HTTPException:
        if idempotency_key:
            await release_reservation(key=idempotency_key, endpoint=_ENDPOINT)
        raise
    except ValueError as e:
        if idempotency_key:
            await release_reservation(key=idempotency_key, endpoint=_ENDPOINT)
        logger.warning(f"API: Validation error: {e}")
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
        import traceback

        from sqlalchemy.exc import IntegrityError

        # NOT NULL / FK constraint violations → unprocessable input (422)
        if isinstance(e, IntegrityError) and (
            "NotNullViolationError" in str(type(e.__cause__))
            or "ForeignKeyViolationError" in str(type(e.__cause__))
            or "not-null constraint" in str(e).lower()
            or "foreign key" in str(e).lower()
        ):
            if idempotency_key:
                await release_reservation(key=idempotency_key, endpoint=_ENDPOINT)
            logger.warning("API: DB constraint violation (422): %s", e)
            raise HTTPException(
                status_code=422,
                detail="Eksik veya geçersiz alan: " + str(e).split("DETAIL")[0][:200],
            )

        if idempotency_key:
            await release_reservation(key=idempotency_key, endpoint=_ENDPOINT)
        logger.error(
            f"API: Unexpected error creating trip: {str(e)}\n{traceback.format_exc()}"
        )
        raise HTTPException(
            status_code=500, detail="Sefer oluşturulurken bir hata oluştu"
        )


@router.post("/{sefer_id}/return", response_model=SeferResponse, status_code=201)
async def create_return_trip(
    sefer_id: int,
    current_admin: Annotated[Kullanici, Depends(require_permissions("sefer:write"))],
    service: SeferService = Depends(get_sefer_service),
):
    """Mevcut bir sefer baz alınarak dönüş seferi oluştur (Backend mantığı)."""
    try:
        actor_id = current_admin.id  # capture pre-commit (see create_sefer)
        new_sefer_id = await service.create_return_trip(sefer_id, user_id=actor_id)

        # Oku ve döndür
        created_dict = await service.get_sefer_by_id(new_sefer_id)
        if not created_dict:
            raise HTTPException(
                status_code=500, detail="Dönüş seferi oluşturuldu ancak okunamadı"
            )

        await log_audit_event(
            module="sefer",
            action="create_return",
            entity_id=str(new_sefer_id),
            new_value={"source_sefer_id": sefer_id},
            user_id=actor_id,
        )

        from pydantic import ValidationError

        try:
            return SeferResponse.model_validate(created_dict)
        except ValidationError as ve:
            logger.error(f"API: Serialization error to SeferResponse: {ve}")
            raise HTTPException(status_code=500, detail=f"Veri dönüşüm hatası: {ve}")

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except DomainError:
        raise
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Return trip creation error: {e}", exc_info=True)
        raise HTTPException(
            status_code=500, detail="Dönüş seferi oluşturulurken hata meydana geldi"
        )


@router.get("/beklemede", response_model=List[SeferResponse])
async def beklemede_seferler(
    current_user: Annotated[Kullanici, Depends(require_permissions("sefer:onayla"))],
    service: SeferService = Depends(get_sefer_service),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
):
    """Telegram botundan gelen, admin onayı bekleyen seferler."""
    try:
        return await service.get_by_onay_durumu("beklemede", skip=skip, limit=limit)
    except DomainError:
        raise
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Beklemede seferler alınamadı: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail="Seferler alınamadı")


@router.get(
    "/excel/template",
    responses=EXCEL_XLSX_RESPONSES,
    response_model=None,
    response_class=Response,
)
async def get_excel_template(
    current_user: Annotated[Kullanici, Depends(require_permissions("sefer:read"))],
):
    """Sefer yükleme için örnek Excel şablonu indir."""
    try:
        content = await generate_template(type="sefer")
        filename = "sefer_yukleme_sablonu.xlsx"

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
        logger.error(f"Error generating trip template: {e}")
        raise HTTPException(status_code=500, detail="Şablon oluşturulamadı")


@router.get("/{sefer_id}", response_model=SeferResponse)
async def read_sefer(
    sefer_id: int,
    current_user: Annotated[Kullanici, Depends(require_permissions("sefer:read"))],
    service: SeferService = Depends(get_sefer_service),
):
    """Tekil sefer getir (Güvenli)."""
    sefer = await service.get_by_id(sefer_id, current_user=current_user)
    if not sefer:
        raise HTTPException(status_code=404, detail="Sefer bulunamadı")
    return sefer


@router.get("/{sefer_id}/cost-analysis", response_model=dict, status_code=202)
async def analyze_trip_costs(
    sefer_id: int,
    current_user: Annotated[Kullanici, Depends(get_current_active_user)],
    service: SeferService = Depends(get_sefer_service),
    job_manager: BackgroundJobManager = Depends(get_background_job_manager),
):
    """
    Sefer maliyet analizi ve Smart Reconciliation tetikleme (Asenkron).
    """
    try:
        # Check permission (get_by_id handles ownership)
        sefer = await service.get_by_id(sefer_id, current_user=current_user)
        if not sefer:
            raise HTTPException(status_code=404, detail="Sefer bulunamadı")

        # Submit to background job manager instead of raw BackgroundTasks
        job_id = await job_manager.submit(service.reconcile_costs, sefer_id)

        return {
            "status": AsyncJobStatus.PROCESSING.value,
            "task_id": job_id,
            "message": "Maliyet analizi arka plana alındı. Lütfen durum sorgulama endpoint'ini kullanın.",
        }
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except DomainError:
        raise
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Cost analysis initialization error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Maliyet analizi başlatılamadı")


@router.patch("/{sefer_id}", response_model=SeferResponse)
async def update_sefer(
    sefer_id: int,
    sefer_in: SeferUpdate,
    current_admin: Annotated[Kullanici, Depends(require_permissions("sefer:write"))],
    service: SeferService = Depends(get_sefer_service),
):
    """Sefer güncelle (Service Layer)."""
    try:
        actor_id = current_admin.id  # capture pre-commit (see create_sefer)
        success = await service.update_sefer(sefer_id, sefer_in, user_id=actor_id)
        if not success:
            raise HTTPException(status_code=404, detail="Sefer bulunamadi")

        # Guncel veriyi getir (cache invalidation sonrasinda taze veri)
        updated = await service.get_sefer_by_id(sefer_id)
        if not updated:
            raise HTTPException(status_code=404, detail="Guncellenen sefer bulunamadi")
        await log_audit_event(
            module="sefer",
            action="update",
            entity_id=str(sefer_id),
            new_value=sefer_in.model_dump(exclude_unset=True),
            user_id=actor_id,
        )
        return updated

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except DomainError:
        raise
    except Exception as e:
        logger.error(f"Update error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Guncelleme sirasinda hata olustu")


@router.delete("/{sefer_id}", response_model=dict)
async def delete_sefer(
    sefer_id: int,
    current_admin: Annotated[Kullanici, Depends(require_permissions("sefer:write"))],
    service: SeferService = Depends(get_sefer_service),
):
    """Seferi soft-delete olarak iptal eder."""

    try:
        actor_id = current_admin.id  # capture pre-commit (see create_sefer)
        success = await service.delete_sefer(sefer_id)
        if not success:
            raise HTTPException(
                status_code=404, detail="Sefer bulunamadi veya silinemedi"
            )

        await log_audit_event(
            module="sefer",
            action="delete",
            entity_id=str(sefer_id),
            user_id=actor_id,
        )
        return {
            "status": "success",
            "message": "Sefer soft-delete olarak iptal edildi",
            "soft_deleted": True,
        }

    except DomainError:
        raise
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting trip: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Silme hatasi")


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


@router.patch(
    "/bulk/status",
    response_model=SeferBulkResponse,
    dependencies=[Depends(RateLimiterDependency("bulk_status", rate=1.0, period=5.0))],
)
async def bulk_update_trip_status(
    data: SeferBulkStatusUpdate,
    current_user: Annotated[Kullanici, Depends(require_permissions("sefer:write"))],
    service: SeferService = Depends(get_sefer_service),
):
    """Secili seferlerin durumunu toplu guncelle (SUPERVISOR+)."""
    if len(data.sefer_ids) > 500:
        raise HTTPException(status_code=400, detail="Bulk limit: maksimum 500 sefer")
    try:
        return await service.bulk_update_status(
            data.sefer_ids, data.new_status, user_id=current_user.id
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@router.patch(
    "/bulk/cancel",
    response_model=SeferBulkResponse,
    dependencies=[Depends(RateLimiterDependency("bulk_cancel", rate=1.0, period=5.0))],
)
async def bulk_cancel_trips(
    data: SeferBulkCancel,
    current_user: Annotated[Kullanici, Depends(require_permissions("sefer:write"))],
    service: SeferService = Depends(get_sefer_service),
):
    """Secili seferleri toplu iptal et (SUPERVISOR+)."""
    if len(data.sefer_ids) > 500:
        raise HTTPException(status_code=400, detail="Bulk limit: maksimum 500 sefer")
    return await service.bulk_cancel(
        data.sefer_ids, data.iptal_nedeni, user_id=current_user.id
    )


@router.post("/bulk-delete", response_model=Dict[str, Any])
async def bulk_delete_trips(
    data: SeferBulkDelete,
    current_user: Annotated[Kullanici, Depends(require_permissions("sefer:write"))],
    service: SeferService = Depends(get_sefer_service),
) -> Any:
    """Secilen seferleri toplu sil."""
    sefer_ids = data.sefer_ids
    if len(sefer_ids) > 500:
        raise HTTPException(status_code=400, detail="Bulk limit: maksimum 500 sefer")
    logger.info(f"Bulk Delete Request: User={current_user.email}, IDs={sefer_ids}")
    if not sefer_ids:
        logger.warning("Bulk delete called with empty ID list")
        return {"success_count": 0, "failed_count": 0, "failed": []}
    actor_id = current_user.id  # capture pre-commit (see create_sefer)
    result = await service.bulk_delete(sefer_ids)
    await log_audit_event(
        module="sefer",
        action="bulk_delete",
        new_value={
            "sefer_ids": sefer_ids,
            "success_count": result.get("success_count"),
        },
        user_id=actor_id,
    )
    return result


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


@router.get("/{sefer_id}/timeline", response_model=TripTimelineResponse)
async def get_sefer_timeline(
    sefer_id: int,
    current_user: Annotated[Kullanici, Depends(require_permissions("sefer:read"))],
    service: SeferService = Depends(get_sefer_service),
):
    """Seferin kronolojik olay akışını (audit log) getirir."""
    try:
        # Sefer var mı kontrolü (isolation/safety)
        await service.get_by_id(sefer_id, current_user=current_user)

        timeline_items = await service.get_timeline(sefer_id)
        return {"items": timeline_items}
    except HTTPException:
        raise
    except DomainError:
        raise
    except Exception as e:
        logger.error(f"Error fetching timeline for trip {sefer_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Zaman çizelgesi alınamadı")


# ── Telegram onay akışı ───────────────────────────────────────────────────────


@router.post("/{sefer_id}/onayla", response_model=SeferResponse)
async def sefer_onayla(
    sefer_id: int,
    current_user: Annotated[Kullanici, Depends(require_permissions("sefer:onayla"))],
    body: SeferOnayRequest = Body(default_factory=SeferOnayRequest),  # type: ignore[arg-type]
    service: SeferService = Depends(get_sefer_service),
):
    """Sefer onaylama — admin veya baş şoför yetkisi gerektirir."""
    sefer = await service.get_by_id(sefer_id, current_user=current_user)
    if not sefer:
        raise HTTPException(status_code=404, detail="Sefer bulunamadı")
    try:
        actor_id = current_user.id  # capture pre-commit (see create_sefer)
        result = await service.set_onay_durumu(
            sefer_id, "onaylandi", body.onay_notu, actor_id
        )
        trip_approval_total.labels(action="onayla").inc()
        await log_audit_event(
            module="sefer",
            action="onayla",
            entity_id=str(sefer_id),
            new_value={"onay_notu": body.onay_notu},
            user_id=actor_id,
        )
        return result
    except DomainError:
        raise
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Sefer onaylanamadı (id=%s): %s", sefer_id, exc, exc_info=True)
        raise HTTPException(status_code=500, detail="Onaylama işlemi başarısız")


@router.post("/{sefer_id}/reddet", response_model=SeferResponse)
async def sefer_reddet(
    sefer_id: int,
    current_user: Annotated[Kullanici, Depends(require_permissions("sefer:onayla"))],
    body: SeferOnayRequest = Body(default_factory=SeferOnayRequest),  # type: ignore[arg-type]
    service: SeferService = Depends(get_sefer_service),
):
    """Sefer reddetme — admin veya baş şoför yetkisi gerektirir."""
    sefer = await service.get_by_id(sefer_id, current_user=current_user)
    if not sefer:
        raise HTTPException(status_code=404, detail="Sefer bulunamadı")
    try:
        actor_id = current_user.id  # capture pre-commit (see create_sefer)
        result = await service.set_onay_durumu(
            sefer_id, "reddedildi", body.onay_notu, actor_id
        )
        trip_approval_total.labels(action="reddet").inc()
        await log_audit_event(
            module="sefer",
            action="reddet",
            entity_id=str(sefer_id),
            new_value={"onay_notu": body.onay_notu},
            user_id=actor_id,
        )
        return result
    except DomainError:
        raise
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Sefer reddedilemedi (id=%s): %s", sefer_id, exc, exc_info=True)
        raise HTTPException(status_code=500, detail="Reddetme işlemi başarısız")


# ── Feature C — Sefer Planlama Sihirbazı ──


@router.post("/plan-wizard", response_model=PlanWizardResponse)
async def plan_wizard(
    payload: PlanWizardRequest,
    _: Annotated[
        None, Depends(RateLimiterDependency("plan_wizard", rate=20.0, period=60.0))
    ],
    current_admin: Annotated[Kullanici, Depends(require_permissions("sefer:write"))],
) -> PlanWizardResponse:
    """Feature C — yeni sefer için 3 araç + 3 şoför önerisi.

    Feature flag `TRIP_PLANNER_ENABLED` kapalıysa 503.
    Hard filter boş ise 200 + boş listeler (404 değil).
    """
    from app.config import settings
    from app.infrastructure.audit.audit_logger import log_audit_event
    from app.services.prediction_service import PredictionService
    from v2.modules.ai_assistant.application.plan_trip import TripPlannerEngine
    from v2.modules.ai_assistant.domain.planner_scoring import PlanInput

    if not settings.TRIP_PLANNER_ENABLED:
        raise HTTPException(status_code=503, detail="Sefer planlama sihirbazı kapalı")

    # route_analysis: payload.guzergah_id verilirse engine kendi UoW'sunda
    # Lokasyon'u fetch eder — endpoint layer DB'ye direkt erişmez.
    inp = PlanInput(
        cikis_yeri=payload.cikis_yeri,
        varis_yeri=payload.varis_yeri,
        mesafe_km=payload.mesafe_km,
        tarih=payload.tarih,
        ascent_m=payload.ascent_m,
        descent_m=payload.descent_m,
        flat_distance_km=payload.flat_distance_km,
        route_analysis=None,  # engine içinde guzergah_id varsa fetch eder
        weight_kg=payload.weight_kg,
        guzergah_id=payload.guzergah_id,
    )

    engine = TripPlannerEngine(PredictionService())
    try:
        result = await engine.plan(inp, top_n=payload.top_n)
    except Exception as exc:
        logger.error("plan_wizard engine failed: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail="Planlama motoru başarısız")

    # Audit-iz (PII'siz; sadece kullanım kanıtı)
    try:
        creator_id = (
            current_admin.id if current_admin.id and current_admin.id > 0 else None
        )
        await log_audit_event(
            action="plan_wizard_used",
            module="trip_planner",
            entity_id=None,
            user_id=creator_id,
            new_value={
                "tarih": payload.tarih.isoformat(),
                "mesafe_km": payload.mesafe_km,
                "guzergah_id": payload.guzergah_id,
                "top_n": payload.top_n,
                "vehicle_count": len(result.vehicles),
                "driver_count": len(result.drivers),
            },
        )
    except Exception as exc:  # pragma: no cover
        logger.warning("plan_wizard audit log failed: %s", exc)

    return PlanWizardResponse(
        weather_impact=result.weather_impact,
        risk_label=cast("Any", result.risk_label),
        route_type=cast("Any", result.route_type),
        vehicles=[VehicleSuggestion.model_validate(v) for v in result.vehicles],
        drivers=[DriverSuggestion.model_validate(d) for d in result.drivers],
        generated_at=result.generated_at,
        cache_hit=result.cache_hit,
    )
