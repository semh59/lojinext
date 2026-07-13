from datetime import datetime, timezone
from typing import Annotated, List, Optional

from fastapi import APIRouter, Depends, File, HTTPException, Query, Response, UploadFile
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, OperationalError

from app.api.deps import (
    SessionDep,
    UOWDep,
    get_current_active_admin,
    get_current_active_user,
)
from app.core.entities.models import VehicleStats
from app.core.exceptions import DomainError
from app.core.services.excel_service import ExcelService
from app.database.models import Arac, Kullanici
from app.infrastructure.audit.audit_logger import log_audit_event
from app.infrastructure.logging.logger import get_logger
from app.schemas.api_responses import (
    EXCEL_XLSX_RESPONSES,
    FleetEventItem,
    FleetStatsResponse,
    InspectionAlertsResponse,
    SuccessCountResponse,
    UploadResultResponse,
)
from app.schemas.base import ResponseMeta, StandardResponse
from v2.modules.fleet.application.create_vehicle import create_vehicle
from v2.modules.fleet.application.delete_vehicle import (
    delete_all_vehicles,
    delete_vehicle,
)
from v2.modules.fleet.application.list_vehicles import (
    get_all_vehicles_paged,
)
from v2.modules.fleet.application.list_vehicles import (
    get_vehicle_stats as get_vehicle_stats_usecase,
)
from v2.modules.fleet.application.update_vehicle import update_vehicle
from v2.modules.fleet.schemas import AracCreate, AracResponse, AracUpdate

logger = get_logger(__name__)

router = APIRouter()


@router.get("/", response_model=StandardResponse[List[AracResponse]])
async def read_araclar(
    db: SessionDep,
    current_user: Annotated[Kullanici, Depends(get_current_active_user)],
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    aktif_only: bool = True,
    search: str = Query(None, min_length=1),
    marka: Optional[str] = Query(None),
    model: Optional[str] = Query(None),
    min_yil: Optional[int] = Query(None),
    max_yil: Optional[int] = Query(None),
):
    """Araçları listele."""
    try:
        data = await get_all_vehicles_paged(
            skip=skip,
            limit=limit,
            aktif_only=aktif_only,
            search=search,
            marka=marka,
            model=model,
            min_yil=min_yil,
            max_yil=max_yil,
        )
        items = data.get("items", []) if isinstance(data, dict) else data
        total = data.get("total", len(items)) if isinstance(data, dict) else len(items)
        return StandardResponse(
            data=items,
            meta=ResponseMeta(
                total=total,
                offset=skip,
                limit=limit,
                count=len(items),
            ),
        )
    except DomainError:
        raise
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error listing vehicles via service: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Liste alınırken hata oluştu")


@router.get(
    "/export",
    responses=EXCEL_XLSX_RESPONSES,
    response_model=None,
    response_class=Response,
)
async def export_araclar(
    current_user: Annotated[Kullanici, Depends(get_current_active_user)],
    aktif_only: bool = True,
    search: str = Query(None, min_length=1),
    marka: Optional[str] = Query(None),
    model: Optional[str] = Query(None),
    min_yil: Optional[int] = Query(None),
    max_yil: Optional[int] = Query(None),
):
    """Araç listesini Excel olarak dışa aktar (Filtreli)."""
    try:
        # Export için limit kaldırılır (veya çok yüksek tutulur)
        vehicles = await get_all_vehicles_paged(
            skip=0,
            limit=10000,  # Makul bir üst sınır
            aktif_only=aktif_only,
            search=search,
            marka=marka,
            model=model,
            min_yil=min_yil,
            max_yil=max_yil,
        )

        # Pydantic modellerini dict'e çevir
        items = vehicles.get("items", []) if isinstance(vehicles, dict) else vehicles
        data = [v.model_dump() if hasattr(v, "model_dump") else dict(v) for v in items]

        # Excel oluştur
        content = await ExcelService.export_data(data, type="arac_listesi")

        filename = (
            f"arac_listesi_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M')}.xlsx"
        )

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
        logger.error(f"Error exporting vehicles: {e}")
        raise HTTPException(status_code=500, detail="Excel oluşturulurken hata oluştu")


@router.post("/", response_model=AracResponse, status_code=201)
async def create_arac(
    arac: AracCreate,
    uow: UOWDep,
    current_admin: Annotated[Kullanici, Depends(get_current_active_admin)],
):
    """Yeni araç oluştur (Duplicate Check + Reactivation)."""
    try:
        # aynı UOW transaction içinde çalışır
        arac_id = await create_vehicle(arac, uow=uow)

        # Fetch created (Use UOW for consistency). include_inactive=True: the
        # duplicate-plate path in create_vehicle can *reactivate* an existing
        # passive vehicle and return its id — by the time we read it back
        # here it has already been flipped to aktif=True in the same
        # transaction, but we read defensively regardless of that ordering.
        created = await uow.arac_repo.get_by_id(arac_id, include_inactive=True)
        if not created:
            raise HTTPException(
                status_code=500, detail="Araç oluşturuldu ancak okunamadı."
            )

        logger.info(
            f"Vehicle processed: {created.get('plaka')} by {current_admin.email}"
        )
        await log_audit_event(
            module="arac",
            action="create",
            entity_id=str(arac_id),
            new_value=dict(created),
            user_id=current_admin.id,
        )
        return created

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except IntegrityError as e:
        logger.warning(f"Vehicle create integrity violation: {e.orig}", exc_info=False)
        raise HTTPException(
            status_code=400, detail="Veri bütünlüğü hatası: araç zaten mevcut olabilir"
        )
    except OperationalError as e:
        logger.error(f"DB connection error in create_arac: {e}", exc_info=True)
        raise HTTPException(
            status_code=503,
            detail="Veritabanı bağlantısı geçici olarak kesildi. Lütfen tekrar deneyin.",
        )
    except DomainError:
        raise
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating vehicle: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Sunucu hatası")


@router.get(
    "/template",
    responses=EXCEL_XLSX_RESPONSES,
    response_model=None,
    response_class=Response,
)
async def get_vehicle_template(
    current_user: Annotated[Kullanici, Depends(get_current_active_user)],
):
    """Araç yükleme Excel şablonunu indir."""
    from fastapi.responses import Response

    content = await ExcelService.generate_template("arac")
    return Response(
        content=content,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": "attachment; filename=arac_yukleme_sablonu.xlsx"
        },
    )


@router.get("/fleet-stats", response_model=FleetStatsResponse)
async def get_fleet_stats(
    current_user: Annotated[Kullanici, Depends(get_current_active_user)],
    db: SessionDep,
):
    """Araç filosu genel istatistikleri (toplam, aktif, muayene uyarısı)."""
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
        FROM araclar
    """)  # noqa: E501
    result = await db.execute(query)
    row = result.mappings().one()
    return {
        "total": row["total"],
        "active": row["active"],
        "inspection_expiring": row["inspection_expiring"],
        "inspection_overdue": row["inspection_overdue"],
    }


@router.get("/inspection-alerts", response_model=InspectionAlertsResponse)
async def get_inspection_alerts(
    current_user: Annotated[Kullanici, Depends(get_current_active_user)],
    db: SessionDep,
    within_days: int = Query(30, ge=1, le=180),
):
    """Muayenesi yaklaşan veya geçmiş araçların listesi.

    Yanıt: ``{ expiring: [...], overdue: [...], within_days }``. Her
    araçta plaka, marka/model/yıl ve muayene tarihi döner. Aktif
    araçlarla sınırlandırılmıştır.
    """
    from sqlalchemy import text

    query = text(
        """
        SELECT
            id,
            plaka,
            marka,
            model,
            yil,
            muayene_tarihi,
            CASE
                WHEN muayene_tarihi < CURRENT_DATE THEN 'overdue'
                ELSE 'expiring'
            END AS bucket,
            (muayene_tarihi - CURRENT_DATE) AS days_remaining
        FROM araclar
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
            "model": row["model"],
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

    return {
        "expiring": expiring,
        "overdue": overdue,
        "within_days": within_days,
    }


@router.delete("/clear-all", response_model=SuccessCountResponse)
async def clear_all_vehicles(
    current_admin: Annotated[Kullanici, Depends(get_current_active_admin)],
):
    """Tüm araçları temizle (Admin Only)."""
    try:
        count = await delete_all_vehicles()
        await log_audit_event(
            module="arac",
            action="delete_all",
            new_value={"deleted_count": count},
            user_id=current_admin.id,
        )
        return {"success": True, "message": f"{count} araç temizlendi."}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except DomainError:
        raise
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error clearing all vehicles: {e}")
        raise HTTPException(
            status_code=500, detail="Temizleme işlemi sırasında hata oluştu"
        )


@router.delete("/{arac_id}", response_model=SuccessCountResponse)
async def delete_arac(
    arac_id: int,
    current_admin: Annotated[Kullanici, Depends(get_current_active_admin)],
):
    """Araç sil (Soft/Hard delete)."""
    try:
        success = await delete_vehicle(arac_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except DomainError:
        raise
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting vehicle {arac_id}: {e}")
        raise HTTPException(status_code=500, detail="Silme işlemi başarısız")
    if not success:
        raise HTTPException(status_code=404, detail="Araç bulunamadı")
    await log_audit_event(
        module="arac",
        action="delete",
        entity_id=str(arac_id),
        user_id=current_admin.id,
    )
    return {"success": True, "message": "Araç silindi"}


@router.get("/{arac_id}", response_model=AracResponse)
async def read_arac(
    arac_id: int,
    db: SessionDep,
    current_user: Annotated[Kullanici, Depends(get_current_active_user)],
):
    """Araç detayını getir."""
    arac = await db.get(Arac, arac_id)
    if not arac:
        raise HTTPException(status_code=404, detail="Araç bulunamadı")
    return arac


@router.put("/{arac_id}", response_model=AracResponse)
async def update_arac(
    arac_id: int,
    arac_update: AracUpdate,
    db: SessionDep,
    current_admin: Annotated[Kullanici, Depends(get_current_active_admin)],
):
    """Araç güncelle."""
    try:
        success = await update_vehicle(arac_id, arac_update)
        if not success:
            raise HTTPException(status_code=404, detail="Araç bulunamadı")

        # Refresh from DB to return updated state
        result = await db.execute(select(Arac).where(Arac.id == arac_id))
        existing = result.scalar_one_or_none()
        await log_audit_event(
            module="arac",
            action="update",
            entity_id=str(arac_id),
            new_value=arac_update.model_dump(exclude_unset=True),
            user_id=current_admin.id,
        )
        return existing
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))


@router.get("/{arac_id}/stats", response_model=VehicleStats)
async def get_vehicle_stats(
    arac_id: int,
    current_user: Annotated[Kullanici, Depends(get_current_active_user)],
):
    """Araç istatistiklerini getir (Sefer sayısı, KM, Tüketim vs)."""
    stats = await get_vehicle_stats_usecase(arac_id)
    if not stats:
        # Eğer araç yoksa 404
        # Eğer araç var ama hiç seferi yoksa yine de boş istatistik (0) dönebilir
        raise HTTPException(status_code=404, detail="Araç bulunamadı")
    return stats


@router.get("/{arac_id}/events", response_model=List[FleetEventItem])
async def get_vehicle_events(
    arac_id: int,
    current_user: Annotated[Kullanici, Depends(get_current_active_user)],
    db: SessionDep,
    limit: int = Query(20, ge=1, le=50),
):
    """Araç olay geçmişini getir (son N kayıt)."""
    from sqlalchemy import text

    query = text("""
        SELECT id, arac_id, event_type, old_status, new_status, triggered_by, details, created_at
        FROM vehicle_event_log
        WHERE arac_id = :arac_id
        ORDER BY created_at DESC
        LIMIT :limit
    """)
    rows = await db.execute(query, {"arac_id": arac_id, "limit": limit})
    return [
        {
            "id": row["id"],
            "event_type": row["event_type"],
            "old_status": row["old_status"],
            "new_status": row["new_status"],
            "triggered_by": row["triggered_by"],
            "details": row["details"],
            "created_at": row["created_at"].isoformat() if row["created_at"] else None,
        }
        for row in rows.mappings()
    ]


@router.post("/upload", response_model=UploadResultResponse)
async def upload_vehicles(
    current_admin: Annotated[Kullanici, Depends(get_current_active_admin)],
    file: UploadFile = File(...),
):
    # ... existing implementation ...
    from app.core.services.import_service import get_import_service

    # MIME Type Validation
    ALLOWED_MIME_TYPES = {
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",  # xlsx
        "application/vnd.ms-excel",  # xls
        "application/octet-stream",  # Some browsers send this
    }
    if not file.content_type or file.content_type not in ALLOWED_MIME_TYPES:
        raise HTTPException(
            status_code=400, detail="Sadece Excel dosyaları (.xlsx, .xls) kabul edilir."
        )

    # File extension validation (double check)
    if file.filename:
        if not file.filename.lower().endswith((".xlsx", ".xls")):
            raise HTTPException(
                status_code=400, detail="Dosya uzantısı .xlsx veya .xls olmalıdır."
            )

    # 10MB Limit Check
    MAX_FILE_SIZE = 10 * 1024 * 1024

    # 1. Check Content-Length header (fast fail)
    if file.size and file.size > MAX_FILE_SIZE:
        raise HTTPException(status_code=413, detail="Dosya boyutu 10MB'ı geçemez.")

    # 2. Secure Read (Chunked) protecting RAM
    content = bytearray()
    chunk_size = 1024 * 1024  # 1MB chunks

    while True:
        chunk = await file.read(chunk_size)
        if not chunk:
            break
        content.extend(chunk)
        if len(content) > MAX_FILE_SIZE:
            raise HTTPException(status_code=413, detail="Dosya boyutu 10MB'ı geçemez.")

    import_service = get_import_service()

    created_count, errors = await import_service.process_vehicle_import(bytes(content))

    return {
        "success": True,
        "message": f"{created_count} araç yüklendi.",
        "errors": errors,
    }
