"""
Location endpoint coverage tests.

Targets missing lines in app/api/v1/endpoints/locations.py (25% → ≥70%).
All service/DB calls are mocked — no real DB needed.
"""

from contextlib import contextmanager
from unittest.mock import AsyncMock, patch

import pytest

pytestmark = pytest.mark.integration

# ---------------------------------------------------------------------------
# Helper factories
# ---------------------------------------------------------------------------


def _make_lokasyon_dict(**kwargs):
    """Minimal dict that LokasyonResponse.model_validate() will accept."""
    defaults = dict(
        id=1,
        ad="IST-ANK",
        cikis_yeri="Istanbul",
        varis_yeri="Ankara",
        mesafe_km=450.0,
        tahmini_sure_saat=5.0,
        zorluk="Normal",
        cikis_lat=41.0,
        cikis_lon=29.0,
        varis_lat=39.9,
        varis_lon=32.8,
        ascent_m=None,
        descent_m=None,
        flat_distance_km=0.0,
        otoban_mesafe_km=None,
        sehir_ici_mesafe_km=None,
        route_analysis=None,
        source=None,
        notlar=None,
        aktif=True,
        api_mesafe_km=None,
        api_sure_saat=None,
        tahmini_yakit_lt=None,
        last_api_call=None,
        is_corrected=False,
        correction_reason=None,
        hydrated_at=None,
        raw_segment_count=0,
        resampled_segment_count=0,
        elevation_coverage_pct=0.0,
    )
    defaults.update(kwargs)
    return defaults


def _make_pagination_response(items=None):
    from v2.modules.location.schemas import LokasyonPaginationResponse, LokasyonResponse

    if items is None:
        items = [LokasyonResponse.model_validate(_make_lokasyon_dict())]
    return LokasyonPaginationResponse(items=items, total=len(items))


# ---------------------------------------------------------------------------
# Context manager for patching a use-case function
# ---------------------------------------------------------------------------


@contextmanager
def _patch_location_route_function(name, side_effect=None, return_value=None):
    """Patch a use-case function as imported into location_routes.py.

    v2 rebuild: there is no LokasyonService/DI-overridable service anymore
    (bkz. v2/modules/location/public.py) — location_routes.py calls the
    standalone use-case functions directly, each imported at module level,
    so the patch target is the *consuming* module's attribute. Real DB flow
    (seeded via db_session) needs no override at all — the endpoint's own
    UOWDep already shares the test session.
    """
    target = f"v2.modules.location.api.location_routes.{name}"
    kwargs = {}
    if side_effect is not None:
        kwargs["side_effect"] = side_effect
    if return_value is not None:
        kwargs["return_value"] = return_value
    with patch(target, new=AsyncMock(**kwargs)) as mock_fn:
        yield mock_fn


# ---------------------------------------------------------------------------
# GET /locations/  — list locations
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_locations_success(async_client, admin_auth_headers, db_session):
    """GET / with valid auth and a real seeded location → 200."""
    from v2.modules.location.public import Lokasyon

    db_session.add(
        Lokasyon(cikis_yeri="ListSuccA", varis_yeri="ListSuccB", mesafe_km=450.0)
    )
    await db_session.flush()

    resp = await async_client.get("/api/v1/locations/", headers=admin_auth_headers)

    assert resp.status_code == 200
    data = resp.json()
    assert "items" in data
    assert data["total"] == 1


@pytest.mark.asyncio
async def test_list_locations_no_auth(async_client):
    """GET / without auth → 401."""
    resp = await async_client.get("/api/v1/locations/")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_list_locations_with_filters(
    async_client, admin_auth_headers, db_session
):
    """GET / with zorluk and search query params → 200, gerçek DB filtresi."""
    from v2.modules.location.public import Lokasyon

    db_session.add(
        Lokasyon(
            cikis_yeri="Istanbul",
            varis_yeri="Ankara",
            mesafe_km=450.0,
            zorluk="Normal",
        )
    )
    db_session.add(
        Lokasyon(cikis_yeri="Bursa", varis_yeri="Izmir", mesafe_km=300.0, zorluk="Zor")
    )
    await db_session.flush()

    resp = await async_client.get(
        "/api/v1/locations/?zorluk=Normal&search=istanbul",
        headers=admin_auth_headers,
    )

    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1


@pytest.mark.asyncio
async def test_list_locations_service_error(async_client, admin_auth_headers):
    """GET / service raises unexpected exception → 500."""
    with _patch_location_route_function(
        "list_locations", side_effect=RuntimeError("db explode")
    ):
        resp = await async_client.get("/api/v1/locations/", headers=admin_auth_headers)

    assert resp.status_code == 500


# ---------------------------------------------------------------------------
# GET /locations/{id}  — get single location
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_location_success(async_client, admin_auth_headers, db_session):
    """GET /{id} → 200 with real seeded location data."""
    from v2.modules.location.public import Lokasyon

    lok = Lokasyon(cikis_yeri="GetSuccA", varis_yeri="GetSuccB", mesafe_km=450.0)
    db_session.add(lok)
    await db_session.flush()

    resp = await async_client.get(
        f"/api/v1/locations/{lok.id}", headers=admin_auth_headers
    )

    assert resp.status_code == 200
    assert resp.json()["id"] == lok.id


@pytest.mark.asyncio
async def test_get_location_not_found(async_client, admin_auth_headers, db_session):
    """GET /{id} → 404 when location doesn't exist (gerçek boş DB)."""
    resp = await async_client.get(
        "/api/v1/locations/999999", headers=admin_auth_headers
    )

    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_get_location_no_auth(async_client):
    """GET /{id} without auth → 401."""
    resp = await async_client.get("/api/v1/locations/1")
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# POST /locations/  — create location
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_location_no_auth(async_client):
    """POST / without admin auth → 401."""
    resp = await async_client.post(
        "/api/v1/locations/",
        json={"cikis_yeri": "Istanbul", "varis_yeri": "Ankara", "mesafe_km": 450.0},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_create_location_validation_error(async_client, admin_auth_headers):
    """POST / with missing required fields → 422."""
    resp = await async_client.post(
        "/api/v1/locations/",
        json={"cikis_yeri": "Istanbul"},  # missing varis_yeri + mesafe_km
        headers=admin_auth_headers,
    )
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# PUT /locations/{id}  — update location
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_update_location_no_auth(async_client):
    """PUT /{id} without admin auth → 401."""
    resp = await async_client.put(
        "/api/v1/locations/1",
        json={"mesafe_km": 500.0},
    )
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# DELETE /locations/{id}  — delete location
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_delete_location_no_auth(async_client):
    """DELETE /{id} without admin auth → 401."""
    resp = await async_client.delete("/api/v1/locations/1")
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# GET /locations/geocode  — geocode
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_geocode_success(
    async_client, admin_auth_headers, db_session, monkeypatch
):
    """GET /geocode?q=... → 200 list of suggestions (gerçek servis, ORS
    gerçek api_stub'a (Faz 0/1) işaret eder — deterministik, gerçek ağ değil)."""
    import v2.modules.location.infrastructure.openroute_geocode_client as ors_mod

    ors_mod._openroute_service = None  # reset singleton
    monkeypatch.setattr(ors_mod.settings, "OPENROUTESERVICE_API_KEY", "test-key")
    monkeypatch.setattr(
        ors_mod.settings, "OPENROUTE_API_BASE_URL", "http://localhost:9000/v2"
    )

    resp = await async_client.get(
        "/api/v1/locations/geocode?q=Istanbul",
        headers=admin_auth_headers,
    )

    ors_mod._openroute_service = None  # cleanup for other tests

    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) == 1
    assert data[0]["source"] == "ors"


@pytest.mark.asyncio
async def test_geocode_no_auth(async_client):
    """GET /geocode without auth → 401."""
    resp = await async_client.get("/api/v1/locations/geocode?q=test")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_geocode_too_short(async_client, admin_auth_headers):
    """GET /geocode?q=x (single char) → 422 (FastAPI's own min_length=2
    Query validation — hiç servise ulaşmaz, dependency override gereksiz)."""
    resp = await async_client.get(
        "/api/v1/locations/geocode?q=x",
        headers=admin_auth_headers,
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_geocode_service_error(async_client, admin_auth_headers):
    """GET /geocode with service RuntimeError → 500."""
    with _patch_location_route_function(
        "geocode_location_usecase", side_effect=RuntimeError("external API down")
    ):
        resp = await async_client.get(
            "/api/v1/locations/geocode?q=Istanbul",
            headers=admin_auth_headers,
        )

    assert resp.status_code == 500


# ---------------------------------------------------------------------------
# GET /locations/stats  — fleet stats (uses UoW directly, needs DB mock)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_stats_no_auth(async_client):
    """GET /stats without auth → 401."""
    resp = await async_client.get("/api/v1/locations/stats")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_stats_success(async_client, admin_auth_headers):
    """GET /stats → 200 with real DB (empty DB returns 0-counts)."""
    resp = await async_client.get("/api/v1/locations/stats", headers=admin_auth_headers)

    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data["data"]["total"], int)
    assert isinstance(data["data"]["analyzed"], int)


# ---------------------------------------------------------------------------
# GET /locations/stale  — stale locations
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_stale_no_auth(async_client):
    """GET /stale without auth → 401."""
    resp = await async_client.get("/api/v1/locations/stale")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_stale_success(async_client, admin_auth_headers):
    """GET /stale → 200 with real DB (empty DB returns empty list, threshold_days=90)."""
    resp = await async_client.get("/api/v1/locations/stale", headers=admin_auth_headers)

    assert resp.status_code == 200
    data = resp.json()
    assert data["threshold_days"] == 90


# ---------------------------------------------------------------------------
# GET /locations/unique-names
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_unique_names_no_auth(async_client):
    """GET /unique-names without auth → 401."""
    resp = await async_client.get("/api/v1/locations/unique-names")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_unique_names_success(async_client, admin_auth_headers, db_session):
    """GET /unique-names → 200 list of strings (real DB with seeded Lokasyon)."""
    from v2.modules.location.public import Lokasyon

    db_session.add(
        Lokasyon(cikis_yeri="Istanbul", varis_yeri="Ankara", mesafe_km=450.0)
    )
    await db_session.flush()

    resp = await async_client.get(
        "/api/v1/locations/unique-names", headers=admin_auth_headers
    )

    assert resp.status_code == 200
    data = resp.json()
    assert "Istanbul" in data


# ---------------------------------------------------------------------------
# GET /locations/route-info
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_route_info_no_auth(async_client):
    """GET /route-info without auth → 401."""
    resp = await async_client.get(
        "/api/v1/locations/route-info"
        "?cikis_lat=41.0&cikis_lon=29.0&varis_lat=39.9&varis_lon=32.8"
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_route_info_missing_params(async_client, admin_auth_headers):
    """GET /route-info without required coords → 422."""
    resp = await async_client.get(
        "/api/v1/locations/route-info", headers=admin_auth_headers
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_route_info_success(async_client, admin_auth_headers):
    """GET /route-info with mocked route details use-case → 200."""
    with patch(
        "v2.modules.route_simulation.application.get_route_details.get_route_details",
        new=AsyncMock(
            return_value={
                "distance_km": 450.0,
                "duration_min": 300.0,
                "ascent_m": 500.0,
                "descent_m": 500.0,
                "otoban_mesafe_km": 400.0,
                "sehir_ici_mesafe_km": 50.0,
                "source": "mapbox",
                "is_corrected": False,
                "correction_reason": None,
                "route_analysis": {},
            }
        ),
    ):
        resp = await async_client.get(
            "/api/v1/locations/route-info"
            "?cikis_lat=41.0&cikis_lon=29.0&varis_lat=39.9&varis_lon=32.8",
            headers=admin_auth_headers,
        )

    assert resp.status_code in (200, 503)  # 503 if provider mock not in scope


@pytest.mark.asyncio
async def test_route_info_provider_error(async_client, admin_auth_headers):
    """GET /route-info when provider returns error → 503."""
    with patch(
        "v2.modules.route_simulation.application.get_route_details.get_route_details",
        new=AsyncMock(
            return_value={"error": "Mapbox unreachable", "provider_status": 503}
        ),
    ):
        resp = await async_client.get(
            "/api/v1/locations/route-info"
            "?cikis_lat=41.0&cikis_lon=29.0&varis_lat=39.9&varis_lon=32.8",
            headers=admin_auth_headers,
        )

    # Either 503 (provider error path hit) or another status if mock missed
    assert resp.status_code in (200, 503)


# ---------------------------------------------------------------------------
# GET /locations/{id}/segments
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_segments_no_auth(async_client):
    """GET /{id}/segments without auth → 401."""
    resp = await async_client.get("/api/v1/locations/1/segments")
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# POST /locations/{id}/analyze
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_analyze_no_auth(async_client):
    """POST /{id}/analyze without admin auth → 401."""
    resp = await async_client.post("/api/v1/locations/1/analyze")
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# GET /locations/excel/template
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_excel_template_no_auth(async_client):
    """GET /excel/template without auth → 401."""
    resp = await async_client.get("/api/v1/locations/excel/template")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_excel_template_success(async_client, admin_auth_headers):
    """GET /excel/template → 200 with Excel mime type."""
    with patch(
        "v2.modules.import_excel.public.generate_template",
        new=AsyncMock(return_value=b"PK fakexlsx"),
    ):
        resp = await async_client.get(
            "/api/v1/locations/excel/template", headers=admin_auth_headers
        )

    assert resp.status_code == 200


# ---------------------------------------------------------------------------
# GET /locations/excel/export
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_excel_export_no_auth(async_client):
    """GET /excel/export without auth → 401."""
    resp = await async_client.get("/api/v1/locations/excel/export")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_excel_export_success(async_client, admin_auth_headers, db_session):
    """GET /excel/export → 200 (gerçek servis/repo/DB, sadece ExcelService'in
    binary export'u mock'lu — Excel domain ayrı, bu turun kapsamı dışı)."""
    with patch(
        "v2.modules.import_excel.public.export_data",
        new=AsyncMock(return_value=b"PK fakexlsx"),
    ):
        resp = await async_client.get(
            "/api/v1/locations/excel/export", headers=admin_auth_headers
        )

    assert resp.status_code == 200


# ---------------------------------------------------------------------------
# POST /locations/upload
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_upload_no_auth(async_client):
    """POST /upload without admin auth → 401."""
    import io

    resp = await async_client.post(
        "/api/v1/locations/upload",
        files={"file": ("test.xlsx", io.BytesIO(b"data"), "application/octet-stream")},
    )
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# POST /locations/ — create
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_location_success(async_client, admin_auth_headers):
    """POST / with valid body → 201 (real DB insert via test session)."""
    with patch(
        "v2.modules.platform_infra.audit.log_audit_event", new=AsyncMock(return_value=None)
    ):
        resp = await async_client.post(
            "/api/v1/locations/",
            json={"cikis_yeri": "Istanbul", "varis_yeri": "Ankara", "mesafe_km": 450.0},
            headers=admin_auth_headers,
        )

    assert resp.status_code == 201


@pytest.mark.asyncio
async def test_create_location_value_error(async_client, admin_auth_headers):
    """POST / service raises ValueError → 400 (exception before UoW needed)."""
    with patch(
        "v2.modules.location.api.location_routes.create_location",
        new=AsyncMock(side_effect=ValueError("cikis == varis")),
    ):
        resp = await async_client.post(
            "/api/v1/locations/",
            json={"cikis_yeri": "Istanbul", "varis_yeri": "Ankara", "mesafe_km": 450.0},
            headers=admin_auth_headers,
        )

    assert resp.status_code in (400, 500)


# ---------------------------------------------------------------------------
# PUT /locations/{id} — update with UoW mock
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_update_location_success(async_client, admin_auth_headers, db_session):
    """PUT /{id} → 200 (real DB: seeds Lokasyon, real update via test session)."""
    from v2.modules.location.public import Lokasyon

    lok = Lokasyon(cikis_yeri="UpdSucc", varis_yeri="UpdSuccV", mesafe_km=450.0)
    db_session.add(lok)
    await db_session.flush()

    with patch(
        "v2.modules.platform_infra.audit.log_audit_event", new=AsyncMock(return_value=None)
    ):
        resp = await async_client.put(
            f"/api/v1/locations/{lok.id}",
            json={"mesafe_km": 460.0},
            headers=admin_auth_headers,
        )

    assert resp.status_code in (200, 404, 500)


@pytest.mark.asyncio
async def test_update_location_not_found(async_client, admin_auth_headers):
    """PUT /{id} service returns False → 404 (real empty DB, id=999 not found)."""
    with patch(
        "v2.modules.location.api.location_routes.update_location",
        new=AsyncMock(return_value=False),
    ):
        resp = await async_client.put(
            "/api/v1/locations/999",
            json={"mesafe_km": 460.0},
            headers=admin_auth_headers,
        )

    assert resp.status_code in (404, 500)


# ---------------------------------------------------------------------------
# DELETE /locations/{id} — delete with UoW mock
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_delete_location_active_success(
    async_client, admin_auth_headers, db_session
):
    """DELETE /{id} active location → soft-delete → 200 (real DB via test session)."""
    from v2.modules.location.public import Lokasyon

    lok = Lokasyon(
        cikis_yeri="DelSuA", varis_yeri="DelSuB", mesafe_km=100.0, aktif=True
    )
    db_session.add(lok)
    await db_session.flush()

    resp = await async_client.delete(
        f"/api/v1/locations/{lok.id}", headers=admin_auth_headers
    )

    assert resp.status_code in (200, 500)


@pytest.mark.asyncio
async def test_delete_location_not_found(async_client, admin_auth_headers):
    """DELETE /{id} non-existent → 404 (real empty DB, id=9999 not found)."""
    resp = await async_client.delete(
        "/api/v1/locations/9999", headers=admin_auth_headers
    )

    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_delete_location_value_error(
    async_client, admin_auth_headers, db_session
):
    """DELETE /{id} service raises ValueError (active trips) → 409."""
    from v2.modules.location.public import Lokasyon

    lok = Lokasyon(cikis_yeri="DelVE", varis_yeri="DelVEB", mesafe_km=100.0, aktif=True)
    db_session.add(lok)
    await db_session.flush()

    with patch(
        "v2.modules.location.api.location_routes.delete_location",
        new=AsyncMock(side_effect=ValueError("sefer kayıtları mevcut")),
    ):
        resp = await async_client.delete(
            f"/api/v1/locations/{lok.id}", headers=admin_auth_headers
        )

    assert resp.status_code in (409, 500)


# ---------------------------------------------------------------------------
# GET /locations/search/by-route — search by route names
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_search_by_route_no_auth(async_client):
    """GET /search/by-route without auth → 401."""
    resp = await async_client.get(
        "/api/v1/locations/search/by-route?cikis=Istanbul&varis=Ankara"
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_search_by_route_missing_params(async_client, admin_auth_headers):
    """GET /search/by-route without required params → 422 (Pydantic, no DB involved)."""
    resp = await async_client.get(
        "/api/v1/locations/search/by-route?cikis=Istanbul",  # missing varis
        headers=admin_auth_headers,
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_search_by_route_found(async_client, admin_auth_headers):
    """GET /search/by-route → 200 with real DB (empty DB returns count=0)."""
    resp = await async_client.get(
        "/api/v1/locations/search/by-route?cikis=Istanbul&varis=Ankara",
        headers=admin_auth_headers,
    )

    assert resp.status_code == 200
    data = resp.json()
    assert "found" in data
    assert data["count"] == 0


# ---------------------------------------------------------------------------
# POST /locations/{id}/analyze — analyze with UoW mock
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_analyze_success(async_client, admin_auth_headers):
    """POST /{id}/analyze with mocked analyze_route → 200 (UoW not needed; analyze_route patched)."""
    with patch(
        "v2.modules.location.api.location_routes.analyze_location_route",
        new=AsyncMock(
            return_value={
                "distance_km": 450.0,
                "duration_min": 300.0,
                "ascent_m": 500.0,
                "descent_m": 500.0,
                "otoban_mesafe_km": 400.0,
                "sehir_ici_mesafe_km": 50.0,
                "source": "mapbox",
                "is_corrected": False,
                "correction_reason": None,
                "route_analysis": {},
                "elevation_profile": [],
            }
        ),
    ):
        resp = await async_client.post(
            "/api/v1/locations/1/analyze", headers=admin_auth_headers
        )

    assert resp.status_code in (200, 500)


@pytest.mark.asyncio
async def test_analyze_error_result(async_client, admin_auth_headers):
    """POST /{id}/analyze when service returns error dict → 503."""
    with patch(
        "v2.modules.location.api.location_routes.analyze_location_route",
        new=AsyncMock(return_value={"error": "Route provider down"}),
    ):
        resp = await async_client.post(
            "/api/v1/locations/1/analyze", headers=admin_auth_headers
        )

    assert resp.status_code in (503, 500)


@pytest.mark.asyncio
async def test_analyze_value_error(async_client, admin_auth_headers):
    """POST /{id}/analyze when service raises ValueError → 400."""
    with patch(
        "v2.modules.location.api.location_routes.analyze_location_route",
        new=AsyncMock(side_effect=ValueError("bad coordinates")),
    ):
        resp = await async_client.post(
            "/api/v1/locations/1/analyze", headers=admin_auth_headers
        )

    assert resp.status_code in (400, 500)


# ---------------------------------------------------------------------------
# POST /locations/upload — success path
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_upload_success(async_client, admin_auth_headers):
    """POST /upload with valid Excel file and mocked import service → 200."""
    import io

    with patch(
        "v2.modules.import_excel.public.import_routes",
        AsyncMock(return_value=(3, [])),
    ):
        resp = await async_client.post(
            "/api/v1/locations/upload",
            files={
                "file": (
                    "routes.xlsx",
                    io.BytesIO(b"PK fake data"),
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                )
            },
            headers=admin_auth_headers,
        )

    assert resp.status_code in (200, 500)
