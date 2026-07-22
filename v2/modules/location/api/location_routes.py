"""
Location and route management endpoints.
"""

from typing import Annotated, Any, List, Optional, cast

from fastapi import APIRouter, Depends, File, HTTPException, Query, Response, UploadFile
from pydantic import BaseModel, Field

from app.api.deps import SessionDep, UOWDep
from v2.modules.auth_rbac.public import (
    Kullanici,
    get_current_active_admin,
    get_current_active_user,
)
from v2.modules.location.application.analyze_location_route import (
    analyze_location_route,
)
from v2.modules.location.application.create_location import create_location
from v2.modules.location.application.delete_location import delete_location
from v2.modules.location.application.geocode_location import (
    geocode_location as geocode_location_usecase,
)
from v2.modules.location.application.get_all_locations import get_all_locations
from v2.modules.location.application.get_location_by_id import get_location_by_id
from v2.modules.location.application.get_location_segments import (
    get_location_segments as get_location_segments_usecase,
)
from v2.modules.location.application.get_location_stats import (
    get_location_stats as get_location_stats_usecase,
)
from v2.modules.location.application.get_stale_locations import (
    get_stale_locations as get_stale_locations_usecase,
)
from v2.modules.location.application.get_unique_location_names import (
    get_unique_location_names,
)
from v2.modules.location.application.hydrate_location import (
    hydrate_location as hydrate_location_usecase,
)
from v2.modules.location.application.hydration import (
    LokasyonHydrator,
    get_lokasyon_hydrator,
)
from v2.modules.location.application.list_locations import list_locations
from v2.modules.location.application.search_locations_by_route import (
    search_locations_by_route,
)
from v2.modules.location.application.update_location import update_location
from v2.modules.location.infrastructure.repository import get_lokasyon_repo
from v2.modules.location.schemas import (
    GeocodeSuggestion,
    LocationStatsResponse,
    LokasyonCreate,
    LokasyonPaginationResponse,
    LokasyonResponse,
    LokasyonSegmentsResponse,
    LokasyonUpdate,
    RouteAnalyzeResponse,
    RouteInfoResponse,
    StaleLocationsResponse,
)
from v2.modules.platform_infra.audit import log_audit_event
from v2.modules.platform_infra.logging.logger import get_logger
from v2.modules.platform_infra.resilience.rate_limiter import RateLimiterDependency
from v2.modules.shared_kernel.exceptions import DomainError
from v2.modules.shared_kernel.schemas.api_responses import (
    EXCEL_XLSX_RESPONSES,
    DeleteResultResponse,
    ImportResultResponse,
)

logger = get_logger(__name__)

router = APIRouter()


class RouteSearchResponse(BaseModel):
    found: bool
    count: int
    location: Optional[LokasyonResponse] = None
    routes: List[LokasyonResponse] = Field(default_factory=list)


@router.get("/stats", response_model=LocationStatsResponse)
async def get_location_stats(
    current_user: Annotated[Kullanici, Depends(get_current_active_user)],
    uow: UOWDep,
):
    """Fleet-wide location statistics for KPI cards."""
    data = await get_location_stats_usecase(uow.lokasyon_repo)
    return {"status": "success", "data": data}


@router.get("/stale", response_model=StaleLocationsResponse)
async def get_stale_locations(
    current_user: Annotated[Kullanici, Depends(get_current_active_user)],
    uow: UOWDep,
    days: int = Query(90, ge=1, le=365),
):
    """Locations not analyzed in the last N days (or never analyzed)."""
    rows = await get_stale_locations_usecase(uow.lokasyon_repo, days)
    return {
        "status": "success",
        "data": rows,
        "threshold_days": days,
    }


@router.get("/route-info", response_model=RouteInfoResponse)
async def get_route_info(
    current_user: Annotated[Kullanici, Depends(get_current_active_user)],
    cikis_lat: float = Query(..., description="Çıkış enlemi"),
    cikis_lon: float = Query(..., description="Çıkış boylamı"),
    varis_lat: float = Query(..., description="Varış enlemi"),
    varis_lon: float = Query(..., description="Varış boylamı"),
) -> RouteInfoResponse:
    """Return live route details for a coordinate pair."""
    from v2.modules.route_simulation.public import get_route_details

    route_details = await get_route_details(
        start_coords=(cikis_lon, cikis_lat),
        end_coords=(varis_lon, varis_lat),
        use_cache=True,
    )

    if "error" in route_details:
        status_hint = (
            f" (provider_status={route_details['provider_status']})"
            if "provider_status" in route_details
            else ""
        )
        raise HTTPException(
            status_code=503,
            detail=route_details.get(
                "error", "Route provider is currently unavailable."
            )
            + status_hint,
        )

    return RouteInfoResponse.model_validate(route_details)


@router.get("/geocode", response_model=List[GeocodeSuggestion])
async def geocode_location(
    q: str = Query(..., min_length=2, description="Adres veya tesis arama metni"),
    limit: int = Query(5, ge=1, le=10),
    current_user: Annotated[Kullanici, Depends(get_current_active_user)] = None,
) -> List[GeocodeSuggestion]:
    try:
        results = await geocode_location_usecase(q, limit=limit)
        return [GeocodeSuggestion.model_validate(result) for result in results]
    except DomainError:
        raise
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Error geocoding location query '%s': %s", q, exc, exc_info=True)
        raise HTTPException(status_code=500, detail="Geocode araması başarısız")


@router.get("/", response_model=LokasyonPaginationResponse)
async def list_lokasyonlar(
    current_user: Annotated[Kullanici, Depends(get_current_active_user)],
    uow: UOWDep,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    zorluk: Optional[str] = Query(
        None, description="Zorluk filtresi: Düz, Hafif Eğimli, Dik/Dağlık"
    ),
    search: Optional[str] = Query(None, description="Arama metni (şehir, notlar)"),
):
    """List locations through the application layer."""
    try:
        return await list_locations(
            uow.lokasyon_repo, skip=skip, limit=limit, zorluk=zorluk, search=search
        )
    except DomainError:
        raise
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Error listing locations: %s", exc)
        raise HTTPException(status_code=500, detail="Liste alınırken hata oluştu")


@router.post("/", response_model=LokasyonResponse, status_code=201)
async def create_lokasyon(
    lokasyon: LokasyonCreate,
    uow: UOWDep,
    current_admin: Annotated[Kullanici, Depends(get_current_active_admin)],
):
    """Create a new location."""
    try:
        lokasyon_id = await create_location(uow.lokasyon_repo, lokasyon)
        await uow.commit()
        created = await get_location_by_id(uow.lokasyon_repo, lokasyon_id)

        await log_audit_event(
            module="location",
            action="create",
            entity_id=str(lokasyon_id),
            old_value={},
            new_value=dict(created),
            user_id=current_admin.id,
        )
        return LokasyonResponse.model_validate(dict(created))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except DomainError:
        raise
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Error creating location: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail="Sunucu hatası")


@router.get("/{lokasyon_id:int}", response_model=LokasyonResponse)
async def get_lokasyon(
    lokasyon_id: int,
    current_user: Annotated[Kullanici, Depends(get_current_active_user)],
    uow: UOWDep,
):
    """Return location details."""
    location = await get_location_by_id(uow.lokasyon_repo, lokasyon_id)
    if not location:
        raise HTTPException(status_code=404, detail="Güzergah bulunamadı")
    return LokasyonResponse.model_validate(dict(location))


@router.put("/{lokasyon_id:int}", response_model=LokasyonResponse)
async def update_lokasyon(
    lokasyon_id: int,
    lokasyon_in: LokasyonUpdate,
    uow: UOWDep,
    current_admin: Annotated[Kullanici, Depends(get_current_active_admin)],
):
    """Update a location."""
    try:
        # include_inactive=True: pasif bir lokasyon güncellenirken (reaktive
        # etmeden, örn. sadece notlar) bu fetch'lerin None dönüp aşağıdaki
        # `dict(updated_loc)`'u çökertmemesi gerekiyor.
        # Audit Snapshot: Pre
        current_loc = await get_location_by_id(
            uow.lokasyon_repo, lokasyon_id, include_inactive=True
        )
        pre_snapshot = dict(current_loc) if current_loc else {}

        success = await update_location(uow.lokasyon_repo, lokasyon_id, lokasyon_in)
        if not success:
            raise HTTPException(status_code=404, detail="Güzergah bulunamadı")
        await uow.commit()

        # Audit Snapshot: Post
        updated_loc = await get_location_by_id(
            uow.lokasyon_repo, lokasyon_id, include_inactive=True
        )
        post_snapshot = dict(updated_loc) if updated_loc else {}

        await log_audit_event(
            module="location",
            action="update",
            entity_id=str(lokasyon_id),
            old_value=pre_snapshot,
            new_value=post_snapshot,
            user_id=current_admin.id,
        )
        return LokasyonResponse.model_validate(dict(updated_loc))
    except HTTPException:
        raise
    except DomainError:
        raise
    except Exception as exc:
        logger.error("Error updating location: %s", exc)
        raise HTTPException(status_code=500, detail="Sunucu hatası")


@router.delete("/{lokasyon_id:int}", response_model=DeleteResultResponse)
async def delete_lokasyon(
    lokasyon_id: int,
    uow: UOWDep,
    current_admin: Annotated[Kullanici, Depends(get_current_active_admin)],
    response: Response,
):
    """Delete a location."""
    # include_inactive=True: bu endpoint pasif (soft-deleted) kayıtları da
    # görmesi gerekiyor — `was_active` hesabı ve hard-delete yolu buna dayanır.
    current = await get_location_by_id(
        uow.lokasyon_repo, lokasyon_id, include_inactive=True
    )
    if not current:
        raise HTTPException(status_code=404, detail="Güzergah bulunamadı")

    was_active = current.get("aktif", False)

    try:
        success = await delete_location(uow.lokasyon_repo, lokasyon_id)
        if not success:
            raise HTTPException(status_code=404, detail="Güzergah bulunamadı")
        await uow.commit()

        if not was_active:
            response.headers["X-Delete-Type"] = "Hard Delete"

        return {
            "success": True,
            "deleted_id": lokasyon_id,
            "mode": "Hard" if not was_active else "Soft",
        }
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except HTTPException:
        raise
    except DomainError:
        raise
    except Exception as exc:
        logger.error("Error deleting location: %s", exc)
        raise HTTPException(status_code=500, detail="Sunucu hatası")


@router.get("/search/by-route", response_model=RouteSearchResponse)
async def search_by_route(
    uow: UOWDep,
    current_user: Annotated[Kullanici, Depends(get_current_active_user)],
    cikis: str = Query(..., description="Çıkış yeri"),
    varis: str = Query(..., description="Varış yeri"),
):
    """Search locations by start and destination names."""
    routes = await search_locations_by_route(uow.lokasyon_repo, cikis, varis)

    return {
        "found": len(routes) > 0,
        "count": len(routes),
        "location": LokasyonResponse.model_validate(routes[0]) if routes else None,
        "routes": [LokasyonResponse.model_validate(route) for route in routes],
    }


@router.get("/unique-names", response_model=List[str])
async def get_unique_names(
    current_user: Annotated[Kullanici, Depends(get_current_active_user)],
    uow: UOWDep,
):
    """Return unique location names for autocomplete."""
    return await get_unique_location_names(uow.lokasyon_repo)


@router.post("/{lokasyon_id:int}/analyze", response_model=RouteAnalyzeResponse)
async def analyze_with_openroute(
    lokasyon_id: int,
    uow: UOWDep,
    current_admin: Annotated[Kullanici, Depends(get_current_active_admin)],
):
    """Analyze a location with the live route provider."""
    try:
        result = await analyze_location_route(uow.lokasyon_repo, lokasyon_id)
        if isinstance(result, dict) and result.get("error"):
            raise HTTPException(
                status_code=503,
                detail=result.get("error", "Route analysis is currently unavailable."),
            )

        await uow.commit()
        return {
            "success": True,
            "api_mesafe_km": result.get("distance_km"),
            "api_sure_saat": round(result.get("duration_min", 0) / 60, 2),
            "ascent_m": result.get("ascent_m"),
            "descent_m": result.get("descent_m"),
            "otoban_mesafe_km": result.get("otoban_mesafe_km"),
            "sehir_ici_mesafe_km": result.get("sehir_ici_mesafe_km"),
            "source": result.get("source"),
            "is_corrected": result.get("is_corrected", False),
            "correction_reason": result.get("correction_reason"),
            "route_analysis": result.get("route_analysis") or result.get("details"),
            "elevation_profile": result.get("elevation_profile", []),
        }
    except ValueError as exc:
        message = str(exc)
        if "Analiz" in message or "analiz" in message:
            raise HTTPException(status_code=503, detail=message)
        raise HTTPException(status_code=400, detail=message)
    except HTTPException:
        raise
    except DomainError:
        raise
    except Exception as exc:
        logger.error("Error analyzing route: %s", exc)
        raise HTTPException(status_code=500, detail="Analiz başarısız")


@router.get(
    "/excel/template",
    responses=EXCEL_XLSX_RESPONSES,
    response_model=None,
    response_class=Response,
)
async def get_excel_template(
    current_user: Annotated[Kullanici, Depends(get_current_active_user)],
):
    """Download the location import template."""
    from v2.modules.import_excel.public import generate_template

    content = await generate_template("guzergah")
    return Response(
        content=content,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": "attachment; filename=guzergah_yukleme_sablonu.xlsx"
        },
    )


@router.get(
    "/excel/export",
    responses=EXCEL_XLSX_RESPONSES,
    response_model=None,
    response_class=Response,
)
async def export_locations(
    current_user: Annotated[Kullanici, Depends(get_current_active_user)],
    uow: UOWDep,
):
    """Export locations as Excel."""
    from v2.modules.import_excel.public import export_data

    data = await get_all_locations(uow.lokasyon_repo)
    content = await export_data(data, type="lokasyon_listesi")

    return Response(
        content=content,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=guzergahlar.xlsx"},
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
            detail=(
                f"Desteklenmeyen dosya tipi: {file.content_type}."
                " Yalnız .xlsx/.xls yüklenir."
            ),
        )
    filename = file.filename or ""
    if filename and not (filename.endswith(".xlsx") or filename.endswith(".xls")):
        raise HTTPException(
            status_code=415,
            detail="Yalnız .xlsx veya .xls uzantılı dosyalar kabul edilir.",
        )


@router.post("/upload", response_model=ImportResultResponse)
async def upload_guzergahlar(
    file: UploadFile = File(...),
    current_user: Annotated[Kullanici, Depends(get_current_active_admin)] = None,
):
    """Upload routes from an Excel file."""
    _validate_excel_upload(file)
    from v2.modules.import_excel.public import import_routes

    content = await file.read()
    if len(content) > _MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"Dosya boyutu sınırı aşıldı (maks {_MAX_UPLOAD_BYTES // 1024 // 1024} MB).",
        )
    count, errors = await import_routes(content)
    return {"count": count, "errors": errors}


# -------------------------------------------------------------------------
# Phase 3.2 — Lokasyon hidrate endpoint
# Yolun ham haritasını (500m bucket'lar) Mapbox + Open-Meteo ile hesaplar
# ve LokasyonSegment kayıtlarına persist eder. Sefer simülasyonu (Phase 3.3)
# bu hidrate veriyi ton/arac_yasi ile birleştirerek yakıt tahmini üretir.
# -------------------------------------------------------------------------


class HydrationStats(BaseModel):
    """POST /locations/{id}/hydrate response."""

    lokasyon_id: int
    raw_segment_count: int
    resampled_segment_count: int
    elevation_coverage_pct: float
    total_km: float
    total_ascent_m: float
    total_descent_m: float
    hydrated_at: Optional[Any] = None


@router.post(
    "/{lokasyon_id:int}/hydrate",
    response_model=HydrationStats,
    dependencies=[
        # Mapbox + Open-Meteo cost koruması (5 req / dk / IP)
        Depends(RateLimiterDependency("locations_hydrate", rate=5.0, period=60.0)),
    ],
)
async def hydrate_lokasyon(
    lokasyon_id: int,
    db: SessionDep,
    # Mutates shared route data (deletes + reinserts segments, commits) and burns
    # Mapbox/Open-Meteo quota — gate on admin like every other location mutation
    # (create/update/delete/analyze/upload), not merely an authenticated user.
    current_admin: Annotated[Kullanici, Depends(get_current_active_admin)],
    hydrator: Annotated[LokasyonHydrator, Depends(get_lokasyon_hydrator)],
) -> HydrationStats:
    """Lokasyona ait ham güzergah verisini hesapla + persist.

    Idempotent: yeniden çağrılırsa eski segment'ler silinir + yeniden insert
    (cascade delete-orphan).
    """
    # get_lokasyon_repo(session=db): must share `db`'s session/transaction —
    # `hydrator.hydrate()` mutates `sim.segments` in-memory and relies on the
    # caller committing the SAME session afterward (see its docstring). A
    # separate UoW session here would silently lose the hydration write.
    repo = get_lokasyon_repo(session=db)
    try:
        stats = await hydrate_location_usecase(repo, hydrator, lokasyon_id)
    except ValueError as exc:
        reason = str(exc)
        if reason == "not_found":
            raise HTTPException(status_code=404, detail="Güzergah bulunamadı")
        if reason == "missing_coords":
            raise HTTPException(
                status_code=422,
                detail="Lokasyon koordinatları eksik (cikis/varis lat-lon)",
            )
        raise HTTPException(
            status_code=502, detail="Routing provider (Mapbox) unavailable"
        )

    await db.commit()
    return HydrationStats(**stats)


@router.get("/{lokasyon_id:int}/segments", response_model=LokasyonSegmentsResponse)
async def get_lokasyon_segments(
    lokasyon_id: int,
    db: SessionDep,
    current_user: Annotated[Kullanici, Depends(get_current_active_user)],
) -> LokasyonSegmentsResponse:
    """Lokasyonun hidrate edilmiş 500m bucket'larını döner (Phase 3.4).

    UI map polyline + per-segment popup için pratik endpoint.
    404 if lokasyon yok. Segments boş döndürebilir (henüz hidrate
    edilmemiş güzergah) — UI uyarı gösterip /hydrate butonu önerebilir.
    """
    repo = get_lokasyon_repo(session=db)
    data = await get_location_segments_usecase(repo, lokasyon_id)
    if data is None:
        raise HTTPException(status_code=404, detail="Güzergah bulunamadı")

    return LokasyonSegmentsResponse(
        lokasyon_id=data["lokasyon_id"],
        ad=data["ad"],
        hydrated_at=data["hydrated_at"],
        raw_segment_count=data["raw_segment_count"],
        resampled_segment_count=data["resampled_segment_count"],
        elevation_coverage_pct=data["elevation_coverage_pct"],
        segments=cast("Any", data["segments"]),
    )
