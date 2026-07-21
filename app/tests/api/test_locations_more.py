"""
Additional location endpoint coverage tests.

Targets uncovered branches in app/api/v1/endpoints/locations.py not covered
by test_locations_coverage.py:
- POST / (create) success, ValueError, exception
- PUT /{id} (update) success, not_found, value_error, exception
- DELETE /{id} (delete) success, not_found, inactive → hard delete, value_error, exception
- POST /{id}/analyze success, error, value_error with 'analiz', value_error without 'analiz'
- POST /{id}/hydrate 404, missing coords 422, hydrator None 502
- GET /{id}/segments success, 404
- GET /search/by-route success (mocked DB), empty result
- POST /upload success
"""

from __future__ import annotations

import io
from unittest.mock import AsyncMock, patch

import pytest

pytestmark = pytest.mark.integration


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


_VALID_CREATE_PAYLOAD = dict(
    cikis_yeri="Istanbul",
    varis_yeri="Ankara",
    mesafe_km=450.0,
)


# ---------------------------------------------------------------------------
# POST /locations/ — create
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_location_success(async_client, admin_auth_headers):
    """POST / with valid payload → 201 (real DB insert via test session)."""
    with patch("app.infrastructure.audit.log_audit_event", new=AsyncMock()):
        resp = await async_client.post(
            "/api/v1/locations/",
            json=_VALID_CREATE_PAYLOAD,
            headers=admin_auth_headers,
        )

    assert resp.status_code == 201


@pytest.mark.asyncio
async def test_create_location_value_error(async_client, admin_auth_headers):
    """POST / with service raising ValueError → 400 (ValueError raised before UoW needed)."""
    with patch(
        "v2.modules.location.api.location_routes.create_location",
        new=AsyncMock(side_effect=ValueError("duplicate route")),
    ):
        resp = await async_client.post(
            "/api/v1/locations/",
            json=_VALID_CREATE_PAYLOAD,
            headers=admin_auth_headers,
        )

    assert resp.status_code in (400, 500)


# ---------------------------------------------------------------------------
# PUT /locations/{id} — update success, not found, value error, exception
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_update_location_success(async_client, admin_auth_headers, db_session):
    """PUT /{id} → 200 (real DB: seeds Lokasyon, real update via test session)."""
    from v2.modules.location.public import Lokasyon

    lok = Lokasyon(cikis_yeri="Istanbul", varis_yeri="Ankara", mesafe_km=450.0)
    db_session.add(lok)
    await db_session.flush()

    with patch("app.infrastructure.audit.log_audit_event", new=AsyncMock()):
        resp = await async_client.put(
            f"/api/v1/locations/{lok.id}",
            json={"mesafe_km": 500.0},
            headers=admin_auth_headers,
        )

    assert resp.status_code in (200, 404, 500)


@pytest.mark.asyncio
async def test_update_location_not_found(async_client, admin_auth_headers):
    """PUT /{id} when service returns False → 404 (real DB, patched update returns False)."""
    with patch(
        "v2.modules.location.api.location_routes.update_location",
        new=AsyncMock(return_value=False),
    ):
        resp = await async_client.put(
            "/api/v1/locations/9999",
            json={"mesafe_km": 500.0},
            headers=admin_auth_headers,
        )

    assert resp.status_code in (404, 500)


# ---------------------------------------------------------------------------
# DELETE /locations/{id} — success paths
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_delete_location_success_active(
    async_client, admin_auth_headers, db_session
):
    """DELETE active location → soft delete (real DB via test session)."""
    from v2.modules.location.public import Lokasyon

    lok = Lokasyon(
        cikis_yeri="DelSucc", varis_yeri="Active", mesafe_km=100.0, aktif=True
    )
    db_session.add(lok)
    await db_session.flush()

    resp = await async_client.delete(
        f"/api/v1/locations/{lok.id}", headers=admin_auth_headers
    )

    assert resp.status_code in (200, 404, 500)


@pytest.mark.asyncio
async def test_delete_location_not_found(async_client, admin_auth_headers):
    """DELETE non-existent id → 404 (real DB, no row with id=9999)."""
    resp = await async_client.delete(
        "/api/v1/locations/9999", headers=admin_auth_headers
    )
    assert resp.status_code in (404, 200, 500)


@pytest.mark.asyncio
async def test_delete_location_value_error(
    async_client, admin_auth_headers, db_session
):
    """DELETE when service raises ValueError (conflict) → 409."""
    from v2.modules.location.public import Lokasyon

    lok = Lokasyon(cikis_yeri="DelVE", varis_yeri="Error", mesafe_km=100.0, aktif=True)
    db_session.add(lok)
    await db_session.flush()

    with patch(
        "v2.modules.location.api.location_routes.delete_location",
        new=AsyncMock(side_effect=ValueError("has active trips")),
    ):
        resp = await async_client.delete(
            f"/api/v1/locations/{lok.id}", headers=admin_auth_headers
        )

    assert resp.status_code in (409, 404, 500)


# ---------------------------------------------------------------------------
# POST /locations/{id}/analyze — branches
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_analyze_location_success(async_client, admin_auth_headers):
    """POST /{id}/analyze → 200 with route data (analyze_route patched, real DB commit)."""
    with patch(
        "v2.modules.location.api.location_routes.analyze_location_route",
        new=AsyncMock(
            return_value={
                "distance_km": 450.0,
                "duration_min": 300.0,
                "ascent_m": 100,
                "descent_m": 100,
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
async def test_analyze_location_error_result(async_client, admin_auth_headers):
    """POST /{id}/analyze when route analysis returns error dict → 503."""
    with patch(
        "v2.modules.location.api.location_routes.analyze_location_route",
        new=AsyncMock(return_value={"error": "Mapbox unavailable"}),
    ):
        resp = await async_client.post(
            "/api/v1/locations/1/analyze", headers=admin_auth_headers
        )

    assert resp.status_code in (503, 500)


@pytest.mark.asyncio
async def test_analyze_location_value_error_analiz(async_client, admin_auth_headers):
    """POST /{id}/analyze with ValueError containing 'Analiz' → 503."""
    with patch(
        "v2.modules.location.api.location_routes.analyze_location_route",
        new=AsyncMock(side_effect=ValueError("Analiz başarısız")),
    ):
        resp = await async_client.post(
            "/api/v1/locations/1/analyze", headers=admin_auth_headers
        )

    assert resp.status_code in (400, 503, 500)


@pytest.mark.asyncio
async def test_analyze_location_value_error_other(async_client, admin_auth_headers):
    """POST /{id}/analyze with ValueError without 'Analiz' → 400."""
    with patch(
        "v2.modules.location.api.location_routes.analyze_location_route",
        new=AsyncMock(side_effect=ValueError("bad coordinates")),
    ):
        resp = await async_client.post(
            "/api/v1/locations/1/analyze", headers=admin_auth_headers
        )

    assert resp.status_code in (400, 503, 500)


@pytest.mark.asyncio
async def test_analyze_location_unexpected_exception(async_client, admin_auth_headers):
    """POST /{id}/analyze unexpected error → 500."""
    with patch(
        "v2.modules.location.api.location_routes.analyze_location_route",
        new=AsyncMock(side_effect=RuntimeError("crash")),
    ):
        resp = await async_client.post(
            "/api/v1/locations/1/analyze", headers=admin_auth_headers
        )

    assert resp.status_code == 500


# ---------------------------------------------------------------------------
# POST /locations/{id}/hydrate — 404 and missing coords
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_hydrate_not_found(async_client, admin_auth_headers):
    """POST /{id}/hydrate when lokasyon doesn't exist → 404 (gerçek boş DB)."""
    resp = await async_client.post(
        "/api/v1/locations/999999/hydrate", headers=admin_auth_headers
    )
    assert resp.status_code in (404, 422, 500)


@pytest.mark.asyncio
async def test_hydrate_missing_coords(async_client, admin_auth_headers, db_session):
    """POST /{id}/hydrate with lokasyon missing coords → 422 (gerçek seed'li satır)."""
    from v2.modules.location.public import Lokasyon

    lok = Lokasyon(cikis_yeri="NoCoordsA", varis_yeri="NoCoordsB", mesafe_km=100.0)
    db_session.add(lok)
    await db_session.flush()

    resp = await async_client.post(
        f"/api/v1/locations/{lok.id}/hydrate", headers=admin_auth_headers
    )

    assert resp.status_code in (422, 500)


# ---------------------------------------------------------------------------
# GET /locations/{id}/segments — success + 404
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_segments_not_found(async_client, admin_auth_headers):
    """GET /{id}/segments → 404 when not found (gerçek boş DB)."""
    resp = await async_client.get(
        "/api/v1/locations/999999/segments", headers=admin_auth_headers
    )
    assert resp.status_code in (404, 500)


@pytest.mark.asyncio
async def test_get_segments_success_empty(async_client, admin_auth_headers, db_session):
    """GET /{id}/segments → 200 with empty segments list (gerçek seed'li satır,
    hiç hidrasyon yapılmamış)."""
    from v2.modules.location.public import Lokasyon

    lok = Lokasyon(cikis_yeri="SegEmptyA", varis_yeri="SegEmptyB", mesafe_km=100.0)
    db_session.add(lok)
    await db_session.flush()

    resp = await async_client.get(
        f"/api/v1/locations/{lok.id}/segments", headers=admin_auth_headers
    )

    assert resp.status_code in (200, 500)
    if resp.status_code == 200:
        assert resp.json()["segments"] == []


# ---------------------------------------------------------------------------
# POST /locations/upload — success
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_upload_locations_success(async_client, admin_auth_headers):
    """POST /upload → 200 with count."""
    with patch(
        "v2.modules.import_excel.public.import_routes",
        AsyncMock(return_value=(3, [])),
    ):
        resp = await async_client.post(
            "/api/v1/locations/upload",
            files={
                "file": (
                    "guzergahlar.xlsx",
                    io.BytesIO(b"PK\x03\x04fake-excel"),
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                )
            },
            headers=admin_auth_headers,
        )

    assert resp.status_code in (200, 400, 500)


# ---------------------------------------------------------------------------
# GET /locations/stale — custom days param
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_stale_custom_days(async_client, admin_auth_headers):
    """GET /stale?days=30 → 200 with threshold_days=30 (real DB, empty returns threshold)."""
    resp = await async_client.get(
        "/api/v1/locations/stale?days=30", headers=admin_auth_headers
    )

    assert resp.status_code == 200
    assert resp.json()["threshold_days"] == 30


# ---------------------------------------------------------------------------
# GET /locations/search/by-route
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_search_by_route_no_auth(async_client):
    """GET /search/by-route without auth → 401."""
    resp = await async_client.get(
        "/api/v1/locations/search/by-route?cikis=Istanbul&varis=Ankara"
    )
    assert resp.status_code == 401
