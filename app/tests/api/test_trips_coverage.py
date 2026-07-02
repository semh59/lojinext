"""
Trips endpoint coverage tests.

Targets missing lines 73-873 in app/api/v1/endpoints/trips.py.
All service calls are mocked — no DB needed.
"""

from contextlib import contextmanager
from datetime import date, datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

pytestmark = pytest.mark.unit

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_sefer_response_dict(**kwargs):
    """Minimal dict that SeferResponse.model_validate() will accept."""
    defaults = dict(
        id=1,
        sefer_no="SFR-001",
        tarih=date.today(),
        saat=None,
        arac_id=1,
        sofor_id=1,
        dorse_id=None,
        guzergah_id=None,
        route_pair_id=None,
        bos_agirlik_kg=0,
        dolu_agirlik_kg=0,
        net_kg=0,
        ton=0.0,
        cikis_yeri="Istanbul",
        varis_yeri="Ankara",
        mesafe_km=450.0,
        baslangic_km=None,
        bitis_km=None,
        bos_sefer=False,
        durum="Planned",
        dagitilan_yakit=None,
        tuketim=None,
        ascent_m=None,
        descent_m=None,
        flat_distance_km=0.0,
        otoban_mesafe_km=None,
        sehir_ici_mesafe_km=None,
        rota_detay=None,
        tahmin_meta=None,
        notlar=None,
        plaka="34 ABC 123",
        dorse_plakasi=None,
        sofor_adi="Ahmet Yilmaz",
        guzergah_adi=None,
        periyot_id=None,
        onay_durumu=None,
    )
    defaults.update(kwargs)
    return defaults


def _make_list_response(items=None):
    """Return a dict matching SeferListResponse."""
    if items is None:
        items = [_make_sefer_response_dict()]
    return {"items": items, "meta": {"total": len(items), "skip": 0, "limit": 100}}


def _make_stats_dict(**kwargs):
    defaults = dict(
        total_count=10,
        completed_count=5,
        cancelled_count=1,
        planned_count=3,
        in_progress_count=1,
        total_distance_km=4500.0,
        avg_consumption=32.5,
    )
    defaults.update(kwargs)
    return defaults


def _make_sefer_response_obj():
    """Return a validated SeferResponse Pydantic object."""
    from app.schemas.sefer import SeferResponse

    return SeferResponse.model_validate(_make_sefer_response_dict())


# ---------------------------------------------------------------------------
# Context manager helper for dependency overrides
# ---------------------------------------------------------------------------


@contextmanager
def _override_sefer_service(mock_svc):
    """Override get_sefer_service FastAPI dependency with a mock."""
    from app.api.deps import get_sefer_service
    from app.main import app

    async def _fake():
        return mock_svc

    app.dependency_overrides[get_sefer_service] = _fake
    try:
        yield
    finally:
        app.dependency_overrides.pop(get_sefer_service, None)


@contextmanager
def _override_job_manager(mock_jm):
    """Override get_background_job_manager dependency."""
    from app.api.deps import get_background_job_manager
    from app.main import app

    async def _fake_jm():
        return mock_jm

    app.dependency_overrides[get_background_job_manager] = _fake_jm
    try:
        yield
    finally:
        app.dependency_overrides.pop(get_background_job_manager, None)


# ---------------------------------------------------------------------------
# GET /trips/  — list trips  (lines 73-96)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_read_seferler_success(async_client, admin_auth_headers):
    """GET / with valid auth → 200 list response (lines 73-87)."""
    from app.schemas.sefer import SeferListResponse

    mock_svc = AsyncMock()
    mock_svc.get_all_paged = AsyncMock(
        return_value=SeferListResponse(
            items=[_make_sefer_response_obj()], meta={"total": 1}
        )
    )
    with _override_sefer_service(mock_svc):
        resp = await async_client.get("/api/v1/trips/", headers=admin_auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "items" in data


@pytest.mark.asyncio
async def test_read_seferler_no_auth(async_client):
    """GET / without auth → 401."""
    resp = await async_client.get("/api/v1/trips/")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_read_seferler_value_error(async_client, admin_auth_headers):
    """GET / service raises ValueError → 422 (lines 88-89)."""
    mock_svc = AsyncMock()
    mock_svc.get_all_paged = AsyncMock(side_effect=ValueError("bad param"))
    with _override_sefer_service(mock_svc):
        resp = await async_client.get("/api/v1/trips/", headers=admin_auth_headers)
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_read_seferler_unexpected_error(async_client, admin_auth_headers):
    """GET / service raises unexpected error → 500 (lines 94-96)."""
    mock_svc = AsyncMock()
    mock_svc.get_all_paged = AsyncMock(side_effect=RuntimeError("boom"))
    with _override_sefer_service(mock_svc):
        resp = await async_client.get("/api/v1/trips/", headers=admin_auth_headers)
    assert resp.status_code == 500


@pytest.mark.asyncio
async def test_read_seferler_with_filters(async_client, admin_auth_headers):
    """GET / with query params passed through."""
    mock_svc = AsyncMock()
    mock_svc.get_all_paged = AsyncMock(return_value=_make_list_response([]))
    with _override_sefer_service(mock_svc):
        resp = await async_client.get(
            "/api/v1/trips/?durum=Planned&skip=0&limit=50&search=Ankara",
            headers=admin_auth_headers,
        )
    assert resp.status_code == 200


# ---------------------------------------------------------------------------
# GET /trips/today  (lines 105-119)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_read_today_success(async_client, admin_auth_headers):
    """GET /today → 200 (lines 105-112)."""
    mock_svc = AsyncMock()
    mock_svc.get_all_paged = AsyncMock(return_value=_make_list_response())
    with _override_sefer_service(mock_svc):
        resp = await async_client.get("/api/v1/trips/today", headers=admin_auth_headers)
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_read_today_unexpected_error(async_client, admin_auth_headers):
    """GET /today service error → 500 (lines 117-119)."""
    mock_svc = AsyncMock()
    mock_svc.get_all_paged = AsyncMock(side_effect=RuntimeError("fail"))
    with _override_sefer_service(mock_svc):
        resp = await async_client.get("/api/v1/trips/today", headers=admin_auth_headers)
    assert resp.status_code == 500


# ---------------------------------------------------------------------------
# GET /trips/export  (lines 137-199)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_export_seferler_success(async_client, admin_auth_headers):
    """GET /export → 200 streaming response (lines 137-190)."""
    item = _make_sefer_response_obj()
    mock_svc = AsyncMock()
    mock_svc.get_all_paged = AsyncMock(
        return_value={"items": [item], "meta": {"total": 1}}
    )
    fake_excel = b"PK\x03\x04dummy-excel-bytes"
    with (
        _override_sefer_service(mock_svc),
        patch(
            "app.api.v1.endpoints.trips.ExcelService.export_data",
            new_callable=AsyncMock,
            return_value=fake_excel,
        ),
    ):
        resp = await async_client.get(
            "/api/v1/trips/export", headers=admin_auth_headers
        )
    assert resp.status_code == 200
    assert "Content-Disposition" in resp.headers


@pytest.mark.asyncio
async def test_export_seferler_value_error(async_client, admin_auth_headers):
    """GET /export with >5000 results → 422 (lines 157-160, 191-192)."""
    item = _make_sefer_response_obj()
    mock_svc = AsyncMock()
    # meta.total > 5000 triggers ValueError inside the endpoint
    mock_svc.get_all_paged = AsyncMock(
        return_value={"items": [item], "meta": {"total": 9999}}
    )
    with _override_sefer_service(mock_svc):
        resp = await async_client.get(
            "/api/v1/trips/export", headers=admin_auth_headers
        )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_export_seferler_unexpected_error(async_client, admin_auth_headers):
    """GET /export service exception → 500 (lines 197-201)."""
    mock_svc = AsyncMock()
    mock_svc.get_all_paged = AsyncMock(side_effect=RuntimeError("unexpected"))
    with _override_sefer_service(mock_svc):
        resp = await async_client.get(
            "/api/v1/trips/export", headers=admin_auth_headers
        )
    assert resp.status_code == 500


# ---------------------------------------------------------------------------
# GET /trips/stats  (lines 216-240)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_trip_stats_success(async_client, admin_auth_headers):
    """GET /stats → 200 (lines 222-228)."""
    mock_svc = AsyncMock()
    mock_svc.get_trip_stats = AsyncMock(return_value=_make_stats_dict())
    with _override_sefer_service(mock_svc):
        resp = await async_client.get("/api/v1/trips/stats", headers=admin_auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "total_count" in data


@pytest.mark.asyncio
async def test_get_trip_stats_invalid_date(async_client, admin_auth_headers):
    """GET /stats with bad date → 422 (lines 219-220)."""
    mock_svc = AsyncMock()
    with _override_sefer_service(mock_svc):
        resp = await async_client.get(
            "/api/v1/trips/stats?baslangic_tarih=not-a-date",
            headers=admin_auth_headers,
        )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_get_trip_stats_with_date_filters(async_client, admin_auth_headers):
    """GET /stats with valid date params → 200."""
    mock_svc = AsyncMock()
    mock_svc.get_trip_stats = AsyncMock(return_value=_make_stats_dict())
    with _override_sefer_service(mock_svc):
        resp = await async_client.get(
            "/api/v1/trips/stats?baslangic_tarih=2026-01-01&bitis_tarih=2026-06-01",
            headers=admin_auth_headers,
        )
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_get_trip_stats_unexpected_error(async_client, admin_auth_headers):
    """GET /stats service error → 500 (lines 235-240)."""
    mock_svc = AsyncMock()
    mock_svc.get_trip_stats = AsyncMock(side_effect=RuntimeError("db error"))
    with _override_sefer_service(mock_svc):
        resp = await async_client.get("/api/v1/trips/stats", headers=admin_auth_headers)
    assert resp.status_code == 500


# ---------------------------------------------------------------------------
# GET /trips/analytics/fuel-performance  (lines 257-280)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_fuel_performance_success(async_client, admin_auth_headers):
    """GET /analytics/fuel-performance → 200 (lines 263-271)."""
    # Tier E madde 33: shape matches
    # SeferRepository.get_fuel_performance_analytics's real return dict — the
    # endpoint now has response_model=FuelPerformanceAnalyticsResponse.
    mock_svc = AsyncMock()
    mock_svc.get_fuel_performance_analytics = AsyncMock(
        return_value={
            "kpis": {
                "mae": 1.2,
                "rmse": 1.5,
                "total_compared": 10,
                "high_deviation_ratio": 0.1,
            },
            "trend": [],
            "distribution": [],
            "outliers": [],
            "low_data": False,
        }
    )
    with _override_sefer_service(mock_svc):
        resp = await async_client.get(
            "/api/v1/trips/analytics/fuel-performance", headers=admin_auth_headers
        )
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_fuel_performance_bad_date(async_client, admin_auth_headers):
    """GET /analytics/fuel-performance with bad date → 422 (lines 260-261)."""
    mock_svc = AsyncMock()
    with _override_sefer_service(mock_svc):
        resp = await async_client.get(
            "/api/v1/trips/analytics/fuel-performance?baslangic_tarih=INVALID",
            headers=admin_auth_headers,
        )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_fuel_performance_unexpected_error(async_client, admin_auth_headers):
    """GET /analytics/fuel-performance service error → 500 (lines 278-280)."""
    mock_svc = AsyncMock()
    mock_svc.get_fuel_performance_analytics = AsyncMock(
        side_effect=RuntimeError("internal")
    )
    with _override_sefer_service(mock_svc):
        resp = await async_client.get(
            "/api/v1/trips/analytics/fuel-performance", headers=admin_auth_headers
        )
    assert resp.status_code == 500


# ---------------------------------------------------------------------------
# POST /trips/  — create  (lines 297-362)
# ---------------------------------------------------------------------------

_SEFER_CREATE_PAYLOAD = dict(
    sefer_no="TEST-001",
    tarih=date.today().isoformat(),
    arac_id=1,
    sofor_id=1,
    cikis_yeri="Istanbul",
    varis_yeri="Ankara",
    mesafe_km=450.0,
    durum="Planned",
)


@pytest.mark.asyncio
async def test_create_sefer_success(async_client, admin_auth_headers):
    """POST / → 201 (lines 297-328)."""
    sefer_obj = _make_sefer_response_obj()
    mock_svc = AsyncMock()
    mock_svc.add_sefer = AsyncMock(return_value=1)
    mock_svc.get_sefer_by_id = AsyncMock(return_value=sefer_obj)
    with _override_sefer_service(mock_svc):
        resp = await async_client.post(
            "/api/v1/trips/", json=_SEFER_CREATE_PAYLOAD, headers=admin_auth_headers
        )
    assert resp.status_code == 201


@pytest.mark.asyncio
async def test_create_sefer_not_found_after_create(async_client, admin_auth_headers):
    """POST / service returns id but get_sefer_by_id returns None → 500 (lines 306-312)."""
    mock_svc = AsyncMock()
    mock_svc.add_sefer = AsyncMock(return_value=99)
    mock_svc.get_sefer_by_id = AsyncMock(return_value=None)
    with _override_sefer_service(mock_svc):
        resp = await async_client.post(
            "/api/v1/trips/", json=_SEFER_CREATE_PAYLOAD, headers=admin_auth_headers
        )
    assert resp.status_code == 500


@pytest.mark.asyncio
async def test_create_sefer_value_error(async_client, admin_auth_headers):
    """POST / service raises ValueError → 400 (lines 332-334)."""
    mock_svc = AsyncMock()
    mock_svc.add_sefer = AsyncMock(side_effect=ValueError("arac not found"))
    with _override_sefer_service(mock_svc):
        resp = await async_client.post(
            "/api/v1/trips/", json=_SEFER_CREATE_PAYLOAD, headers=admin_auth_headers
        )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_create_sefer_invalid_payload(async_client, admin_auth_headers):
    """POST / with missing required fields → 422."""
    resp = await async_client.post(
        "/api/v1/trips/", json={"arac_id": 1}, headers=admin_auth_headers
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_create_sefer_unexpected_error(async_client, admin_auth_headers):
    """POST / unexpected exception → 500 (lines 339-362)."""
    mock_svc = AsyncMock()
    mock_svc.add_sefer = AsyncMock(side_effect=RuntimeError("database gone"))
    with _override_sefer_service(mock_svc):
        resp = await async_client.post(
            "/api/v1/trips/", json=_SEFER_CREATE_PAYLOAD, headers=admin_auth_headers
        )
    assert resp.status_code == 500


# ---------------------------------------------------------------------------
# POST /trips/{id}/return  (lines 365-402)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_return_trip_success(async_client, admin_auth_headers):
    """POST /{id}/return → 201 (lines 372-390)."""
    sefer_obj = _make_sefer_response_obj()
    mock_svc = AsyncMock()
    mock_svc.create_return_trip = AsyncMock(return_value=2)
    mock_svc.get_sefer_by_id = AsyncMock(return_value=sefer_obj)
    with _override_sefer_service(mock_svc):
        resp = await async_client.post(
            "/api/v1/trips/1/return", headers=admin_auth_headers
        )
    assert resp.status_code == 201


@pytest.mark.asyncio
async def test_create_return_trip_not_found_after_create(
    async_client, admin_auth_headers
):
    """POST /{id}/return → get_sefer_by_id None → 500 (lines 379-382)."""
    mock_svc = AsyncMock()
    mock_svc.create_return_trip = AsyncMock(return_value=3)
    mock_svc.get_sefer_by_id = AsyncMock(return_value=None)
    with _override_sefer_service(mock_svc):
        resp = await async_client.post(
            "/api/v1/trips/1/return", headers=admin_auth_headers
        )
    assert resp.status_code == 500


@pytest.mark.asyncio
async def test_create_return_trip_value_error(async_client, admin_auth_headers):
    """POST /{id}/return raises ValueError → 400 (lines 392-393)."""
    mock_svc = AsyncMock()
    mock_svc.create_return_trip = AsyncMock(side_effect=ValueError("no sefer"))
    with _override_sefer_service(mock_svc):
        resp = await async_client.post(
            "/api/v1/trips/1/return", headers=admin_auth_headers
        )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_create_return_trip_unexpected_error(async_client, admin_auth_headers):
    """POST /{id}/return unexpected error → 500 (lines 398-402)."""
    mock_svc = AsyncMock()
    mock_svc.create_return_trip = AsyncMock(side_effect=RuntimeError("crash"))
    with _override_sefer_service(mock_svc):
        resp = await async_client.post(
            "/api/v1/trips/1/return", headers=admin_auth_headers
        )
    assert resp.status_code == 500


# ---------------------------------------------------------------------------
# GET /trips/beklemede  (lines 413-421)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_beklemede_seferler_success(async_client, admin_auth_headers):
    """GET /beklemede → 200 list (lines 413-414)."""
    sefer_obj = _make_sefer_response_obj()
    mock_svc = AsyncMock()
    mock_svc.get_by_onay_durumu = AsyncMock(return_value=[sefer_obj])
    with _override_sefer_service(mock_svc):
        resp = await async_client.get(
            "/api/v1/trips/beklemede", headers=admin_auth_headers
        )
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


@pytest.mark.asyncio
async def test_beklemede_seferler_error(async_client, admin_auth_headers):
    """GET /beklemede service error → 500 (lines 419-421)."""
    mock_svc = AsyncMock()
    mock_svc.get_by_onay_durumu = AsyncMock(side_effect=RuntimeError("fail"))
    with _override_sefer_service(mock_svc):
        resp = await async_client.get(
            "/api/v1/trips/beklemede", headers=admin_auth_headers
        )
    assert resp.status_code == 500


# ---------------------------------------------------------------------------
# GET /trips/excel/template  (lines 429-446)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_excel_template_success(async_client, admin_auth_headers):
    """GET /excel/template → 200 with file content (lines 429-439)."""
    fake_bytes = b"PK\x03\x04fake-template"
    with patch(
        "app.api.v1.endpoints.trips.ExcelService.generate_template",
        new_callable=AsyncMock,
        return_value=fake_bytes,
    ):
        resp = await async_client.get(
            "/api/v1/trips/excel/template", headers=admin_auth_headers
        )
    assert resp.status_code == 200
    assert "Content-Disposition" in resp.headers


@pytest.mark.asyncio
async def test_get_excel_template_error(async_client, admin_auth_headers):
    """GET /excel/template ExcelService raises → 500 (lines 444-446)."""
    with patch(
        "app.api.v1.endpoints.trips.ExcelService.generate_template",
        new_callable=AsyncMock,
        side_effect=RuntimeError("template generation failed"),
    ):
        resp = await async_client.get(
            "/api/v1/trips/excel/template", headers=admin_auth_headers
        )
    assert resp.status_code == 500


# ---------------------------------------------------------------------------
# GET /trips/{sefer_id}  — single trip  (lines 456-459)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_read_sefer_success(async_client, admin_auth_headers):
    """GET /{id} → 200 (lines 456-459)."""
    sefer_obj = _make_sefer_response_obj()
    mock_svc = AsyncMock()
    mock_svc.get_by_id = AsyncMock(return_value=sefer_obj)
    with _override_sefer_service(mock_svc):
        resp = await async_client.get("/api/v1/trips/1", headers=admin_auth_headers)
    assert resp.status_code == 200
    assert resp.json()["id"] == 1


@pytest.mark.asyncio
async def test_read_sefer_not_found(async_client, admin_auth_headers):
    """GET /{id} not found → 404 (lines 457-458)."""
    mock_svc = AsyncMock()
    mock_svc.get_by_id = AsyncMock(return_value=None)
    with _override_sefer_service(mock_svc):
        resp = await async_client.get("/api/v1/trips/9999", headers=admin_auth_headers)
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# GET /trips/{sefer_id}/cost-analysis  (lines 472-494)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_analyze_trip_costs_success(async_client, admin_auth_headers):
    """GET /{id}/cost-analysis → 202 with task_id (lines 472-485)."""
    sefer_obj = _make_sefer_response_obj()
    mock_svc = AsyncMock()
    mock_svc.get_by_id = AsyncMock(return_value=sefer_obj)
    mock_svc.reconcile_costs = AsyncMock(return_value={"result": "ok"})

    mock_jm = MagicMock()
    mock_jm.submit = AsyncMock(return_value="job-uuid-1")

    with _override_sefer_service(mock_svc), _override_job_manager(mock_jm):
        resp = await async_client.get(
            "/api/v1/trips/1/cost-analysis", headers=admin_auth_headers
        )
    assert resp.status_code == 202
    data = resp.json()
    assert data["status"] == "PROCESSING"
    assert "task_id" in data


@pytest.mark.asyncio
async def test_analyze_trip_costs_not_found(async_client, admin_auth_headers):
    """GET /{id}/cost-analysis trip not found → 404 (lines 475-476)."""
    mock_svc = AsyncMock()
    mock_svc.get_by_id = AsyncMock(return_value=None)

    mock_jm = MagicMock()
    with _override_sefer_service(mock_svc), _override_job_manager(mock_jm):
        resp = await async_client.get(
            "/api/v1/trips/9999/cost-analysis", headers=admin_auth_headers
        )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_analyze_trip_costs_unexpected_error(async_client, admin_auth_headers):
    """GET /{id}/cost-analysis unexpected error → 500 (lines 492-494)."""
    mock_svc = AsyncMock()
    mock_svc.get_by_id = AsyncMock(side_effect=RuntimeError("crash"))

    mock_jm = MagicMock()
    with _override_sefer_service(mock_svc), _override_job_manager(mock_jm):
        resp = await async_client.get(
            "/api/v1/trips/1/cost-analysis", headers=admin_auth_headers
        )
    assert resp.status_code == 500


# ---------------------------------------------------------------------------
# PATCH /trips/{sefer_id}  — update  (lines 505-526)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_update_sefer_success(async_client, admin_auth_headers):
    """PATCH /{id} → 200 (lines 505-516)."""
    sefer_obj = _make_sefer_response_obj()
    mock_svc = AsyncMock()
    mock_svc.update_sefer = AsyncMock(return_value=True)
    mock_svc.get_sefer_by_id = AsyncMock(return_value=sefer_obj)
    with _override_sefer_service(mock_svc):
        resp = await async_client.patch(
            "/api/v1/trips/1",
            json={"mesafe_km": 500.0},
            headers=admin_auth_headers,
        )
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_update_sefer_not_found(async_client, admin_auth_headers):
    """PATCH /{id} not found → 404 (lines 509-510)."""
    mock_svc = AsyncMock()
    mock_svc.update_sefer = AsyncMock(return_value=False)
    with _override_sefer_service(mock_svc):
        resp = await async_client.patch(
            "/api/v1/trips/9999",
            json={"mesafe_km": 100.0},
            headers=admin_auth_headers,
        )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_update_sefer_value_error(async_client, admin_auth_headers):
    """PATCH /{id} ValueError → 400 (lines 518-519)."""
    mock_svc = AsyncMock()
    mock_svc.update_sefer = AsyncMock(side_effect=ValueError("bad status"))
    with _override_sefer_service(mock_svc):
        resp = await async_client.patch(
            "/api/v1/trips/1",
            json={"mesafe_km": 100.0},
            headers=admin_auth_headers,
        )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_update_sefer_unexpected_error(async_client, admin_auth_headers):
    """PATCH /{id} unexpected error → 500 (lines 523-526)."""
    mock_svc = AsyncMock()
    mock_svc.update_sefer = AsyncMock(side_effect=RuntimeError("db error"))
    with _override_sefer_service(mock_svc):
        resp = await async_client.patch(
            "/api/v1/trips/1",
            json={"mesafe_km": 200.0},
            headers=admin_auth_headers,
        )
    assert resp.status_code == 500


# ---------------------------------------------------------------------------
# DELETE /trips/{sefer_id}  (lines 537-556)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_delete_sefer_success(async_client, admin_auth_headers):
    """DELETE /{id} → 200 soft-delete (lines 537-548)."""
    mock_svc = AsyncMock()
    mock_svc.delete_sefer = AsyncMock(return_value=True)
    with _override_sefer_service(mock_svc):
        resp = await async_client.delete("/api/v1/trips/1", headers=admin_auth_headers)
    assert resp.status_code == 200
    assert resp.json()["soft_deleted"] is True


@pytest.mark.asyncio
async def test_delete_sefer_not_found(async_client, admin_auth_headers):
    """DELETE /{id} not found → 404 (lines 539-542)."""
    mock_svc = AsyncMock()
    mock_svc.delete_sefer = AsyncMock(return_value=False)
    with _override_sefer_service(mock_svc):
        resp = await async_client.delete(
            "/api/v1/trips/9999", headers=admin_auth_headers
        )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_delete_sefer_unexpected_error(async_client, admin_auth_headers):
    """DELETE /{id} unexpected error → 500 (lines 553-556)."""
    mock_svc = AsyncMock()
    mock_svc.delete_sefer = AsyncMock(side_effect=RuntimeError("crash"))
    with _override_sefer_service(mock_svc):
        resp = await async_client.delete("/api/v1/trips/1", headers=admin_auth_headers)
    assert resp.status_code == 500


# ---------------------------------------------------------------------------
# POST /trips/upload  (lines 577-637)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_upload_sefer_excel_success(async_client, admin_auth_headers):
    """POST /upload with valid Excel → 200 (lines 617-637)."""
    mock_import_svc = AsyncMock()
    mock_import_svc.process_excel_import = AsyncMock(return_value=(5, []))

    mock_jm = MagicMock()
    mock_jm.submit = AsyncMock(return_value="job-uuid-upload")

    with (
        _override_job_manager(mock_jm),
        patch(
            "app.services.api.sefer_import_service.get_sefer_import_service",
            return_value=mock_import_svc,
        ),
    ):
        resp = await async_client.post(
            "/api/v1/trips/upload",
            files={
                "file": (
                    "trips.xlsx",
                    b"PK\x03\x04fake-excel",
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                )
            },
            headers=admin_auth_headers,
        )
    assert resp.status_code == 200
    data = resp.json()
    assert "success_count" in data


@pytest.mark.asyncio
async def test_upload_sefer_excel_async_mode(async_client, admin_auth_headers):
    """POST /upload?async_mode=true → 200 with task_id (lines 629-635)."""
    mock_import_svc = AsyncMock()
    mock_import_svc.process_excel_import = AsyncMock(return_value=(2, []))

    mock_jm = MagicMock()
    mock_jm.submit = AsyncMock(return_value="job-uuid-async")

    with (
        _override_job_manager(mock_jm),
        patch(
            "app.services.api.sefer_import_service.get_sefer_import_service",
            return_value=mock_import_svc,
        ),
    ):
        resp = await async_client.post(
            "/api/v1/trips/upload?async_mode=true",
            files={
                "file": (
                    "trips.xlsx",
                    b"PK\x03\x04fake-excel",
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                )
            },
            headers=admin_auth_headers,
        )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "PROCESSING"
    assert "task_id" in data


@pytest.mark.asyncio
async def test_upload_invalid_file_extension(async_client, admin_auth_headers):
    """POST /upload with .csv file → 400 (lines 589-592)."""
    resp = await async_client.post(
        "/api/v1/trips/upload",
        files={"file": ("trips.csv", b"col1,col2\n1,2", "text/csv")},
        headers=admin_auth_headers,
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_upload_invalid_mime_type(async_client, admin_auth_headers):
    """POST /upload with wrong MIME type → 400 (lines 582-586)."""
    resp = await async_client.post(
        "/api/v1/trips/upload",
        files={"file": ("trips.xlsx", b"data", "text/plain")},
        headers=admin_auth_headers,
    )
    assert resp.status_code == 400


# ---------------------------------------------------------------------------
# PATCH /trips/bulk/status  (lines 651-658)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_bulk_update_status_success(async_client, admin_auth_headers):
    """PATCH /bulk/status → 200 (lines 651-658)."""
    mock_svc = AsyncMock()
    mock_svc.bulk_update_status = AsyncMock(
        return_value={"success_count": 2, "failed_count": 0, "failed": []}
    )
    with _override_sefer_service(mock_svc):
        resp = await async_client.patch(
            "/api/v1/trips/bulk/status",
            json={"sefer_ids": [1, 2], "new_status": "Completed"},
            headers=admin_auth_headers,
        )
    assert resp.status_code == 200
    assert resp.json()["success_count"] == 2


@pytest.mark.asyncio
async def test_bulk_update_status_limit_exceeded(async_client, admin_auth_headers):
    """PATCH /bulk/status with >500 IDs → 400 (line 651-652)."""
    resp = await async_client.patch(
        "/api/v1/trips/bulk/status",
        json={"sefer_ids": list(range(501)), "new_status": "Completed"},
        headers=admin_auth_headers,
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_bulk_update_status_value_error(async_client, admin_auth_headers):
    """PATCH /bulk/status service ValueError → 422 (lines 657-658)."""
    mock_svc = AsyncMock()
    mock_svc.bulk_update_status = AsyncMock(side_effect=ValueError("invalid status"))
    with _override_sefer_service(mock_svc):
        resp = await async_client.patch(
            "/api/v1/trips/bulk/status",
            json={"sefer_ids": [1, 2], "new_status": "Completed"},
            headers=admin_auth_headers,
        )
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# PATCH /trips/bulk/cancel  (lines 672-676)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_bulk_cancel_success(async_client, admin_auth_headers):
    """PATCH /bulk/cancel → 200 (lines 672-676)."""
    mock_svc = AsyncMock()
    mock_svc.bulk_cancel = AsyncMock(
        return_value={"success_count": 3, "failed_count": 0, "failed": []}
    )
    with _override_sefer_service(mock_svc):
        resp = await async_client.patch(
            "/api/v1/trips/bulk/cancel",
            json={"sefer_ids": [1, 2, 3], "iptal_nedeni": "Test iptal"},
            headers=admin_auth_headers,
        )
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_bulk_cancel_limit_exceeded(async_client, admin_auth_headers):
    """PATCH /bulk/cancel >500 IDs → 400 (lines 672-673)."""
    resp = await async_client.patch(
        "/api/v1/trips/bulk/cancel",
        json={"sefer_ids": list(range(501)), "iptal_nedeni": "test"},
        headers=admin_auth_headers,
    )
    assert resp.status_code == 400


# ---------------------------------------------------------------------------
# POST /trips/bulk-delete  (lines 686-693)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_bulk_delete_success(async_client, admin_auth_headers):
    """POST /bulk-delete → 200 (lines 686-693)."""
    mock_svc = AsyncMock()
    mock_svc.bulk_delete = AsyncMock(
        return_value={"success_count": 2, "failed_count": 0, "failed": []}
    )
    with _override_sefer_service(mock_svc):
        resp = await async_client.post(
            "/api/v1/trips/bulk-delete",
            json={"sefer_ids": [1, 2]},
            headers=admin_auth_headers,
        )
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_bulk_delete_empty_list(async_client, admin_auth_headers):
    """POST /bulk-delete with empty list → returns zeroed response (lines 690-692)."""
    mock_svc = AsyncMock()
    with _override_sefer_service(mock_svc):
        resp = await async_client.post(
            "/api/v1/trips/bulk-delete",
            json={"sefer_ids": []},
            headers=admin_auth_headers,
        )
    assert resp.status_code == 200
    data = resp.json()
    assert data["success_count"] == 0


@pytest.mark.asyncio
async def test_bulk_delete_limit_exceeded(async_client, admin_auth_headers):
    """POST /bulk-delete >500 IDs → 400 (lines 687-688)."""
    resp = await async_client.post(
        "/api/v1/trips/bulk-delete",
        json={"sefer_ids": list(range(501))},
        headers=admin_auth_headers,
    )
    assert resp.status_code == 400


# ---------------------------------------------------------------------------
# GET /trips/tasks/{task_id}/status  (lines 705-725)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_task_status_processing(async_client, admin_auth_headers):
    """GET /tasks/{id}/status → PROCESSING (lines 712-715)."""
    mock_jm = MagicMock()
    mock_jm.get_status = MagicMock(
        return_value={
            "status": "running",
            "result": None,
            "error": None,
            "timestamp": None,
        }
    )
    with _override_job_manager(mock_jm):
        resp = await async_client.get(
            "/api/v1/trips/tasks/job-123/status", headers=admin_auth_headers
        )
    assert resp.status_code == 200
    assert resp.json()["status"] == "PROCESSING"


@pytest.mark.asyncio
async def test_get_task_status_success(async_client, admin_auth_headers):
    """GET /tasks/{id}/status completed → SUCCESS (lines 713-715)."""
    mock_jm = MagicMock()
    mock_jm.get_status = MagicMock(
        return_value={
            "status": "completed",
            "result": {"success_count": 5},
            "error": None,
            "timestamp": None,
        }
    )
    with _override_job_manager(mock_jm):
        resp = await async_client.get(
            "/api/v1/trips/tasks/job-456/status", headers=admin_auth_headers
        )
    assert resp.status_code == 200
    assert resp.json()["status"] == "SUCCESS"


@pytest.mark.asyncio
async def test_get_task_status_failed(async_client, admin_auth_headers):
    """GET /tasks/{id}/status failed → FAILED (lines 716-717)."""
    mock_jm = MagicMock()
    mock_jm.get_status = MagicMock(
        return_value={
            "status": "failed",
            "result": None,
            "error": "Something broke",
            "timestamp": None,
        }
    )
    with _override_job_manager(mock_jm):
        resp = await async_client.get(
            "/api/v1/trips/tasks/job-789/status", headers=admin_auth_headers
        )
    assert resp.status_code == 200
    assert resp.json()["status"] == "FAILED"


@pytest.mark.asyncio
async def test_get_task_status_not_found(async_client, admin_auth_headers):
    """GET /tasks/{id}/status unknown → 404 (lines 707-710)."""
    mock_jm = MagicMock()
    mock_jm.get_status = MagicMock(return_value={"status": "unknown"})
    with _override_job_manager(mock_jm):
        resp = await async_client.get(
            "/api/v1/trips/tasks/no-such-task/status", headers=admin_auth_headers
        )
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# GET /trips/{sefer_id}/timeline  (lines 735-747)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_sefer_timeline_success(async_client, admin_auth_headers):
    """GET /{id}/timeline → 200 with items (lines 735-740)."""
    sefer_obj = _make_sefer_response_obj()
    mock_svc = AsyncMock()
    mock_svc.get_by_id = AsyncMock(return_value=sefer_obj)
    mock_svc.get_timeline = AsyncMock(
        return_value=[{"event": "created", "timestamp": "2026-06-01T10:00:00"}]
    )
    with _override_sefer_service(mock_svc):
        resp = await async_client.get(
            "/api/v1/trips/1/timeline", headers=admin_auth_headers
        )
    assert resp.status_code == 200
    assert "items" in resp.json()


@pytest.mark.asyncio
async def test_get_sefer_timeline_unexpected_error(async_client, admin_auth_headers):
    """GET /{id}/timeline unexpected error → 500 (lines 745-747)."""
    mock_svc = AsyncMock()
    mock_svc.get_by_id = AsyncMock(side_effect=RuntimeError("fail"))
    with _override_sefer_service(mock_svc):
        resp = await async_client.get(
            "/api/v1/trips/1/timeline", headers=admin_auth_headers
        )
    assert resp.status_code == 500


# ---------------------------------------------------------------------------
# POST /trips/{sefer_id}/onayla  (lines 761-776)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_sefer_onayla_success(async_client, admin_auth_headers):
    """POST /{id}/onayla → 200 (lines 761-769)."""
    sefer_obj = _make_sefer_response_obj()
    mock_svc = AsyncMock()
    mock_svc.get_by_id = AsyncMock(return_value=sefer_obj)
    mock_svc.set_onay_durumu = AsyncMock(return_value=sefer_obj)
    with (
        _override_sefer_service(mock_svc),
        patch("app.api.v1.endpoints.trips.trip_approval_total") as mock_metric,
    ):
        mock_metric.labels.return_value.inc = MagicMock()
        resp = await async_client.post(
            "/api/v1/trips/1/onayla",
            json={"onay_notu": "OK"},
            headers=admin_auth_headers,
        )
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_sefer_onayla_not_found(async_client, admin_auth_headers):
    """POST /{id}/onayla trip not found → 404 (lines 762-763)."""
    mock_svc = AsyncMock()
    mock_svc.get_by_id = AsyncMock(return_value=None)
    with _override_sefer_service(mock_svc):
        resp = await async_client.post(
            "/api/v1/trips/9999/onayla", json={}, headers=admin_auth_headers
        )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_sefer_onayla_unexpected_error(async_client, admin_auth_headers):
    """POST /{id}/onayla service error → 500 (lines 773-776)."""
    sefer_obj = _make_sefer_response_obj()
    mock_svc = AsyncMock()
    mock_svc.get_by_id = AsyncMock(return_value=sefer_obj)
    mock_svc.set_onay_durumu = AsyncMock(side_effect=RuntimeError("crash"))
    with _override_sefer_service(mock_svc):
        resp = await async_client.post(
            "/api/v1/trips/1/onayla", json={}, headers=admin_auth_headers
        )
    assert resp.status_code == 500


# ---------------------------------------------------------------------------
# POST /trips/{sefer_id}/reddet  (lines 787-802)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_sefer_reddet_success(async_client, admin_auth_headers):
    """POST /{id}/reddet → 200 (lines 787-796)."""
    sefer_obj = _make_sefer_response_obj()
    mock_svc = AsyncMock()
    mock_svc.get_by_id = AsyncMock(return_value=sefer_obj)
    mock_svc.set_onay_durumu = AsyncMock(return_value=sefer_obj)
    with (
        _override_sefer_service(mock_svc),
        patch("app.api.v1.endpoints.trips.trip_approval_total") as mock_metric,
    ):
        mock_metric.labels.return_value.inc = MagicMock()
        resp = await async_client.post(
            "/api/v1/trips/1/reddet",
            json={"onay_notu": "Reddedildi"},
            headers=admin_auth_headers,
        )
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_sefer_reddet_not_found(async_client, admin_auth_headers):
    """POST /{id}/reddet trip not found → 404 (lines 788-789)."""
    mock_svc = AsyncMock()
    mock_svc.get_by_id = AsyncMock(return_value=None)
    with _override_sefer_service(mock_svc):
        resp = await async_client.post(
            "/api/v1/trips/9999/reddet", json={}, headers=admin_auth_headers
        )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_sefer_reddet_unexpected_error(async_client, admin_auth_headers):
    """POST /{id}/reddet service error → 500 (lines 800-802)."""
    sefer_obj = _make_sefer_response_obj()
    mock_svc = AsyncMock()
    mock_svc.get_by_id = AsyncMock(return_value=sefer_obj)
    mock_svc.set_onay_durumu = AsyncMock(side_effect=RuntimeError("crash"))
    with _override_sefer_service(mock_svc):
        resp = await async_client.post(
            "/api/v1/trips/1/reddet", json={}, headers=admin_auth_headers
        )
    assert resp.status_code == 500


# ---------------------------------------------------------------------------
# POST /trips/plan-wizard  (lines 821-881)
# ---------------------------------------------------------------------------

_PLAN_WIZARD_PAYLOAD = dict(
    tarih=date.today().isoformat(),
    cikis_yeri="Istanbul",
    varis_yeri="Ankara",
    mesafe_km=450.0,
)


@pytest.mark.asyncio
async def test_plan_wizard_disabled(async_client, admin_auth_headers):
    """POST /plan-wizard when feature flag off → 503 (lines 826-827)."""
    from app.config import settings

    original = settings.TRIP_PLANNER_ENABLED
    settings.TRIP_PLANNER_ENABLED = False
    try:
        resp = await async_client.post(
            "/api/v1/trips/plan-wizard",
            json=_PLAN_WIZARD_PAYLOAD,
            headers=admin_auth_headers,
        )
    finally:
        settings.TRIP_PLANNER_ENABLED = original
    assert resp.status_code == 503


@pytest.mark.asyncio
async def test_plan_wizard_success(async_client, admin_auth_headers):
    """POST /plan-wizard → 200 with plan response (lines 844-881)."""
    from app.config import settings

    original = settings.TRIP_PLANNER_ENABLED
    settings.TRIP_PLANNER_ENABLED = True

    fake_result = MagicMock()
    fake_result.weather_impact = 1.02
    fake_result.risk_label = "low"
    fake_result.route_type = "highway_dominant"
    fake_result.vehicles = []
    fake_result.drivers = []
    fake_result.generated_at = datetime.now(timezone.utc)
    fake_result.cache_hit = False

    mock_engine = MagicMock()
    mock_engine.plan = AsyncMock(return_value=fake_result)

    try:
        with (
            patch(
                "app.core.ai.trip_planner.TripPlannerEngine", return_value=mock_engine
            ),
            patch(
                "app.infrastructure.audit.audit_logger.log_audit_event",
                new_callable=AsyncMock,
            ),
        ):
            resp = await async_client.post(
                "/api/v1/trips/plan-wizard",
                json=_PLAN_WIZARD_PAYLOAD,
                headers=admin_auth_headers,
            )
    finally:
        settings.TRIP_PLANNER_ENABLED = original

    assert resp.status_code == 200
    data = resp.json()
    assert "vehicles" in data
    assert "drivers" in data


@pytest.mark.asyncio
async def test_plan_wizard_engine_error(async_client, admin_auth_headers):
    """POST /plan-wizard engine error → 500 (lines 847-849)."""
    from app.config import settings

    original = settings.TRIP_PLANNER_ENABLED
    settings.TRIP_PLANNER_ENABLED = True

    mock_engine = MagicMock()
    mock_engine.plan = AsyncMock(side_effect=RuntimeError("engine failed"))

    try:
        with patch(
            "app.core.ai.trip_planner.TripPlannerEngine", return_value=mock_engine
        ):
            resp = await async_client.post(
                "/api/v1/trips/plan-wizard",
                json=_PLAN_WIZARD_PAYLOAD,
                headers=admin_auth_headers,
            )
    finally:
        settings.TRIP_PLANNER_ENABLED = original

    assert resp.status_code == 500
