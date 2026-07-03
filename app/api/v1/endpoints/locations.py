"""
Location and route management endpoints.
"""

from typing import Annotated, Any, List, Optional, cast

from fastapi import APIRouter, Depends, File, HTTPException, Query, Response, UploadFile
from pydantic import BaseModel, Field

from app.api.deps import (
    SessionDep,
    UOWDep,
    get_current_active_admin,
    get_current_active_user,
    get_lokasyon_service,
)
from app.core.exceptions import DomainError
from app.core.services.lokasyon_hydrator import (
    LokasyonHydrator,
    get_lokasyon_hydrator,
)
from app.database.models import Kullanici
from app.database.repositories.lokasyon_repo import get_lokasyon_repo
from app.infrastructure.audit import log_audit_event
from app.infrastructure.logging.logger import get_logger
from app.infrastructure.resilience.rate_limiter import RateLimiterDependency
from app.schemas.api_responses import (
    EXCEL_XLSX_RESPONSES,
    DeleteResultResponse,
    ImportResultResponse,
    LocationStatsResponse,
    RouteAnalyzeResponse,
    RouteInfoResponse,
    StaleLocationsResponse,
)
from app.schemas.lokasyon import (
    GeocodeSuggestion,
    LokasyonCreate,
    LokasyonPaginationResponse,
    LokasyonResponse,
    LokasyonSegmentsResponse,
    LokasyonUpdate,
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
    data = await uow.lokasyon_repo.get_location_stats()
    return {"status": "success", "data": data}


@router.get("/stale", response_model=StaleLocationsResponse)
async def get_stale_locations(
    current_user: Annotated[Kullanici, Depends(get_current_active_user)],
    uow: UOWDep,
    days: int = Query(90, ge=1, le=365),
):
    """Locations not analyzed in the last N days (or never analyzed)."""
    rows = await uow.lokasyon_repo.get_stale_locations(days)
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
    from app.services.route_service import get_route_service

    route_service = get_route_service()
    route_details = await route_service.get_route_details(
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
    service: Annotated[Any, Depends(get_lokasyon_service)] = None,
) -> List[GeocodeSuggestion]:
    try:
        results = await service.geocode_query(q, limit=limit)
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
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    zorluk: Optional[str] = Query(
        None, description="Zorluk filtresi: Düz, Hafif Eğimli, Dik/Dağlık"
    ),
    search: Optional[str] = Query(None, description="Arama metni (şehir, notlar)"),
    service: Annotated[Any, Depends(get_lokasyon_service)] = None,
):
    """List locations through the service layer."""
    try:
        return await service.get_all_paged(
            skip=skip, limit=limit, zorluk=zorluk, search=search
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
    service: Annotated[Any, Depends(get_lokasyon_service)] = None,
):
    """Create a new location."""
    from app.core.services.lokasyon_service import LokasyonService

    service = LokasyonService(
        repo=uow.lokasyon_repo, event_bus=getattr(service, "event_bus", None)
    )
    try:
        lokasyon_id = await service.add_lokasyon(lokasyon)
        await uow.commit()
        created = await uow.lokasyon_repo.get_by_id(lokasyon_id)

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
    service: Annotated[Any, Depends(get_lokasyon_service)] = None,
):
    """Return location details."""
    location = await service.repo.get_by_id(lokasyon_id)
    if not location:
        raise HTTPException(status_code=404, detail="Güzergah bulunamadı")
    return LokasyonResponse.model_validate(dict(location))


@router.put("/{lokasyon_id:int}", response_model=LokasyonResponse)
async def update_lokasyon(
    lokasyon_id: int,
    lokasyon_in: LokasyonUpdate,
    uow: UOWDep,
    current_admin: Annotated[Kullanici, Depends(get_current_active_admin)],
    service: Annotated[Any, Depends(get_lokasyon_service)] = None,
):
    """Update a location."""
    from app.core.services.lokasyon_service import LokasyonService

    service = LokasyonService(
        repo=uow.lokasyon_repo, event_bus=getattr(service, "event_bus", None)
    )
    try:
        # include_inactive=True: pasif bir lokasyon güncellenirken (reaktive
        # etmeden, örn. sadece notlar) bu fetch'lerin None dönüp aşağıdaki
        # `dict(updated_loc)`'u çökertmemesi gerekiyor.
        # Audit Snapshot: Pre
        current_loc = await service.repo.get_by_id(lokasyon_id, include_inactive=True)
        pre_snapshot = dict(current_loc) if current_loc else {}

        success = await service.update_lokasyon(lokasyon_id, lokasyon_in)
        if not success:
            raise HTTPException(status_code=404, detail="Güzergah bulunamadı")
        await uow.commit()

        # Audit Snapshot: Post
        updated_loc = await service.repo.get_by_id(lokasyon_id, include_inactive=True)
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
    except HTTPException:
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
    service: Annotated[Any, Depends(get_lokasyon_service)] = None,
):
    """Delete a location."""
    from app.core.services.lokasyon_service import LokasyonService

    service = LokasyonService(
        repo=uow.lokasyon_repo, event_bus=getattr(service, "event_bus", None)
    )
    # include_inactive=True: bu endpoint pasif (soft-deleted) kayıtları da
    # görmesi gerekiyor — `was_active` hesabı ve hard-delete yolu buna dayanır.
    current = await service.repo.get_by_id(lokasyon_id, include_inactive=True)
    if not current:
        raise HTTPException(status_code=404, detail="Güzergah bulunamadı")

    was_active = current.get("aktif", False)

    try:
        success = await service.delete_lokasyon(lokasyon_id)
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
    except HTTPException:
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
    routes = await uow.lokasyon_repo.search_by_route_names(cikis, varis)

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
    return await uow.lokasyon_repo.get_benzersiz_lokasyonlar()


@router.post("/{lokasyon_id:int}/analyze", response_model=RouteAnalyzeResponse)
async def analyze_with_openroute(
    lokasyon_id: int,
    uow: UOWDep,
    current_admin: Annotated[Kullanici, Depends(get_current_active_admin)],
    service: Annotated[Any, Depends(get_lokasyon_service)] = None,
):
    """Analyze a location with the live route provider."""
    from app.core.services.lokasyon_service import LokasyonService

    service = LokasyonService(
        repo=uow.lokasyon_repo, event_bus=getattr(service, "event_bus", None)
    )
    try:
        result = await service.analyze_route(lokasyon_id)
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
    except HTTPException:
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
    from app.core.services.excel_service import ExcelService

    content = await ExcelService.generate_template("guzergah")
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
    service: Annotated[Any, Depends(get_lokasyon_service)] = None,
):
    """Export locations as Excel."""
    from app.core.services.excel_service import ExcelService

    data = await service.repo.get_all()
    content = await ExcelService.export_data(data, type="lokasyon_listesi")

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
    from app.core.services.import_service import get_import_service

    service = get_import_service()
    content = await file.read()
    if len(content) > _MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"Dosya boyutu sınırı aşıldı (maks {_MAX_UPLOAD_BYTES // 1024 // 1024} MB).",
        )
    count, errors = await service.import_routes(content)
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
    sim = await repo.get_with_segments(lokasyon_id)
    if sim is None:
        raise HTTPException(status_code=404, detail="Güzergah bulunamadı")

    if (
        sim.cikis_lat is None
        or sim.cikis_lon is None
        or sim.varis_lat is None
        or sim.varis_lon is None
    ):
        raise HTTPException(
            status_code=422,
            detail="Lokasyon koordinatları eksik (cikis/varis lat-lon)",
        )

    result = await hydrator.hydrate(sim)
    if result is None:
        raise HTTPException(
            status_code=502, detail="Routing provider (Mapbox) unavailable"
        )

    await db.commit()
    return HydrationStats(
        lokasyon_id=result.lokasyon_id,
        raw_segment_count=result.raw_segment_count,
        resampled_segment_count=result.resampled_segment_count,
        elevation_coverage_pct=result.elevation_coverage_pct,
        total_km=result.total_km,
        total_ascent_m=result.total_ascent_m,
        total_descent_m=result.total_descent_m,
        hydrated_at=sim.hydrated_at,
    )


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
    lok = await repo.get_with_segments(lokasyon_id)
    if lok is None:
        raise HTTPException(status_code=404, detail="Güzergah bulunamadı")

    return LokasyonSegmentsResponse(
        lokasyon_id=lok.id,
        ad=lok.ad,
        hydrated_at=lok.hydrated_at,
        raw_segment_count=lok.raw_segment_count,
        resampled_segment_count=lok.resampled_segment_count,
        elevation_coverage_pct=lok.elevation_coverage_pct,
        segments=cast(
            "Any",
            [
                {
                    "seq": s.seq,
                    "length_km": round(s.length_km, 3),
                    "grade_pct": round(s.grade_pct, 2),
                    "road_class": s.road_class,
                    "maxspeed_kmh": s.maxspeed_kmh,
                    "mid_lon": s.mid_lon,
                    "mid_lat": s.mid_lat,
                }
                for s in lok.segments
            ],
        ),
    )
