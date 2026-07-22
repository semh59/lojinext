"""Driver module HTTP routes.

``router`` mounts at ``/drivers`` (14 route), per ``TASKS/modules/driver.md``
§2 route envanteri.
"""

import io
from datetime import datetime, timezone
from typing import Annotated, Any, Dict, List, Optional

from fastapi import (
    APIRouter,
    Body,
    Depends,
    File,
    HTTPException,
    Query,
    Response,
    UploadFile,
)
from fastapi.responses import StreamingResponse
from sqlalchemy.exc import IntegrityError

from app.api.deps import get_current_active_admin, get_current_active_user
from v2.modules.auth_rbac.public import Kullanici
from v2.modules.driver.application.delete_sofor import bulk_delete
from v2.modules.driver.application.delete_sofor import (
    delete_sofor as delete_sofor_usecase,
)
from v2.modules.driver.application.get_performance import get_performance_details
from v2.modules.driver.application.get_route_profile import get_route_profile_sofor
from v2.modules.driver.application.get_score import get_score_breakdown_sofor
from v2.modules.driver.application.list_sofor import get_all_paged, get_by_id
from v2.modules.driver.application.list_sofor import (
    get_driver_fleet_stats as get_driver_fleet_stats_usecase,
)
from v2.modules.driver.application.update_sofor import update_score
from v2.modules.driver.application.update_sofor import (
    update_sofor as update_sofor_usecase,
)
from v2.modules.driver.schemas import (
    DriverFleetStatsResponse,
    DriverPerformanceSchema,
    DriverRouteProfileSchema,
    DriverScoreBreakdownSchema,
    SoforCreate,
    SoforResponse,
    SoforUpdate,
)
from v2.modules.import_excel.public import export_data, generate_template
from v2.modules.platform_infra.audit.audit_logger import log_audit_event
from v2.modules.platform_infra.logging.logger import get_logger
from v2.modules.shared_kernel.exceptions import DomainError
from v2.modules.shared_kernel.schemas.api_responses import (
    EXCEL_XLSX_RESPONSES,
    UploadResultResponse,
)
from v2.modules.shared_kernel.schemas.base import ResponseMeta, StandardResponse

logger = get_logger(__name__)


router = APIRouter()


@router.get("/", response_model=StandardResponse[List[SoforResponse]])
async def read_soforler(
    current_user: Annotated[Kullanici, Depends(get_current_active_user)],
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    aktif_only: bool = Query(True, description="Sadece aktif şoförler"),
    search: Optional[str] = Query(None, description="İsim veya telefon araması"),
    ehliyet_sinifi: Optional[str] = Query(None, description="Ehliyet sınıfı"),
    min_score: Optional[float] = Query(None, ge=0.1, le=2.0),
    max_score: Optional[float] = Query(None, ge=0.1, le=2.0),
):
    try:
        result = await get_all_paged(
            skip=skip,
            limit=limit,
            aktif_only=aktif_only,
            search=search,
            ehliyet_sinifi=ehliyet_sinifi,
            min_score=min_score,
            max_score=max_score,
        )
        return StandardResponse(
            data=result["items"],
            meta=ResponseMeta(
                total=result["total"],
                offset=skip,
                limit=limit,
                count=len(result["items"]),
            ),
        )
    except DomainError:
        raise
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error listing drivers via service: {e}")
        raise HTTPException(status_code=500, detail="Liste alınırken hata oluştu")


@router.get("/fleet-stats", response_model=DriverFleetStatsResponse)
async def get_driver_fleet_stats(
    current_user: Annotated[Kullanici, Depends(get_current_active_user)],
):
    """Sürücü filosu özeti — tek sorgu, total + active."""
    return await get_driver_fleet_stats_usecase()


@router.post("/", response_model=SoforResponse, status_code=201)
async def create_sofor(
    sofor: SoforCreate,
    current_admin: Annotated[Kullanici, Depends(get_current_active_admin)],
) -> Any:
    from v2.modules.driver.application.add_sofor import add_sofor

    try:
        sofor_id = await add_sofor(
            ad_soyad=sofor.ad_soyad,
            telefon=sofor.telefon,
            ehliyet_sinifi=sofor.ehliyet_sinifi,
            ise_baslama=sofor.ise_baslama,
            manual_score=sofor.manual_score,
            notlar=sofor.notlar,
            telegram_id=sofor.telegram_id,
        )
        created_sofor = await get_by_id(sofor_id)
        if not created_sofor:
            raise HTTPException(
                status_code=500, detail="Sürücü oluşturuldu fakat geri getirilemedi."
            )

        logger.info(
            f"Driver processed via Service: {created_sofor['ad_soyad']} by {current_admin.email}"
        )
        await log_audit_event(
            module="sofor",
            action="create",
            entity_id=str(sofor_id),
            new_value={"ad_soyad": created_sofor["ad_soyad"]},
            user_id=current_admin.id,
        )
        return created_sofor

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except IntegrityError as e:
        # Concurrent duplicate create: the pre-check SELECT cannot lock a
        # row that does not exist yet, so two racing inserts both pass it
        # and the UNIQUE(ad_soyad) constraint is the real guard — the loser
        # surfaces here. Map it to the same friendly 400 the vehicle path uses
        # instead of falling through to a misleading 500.
        logger.warning(
            f"Driver create integrity violation: {getattr(e, 'orig', e)}",
            exc_info=False,
        )
        raise HTTPException(
            status_code=400,
            detail="Veri bütünlüğü hatası: şoför zaten kayıtlı olabilir",
        )
    except DomainError:
        raise
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating driver: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Sunucu hatası")


@router.get(
    "/excel/template",
    responses=EXCEL_XLSX_RESPONSES,
    response_model=None,
    response_class=Response,
)
async def download_template(
    current_user: Annotated[Kullanici, Depends(get_current_active_user)],
):
    """Şoför yükleme için Excel şablonu indir"""
    template_data = await generate_template("sofor")
    return StreamingResponse(
        io.BytesIO(template_data),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": "attachment; filename=sofor_yukleme_sablonu.xlsx"
        },
    )


@router.get(
    "/excel/export",
    responses=EXCEL_XLSX_RESPONSES,
    response_model=None,
    response_class=Response,
)
async def export_drivers(
    current_user: Annotated[Kullanici, Depends(get_current_active_user)],
    aktif_only: bool = Query(True, description="Sadece aktif şoförler"),
    search: Optional[str] = Query(None, description="İsim veya telefon araması"),
    ehliyet_sinifi: Optional[str] = Query(None, description="Ehliyet sınıfı"),
    min_score: Optional[float] = Query(None, ge=0.1, le=2.0),
    max_score: Optional[float] = Query(None, ge=0.1, le=2.0),
):
    """Mevcut şoförleri Excel olarak indir (Filtreli & Kurumsal Format)"""
    try:
        drivers = await get_all_paged(
            skip=0,
            limit=10000,
            aktif_only=aktif_only,
            search=search,
            ehliyet_sinifi=ehliyet_sinifi,
            min_score=min_score,
            max_score=max_score,
        )

        driver_items = (
            drivers.get("items", []) if isinstance(drivers, dict) else drivers
        )
        clean_data = []
        for d in driver_items:
            clean_item = {
                "id": d.get("id"),
                "ad_soyad": d.get("ad_soyad"),
                "ehliyet_sinifi": d.get("ehliyet_sinifi", "E"),
                "ise_baslama": d.get("ise_baslama"),
                "score": d.get("score", 1.0),
                "manual_score": d.get("manual_score", 1.0),
                "aktif": "Aktif" if d.get("aktif") else "Pasif",
            }
            clean_data.append(clean_item)

        content = await export_data(clean_data, type="sofor_listesi")

        filename = (
            f"sofor_listesi_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M')}.xlsx"
        )

        return StreamingResponse(
            io.BytesIO(content),
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f"attachment; filename={filename}"},
        )
    except DomainError:
        raise
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error exporting drivers: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Excel oluşturulurken hata oluştu")


@router.post("/excel/upload", response_model=UploadResultResponse)
async def upload_drivers(
    current_admin: Annotated[Kullanici, Depends(get_current_active_admin)],
    file: UploadFile = File(...),
):
    """Excel'den toplu şoför yükle"""
    from v2.modules.import_excel.public import process_driver_import

    ALLOWED_MIME_TYPES = {
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "application/vnd.ms-excel",
        "application/octet-stream",
    }
    if file.content_type and file.content_type not in ALLOWED_MIME_TYPES:
        raise HTTPException(
            status_code=400, detail="Sadece Excel dosyaları kabul edilir."
        )

    content = await file.read()
    if len(content) > 10 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="Dosya boyutu 10MB'ı geçemez.")

    created_count, errors = await process_driver_import(content)

    return {
        "success": True,
        "message": f"{created_count} şoför yüklendi.",
        "errors": errors,
    }


@router.get("/{sofor_id}", response_model=SoforResponse)
async def read_sofor(
    sofor_id: int,
    current_user: Annotated[Kullanici, Depends(get_current_active_user)],
):
    # include_inactive=True: eski `db.get(Sofor, sofor_id)` ham PK lookup'ı
    # aktif/pasif ayrımı yapmıyordu — davranış birebir korunuyor.
    sofor = await get_by_id(sofor_id, include_inactive=True)
    if not sofor:
        raise HTTPException(status_code=404, detail="Şoför bulunamadı")
    return sofor


@router.get("/{sofor_id}/performance", response_model=DriverPerformanceSchema)
async def get_driver_performance(
    sofor_id: int,
    current_user: Annotated[Kullanici, Depends(get_current_active_user)],
):
    """
    Sürücü performans karnesini getir (AI Analizli)
    """
    sofor = await get_by_id(sofor_id, include_inactive=True)
    if not sofor:
        raise HTTPException(status_code=404, detail="Şoför bulunamadı")

    try:
        performance = await get_performance_details(sofor_id)
        return performance
    except DomainError:
        raise
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching driver performance: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Performans verileri alınamadı")


@router.get(
    "/{sofor_id}/score-breakdown",
    response_model=DriverScoreBreakdownSchema,
)
async def get_driver_score_breakdown(
    sofor_id: int,
    current_user: Annotated[Kullanici, Depends(get_current_active_user)],
):
    """Hibrit skorun ağırlık kırılımını (XAI) döner.

    `manual_score`, otomatik (performans-bazlı) `auto`, ve hesaplanan
    `total` ile ağırlıkları aynı response içinde gönderir. Frontend
    bunları görsel formül olarak gösterir.
    """
    sofor = await get_by_id(sofor_id, include_inactive=True)
    if not sofor:
        raise HTTPException(status_code=404, detail="Şoför bulunamadı")
    try:
        return await get_score_breakdown_sofor(sofor_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except DomainError:
        raise
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching driver score breakdown: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Skor kırılımı alınamadı")


@router.get(
    "/{sofor_id}/route-profile",
    response_model=DriverRouteProfileSchema,
)
async def get_driver_route_profile(
    sofor_id: int,
    current_user: Annotated[Kullanici, Depends(get_current_active_user)],
):
    """Şoförün güzergah tipi bazlı performans profilini döner.

    4 güzergah tipi (otoyol, dağlık, şehir içi, karışık) için ortalama
    gerçek/tahmini tüketim ve sapma % verilir. ``best_route_type`` en iyi
    performans gösterilen tip — yeterli veri (>=5 sefer) yoksa None.
    """
    sofor = await get_by_id(sofor_id, include_inactive=True)
    if not sofor:
        raise HTTPException(status_code=404, detail="Şoför bulunamadı")
    try:
        return await get_route_profile_sofor(sofor_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except DomainError:
        raise
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching driver route profile: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Güzergah profili alınamadı")


@router.put("/{sofor_id}", response_model=SoforResponse)
async def update_sofor(
    sofor_id: int,
    sofor_in: SoforUpdate,
    current_admin: Annotated[Kullanici, Depends(get_current_active_admin)],
):
    try:
        update_data = sofor_in.model_dump(exclude_unset=True)
        if not update_data:
            raise HTTPException(
                status_code=400, detail="Güncellenecek veri gönderilmedi"
            )

        success = await update_sofor_usecase(sofor_id, **update_data)
        if not success:
            raise HTTPException(
                status_code=404, detail="Şoför bulunamadı veya güncellenemedi"
            )

        updated_sofor = await get_by_id(sofor_id)
        await log_audit_event(
            module="sofor",
            action="update",
            entity_id=str(sofor_id),
            new_value=update_data,
            user_id=current_admin.id,
        )
        return updated_sofor

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except DomainError:
        raise
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating driver: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Sunucu hatası")


@router.delete("/bulk", response_model=Dict)
async def bulk_delete_soforler(
    current_admin: Annotated[Kullanici, Depends(get_current_active_admin)],
    ids: List[int] = Body(...),
):
    """Toplu şoför silme (Soft Delete & Optimized Transaction)."""
    if not ids:
        raise HTTPException(status_code=400, detail="Silinecek ID listesi boş olamaz")

    if len(ids) > 100:
        raise HTTPException(
            status_code=400, detail="Tek seferde en fazla 100 kayıt silinebilir"
        )

    try:
        result = await bulk_delete(ids)

        logger.info(
            f"Bulk delete completed: {result['deleted']} drivers deleted by {current_admin.email}"
        )
        await log_audit_event(
            module="sofor",
            action="bulk_delete",
            new_value={"ids": ids, "deleted": result.get("deleted")},
            user_id=current_admin.id,
        )
        return result

    except DomainError:
        raise
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in bulk delete API: {e}", exc_info=True)
        raise HTTPException(
            status_code=500, detail="Toplu silme işlemi sırasında hata oluştu"
        )


@router.delete("/{sofor_id}", response_model=Dict)
async def delete_sofor(
    sofor_id: int,
    current_admin: Annotated[Kullanici, Depends(get_current_active_admin)],
):
    """Şoför sil (Akıllı Silme / Smart Delete).

    Aktif şoförleri pasife çeker (soft-delete); zaten pasif olanlar
    kalıcı olarak silinir.  Aktif sefer kaydı olan şoförler 409
    Conflict ile reddedilir.

    Yetki: ADMIN
    """
    sofor = await get_by_id(sofor_id, include_inactive=True)
    if not sofor:
        raise HTTPException(status_code=404, detail="Şoför bulunamadı")

    was_active = sofor.get("aktif")

    try:
        success = await delete_sofor_usecase(sofor_id)
        if not success:
            raise HTTPException(status_code=404, detail="Şoför bulunamadı")

        msg = "Şoför pasife çekildi" if was_active else "Şoför tamamen silindi"
        logger.info(f"Delete action for {sofor_id}: {msg}")

        await log_audit_event(
            module="sofor",
            action="delete",
            entity_id=str(sofor_id),
            new_value={"was_active": was_active},
            user_id=current_admin.id,
        )
        return {"success": True, "message": msg}

    except DomainError:
        raise
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting driver: {e}", exc_info=True)
        if "sefer kayıtları" in str(e):
            raise HTTPException(status_code=409, detail=str(e))
        raise HTTPException(status_code=500, detail="Silme işlemi başarısız")


@router.post("/{sofor_id}/score", response_model=SoforResponse)
async def update_driver_score(
    sofor_id: int,
    current_admin: Annotated[Kullanici, Depends(get_current_active_admin)],
    score: float = Query(..., ge=0.1, le=2.0),
):
    try:
        success = await update_score(sofor_id, score)
        if not success:
            raise HTTPException(
                status_code=404, detail="Şoför bulunamadı veya puan güncellenemedi"
            )

        updated_sofor = await get_by_id(sofor_id)
        await log_audit_event(
            module="sofor",
            action="update_score",
            entity_id=str(sofor_id),
            new_value={"score": score},
            user_id=current_admin.id,
        )
        return updated_sofor

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except DomainError:
        raise
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating score via service: {e}")
        raise HTTPException(status_code=500, detail="Puan güncellenirken sunucu hatası")
