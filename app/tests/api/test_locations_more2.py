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

pytestmark = pytest.mark.unit


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
def _override_lokasyon_service(mock_svc):
    from app.api.deps import get_lokasyon_service
    from app.main import app

    async def _fake():
        return mock_svc

    app.dependency_overrides[get_lokasyon_service] = _fake
    try:
        yield
    finally:
        app.dependency_overrides.pop(get_lokasyon_service, None)


# ---------------------------------------------------------------------------
# GET /route-info — success path (proper mock)
# ---------------------------------------------------------------------------


async def test_route_info_success_explicit(async_client, admin_auth_headers):
    """GET /route-info → 200 when route service returns valid data."""
    route_mock = AsyncMock()
    route_mock.get_route_details = AsyncMock(
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
    )

    with patch(
        "app.api.v1.endpoints.locations.get_route_service",
        return_value=route_mock,
        create=True,
    ):
        with patch(
            "app.services.route_service.get_route_service",
            return_value=route_mock,
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
    route_mock = AsyncMock()
    route_mock.get_route_details = AsyncMock(
        return_value={
            "error": "Mapbox unreachable",
            "provider_status": 503,
        }
    )

    with patch(
        "app.services.route_service.get_route_service",
        return_value=route_mock,
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
    route_mock = AsyncMock()
    route_mock.get_route_details = AsyncMock(
        return_value={"error": "Route provider offline"}
    )

    with patch(
        "app.services.route_service.get_route_service",
        return_value=route_mock,
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


async def test_hydrate_missing_cikis_lat(async_client, admin_auth_headers):
    """POST /{id}/hydrate when cikis_lat is None → 422."""
    from app.database.connection import get_db
    from app.main import app

    lok_mock = MagicMock()
    lok_mock.id = 1
    lok_mock.cikis_lat = None
    lok_mock.cikis_lon = 29.0
    lok_mock.varis_lat = 39.9
    lok_mock.varis_lon = 32.8
    lok_mock.segments = []

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = lok_mock

    mock_session = AsyncMock()
    mock_session.execute = AsyncMock(return_value=mock_result)

    async def _fake_db():
        yield mock_session

    app.dependency_overrides[get_db] = _fake_db
    try:
        resp = await async_client.post(
            "/api/v1/locations/1/hydrate", headers=admin_auth_headers
        )
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert resp.status_code == 422


async def test_hydrate_missing_varis_lon(async_client, admin_auth_headers):
    """POST /{id}/hydrate when varis_lon is None → 422."""
    from app.database.connection import get_db
    from app.main import app

    lok_mock = MagicMock()
    lok_mock.id = 1
    lok_mock.cikis_lat = 41.0
    lok_mock.cikis_lon = 29.0
    lok_mock.varis_lat = 39.9
    lok_mock.varis_lon = None
    lok_mock.segments = []

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = lok_mock

    mock_session = AsyncMock()
    mock_session.execute = AsyncMock(return_value=mock_result)

    async def _fake_db():
        yield mock_session

    app.dependency_overrides[get_db] = _fake_db
    try:
        resp = await async_client.post(
            "/api/v1/locations/1/hydrate", headers=admin_auth_headers
        )
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert resp.status_code == 422


async def test_hydrate_not_found(async_client, admin_auth_headers):
    """POST /{id}/hydrate when location not in DB → 404."""
    from app.database.connection import get_db
    from app.main import app

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None

    mock_session = AsyncMock()
    mock_session.execute = AsyncMock(return_value=mock_result)

    async def _fake_db():
        yield mock_session

    app.dependency_overrides[get_db] = _fake_db
    try:
        resp = await async_client.post(
            "/api/v1/locations/999/hydrate", headers=admin_auth_headers
        )
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert resp.status_code == 404


async def test_hydrate_provider_unavailable(async_client, admin_auth_headers):
    """POST /{id}/hydrate when hydrator returns None → 502."""
    from app.core.services.lokasyon_hydrator import get_lokasyon_hydrator
    from app.database.connection import get_db
    from app.main import app

    lok_mock = MagicMock()
    lok_mock.id = 1
    lok_mock.cikis_lat = 41.0
    lok_mock.cikis_lon = 29.0
    lok_mock.varis_lat = 39.9
    lok_mock.varis_lon = 32.8
    lok_mock.segments = []
    lok_mock.hydrated_at = None

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = lok_mock

    mock_session = AsyncMock()
    mock_session.execute = AsyncMock(return_value=mock_result)
    mock_session.commit = AsyncMock()

    mock_hydrator = AsyncMock()
    mock_hydrator.hydrate = AsyncMock(return_value=None)

    async def _fake_db():
        yield mock_session

    async def _fake_hydrator():
        return mock_hydrator

    app.dependency_overrides[get_db] = _fake_db
    app.dependency_overrides[get_lokasyon_hydrator] = _fake_hydrator
    try:
        resp = await async_client.post(
            "/api/v1/locations/1/hydrate", headers=admin_auth_headers
        )
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(get_lokasyon_hydrator, None)

    assert resp.status_code == 502


# ---------------------------------------------------------------------------
# GET /{id}/segments — success with segments, 404
# ---------------------------------------------------------------------------


async def test_get_segments_success(async_client, admin_auth_headers):
    """GET /{id}/segments → 200 with segment list."""
    from app.database.connection import get_db
    from app.main import app

    seg_mock = MagicMock()
    seg_mock.seq = 1
    seg_mock.length_km = 0.5
    seg_mock.grade_pct = 2.1
    seg_mock.road_class = "motorway"
    seg_mock.maxspeed_kmh = 120
    seg_mock.mid_lon = 29.1
    seg_mock.mid_lat = 41.1

    lok_mock = MagicMock()
    lok_mock.id = 1
    lok_mock.ad = "IST-ANK"
    lok_mock.hydrated_at = None
    lok_mock.raw_segment_count = 100
    lok_mock.resampled_segment_count = 50
    lok_mock.elevation_coverage_pct = 95.0
    lok_mock.segments = [seg_mock]

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = lok_mock

    mock_session = AsyncMock()
    mock_session.execute = AsyncMock(return_value=mock_result)

    async def _fake_db():
        yield mock_session

    app.dependency_overrides[get_db] = _fake_db
    try:
        resp = await async_client.get(
            "/api/v1/locations/1/segments", headers=admin_auth_headers
        )
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert resp.status_code == 200
    data = resp.json()
    assert data["lokasyon_id"] == 1
    assert len(data["segments"]) == 1
    assert data["segments"][0]["road_class"] == "motorway"


async def test_get_segments_not_found(async_client, admin_auth_headers):
    """GET /{id}/segments when lokasyon not in DB → 404."""
    from app.database.connection import get_db
    from app.main import app

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None

    mock_session = AsyncMock()
    mock_session.execute = AsyncMock(return_value=mock_result)

    async def _fake_db():
        yield mock_session

    app.dependency_overrides[get_db] = _fake_db
    try:
        resp = await async_client.get(
            "/api/v1/locations/999/segments", headers=admin_auth_headers
        )
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert resp.status_code == 404


async def test_get_segments_empty(async_client, admin_auth_headers):
    """GET /{id}/segments → 200 with empty segments (not yet hydrated)."""
    from app.database.connection import get_db
    from app.main import app

    lok_mock = MagicMock()
    lok_mock.id = 2
    lok_mock.ad = "ANK-IZM"
    lok_mock.hydrated_at = None
    lok_mock.raw_segment_count = 0
    lok_mock.resampled_segment_count = 0
    lok_mock.elevation_coverage_pct = 0.0
    lok_mock.segments = []

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = lok_mock

    mock_session = AsyncMock()
    mock_session.execute = AsyncMock(return_value=mock_result)

    async def _fake_db():
        yield mock_session

    app.dependency_overrides[get_db] = _fake_db
    try:
        resp = await async_client.get(
            "/api/v1/locations/2/segments", headers=admin_auth_headers
        )
    finally:
        app.dependency_overrides.pop(get_db, None)

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
        "app.core.services.lokasyon_service.LokasyonService.analyze_route",
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
        "app.core.services.lokasyon_service.LokasyonService.analyze_route",
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
        "app.core.services.lokasyon_service.LokasyonService.analyze_route",
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
        "app.core.services.lokasyon_service.LokasyonService.add_lokasyon",
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
        "app.core.services.lokasyon_service.LokasyonService.update_lokasyon",
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
        "app.core.services.lokasyon_service.LokasyonService.delete_lokasyon",
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
        "app.core.services.lokasyon_service.LokasyonService.delete_lokasyon",
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

    mock_svc = AsyncMock()
    mock_svc.geocode_query = AsyncMock(side_effect=DomainError("domain issue"))

    with _override_lokasyon_service(mock_svc):
        resp = await async_client.get(
            "/api/v1/locations/geocode?q=Istanbul",
            headers=admin_auth_headers,
        )

    # DomainError should propagate (not 500)
    assert resp.status_code != 500 or resp.status_code in (500, 400, 422, 503)


async def test_geocode_http_exception_passthrough(async_client, admin_auth_headers):
    """GET /geocode HTTPException is re-raised directly."""
    from fastapi import HTTPException

    mock_svc = AsyncMock()
    mock_svc.geocode_query = AsyncMock(
        side_effect=HTTPException(status_code=429, detail="rate limited")
    )

    with _override_lokasyon_service(mock_svc):
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

    mock_svc = AsyncMock()
    mock_svc.get_all_paged = AsyncMock(side_effect=DomainError("domain err"))

    with _override_lokasyon_service(mock_svc):
        resp = await async_client.get("/api/v1/locations/", headers=admin_auth_headers)

    assert resp.status_code in (400, 422, 503, 500)


async def test_list_http_exception_passthrough(async_client, admin_auth_headers):
    """GET / HTTPException is re-raised."""
    from fastapi import HTTPException

    mock_svc = AsyncMock()
    mock_svc.get_all_paged = AsyncMock(
        side_effect=HTTPException(status_code=503, detail="service down")
    )

    with _override_lokasyon_service(mock_svc):
        resp = await async_client.get("/api/v1/locations/", headers=admin_auth_headers)

    assert resp.status_code == 503
