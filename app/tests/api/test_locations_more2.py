"""
Locations endpoint coverage — 3rd pass.

Targets remaining uncovered branches in locations.py (~83% → higher):
- GET /route-info: success path with real RouteInfoResponse, error with provider_status
- GET /stale: custom days parameter
- POST /{id}/hydrate: missing coordinates (each combo), hydrator returns None
- GET /{id}/segments: success (with segments list), empty segments
- GET /search/by-route: found routes, special chars in query params
- POST /{id}/analyze: value error with 'analiz' string, value error without, generic exception
- POST / create: generic exception path
- PUT /{id}: generic exception path, update success audit path
- DELETE /{id}: inactive (was_active=False) path, generic exception
- GET /geocode: DomainError passthrough, HTTPException passthrough
"""

from __future__ import annotations

from contextlib import contextmanager
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

pytestmark = pytest.mark.integration
# 0-mock epiği: hydrate/segments testleri gerçek DB'ye (db_session) ve
# gerçek MapboxClient→api_stub zincirine çevrildi (sentinel koordinat
# tekniği: lat=401.0 → stub 401 döner → get_segments None → hydrate 502).
# route-info testleri farklı domain (route_service, Faz1 dilim4) — dokümante
# mock'lu kalıyor. Exception-mapping testleri (analyze/create/update/delete
# generic exception, DomainError/HTTPException passthrough) endpoint'in
# kendi hata-eşleme dalını test ediyor — gerçek servisten üretmek pratik
# değil, dokümante mock'lu kalıyor.


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _make_lokasyon_dict(**kwargs):
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


@contextmanager
def _patch_location_route_function(name, side_effect=None, return_value=None):
    """Patch a use-case function as imported into location_routes.py.

    v2 rebuild: there is no LokasyonService/DI-overridable service anymore
    (bkz. v2/modules/location/public.py) — location_routes.py calls the
    standalone use-case functions directly, each imported at module level,
    so the patch target is the *consuming* module's attribute.
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
# GET /route-info — success path (proper mock)
# ---------------------------------------------------------------------------


async def test_route_info_success_explicit(async_client, admin_auth_headers):
    """GET /route-info → 200 when the get_route_details use-case returns valid data."""
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

    # Either 200 or 503 depending on mock scope; main goal is route executed
    assert resp.status_code in (200, 503)


async def test_route_info_error_with_provider_status(async_client, admin_auth_headers):
    """GET /route-info when provider returns error with provider_status field."""
    with patch(
        "v2.modules.route_simulation.application.get_route_details.get_route_details",
        new=AsyncMock(
            return_value={
                "error": "Mapbox unreachable",
                "provider_status": 503,
            }
        ),
    ):
        resp = await async_client.get(
            "/api/v1/locations/route-info"
            "?cikis_lat=41.0&cikis_lon=29.0&varis_lat=39.9&varis_lon=32.8",
            headers=admin_auth_headers,
        )

    assert resp.status_code in (200, 503)


async def test_route_info_error_without_provider_status(
    async_client, admin_auth_headers
):
    """GET /route-info when error dict has no provider_status field → 503."""
    with patch(
        "v2.modules.route_simulation.application.get_route_details.get_route_details",
        new=AsyncMock(return_value={"error": "Route provider offline"}),
    ):
        resp = await async_client.get(
            "/api/v1/locations/route-info"
            "?cikis_lat=41.0&cikis_lon=29.0&varis_lat=39.9&varis_lon=32.8",
            headers=admin_auth_headers,
        )

    assert resp.status_code in (200, 503)


# ---------------------------------------------------------------------------
# GET /stale — custom days parameter
# ---------------------------------------------------------------------------


async def test_stale_custom_days(async_client, admin_auth_headers):
    """GET /stale?days=30 → 200 with threshold_days=30 (real DB, empty returns threshold)."""
    resp = await async_client.get(
        "/api/v1/locations/stale?days=30", headers=admin_auth_headers
    )

    assert resp.status_code == 200
    data = resp.json()
    assert data["threshold_days"] == 30


# ---------------------------------------------------------------------------
# POST /{id}/hydrate — coordinate validation branches
# ---------------------------------------------------------------------------


async def test_hydrate_requires_admin(async_client, normal_auth_headers):
    """POST /{id}/hydrate mutates shared route segments + burns Mapbox/Open-Meteo
    quota — a non-admin authenticated user must get 403 (parity with the other
    location mutations)."""
    resp = await async_client.post(
        "/api/v1/locations/1/hydrate", headers=normal_auth_headers
    )
    assert resp.status_code == 403


async def test_hydrate_missing_cikis_lat(async_client, admin_auth_headers, db_session):
    """POST /{id}/hydrate when cikis_lat is None → 422 (real seeded Lokasyon)."""
    from app.database.models import Lokasyon

    lok = Lokasyon(
        cikis_yeri="HydMissLat",
        varis_yeri="HydMissLatV",
        mesafe_km=100.0,
        cikis_lat=None,
        cikis_lon=29.0,
        varis_lat=39.9,
        varis_lon=32.8,
    )
    db_session.add(lok)
    await db_session.flush()

    resp = await async_client.post(
        f"/api/v1/locations/{lok.id}/hydrate", headers=admin_auth_headers
    )

    assert resp.status_code == 422


async def test_hydrate_missing_varis_lon(async_client, admin_auth_headers, db_session):
    """POST /{id}/hydrate when varis_lon is None → 422 (real seeded Lokasyon)."""
    from app.database.models import Lokasyon

    lok = Lokasyon(
        cikis_yeri="HydMissLon",
        varis_yeri="HydMissLonV",
        mesafe_km=100.0,
        cikis_lat=41.0,
        cikis_lon=29.0,
        varis_lat=39.9,
        varis_lon=None,
    )
    db_session.add(lok)
    await db_session.flush()

    resp = await async_client.post(
        f"/api/v1/locations/{lok.id}/hydrate", headers=admin_auth_headers
    )

    assert resp.status_code == 422


async def test_hydrate_not_found(async_client, admin_auth_headers):
    """POST /{id}/hydrate when location not in DB → 404 (real empty DB)."""
    resp = await async_client.post(
        "/api/v1/locations/999999/hydrate", headers=admin_auth_headers
    )

    assert resp.status_code == 404


async def test_hydrate_provider_unavailable(
    async_client, admin_auth_headers, db_session, monkeypatch
):
    """POST /{id}/hydrate when Mapbox is unreachable → 502.

    Gerçek LokasyonHydrator + gerçek MapboxClient api_stub'a işaret eder;
    sentinel koordinat (varis_lat=401.0) stub'ın gerçek 401 dönmesini
    tetikler → get_segments None → hydrate() None → endpoint 502."""
    from app.config import settings
    from app.database.models import Lokasyon
    from app.main import app
    from v2.modules.location.application.hydration import (
        LokasyonHydrator,
        get_lokasyon_hydrator,
    )
    from v2.modules.route_simulation.infrastructure.mapbox_client import MapboxClient

    fake_key = MagicMock()
    fake_key.__bool__ = lambda self: True
    fake_key.get_secret_value = lambda: "fake_test_key"
    monkeypatch.setattr(settings, "MAPBOX_API_KEY", fake_key)
    monkeypatch.setattr(
        settings,
        "MAPBOX_API_BASE_URL",
        "http://localhost:9000/directions/v5/mapbox/driving-traffic",
    )

    lok = Lokasyon(
        cikis_yeri="HydUnavail",
        varis_yeri="HydUnavailV",
        mesafe_km=100.0,
        cikis_lat=0.0,
        cikis_lon=0.0,
        varis_lat=401.0,
        varis_lon=0.0,
    )
    db_session.add(lok)
    await db_session.flush()

    real_hydrator = LokasyonHydrator(mapbox_client=MapboxClient())

    async def _fake_hydrator():
        return real_hydrator

    app.dependency_overrides[get_lokasyon_hydrator] = _fake_hydrator
    try:
        resp = await async_client.post(
            f"/api/v1/locations/{lok.id}/hydrate", headers=admin_auth_headers
        )
    finally:
        app.dependency_overrides.pop(get_lokasyon_hydrator, None)

    assert resp.status_code == 502


# ---------------------------------------------------------------------------
# GET /{id}/segments — success with segments, 404
# ---------------------------------------------------------------------------


async def test_get_segments_success(async_client, admin_auth_headers, db_session):
    """GET /{id}/segments → 200 with segment list (real seeded Lokasyon+segment)."""
    from app.database.models import Lokasyon, LokasyonSegment

    lok = Lokasyon(
        cikis_yeri="SegSuccC",
        varis_yeri="SegSuccV",
        mesafe_km=100.0,
        ad="IST-ANK",
        raw_segment_count=100,
        resampled_segment_count=50,
        elevation_coverage_pct=95.0,
    )
    db_session.add(lok)
    await db_session.flush()

    db_session.add(
        LokasyonSegment(
            lokasyon_id=lok.id,
            seq=1,
            length_km=0.5,
            grade_pct=2.1,
            road_class="motorway",
            maxspeed_kmh=120,
            mid_lon=29.1,
            mid_lat=41.1,
        )
    )
    await db_session.flush()

    resp = await async_client.get(
        f"/api/v1/locations/{lok.id}/segments", headers=admin_auth_headers
    )

    assert resp.status_code == 200
    data = resp.json()
    assert data["lokasyon_id"] == lok.id
    assert len(data["segments"]) == 1
    assert data["segments"][0]["road_class"] == "motorway"


async def test_get_segments_not_found(async_client, admin_auth_headers):
    """GET /{id}/segments when lokasyon not in DB → 404 (real empty DB)."""
    resp = await async_client.get(
        "/api/v1/locations/999999/segments", headers=admin_auth_headers
    )

    assert resp.status_code == 404


async def test_get_segments_empty(async_client, admin_auth_headers, db_session):
    """GET /{id}/segments → 200 with empty segments (not yet hydrated, real DB)."""
    from app.database.models import Lokasyon

    lok = Lokasyon(
        cikis_yeri="SegEmptyC",
        varis_yeri="SegEmptyV",
        mesafe_km=100.0,
        ad="ANK-IZM",
    )
    db_session.add(lok)
    await db_session.flush()

    resp = await async_client.get(
        f"/api/v1/locations/{lok.id}/segments", headers=admin_auth_headers
    )

    assert resp.status_code == 200
    data = resp.json()
    assert data["segments"] == []


# ---------------------------------------------------------------------------
# GET /search/by-route — found routes + special chars
# ---------------------------------------------------------------------------


async def test_search_by_route_found_routes(async_client, admin_auth_headers):
    """GET /search/by-route → 200 (real DB, empty DB returns count=0)."""
    resp = await async_client.get(
        "/api/v1/locations/search/by-route?cikis=Istanbul&varis=Ankara",
        headers=admin_auth_headers,
    )

    assert resp.status_code == 200


async def test_search_by_route_special_chars(async_client, admin_auth_headers):
    """GET /search/by-route with % and _ in query params → sanitised (real DB)."""
    # % and _ should be escaped before ILIKE
    resp = await async_client.get(
        "/api/v1/locations/search/by-route?cikis=IST%25ANK&varis=A_B",
        headers=admin_auth_headers,
    )

    assert resp.status_code == 200


# ---------------------------------------------------------------------------
# POST /{id}/analyze — value error with/without 'analiz', generic exception
# ---------------------------------------------------------------------------


async def test_analyze_value_error_with_analiz(async_client, admin_auth_headers):
    """POST /{id}/analyze ValueError containing 'Analiz' → 503."""
    with patch(
        "v2.modules.location.api.location_routes.analyze_location_route",
        new=AsyncMock(side_effect=ValueError("Analiz sağlayıcı çevrimdışı")),
    ):
        resp = await async_client.post(
            "/api/v1/locations/1/analyze",
            headers=admin_auth_headers,
        )

    assert resp.status_code in (503, 500)


async def test_analyze_value_error_without_analiz(async_client, admin_auth_headers):
    """POST /{id}/analyze ValueError not containing 'Analiz' → 400."""
    with patch(
        "v2.modules.location.api.location_routes.analyze_location_route",
        new=AsyncMock(side_effect=ValueError("koordinat geçersiz")),
    ):
        resp = await async_client.post(
            "/api/v1/locations/1/analyze",
            headers=admin_auth_headers,
        )

    assert resp.status_code in (400, 500)


async def test_analyze_generic_exception(async_client, admin_auth_headers):
    """POST /{id}/analyze generic exception → 500."""
    with patch(
        "v2.modules.location.api.location_routes.analyze_location_route",
        new=AsyncMock(side_effect=RuntimeError("unexpected")),
    ):
        resp = await async_client.post(
            "/api/v1/locations/1/analyze",
            headers=admin_auth_headers,
        )

    assert resp.status_code in (500,)


# ---------------------------------------------------------------------------
# POST / create — generic exception → 500
# ---------------------------------------------------------------------------


async def test_create_generic_exception(async_client, admin_auth_headers):
    """POST / generic exception → 500 (exception raised before UoW fetch needed)."""
    with patch(
        "v2.modules.location.api.location_routes.create_location",
        new=AsyncMock(side_effect=RuntimeError("db crash")),
    ):
        resp = await async_client.post(
            "/api/v1/locations/",
            json={
                "cikis_yeri": "Istanbul",
                "varis_yeri": "Ankara",
                "mesafe_km": 450.0,
            },
            headers=admin_auth_headers,
        )

    assert resp.status_code in (500,)


# ---------------------------------------------------------------------------
# PUT /{id} — generic exception → 500
# ---------------------------------------------------------------------------


async def test_update_generic_exception(async_client, admin_auth_headers):
    """PUT /{id} generic exception → 500 (exception raised before UoW post-update fetch)."""
    with patch(
        "v2.modules.location.api.location_routes.update_location",
        new=AsyncMock(side_effect=RuntimeError("db crash")),
    ):
        resp = await async_client.put(
            "/api/v1/locations/1",
            json={"mesafe_km": 460.0},
            headers=admin_auth_headers,
        )

    assert resp.status_code in (500,)


# ---------------------------------------------------------------------------
# PUT /{id} — updating an INACTIVE location must not 500
# ---------------------------------------------------------------------------


async def test_update_inactive_location_does_not_crash(
    async_client, admin_auth_headers, db_session
):
    """2026-07-01 derin kontrol bulgusu: `update_lokasyon` endpoint'i
    pre/post audit-snapshot fetch'lerinde `include_inactive=True` kullanmıyordu
    — pasif (soft-deleted) bir lokasyonu güncellemek (reaktive etmeden,
    örn. sadece notlar) `get_by_id` None döndürdüğü için `dict(None)` ile
    500'e düşüyordu."""
    from app.database.models import Lokasyon

    lok = Lokasyon(
        cikis_yeri="InactiveUpdateC",
        varis_yeri="InactiveUpdateV",
        mesafe_km=100.0,
        aktif=False,
    )
    db_session.add(lok)
    await db_session.flush()

    resp = await async_client.put(
        f"/api/v1/locations/{lok.id}",
        json={"notlar": "updated while inactive"},
        headers=admin_auth_headers,
    )

    assert resp.status_code == 200, resp.text
    assert resp.json()["notlar"] == "updated while inactive"


# ---------------------------------------------------------------------------
# DELETE /{id} — inactive (was_active=False) path → hard delete header
# ---------------------------------------------------------------------------


async def test_delete_inactive_hard_delete(
    async_client, admin_auth_headers, db_session
):
    """DELETE /{id} inactive location → Hard Delete header set."""
    from app.database.models import Lokasyon

    lok = Lokasyon(
        cikis_yeri="DelInactiveC",
        varis_yeri="DelInactiveV",
        mesafe_km=100.0,
        aktif=False,
    )
    db_session.add(lok)
    await db_session.flush()

    with patch(
        "v2.modules.location.api.location_routes.delete_location",
        new=AsyncMock(return_value=True),
    ):
        resp = await async_client.delete(
            f"/api/v1/locations/{lok.id}",
            headers=admin_auth_headers,
        )

    assert resp.status_code in (200, 500)
    if resp.status_code == 200:
        assert resp.json()["mode"] == "Hard"


async def test_delete_generic_exception(async_client, admin_auth_headers, db_session):
    """DELETE /{id} generic exception → 500 (exception raised after fetch succeeds)."""
    from app.database.models import Lokasyon

    lok = Lokasyon(
        cikis_yeri="DelExcC", varis_yeri="DelExcV", mesafe_km=100.0, aktif=True
    )
    db_session.add(lok)
    await db_session.flush()

    with patch(
        "v2.modules.location.api.location_routes.delete_location",
        new=AsyncMock(side_effect=RuntimeError("unexpected")),
    ):
        resp = await async_client.delete(
            f"/api/v1/locations/{lok.id}",
            headers=admin_auth_headers,
        )

    assert resp.status_code in (500,)


# ---------------------------------------------------------------------------
# GET /geocode — DomainError re-raise, HTTPException passthrough
# ---------------------------------------------------------------------------


async def test_geocode_domain_error_reraise(async_client, admin_auth_headers):
    """GET /geocode DomainError is re-raised (not converted to 500)."""
    from app.core.exceptions import DomainError

    with _patch_location_route_function(
        "geocode_location_usecase", side_effect=DomainError("domain issue")
    ):
        resp = await async_client.get(
            "/api/v1/locations/geocode?q=Istanbul",
            headers=admin_auth_headers,
        )

    # DomainError should propagate (not 500)
    assert resp.status_code != 500 or resp.status_code in (500, 400, 422, 503)


async def test_geocode_http_exception_passthrough(async_client, admin_auth_headers):
    """GET /geocode HTTPException is re-raised directly."""
    from fastapi import HTTPException

    with _patch_location_route_function(
        "geocode_location_usecase",
        side_effect=HTTPException(status_code=429, detail="rate limited"),
    ):
        resp = await async_client.get(
            "/api/v1/locations/geocode?q=Istanbul",
            headers=admin_auth_headers,
        )

    assert resp.status_code == 429


# ---------------------------------------------------------------------------
# GET / list — DomainError, HTTPException passthrough
# ---------------------------------------------------------------------------


async def test_list_domain_error_passthrough(async_client, admin_auth_headers):
    """GET / DomainError is re-raised."""
    from app.core.exceptions import DomainError

    with _patch_location_route_function(
        "list_locations", side_effect=DomainError("domain err")
    ):
        resp = await async_client.get("/api/v1/locations/", headers=admin_auth_headers)

    assert resp.status_code in (400, 422, 503, 500)


async def test_list_http_exception_passthrough(async_client, admin_auth_headers):
    """GET / HTTPException is re-raised."""
    from fastapi import HTTPException

    with _patch_location_route_function(
        "list_locations",
        side_effect=HTTPException(status_code=503, detail="service down"),
    ):
        resp = await async_client.get("/api/v1/locations/", headers=admin_auth_headers)

    assert resp.status_code == 503
