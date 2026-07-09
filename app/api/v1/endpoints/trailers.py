from typing import Annotated, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Response, UploadFile
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.api.deps import (
    SessionDep,
    UOWDep,
    get_current_active_admin,
    get_current_active_user,
    get_dorse_service,
)
from app.core.exceptions import DomainError
from app.core.services.dorse_service import DorseService
from app.database.models import Dorse, Kullanici
from app.infrastructure.audit.audit_logger import log_audit_event
from app.infrastructure.logging.logger import get_logger
from app.schemas.api_responses import (
    EXCEL_XLSX_RESPONSES,
    DorseImportResult,
    DorseInspectionAlertsResponse,
    FleetStatsResponse,
)
from app.schemas.base import ResponseMeta, StandardResponse
from app.schemas.dorse import DorseCreate, DorseResponse, DorseUpdate

logger = get_logger(__name__)

router = APIRouter()


@router.get("/", response_model=StandardResponse[List[DorseResponse]])
async def read_dorseler(
    db: SessionDep,
    current_user: Annotated[Kullanici, Depends(get_current_active_user)],
    service: DorseService = Depends(get_dorse_service),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    aktif_only: bool = True,
    search: str = Query(None, min_length=1),
    marka: Optional[str] = Query(None),
    model: Optional[str] = Query(None),
    min_yil: Optional[int] = Query(None),
    max_yil: Optional[int] = Query(None),
):
    """Dorseleri listele."""
    try:
        data = await service.get_all_paged(
            skip=skip,
            limit=limit,
            aktif_only=aktif_only,
            search=search,
            marka=marka,
            model=model,
            min_yil=min_yil,
            max_yil=max_yil,
        )
        return StandardResponse(
            data=data, meta=ResponseMeta(count=len(data), offset=skip, limit=limit)
        )
    except DomainError:
        raise
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error listing trailers: {e}")
        raise HTTPException(status_code=500, detail="Liste alınırken hata oluştu")


@router.get("/fleet-stats", response_model=FleetStatsResponse)
async def get_dorse_fleet_stats(
    current_user: Annotated[Kullanici, Depends(get_current_active_user)],
    db: SessionDep,
):
    """Dorse filosu genel istatistikleri (toplam, aktif, muayene uyarısı)."""
    from sqlalchemy import text

    query = text("""
        SELECT
            COUNT(*)                                                                              AS total,
            COUNT(*) FILTER (WHERE aktif = true)                                                  AS active,
            COUNT(*) FILTER (WHERE muayene_tarihi IS NOT NULL
                                AND muayene_tarihi >= CURRENT_DATE
                                AND muayene_tarihi <= CURRENT_DATE + INTERVAL '30 days')          AS inspection_expiring,
            COUNT(*) FILTER (WHERE muayene_tarihi IS NOT NULL
                                AND muayene_tarihi < CURRENT_DATE)                                AS inspection_overdue
        FROM dorseler
    """)  # noqa: E501
    row = (await db.execute(query)).mappings().one()
    return {
        "total": row["total"],
        "active": row["active"],
        "inspection_expiring": row["inspection_expiring"],
        "inspection_overdue": row["inspection_overdue"],
    }


@router.get("/inspection-alerts", response_model=DorseInspectionAlertsResponse)
async def get_dorse_inspection_alerts(
    current_user: Annotated[Kullanici, Depends(get_current_active_user)],
    db: SessionDep,
    within_days: int = Query(30, ge=1, le=180),
):
    """Muayenesi yaklaşan veya geçmiş dorselerin listesi.

    Yanıt: ``{ expiring: [...], overdue: [...], within_days }``. Araç
    ``inspection-alerts`` ile aynı sözleşme (dorse'de model yok, tipi var).
    Aktif + soft-delete edilmemiş dorselerle sınırlı.
    """
    from sqlalchemy import text

    query = text(
        """
        SELECT
            id,
            plaka,
            marka,
            tipi,
            yil,
            muayene_tarihi,
            CASE
                WHEN muayene_tarihi < CURRENT_DATE THEN 'overdue'
                ELSE 'expiring'
            END AS bucket,
            (muayene_tarihi - CURRENT_DATE) AS days_remaining
        FROM dorseler
        WHERE aktif = TRUE
          AND is_deleted = FALSE
          AND muayene_tarihi IS NOT NULL
          AND (
              muayene_tarihi < CURRENT_DATE
              OR muayene_tarihi <= CURRENT_DATE + (:within_days || ' days')::interval
          )
        ORDER BY muayene_tarihi ASC
        """
    )
    result = await db.execute(query, {"within_days": str(within_days)})
    rows = result.mappings().all()

    expiring: list[dict] = []
    overdue: list[dict] = []
    for row in rows:
        item = {
            "id": row["id"],
            "plaka": row["plaka"],
            "marka": row["marka"],
            "tipi": row["tipi"],
            "yil": row["yil"],
            "muayene_tarihi": row["muayene_tarihi"].isoformat()
            if row["muayene_tarihi"]
            else None,
            "days_remaining": int(row["days_remaining"])
            if row["days_remaining"] is not None
            else None,
        }
        if row["bucket"] == "overdue":
            overdue.append(item)
        else:
            expiring.append(item)

    return {"expiring": expiring, "overdue": overdue, "within_days": within_days}


@router.post("/", response_model=StandardResponse[DorseResponse], status_code=201)
async def create_dorse(
    dorse: DorseCreate,
    uow: UOWDep,
    current_admin: Annotated[Kullanici, Depends(get_current_active_admin)],
    service: DorseService = Depends(get_dorse_service),
):
    """Yeni dorse oluştur."""
    try:
        dorse_id = await service.create(**dorse.model_dump())
        # include_inactive=True: az önce oluşturulan kaydı aynı transaction
        # içinde geri okuyoruz (bkz. vehicles.py:145 için aynı desen).
        created = await uow.dorse_repo.get_by_id(dorse_id, include_inactive=True)
        if not created:
            raise HTTPException(
                status_code=500, detail="Dorse oluşturuldu ancak okunamadı."
            )
        await log_audit_event(
            module="dorse",
            action="create",
            entity_id=str(dorse_id),
            new_value=dict(created),
            user_id=current_admin.id,
        )
        return StandardResponse(data=created)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except IntegrityError as e:
        logger.warning(f"Trailer create integrity violation: {e.orig}", exc_info=False)
        raise HTTPException(
            status_code=400, detail="Veri bütünlüğü hatası: dorse zaten mevcut olabilir"
        )
    except DomainError:
        raise
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating trailer: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Sunucu hatası")


@router.get(
    "/export",
    responses=EXCEL_XLSX_RESPONSES,
    response_model=None,
    response_class=Response,
)
async def export_trailers(
    current_admin: Annotated[Kullanici, Depends(get_current_active_admin)],
    service: DorseService = Depends(get_dorse_service),
):
    """Tüm dorseleri Excel olarak indir."""
    from fastapi.responses import Response

    content = await service.export_all_trailers()
    return Response(
        content=content,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=dorseler.xlsx"},
    )


@router.get(
    "/template",
    responses=EXCEL_XLSX_RESPONSES,
    response_model=None,
    response_class=Response,
)
async def get_trailer_template(
    current_admin: Annotated[Kullanici, Depends(get_current_active_admin)],
    service: DorseService = Depends(get_dorse_service),
):
    """Dorse yükleme şablonunu indir."""
    from fastapi.responses import Response

    content = await service.get_template()
    return Response(
        content=content,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=dorse_sablonu.xlsx"},
    )


_ALLOWED_EXCEL_MIME = {
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "application/vnd.ms-excel",
    "application/octet-stream",
}
_MAX_UPLOAD_BYTES = 10 * 1024 * 1024  # 10 MB


def _validate_excel_upload(file: UploadFile) -> None:
    if file.content_type and file.content_type not in _ALLOWED_EXCEL_MIME:
        raise HTTPException(
            status_code=415,
            detail=f"Desteklenmeyen dosya tipi: {file.content_type}. Yalnız .xlsx/.xls yüklenir.",
        )
    filename = file.filename or ""
    if filename and not (filename.endswith(".xlsx") or filename.endswith(".xls")):
        raise HTTPException(
            status_code=415,
            detail="Yalnız .xlsx veya .xls uzantılı dosyalar kabul edilir.",
        )


@router.post("/import", response_model=StandardResponse[DorseImportResult])
async def import_trailers(
    file: UploadFile,
    current_admin: Annotated[Kullanici, Depends(get_current_active_admin)],
    service: DorseService = Depends(get_dorse_service),
):
    """Excel'den dorse verileri yükle."""
    _validate_excel_upload(file)
    try:
        content = await file.read()
        if len(content) > _MAX_UPLOAD_BYTES:
            raise HTTPException(
                status_code=413,
                detail=f"Dosya boyutu sınırı aşıldı (maks {_MAX_UPLOAD_BYTES // 1024 // 1024} MB).",
            )
        result = await service.import_trailers(content)
        return StandardResponse(data=result)
    except DomainError:
        raise
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Import error: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{dorse_id}", response_model=StandardResponse[DorseResponse])
async def read_dorse(
    dorse_id: int,
    db: SessionDep,
    current_user: Annotated[Kullanici, Depends(get_current_active_user)],
):
    """Dorse detayını getir."""
    dorse = await db.get(Dorse, dorse_id)
    if not dorse:
        raise HTTPException(status_code=404, detail="Dorse bulunamadı")
    return StandardResponse(data=dorse)


@router.put("/{dorse_id}", response_model=StandardResponse[DorseResponse])
async def update_dorse(
    dorse_id: int,
    dorse_update: DorseUpdate,
    db: SessionDep,
    current_admin: Annotated[Kullanici, Depends(get_current_active_admin)],
    service: DorseService = Depends(get_dorse_service),
):
    """Dorse güncelle."""
    try:
        success = await service.update(
            dorse_id, **dorse_update.model_dump(exclude_unset=True)
        )
        if not success:
            raise HTTPException(status_code=404, detail="Dorse bulunamadı")

        result = await db.execute(select(Dorse).where(Dorse.id == dorse_id))
        updated = result.scalar_one_or_none()
        await log_audit_event(
            module="dorse",
            action="update",
            entity_id=str(dorse_id),
            new_value=dorse_update.model_dump(exclude_unset=True),
            user_id=current_admin.id,
        )
        return StandardResponse(data=updated)
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))


@router.delete("/{dorse_id}", response_model=StandardResponse[dict])
async def delete_dorse(
    dorse_id: int,
    current_admin: Annotated[Kullanici, Depends(get_current_active_admin)],
    service: DorseService = Depends(get_dorse_service),
):
    """Dorse sil."""
    try:
        success = await service.delete(dorse_id)
        if not success:
            raise HTTPException(status_code=404, detail="Dorse bulunamadı")
        await log_audit_event(
            module="dorse",
            action="delete",
            entity_id=str(dorse_id),
            user_id=current_admin.id,
        )
        return StandardResponse(data={"status": "success", "message": "Dorse silindi"})
    except DomainError:
        raise
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting trailer {dorse_id}: {e}")
        raise HTTPException(status_code=500, detail="Silme işlemi başarısız")
