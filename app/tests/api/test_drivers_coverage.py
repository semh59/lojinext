"""
Drivers endpoint coverage tests.

Targets missing lines in app/api/v1/endpoints/drivers.py (28% → ≥70%).
All service/DB calls are mocked — no real DB needed.
"""

from contextlib import contextmanager
from datetime import date, datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

pytestmark = pytest.mark.unit

# ---------------------------------------------------------------------------
# Helper factories
# ---------------------------------------------------------------------------


def _make_sofor_orm(**kwargs):
    """Return a mock ORM Sofor object compatible with SoforResponse."""
    obj = MagicMock()
    obj.id = kwargs.get("id", 1)
    obj.ad_soyad = kwargs.get("ad_soyad", "Ahmet Yilmaz")
    obj.telefon = kwargs.get("telefon", "05321234567")
    obj.ehliyet_sinifi = kwargs.get("ehliyet_sinifi", "E")
    obj.ise_baslama = kwargs.get("ise_baslama", date(2020, 1, 1))
    obj.score = kwargs.get("score", 1.0)
    obj.manual_score = kwargs.get("manual_score", 1.0)
    obj.aktif = kwargs.get("aktif", True)
    obj.notlar = kwargs.get("notlar", None)
    obj.telegram_id = kwargs.get("telegram_id", None)
    obj.created_at = kwargs.get("created_at", datetime(2020, 1, 1, tzinfo=timezone.utc))
    return obj


def _make_paged_result(items=None):
    """Return service.get_all_paged() return value."""
    if items is None:
        items = [
            {
                "id": 1,
                "ad_soyad": "Ahmet Yilmaz",
                "telefon": "05321234567",
                "ehliyet_sinifi": "E",
                "ise_baslama": None,
                "score": 1.0,
                "manual_score": 1.0,
                "aktif": True,
                "notlar": None,
                "telegram_id": None,
                "created_at": datetime(2020, 1, 1, tzinfo=timezone.utc),
            }
        ]
    return {"items": items, "total": len(items)}


# ---------------------------------------------------------------------------
# Context manager for sofor service override
# ---------------------------------------------------------------------------


@contextmanager
def _override_sofor_service(mock_svc):
    from app.api.deps import get_sofor_service
    from app.main import app

    async def _fake():
        return mock_svc

    app.dependency_overrides[get_sofor_service] = _fake
    try:
        yield
    finally:
        app.dependency_overrides.pop(get_sofor_service, None)


# ---------------------------------------------------------------------------
# GET /drivers/  — list drivers
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_drivers_success(async_client, admin_auth_headers):
    """GET / with valid auth → 200 standardresponse."""
    mock_svc = AsyncMock()
    mock_svc.get_all_paged = AsyncMock(return_value=_make_paged_result())

    with _override_sofor_service(mock_svc):
        resp = await async_client.get("/api/v1/drivers/", headers=admin_auth_headers)

    assert resp.status_code == 200
    data = resp.json()
    assert "data" in data
    assert "meta" in data


@pytest.mark.asyncio
async def test_list_drivers_no_auth(async_client):
    """GET / without auth → 401."""
    resp = await async_client.get("/api/v1/drivers/")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_list_drivers_with_filters(async_client, admin_auth_headers):
    """GET / with all query params passes them to service."""
    mock_svc = AsyncMock()
    mock_svc.get_all_paged = AsyncMock(return_value=_make_paged_result())

    with _override_sofor_service(mock_svc):
        resp = await async_client.get(
            "/api/v1/drivers/?aktif_only=true&search=Ahmet&ehliyet_sinifi=E"
            "&min_score=0.5&max_score=1.5",
            headers=admin_auth_headers,
        )

    assert resp.status_code == 200
    mock_svc.get_all_paged.assert_awaited_once()
    kwargs = mock_svc.get_all_paged.call_args.kwargs
    assert kwargs.get("search") == "Ahmet"
    assert kwargs.get("ehliyet_sinifi") == "E"


@pytest.mark.asyncio
async def test_list_drivers_service_error(async_client, admin_auth_headers):
    """GET / service raises unexpected error → 500."""
    mock_svc = AsyncMock()
    mock_svc.get_all_paged = AsyncMock(side_effect=RuntimeError("db crash"))

    with _override_sofor_service(mock_svc):
        resp = await async_client.get("/api/v1/drivers/", headers=admin_auth_headers)

    assert resp.status_code == 500


# ---------------------------------------------------------------------------
# GET /drivers/fleet-stats
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_fleet_stats_no_auth(async_client):
    """GET /fleet-stats without auth → 401."""
    resp = await async_client.get("/api/v1/drivers/fleet-stats")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_fleet_stats_success(async_client, admin_auth_headers):
    """GET /fleet-stats with mocked DB session → 200."""
    from app.database.connection import get_db
    from app.main import app

    mock_row = {"total": 20, "active": 15}
    mock_mapping = MagicMock()
    mock_mapping.one.return_value = mock_row
    mock_result = MagicMock()
    mock_result.mappings.return_value = mock_mapping

    mock_session = AsyncMock()
    mock_session.execute = AsyncMock(return_value=mock_result)

    async def _fake_db():
        return mock_session

    app.dependency_overrides[get_db] = _fake_db
    try:
        resp = await async_client.get(
            "/api/v1/drivers/fleet-stats", headers=admin_auth_headers
        )
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 20
    assert data["active"] == 15


# ---------------------------------------------------------------------------
# GET /drivers/{id}  — get single driver
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_driver_no_auth(async_client):
    """GET /{id} without auth → 401."""
    resp = await async_client.get("/api/v1/drivers/1")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_get_driver_not_found(async_client, admin_auth_headers):
    """GET /{id} for non-existent driver → 404."""
    from app.database.connection import get_db
    from app.main import app

    mock_session = AsyncMock()
    mock_session.get = AsyncMock(return_value=None)

    async def _fake_db():
        return mock_session

    app.dependency_overrides[get_db] = _fake_db
    try:
        resp = await async_client.get(
            "/api/v1/drivers/9999", headers=admin_auth_headers
        )
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_get_driver_success(async_client, admin_auth_headers):
    """GET /{id} → 200 with driver data."""
    from app.database.connection import get_db
    from app.main import app

    sofor = _make_sofor_orm(id=42)

    mock_session = AsyncMock()
    mock_session.get = AsyncMock(return_value=sofor)

    async def _fake_db():
        return mock_session

    app.dependency_overrides[get_db] = _fake_db
    try:
        resp = await async_client.get("/api/v1/drivers/42", headers=admin_auth_headers)
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert resp.status_code == 200


# ---------------------------------------------------------------------------
# POST /drivers/  — create driver
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_driver_no_auth(async_client):
    """POST / without admin auth → 401."""
    resp = await async_client.post(
        "/api/v1/drivers/",
        json={"ad_soyad": "Mehmet Kaya", "ehliyet_sinifi": "E"},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_create_driver_validation_error(async_client, admin_auth_headers):
    """POST / with too short ad_soyad → 422."""
    resp = await async_client.post(
        "/api/v1/drivers/",
        json={"ad_soyad": "AB", "ehliyet_sinifi": "E"},  # min_length=3
        headers=admin_auth_headers,
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_create_driver_success(async_client, admin_auth_headers):
    """POST / with valid body and mocked service → 201."""
    from app.database.connection import get_db
    from app.main import app

    sofor = _make_sofor_orm(id=10)

    mock_session = AsyncMock()
    mock_session.get = AsyncMock(return_value=sofor)

    mock_svc = AsyncMock()
    mock_svc.add_sofor = AsyncMock(return_value=10)
    mock_svc.get_by_id = AsyncMock(return_value=sofor)

    async def _fake_db():
        return mock_session

    app.dependency_overrides[get_db] = _fake_db
    with _override_sofor_service(mock_svc):
        resp = await async_client.post(
            "/api/v1/drivers/",
            json={"ad_soyad": "Mehmet Kaya", "ehliyet_sinifi": "E"},
            headers=admin_auth_headers,
        )
    app.dependency_overrides.pop(get_db, None)

    assert resp.status_code == 201


@pytest.mark.asyncio
async def test_create_driver_value_error(async_client, admin_auth_headers):
    """POST / service raises ValueError (e.g. duplicate) → 400."""
    from app.database.connection import get_db
    from app.main import app

    mock_session = AsyncMock()
    mock_svc = AsyncMock()
    mock_svc.add_sofor = AsyncMock(side_effect=ValueError("Zaten var"))

    async def _fake_db():
        return mock_session

    app.dependency_overrides[get_db] = _fake_db
    with _override_sofor_service(mock_svc):
        resp = await async_client.post(
            "/api/v1/drivers/",
            json={"ad_soyad": "Mehmet Kaya", "ehliyet_sinifi": "E"},
            headers=admin_auth_headers,
        )
    app.dependency_overrides.pop(get_db, None)

    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_create_driver_integrity_error(async_client, admin_auth_headers):
    """Concurrent duplicate: service hits the UNIQUE(ad_soyad) constraint and
    raises IntegrityError → endpoint maps to 400 (not a misleading 500)."""
    from sqlalchemy.exc import IntegrityError

    from app.database.connection import get_db
    from app.main import app

    mock_session = AsyncMock()
    mock_svc = AsyncMock()
    mock_svc.add_sofor = AsyncMock(
        side_effect=IntegrityError("INSERT ...", {}, Exception("duplicate key"))
    )

    async def _fake_db():
        return mock_session

    app.dependency_overrides[get_db] = _fake_db
    with _override_sofor_service(mock_svc):
        resp = await async_client.post(
            "/api/v1/drivers/",
            json={"ad_soyad": "Mehmet Kaya", "ehliyet_sinifi": "E"},
            headers=admin_auth_headers,
        )
    app.dependency_overrides.pop(get_db, None)

    assert resp.status_code == 400


# ---------------------------------------------------------------------------
# PUT /drivers/{id}  — update driver
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_update_driver_no_auth(async_client):
    """PUT /{id} without admin auth → 401."""
    resp = await async_client.put("/api/v1/drivers/1", json={"aktif": False})
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_update_driver_empty_body(async_client, admin_auth_headers):
    """PUT /{id} with no fields set → 400."""
    from app.database.connection import get_db
    from app.main import app

    mock_session = AsyncMock()
    mock_svc = AsyncMock()

    async def _fake_db():
        return mock_session

    app.dependency_overrides[get_db] = _fake_db
    with _override_sofor_service(mock_svc):
        resp = await async_client.put(
            "/api/v1/drivers/1",
            json={},
            headers=admin_auth_headers,
        )
    app.dependency_overrides.pop(get_db, None)

    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_update_driver_not_found(async_client, admin_auth_headers):
    """PUT /{id} service returns False → 404."""
    from app.database.connection import get_db
    from app.main import app

    mock_session = AsyncMock()
    mock_svc = AsyncMock()
    mock_svc.update_sofor = AsyncMock(return_value=False)

    async def _fake_db():
        return mock_session

    app.dependency_overrides[get_db] = _fake_db
    with _override_sofor_service(mock_svc):
        resp = await async_client.put(
            "/api/v1/drivers/1",
            json={"aktif": False},
            headers=admin_auth_headers,
        )
    app.dependency_overrides.pop(get_db, None)

    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# DELETE /drivers/{id}  — delete driver
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_delete_driver_no_auth(async_client):
    """DELETE /{id} without admin auth → 401."""
    resp = await async_client.delete("/api/v1/drivers/1")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_delete_driver_not_found(async_client, admin_auth_headers):
    """DELETE /{id} driver doesn't exist → 404."""
    from app.database.connection import get_db
    from app.main import app

    mock_session = AsyncMock()
    mock_session.get = AsyncMock(return_value=None)
    mock_svc = AsyncMock()

    async def _fake_db():
        return mock_session

    app.dependency_overrides[get_db] = _fake_db
    with _override_sofor_service(mock_svc):
        resp = await async_client.delete(
            "/api/v1/drivers/9999", headers=admin_auth_headers
        )
    app.dependency_overrides.pop(get_db, None)

    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_delete_active_driver_success(async_client, admin_auth_headers):
    """DELETE /{id} active driver → soft-delete → 200 'pasife çekildi'."""
    from app.database.connection import get_db
    from app.main import app

    sofor = _make_sofor_orm(id=5, aktif=True)
    mock_session = AsyncMock()
    mock_session.get = AsyncMock(return_value=sofor)
    mock_svc = AsyncMock()
    mock_svc.delete_sofor = AsyncMock(return_value=True)

    async def _fake_db():
        return mock_session

    app.dependency_overrides[get_db] = _fake_db
    with _override_sofor_service(mock_svc):
        resp = await async_client.delete(
            "/api/v1/drivers/5", headers=admin_auth_headers
        )
    app.dependency_overrides.pop(get_db, None)

    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert "pasife" in data["message"]


@pytest.mark.asyncio
async def test_delete_inactive_driver_success(async_client, admin_auth_headers):
    """DELETE /{id} inactive driver → hard-delete → 200 'tamamen silindi'."""
    from app.database.connection import get_db
    from app.main import app

    sofor = _make_sofor_orm(id=6, aktif=False)
    mock_session = AsyncMock()
    mock_session.get = AsyncMock(return_value=sofor)
    mock_svc = AsyncMock()
    mock_svc.delete_sofor = AsyncMock(return_value=True)

    async def _fake_db():
        return mock_session

    app.dependency_overrides[get_db] = _fake_db
    with _override_sofor_service(mock_svc):
        resp = await async_client.delete(
            "/api/v1/drivers/6", headers=admin_auth_headers
        )
    app.dependency_overrides.pop(get_db, None)

    assert resp.status_code == 200
    data = resp.json()
    assert "silindi" in data["message"]


# ---------------------------------------------------------------------------
# DELETE /drivers/bulk  — bulk delete
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_bulk_delete_no_auth(async_client):
    """DELETE /bulk without admin auth → 401."""
    import json as _json

    resp = await async_client.request(
        "DELETE",
        "/api/v1/drivers/bulk",
        content=_json.dumps([1, 2, 3]),
        headers={"Content-Type": "application/json"},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_bulk_delete_empty_list(async_client, admin_auth_headers):
    """DELETE /bulk with empty list → 400."""
    import json as _json

    mock_svc = AsyncMock()

    with _override_sofor_service(mock_svc):
        resp = await async_client.request(
            "DELETE",
            "/api/v1/drivers/bulk",
            content=_json.dumps([]),
            headers={
                **admin_auth_headers,
                "Content-Type": "application/json",
            },
        )

    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_bulk_delete_too_many(async_client, admin_auth_headers):
    """DELETE /bulk with >100 IDs → 400."""
    import json as _json

    mock_svc = AsyncMock()
    ids = list(range(1, 102))  # 101 items

    with _override_sofor_service(mock_svc):
        resp = await async_client.request(
            "DELETE",
            "/api/v1/drivers/bulk",
            content=_json.dumps(ids),
            headers={
                **admin_auth_headers,
                "Content-Type": "application/json",
            },
        )

    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_bulk_delete_success(async_client, admin_auth_headers):
    """DELETE /bulk with valid IDs and mocked service → 200."""
    import json as _json

    mock_svc = AsyncMock()
    mock_svc.bulk_delete = AsyncMock(
        return_value={"deleted": 2, "not_found": [], "errors": []}
    )

    with _override_sofor_service(mock_svc):
        resp = await async_client.request(
            "DELETE",
            "/api/v1/drivers/bulk",
            content=_json.dumps([1, 2]),
            headers={
                **admin_auth_headers,
                "Content-Type": "application/json",
            },
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["deleted"] == 2


# ---------------------------------------------------------------------------
# POST /drivers/{id}/score
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_update_score_no_auth(async_client):
    """POST /{id}/score without admin auth → 401."""
    resp = await async_client.post("/api/v1/drivers/1/score?score=1.2")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_update_score_out_of_range(async_client, admin_auth_headers):
    """POST /{id}/score with score=3.0 (>2.0) → 422."""
    mock_svc = AsyncMock()
    with _override_sofor_service(mock_svc):
        resp = await async_client.post(
            "/api/v1/drivers/1/score?score=3.0",
            headers=admin_auth_headers,
        )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_update_score_not_found(async_client, admin_auth_headers):
    """POST /{id}/score service returns False → 404."""
    from app.database.connection import get_db
    from app.main import app

    mock_session = AsyncMock()
    mock_svc = AsyncMock()
    mock_svc.update_score = AsyncMock(return_value=False)

    async def _fake_db():
        return mock_session

    app.dependency_overrides[get_db] = _fake_db
    with _override_sofor_service(mock_svc):
        resp = await async_client.post(
            "/api/v1/drivers/999/score?score=1.2",
            headers=admin_auth_headers,
        )
    app.dependency_overrides.pop(get_db, None)

    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_update_score_success(async_client, admin_auth_headers):
    """POST /{id}/score with valid score → 200."""
    from app.database.connection import get_db
    from app.main import app

    sofor = _make_sofor_orm(id=3, score=1.2)
    mock_session = AsyncMock()
    mock_session.get = AsyncMock(return_value=sofor)
    mock_svc = AsyncMock()
    mock_svc.update_score = AsyncMock(return_value=True)
    mock_svc.get_by_id = AsyncMock(return_value=sofor)

    async def _fake_db():
        return mock_session

    app.dependency_overrides[get_db] = _fake_db
    with _override_sofor_service(mock_svc):
        resp = await async_client.post(
            "/api/v1/drivers/3/score?score=1.2",
            headers=admin_auth_headers,
        )
    app.dependency_overrides.pop(get_db, None)

    assert resp.status_code == 200


# ---------------------------------------------------------------------------
# GET /drivers/{id}/performance
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_performance_no_auth(async_client):
    """GET /{id}/performance without auth → 401."""
    resp = await async_client.get("/api/v1/drivers/1/performance")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_performance_not_found(async_client, admin_auth_headers):
    """GET /{id}/performance for non-existent driver → 404."""
    from app.database.connection import get_db
    from app.main import app

    mock_session = AsyncMock()
    mock_session.get = AsyncMock(return_value=None)
    mock_svc = AsyncMock()

    async def _fake_db():
        return mock_session

    app.dependency_overrides[get_db] = _fake_db
    with _override_sofor_service(mock_svc):
        resp = await async_client.get(
            "/api/v1/drivers/9999/performance",
            headers=admin_auth_headers,
        )
    app.dependency_overrides.pop(get_db, None)

    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_performance_success(async_client, admin_auth_headers):
    """GET /{id}/performance → 200 with performance data."""
    from app.database.connection import get_db
    from app.main import app

    sofor = _make_sofor_orm(id=7)
    mock_session = AsyncMock()
    mock_session.get = AsyncMock(return_value=sofor)
    mock_svc = AsyncMock()
    mock_svc.get_performance_details = AsyncMock(
        return_value={
            "safety_score": 80.0,
            "eco_score": 75.0,
            "compliance_score": 90.0,
            "total_score": 82.0,
            "trend": "stable",
            "total_km": 10000.0,
            "total_trips": 50,
        }
    )

    async def _fake_db():
        return mock_session

    app.dependency_overrides[get_db] = _fake_db
    with _override_sofor_service(mock_svc):
        resp = await async_client.get(
            "/api/v1/drivers/7/performance",
            headers=admin_auth_headers,
        )
    app.dependency_overrides.pop(get_db, None)

    assert resp.status_code == 200


# ---------------------------------------------------------------------------
# GET /drivers/{id}/score-breakdown  — XAI score
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_score_breakdown_no_auth(async_client):
    """GET /{id}/score-breakdown without auth → 401."""
    resp = await async_client.get("/api/v1/drivers/1/score-breakdown")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_score_breakdown_not_found(async_client, admin_auth_headers):
    """GET /{id}/score-breakdown for non-existent driver → 404."""
    from app.database.connection import get_db
    from app.main import app

    mock_session = AsyncMock()
    mock_session.get = AsyncMock(return_value=None)
    mock_svc = AsyncMock()

    async def _fake_db():
        return mock_session

    app.dependency_overrides[get_db] = _fake_db
    with _override_sofor_service(mock_svc):
        resp = await async_client.get(
            "/api/v1/drivers/9999/score-breakdown",
            headers=admin_auth_headers,
        )
    app.dependency_overrides.pop(get_db, None)

    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_score_breakdown_success(async_client, admin_auth_headers):
    """GET /{id}/score-breakdown → 200 with XAI breakdown."""
    from app.database.connection import get_db
    from app.main import app

    sofor = _make_sofor_orm(id=8)
    mock_session = AsyncMock()
    mock_session.get = AsyncMock(return_value=sofor)
    mock_svc = AsyncMock()
    mock_svc.get_score_breakdown = AsyncMock(
        return_value={
            "sofor_id": 8,
            "ad_soyad": "Ahmet Yilmaz",
            "manual": 1.0,
            "manual_weight": 0.4,
            "auto": 1.1,
            "auto_weight": 0.6,
            "total": 1.06,
            "trip_count": 10,
            "avg_consumption": 32.5,
            "target_reference": 30.0,
            "has_trips": True,
        }
    )

    async def _fake_db():
        return mock_session

    app.dependency_overrides[get_db] = _fake_db
    with _override_sofor_service(mock_svc):
        resp = await async_client.get(
            "/api/v1/drivers/8/score-breakdown",
            headers=admin_auth_headers,
        )
    app.dependency_overrides.pop(get_db, None)

    assert resp.status_code == 200
    data = resp.json()
    assert data["sofor_id"] == 8
    assert data["has_trips"] is True


# ---------------------------------------------------------------------------
# GET /drivers/{id}/route-profile
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_route_profile_no_auth(async_client):
    """GET /{id}/route-profile without auth → 401."""
    resp = await async_client.get("/api/v1/drivers/1/route-profile")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_route_profile_not_found(async_client, admin_auth_headers):
    """GET /{id}/route-profile for non-existent driver → 404."""
    from app.database.connection import get_db
    from app.main import app

    mock_session = AsyncMock()
    mock_session.get = AsyncMock(return_value=None)
    mock_svc = AsyncMock()

    async def _fake_db():
        return mock_session

    app.dependency_overrides[get_db] = _fake_db
    with _override_sofor_service(mock_svc):
        resp = await async_client.get(
            "/api/v1/drivers/9999/route-profile",
            headers=admin_auth_headers,
        )
    app.dependency_overrides.pop(get_db, None)

    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_route_profile_success(async_client, admin_auth_headers):
    """GET /{id}/route-profile → 200 with profile data."""
    from app.database.connection import get_db
    from app.main import app

    sofor = _make_sofor_orm(id=9)
    mock_session = AsyncMock()
    mock_session.get = AsyncMock(return_value=sofor)
    mock_svc = AsyncMock()
    mock_svc.get_route_profile = AsyncMock(
        return_value={
            "sofor_id": 9,
            "ad_soyad": "Ahmet Yilmaz",
            "profiles": [
                {
                    "route_type": "highway_dominant",
                    "label": "Otoyol Ağırlıklı",
                    "trip_count": 10,
                    "avg_actual": 32.5,
                    "avg_predicted": 31.0,
                    "deviation_pct": 4.8,
                }
            ],
            "best_route_type": "highway_dominant",
            "min_trips_for_best": 5,
        }
    )

    async def _fake_db():
        return mock_session

    app.dependency_overrides[get_db] = _fake_db
    with _override_sofor_service(mock_svc):
        resp = await async_client.get(
            "/api/v1/drivers/9/route-profile",
            headers=admin_auth_headers,
        )
    app.dependency_overrides.pop(get_db, None)

    assert resp.status_code == 200
    data = resp.json()
    assert data["sofor_id"] == 9
    assert data["best_route_type"] == "highway_dominant"


# ---------------------------------------------------------------------------
# GET /drivers/excel/template
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_excel_template_no_auth(async_client):
    """GET /excel/template without auth → 401."""
    resp = await async_client.get("/api/v1/drivers/excel/template")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_excel_template_success(async_client, admin_auth_headers):
    """GET /excel/template → 200 with spreadsheet content."""
    with patch(
        "app.api.v1.endpoints.drivers.ExcelService.generate_template",
        new=AsyncMock(return_value=b"PK fakexlsx"),
    ):
        resp = await async_client.get(
            "/api/v1/drivers/excel/template", headers=admin_auth_headers
        )

    assert resp.status_code == 200


# ---------------------------------------------------------------------------
# GET /drivers/excel/export
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_excel_export_no_auth(async_client):
    """GET /excel/export without auth → 401."""
    resp = await async_client.get("/api/v1/drivers/excel/export")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_excel_export_success(async_client, admin_auth_headers):
    """GET /excel/export → 200 streaming response."""
    mock_svc = AsyncMock()
    mock_svc.get_all_paged = AsyncMock(return_value={"items": [], "total": 0})

    with _override_sofor_service(mock_svc):
        with patch(
            "app.api.v1.endpoints.drivers.ExcelService.export_data",
            new=AsyncMock(return_value=b"PK fakexlsx"),
        ):
            resp = await async_client.get(
                "/api/v1/drivers/excel/export", headers=admin_auth_headers
            )

    assert resp.status_code == 200


# ---------------------------------------------------------------------------
# POST /drivers/excel/upload
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_excel_upload_no_auth(async_client):
    """POST /excel/upload without admin auth → 401."""
    import io

    resp = await async_client.post(
        "/api/v1/drivers/excel/upload",
        files={
            "file": (
                "drivers.xlsx",
                io.BytesIO(b"PK data"),
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_excel_upload_invalid_mime(async_client, admin_auth_headers):
    """POST /excel/upload with text/plain mime → 400."""
    import io

    resp = await async_client.post(
        "/api/v1/drivers/excel/upload",
        files={"file": ("drivers.txt", io.BytesIO(b"not excel"), "text/plain")},
        headers=admin_auth_headers,
    )
    assert resp.status_code == 400
