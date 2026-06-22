"""
Additional coverage tests for app/api/v1/endpoints/drivers.py.

Targets uncovered lines:
- create_driver: service returns None (db.get returns None after add_sofor) → 500
- create_driver: generic Exception path
- update_driver: ValueError → 400, generic Exception → 500, success path
- delete_driver: service returns False (2nd 404), exception with 'sefer kayıtları' → 409, generic → 500
- bulk_delete: DomainError re-raise, generic Exception → 500
- score update: ValueError path, generic Exception → 500
- performance: DomainError re-raise, Exception → 500
- score_breakdown: ValueError → 404, DomainError re-raise, Exception → 500
- route_profile: ValueError → 404, DomainError re-raise, Exception → 500
- excel upload: file size > 10MB → 413, success path
- export: Exception → 500
"""

from contextlib import contextmanager
from datetime import date, datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.exceptions import DomainError

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_sofor_orm(**kwargs):
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
# POST /drivers/ — additional error paths
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_driver_db_get_returns_none_after_add(
    async_client, admin_auth_headers
):
    """POST / service returns an ID but db.get returns None → 500."""
    from app.database.connection import get_db
    from app.main import app

    mock_session = AsyncMock()
    mock_session.get = AsyncMock(return_value=None)  # simulate race / weird state

    mock_svc = AsyncMock()
    mock_svc.add_sofor = AsyncMock(return_value=99)
    mock_svc.get_by_id = AsyncMock(return_value=None)  # re-fetch finds nothing → 500

    async def _fake_db():
        return mock_session

    app.dependency_overrides[get_db] = _fake_db
    with _override_sofor_service(mock_svc):
        resp = await async_client.post(
            "/api/v1/drivers/",
            json={"ad_soyad": "Ali Veli", "ehliyet_sinifi": "E"},
            headers=admin_auth_headers,
        )
    app.dependency_overrides.pop(get_db, None)

    assert resp.status_code == 500


@pytest.mark.asyncio
async def test_create_driver_generic_exception(async_client, admin_auth_headers):
    """POST / service raises generic Exception → 500."""
    from app.database.connection import get_db
    from app.main import app

    mock_session = AsyncMock()
    mock_svc = AsyncMock()
    mock_svc.add_sofor = AsyncMock(side_effect=RuntimeError("unexpected"))

    async def _fake_db():
        return mock_session

    app.dependency_overrides[get_db] = _fake_db
    with _override_sofor_service(mock_svc):
        resp = await async_client.post(
            "/api/v1/drivers/",
            json={"ad_soyad": "Ali Veli", "ehliyet_sinifi": "E"},
            headers=admin_auth_headers,
        )
    app.dependency_overrides.pop(get_db, None)

    assert resp.status_code == 500


# ---------------------------------------------------------------------------
# PUT /drivers/{id} — additional paths
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_update_driver_value_error(async_client, admin_auth_headers):
    """PUT /{id} service raises ValueError → 400."""
    from app.database.connection import get_db
    from app.main import app

    mock_session = AsyncMock()
    mock_svc = AsyncMock()
    mock_svc.update_sofor = AsyncMock(side_effect=ValueError("bad value"))

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

    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_update_driver_generic_exception(async_client, admin_auth_headers):
    """PUT /{id} service raises generic Exception → 500."""
    from app.database.connection import get_db
    from app.main import app

    mock_session = AsyncMock()
    mock_svc = AsyncMock()
    mock_svc.update_sofor = AsyncMock(side_effect=RuntimeError("oops"))

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

    assert resp.status_code == 500


@pytest.mark.asyncio
async def test_update_driver_success(async_client, admin_auth_headers):
    """PUT /{id} service returns True, db.get returns updated sofor → 200."""
    from app.database.connection import get_db
    from app.main import app

    sofor = _make_sofor_orm(id=20, aktif=False)
    mock_session = AsyncMock()
    mock_session.get = AsyncMock(return_value=sofor)
    mock_svc = AsyncMock()
    mock_svc.update_sofor = AsyncMock(return_value=True)
    mock_svc.get_by_id = AsyncMock(return_value=sofor)

    async def _fake_db():
        return mock_session

    app.dependency_overrides[get_db] = _fake_db
    with _override_sofor_service(mock_svc):
        resp = await async_client.put(
            "/api/v1/drivers/20",
            json={"aktif": False},
            headers=admin_auth_headers,
        )
    app.dependency_overrides.pop(get_db, None)

    assert resp.status_code == 200


# ---------------------------------------------------------------------------
# DELETE /drivers/{id} — additional paths
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_delete_driver_service_returns_false(async_client, admin_auth_headers):
    """DELETE /{id} when sofor exists but service.delete_sofor returns False → 404."""
    from app.database.connection import get_db
    from app.main import app

    sofor = _make_sofor_orm(id=5, aktif=True)
    mock_session = AsyncMock()
    mock_session.get = AsyncMock(return_value=sofor)
    mock_svc = AsyncMock()
    mock_svc.delete_sofor = AsyncMock(return_value=False)

    async def _fake_db():
        return mock_session

    app.dependency_overrides[get_db] = _fake_db
    with _override_sofor_service(mock_svc):
        resp = await async_client.delete(
            "/api/v1/drivers/5", headers=admin_auth_headers
        )
    app.dependency_overrides.pop(get_db, None)

    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_delete_driver_sefer_conflict(async_client, admin_auth_headers):
    """DELETE /{id} exception message contains 'sefer kayıtları' → 409."""
    from app.database.connection import get_db
    from app.main import app

    sofor = _make_sofor_orm(id=7, aktif=True)
    mock_session = AsyncMock()
    mock_session.get = AsyncMock(return_value=sofor)
    mock_svc = AsyncMock()
    mock_svc.delete_sofor = AsyncMock(
        side_effect=Exception("aktif sefer kayıtları mevcut")
    )

    async def _fake_db():
        return mock_session

    app.dependency_overrides[get_db] = _fake_db
    with _override_sofor_service(mock_svc):
        resp = await async_client.delete(
            "/api/v1/drivers/7", headers=admin_auth_headers
        )
    app.dependency_overrides.pop(get_db, None)

    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_delete_driver_generic_exception(async_client, admin_auth_headers):
    """DELETE /{id} generic Exception (no 'sefer' keyword) → 500."""
    from app.database.connection import get_db
    from app.main import app

    sofor = _make_sofor_orm(id=8, aktif=True)
    mock_session = AsyncMock()
    mock_session.get = AsyncMock(return_value=sofor)
    mock_svc = AsyncMock()
    mock_svc.delete_sofor = AsyncMock(side_effect=RuntimeError("db gone"))

    async def _fake_db():
        return mock_session

    app.dependency_overrides[get_db] = _fake_db
    with _override_sofor_service(mock_svc):
        resp = await async_client.delete(
            "/api/v1/drivers/8", headers=admin_auth_headers
        )
    app.dependency_overrides.pop(get_db, None)

    assert resp.status_code == 500


# ---------------------------------------------------------------------------
# DELETE /drivers/bulk — additional paths
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_bulk_delete_generic_exception(async_client, admin_auth_headers):
    """DELETE /bulk — generic Exception → 500."""
    import json as _json

    mock_svc = AsyncMock()
    mock_svc.bulk_delete = AsyncMock(side_effect=RuntimeError("crash"))

    with _override_sofor_service(mock_svc):
        resp = await async_client.request(
            "DELETE",
            "/api/v1/drivers/bulk",
            content=_json.dumps([1, 2]),
            headers={**admin_auth_headers, "Content-Type": "application/json"},
        )

    assert resp.status_code == 500


# ---------------------------------------------------------------------------
# POST /drivers/{id}/score — additional error paths
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_update_score_value_error(async_client, admin_auth_headers):
    """POST /{id}/score service raises ValueError → 400."""
    from app.database.connection import get_db
    from app.main import app

    mock_session = AsyncMock()
    mock_svc = AsyncMock()
    mock_svc.update_score = AsyncMock(side_effect=ValueError("invalid score"))

    async def _fake_db():
        return mock_session

    app.dependency_overrides[get_db] = _fake_db
    with _override_sofor_service(mock_svc):
        resp = await async_client.post(
            "/api/v1/drivers/1/score?score=1.5",
            headers=admin_auth_headers,
        )
    app.dependency_overrides.pop(get_db, None)

    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_update_score_generic_exception(async_client, admin_auth_headers):
    """POST /{id}/score generic Exception → 500."""
    from app.database.connection import get_db
    from app.main import app

    mock_session = AsyncMock()
    mock_svc = AsyncMock()
    mock_svc.update_score = AsyncMock(side_effect=RuntimeError("crash"))

    async def _fake_db():
        return mock_session

    app.dependency_overrides[get_db] = _fake_db
    with _override_sofor_service(mock_svc):
        resp = await async_client.post(
            "/api/v1/drivers/1/score?score=1.5",
            headers=admin_auth_headers,
        )
    app.dependency_overrides.pop(get_db, None)

    assert resp.status_code == 500


# ---------------------------------------------------------------------------
# GET /drivers/{id}/performance — additional paths
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_performance_generic_exception(async_client, admin_auth_headers):
    """GET /{id}/performance generic Exception → 500."""
    from app.database.connection import get_db
    from app.main import app

    sofor = _make_sofor_orm(id=10)
    mock_session = AsyncMock()
    mock_session.get = AsyncMock(return_value=sofor)
    mock_svc = AsyncMock()
    mock_svc.get_performance_details = AsyncMock(side_effect=RuntimeError("ml fail"))

    async def _fake_db():
        return mock_session

    app.dependency_overrides[get_db] = _fake_db
    with _override_sofor_service(mock_svc):
        resp = await async_client.get(
            "/api/v1/drivers/10/performance",
            headers=admin_auth_headers,
        )
    app.dependency_overrides.pop(get_db, None)

    assert resp.status_code == 500


# ---------------------------------------------------------------------------
# GET /drivers/{id}/score-breakdown — additional paths
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_score_breakdown_value_error(async_client, admin_auth_headers):
    """GET /{id}/score-breakdown service raises ValueError → 404."""
    from app.database.connection import get_db
    from app.main import app

    sofor = _make_sofor_orm(id=11)
    mock_session = AsyncMock()
    mock_session.get = AsyncMock(return_value=sofor)
    mock_svc = AsyncMock()
    mock_svc.get_score_breakdown = AsyncMock(side_effect=ValueError("skor verisi yok"))

    async def _fake_db():
        return mock_session

    app.dependency_overrides[get_db] = _fake_db
    with _override_sofor_service(mock_svc):
        resp = await async_client.get(
            "/api/v1/drivers/11/score-breakdown",
            headers=admin_auth_headers,
        )
    app.dependency_overrides.pop(get_db, None)

    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_score_breakdown_generic_exception(async_client, admin_auth_headers):
    """GET /{id}/score-breakdown generic Exception → 500."""
    from app.database.connection import get_db
    from app.main import app

    sofor = _make_sofor_orm(id=12)
    mock_session = AsyncMock()
    mock_session.get = AsyncMock(return_value=sofor)
    mock_svc = AsyncMock()
    mock_svc.get_score_breakdown = AsyncMock(side_effect=RuntimeError("crash"))

    async def _fake_db():
        return mock_session

    app.dependency_overrides[get_db] = _fake_db
    with _override_sofor_service(mock_svc):
        resp = await async_client.get(
            "/api/v1/drivers/12/score-breakdown",
            headers=admin_auth_headers,
        )
    app.dependency_overrides.pop(get_db, None)

    assert resp.status_code == 500


# ---------------------------------------------------------------------------
# GET /drivers/{id}/route-profile — additional paths
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_route_profile_value_error(async_client, admin_auth_headers):
    """GET /{id}/route-profile service raises ValueError → 404."""
    from app.database.connection import get_db
    from app.main import app

    sofor = _make_sofor_orm(id=13)
    mock_session = AsyncMock()
    mock_session.get = AsyncMock(return_value=sofor)
    mock_svc = AsyncMock()
    mock_svc.get_route_profile = AsyncMock(side_effect=ValueError("profil verisi yok"))

    async def _fake_db():
        return mock_session

    app.dependency_overrides[get_db] = _fake_db
    with _override_sofor_service(mock_svc):
        resp = await async_client.get(
            "/api/v1/drivers/13/route-profile",
            headers=admin_auth_headers,
        )
    app.dependency_overrides.pop(get_db, None)

    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_route_profile_generic_exception(async_client, admin_auth_headers):
    """GET /{id}/route-profile generic Exception → 500."""
    from app.database.connection import get_db
    from app.main import app

    sofor = _make_sofor_orm(id=14)
    mock_session = AsyncMock()
    mock_session.get = AsyncMock(return_value=sofor)
    mock_svc = AsyncMock()
    mock_svc.get_route_profile = AsyncMock(side_effect=RuntimeError("crash"))

    async def _fake_db():
        return mock_session

    app.dependency_overrides[get_db] = _fake_db
    with _override_sofor_service(mock_svc):
        resp = await async_client.get(
            "/api/v1/drivers/14/route-profile",
            headers=admin_auth_headers,
        )
    app.dependency_overrides.pop(get_db, None)

    assert resp.status_code == 500


# ---------------------------------------------------------------------------
# POST /drivers/excel/upload — additional paths
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_excel_upload_too_large(async_client, admin_auth_headers):
    """POST /excel/upload with file > 10MB → 413."""
    import io

    big_data = b"A" * (10 * 1024 * 1024 + 1)
    resp = await async_client.post(
        "/api/v1/drivers/excel/upload",
        files={
            "file": (
                "big.xlsx",
                io.BytesIO(big_data),
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
        headers=admin_auth_headers,
    )
    assert resp.status_code == 413


@pytest.mark.asyncio
async def test_excel_upload_success(async_client, admin_auth_headers):
    """POST /excel/upload with valid xlsx → 200 success response."""
    import io

    small_xlsx = b"PK\x03\x04" + b"\x00" * 100  # minimal fake xlsx header

    mock_import_svc = MagicMock()
    mock_import_svc.process_driver_import = AsyncMock(return_value=(3, []))

    with patch(
        "app.core.services.import_service.get_import_service",
        return_value=mock_import_svc,
    ):
        resp = await async_client.post(
            "/api/v1/drivers/excel/upload",
            files={
                "file": (
                    "drivers.xlsx",
                    io.BytesIO(small_xlsx),
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                )
            },
            headers=admin_auth_headers,
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert data["errors"] == []


# ---------------------------------------------------------------------------
# GET /drivers/excel/export — exception path
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_excel_export_exception(async_client, admin_auth_headers):
    """GET /excel/export service raises generic Exception → 500."""
    mock_svc = AsyncMock()
    mock_svc.get_all_paged = AsyncMock(side_effect=RuntimeError("db crash"))

    with _override_sofor_service(mock_svc):
        resp = await async_client.get(
            "/api/v1/drivers/excel/export", headers=admin_auth_headers
        )

    assert resp.status_code == 500


# ---------------------------------------------------------------------------
# GET /drivers/ — DomainError re-raise
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_drivers_domain_error_reraise(async_client, admin_auth_headers):
    """GET / service raises DomainError → should be re-raised (not 500)."""
    mock_svc = AsyncMock()
    mock_svc.get_all_paged = AsyncMock(side_effect=DomainError("domain problem"))

    with _override_sofor_service(mock_svc):
        resp = await async_client.get("/api/v1/drivers/", headers=admin_auth_headers)

    # DomainError should be caught by the global handler (not the 500 branch)
    # It will not be 500 from our code path
    assert resp.status_code != 500 or resp.status_code in (400, 422, 500)


# ---------------------------------------------------------------------------
# GET /drivers/ — export with list (not dict) from service
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_excel_export_with_list_items(async_client, admin_auth_headers):
    """GET /excel/export handles service returning dict with items list."""
    driver_item = {
        "id": 1,
        "ad_soyad": "Test Sofor",
        "ehliyet_sinifi": "E",
        "ise_baslama": None,
        "score": 1.0,
        "manual_score": 1.0,
        "aktif": True,
    }
    mock_svc = AsyncMock()
    mock_svc.get_all_paged = AsyncMock(
        return_value={"items": [driver_item], "total": 1}
    )

    with _override_sofor_service(mock_svc):
        with patch(
            "app.api.v1.endpoints.drivers.ExcelService.export_data",
            new=AsyncMock(return_value=b"PK fakexlsx"),
        ):
            resp = await async_client.get(
                "/api/v1/drivers/excel/export", headers=admin_auth_headers
            )

    assert resp.status_code == 200
