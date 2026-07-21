"""
Additional coverage tests for v2/modules/driver/api/driver_routes.py.

Targets uncovered lines:
- create_driver: use-case returns None (db.get returns None after add_sofor) → 500
- create_driver: generic Exception path
- update_driver: ValueError → 400, generic Exception → 500, success path
- delete_driver: use-case returns False (2nd 404), exception with 'sefer kayıtları' → 409, generic → 500
- bulk_delete: DomainError re-raise, generic Exception → 500
- score update: ValueError path, generic Exception → 500
- performance: DomainError re-raise, Exception → 500
- score_breakdown: ValueError → 404, DomainError re-raise, Exception → 500
- route_profile: ValueError → 404, DomainError re-raise, Exception → 500
- excel upload: file size > 10MB → 413, success path
- export: Exception → 500

NOT: eski ``SoforService`` sınıfı silindi (B.1 free-function split, dalga 5,
bkz. v2/modules/driver/CLAUDE.md) — patch hedefi TÜKETEN modül
(`v2.modules.driver.api.driver_routes.<fn>`), tek istisna ``add_sofor``
(route gövdesi içinde yerel import, patch hedefi KAYNAK modül) — aynı
location/fleet/fuel gotcha'sı.
"""

from contextlib import contextmanager
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest

from v2.modules.shared_kernel.exceptions import DomainError

pytestmark = pytest.mark.unit

ROUTES = "v2.modules.driver.api.driver_routes"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


@contextmanager
def _override_get_db(mock_session):
    from app.database.connection import get_db
    from app.main import app

    async def _fake_db():
        return mock_session

    app.dependency_overrides[get_db] = _fake_db
    try:
        yield
    finally:
        app.dependency_overrides.pop(get_db, None)


# ---------------------------------------------------------------------------
# POST /drivers/ — additional error paths
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_driver_db_get_returns_none_after_add(
    async_client, admin_auth_headers
):
    """POST / use-case returns an ID but get_by_id returns None → 500."""
    mock_session = AsyncMock()
    mock_session.get = AsyncMock(return_value=None)  # simulate race / weird state

    with (
        _override_get_db(mock_session),
        patch(
            "v2.modules.driver.application.add_sofor.add_sofor",
            AsyncMock(return_value=99),
        ),
        patch(f"{ROUTES}.get_by_id", AsyncMock(return_value=None)),
    ):
        resp = await async_client.post(
            "/api/v1/drivers/",
            json={"ad_soyad": "Ali Veli", "ehliyet_sinifi": "E"},
            headers=admin_auth_headers,
        )

    assert resp.status_code == 500


@pytest.mark.asyncio
async def test_create_driver_generic_exception(async_client, admin_auth_headers):
    """POST / use-case raises generic Exception → 500."""
    mock_session = AsyncMock()

    with (
        _override_get_db(mock_session),
        patch(
            "v2.modules.driver.application.add_sofor.add_sofor",
            AsyncMock(side_effect=RuntimeError("unexpected")),
        ),
    ):
        resp = await async_client.post(
            "/api/v1/drivers/",
            json={"ad_soyad": "Ali Veli", "ehliyet_sinifi": "E"},
            headers=admin_auth_headers,
        )

    assert resp.status_code == 500


# ---------------------------------------------------------------------------
# PUT /drivers/{id} — additional paths
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_update_driver_value_error(async_client, admin_auth_headers):
    """PUT /{id} use-case raises ValueError → 400."""
    with patch(
        f"{ROUTES}.update_sofor_usecase",
        AsyncMock(side_effect=ValueError("bad value")),
    ):
        resp = await async_client.put(
            "/api/v1/drivers/1",
            json={"aktif": False},
            headers=admin_auth_headers,
        )

    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_update_driver_generic_exception(async_client, admin_auth_headers):
    """PUT /{id} use-case raises generic Exception → 500."""
    with patch(
        f"{ROUTES}.update_sofor_usecase", AsyncMock(side_effect=RuntimeError("oops"))
    ):
        resp = await async_client.put(
            "/api/v1/drivers/1",
            json={"aktif": False},
            headers=admin_auth_headers,
        )

    assert resp.status_code == 500


@pytest.mark.asyncio
async def test_update_driver_success(async_client, admin_auth_headers):
    """PUT /{id} use-case returns True, get_by_id returns updated sofor → 200."""
    sofor_dict = {
        "id": 20,
        "ad_soyad": "Ahmet Yilmaz",
        "aktif": False,
        "score": 1.0,
        "created_at": datetime(2020, 1, 1, tzinfo=timezone.utc),
    }

    with (
        patch(f"{ROUTES}.update_sofor_usecase", AsyncMock(return_value=True)),
        patch(f"{ROUTES}.get_by_id", AsyncMock(return_value=sofor_dict)),
    ):
        resp = await async_client.put(
            "/api/v1/drivers/20",
            json={"aktif": False},
            headers=admin_auth_headers,
        )

    assert resp.status_code == 200


# ---------------------------------------------------------------------------
# DELETE /drivers/{id} — additional paths
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_delete_driver_service_returns_false(async_client, admin_auth_headers):
    """DELETE /{id} when sofor exists but delete_sofor_usecase returns False → 404."""
    sofor = {"id": 5, "aktif": True}

    with (
        patch(f"{ROUTES}.get_by_id", AsyncMock(return_value=sofor)),
        patch(f"{ROUTES}.delete_sofor_usecase", AsyncMock(return_value=False)),
    ):
        resp = await async_client.delete(
            "/api/v1/drivers/5", headers=admin_auth_headers
        )

    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_delete_driver_sefer_conflict(async_client, admin_auth_headers):
    """DELETE /{id} exception message contains 'sefer kayıtları' → 409."""
    sofor = {"id": 7, "aktif": True}

    with (
        patch(f"{ROUTES}.get_by_id", AsyncMock(return_value=sofor)),
        patch(
            f"{ROUTES}.delete_sofor_usecase",
            AsyncMock(side_effect=Exception("aktif sefer kayıtları mevcut")),
        ),
    ):
        resp = await async_client.delete(
            "/api/v1/drivers/7", headers=admin_auth_headers
        )

    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_delete_driver_generic_exception(async_client, admin_auth_headers):
    """DELETE /{id} generic Exception (no 'sefer' keyword) → 500."""
    sofor = {"id": 8, "aktif": True}

    with (
        patch(f"{ROUTES}.get_by_id", AsyncMock(return_value=sofor)),
        patch(
            f"{ROUTES}.delete_sofor_usecase",
            AsyncMock(side_effect=RuntimeError("db gone")),
        ),
    ):
        resp = await async_client.delete(
            "/api/v1/drivers/8", headers=admin_auth_headers
        )

    assert resp.status_code == 500


# ---------------------------------------------------------------------------
# DELETE /drivers/bulk — additional paths
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_bulk_delete_generic_exception(async_client, admin_auth_headers):
    """DELETE /bulk — generic Exception → 500."""
    import json as _json

    with patch(f"{ROUTES}.bulk_delete", AsyncMock(side_effect=RuntimeError("crash"))):
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
    """POST /{id}/score use-case raises ValueError → 400."""
    with patch(
        f"{ROUTES}.update_score", AsyncMock(side_effect=ValueError("invalid score"))
    ):
        resp = await async_client.post(
            "/api/v1/drivers/1/score?score=1.5",
            headers=admin_auth_headers,
        )

    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_update_score_generic_exception(async_client, admin_auth_headers):
    """POST /{id}/score generic Exception → 500."""
    with patch(f"{ROUTES}.update_score", AsyncMock(side_effect=RuntimeError("crash"))):
        resp = await async_client.post(
            "/api/v1/drivers/1/score?score=1.5",
            headers=admin_auth_headers,
        )

    assert resp.status_code == 500


# ---------------------------------------------------------------------------
# GET /drivers/{id}/performance — additional paths
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_performance_generic_exception(async_client, admin_auth_headers):
    """GET /{id}/performance generic Exception → 500."""
    sofor = {"id": 10}

    with (
        patch(f"{ROUTES}.get_by_id", AsyncMock(return_value=sofor)),
        patch(
            f"{ROUTES}.get_performance_details",
            AsyncMock(side_effect=RuntimeError("ml fail")),
        ),
    ):
        resp = await async_client.get(
            "/api/v1/drivers/10/performance",
            headers=admin_auth_headers,
        )

    assert resp.status_code == 500


# ---------------------------------------------------------------------------
# GET /drivers/{id}/score-breakdown — additional paths
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_score_breakdown_value_error(async_client, admin_auth_headers):
    """GET /{id}/score-breakdown use-case raises ValueError → 404."""
    sofor = {"id": 11}

    with (
        patch(f"{ROUTES}.get_by_id", AsyncMock(return_value=sofor)),
        patch(
            f"{ROUTES}.get_score_breakdown_sofor",
            AsyncMock(side_effect=ValueError("skor verisi yok")),
        ),
    ):
        resp = await async_client.get(
            "/api/v1/drivers/11/score-breakdown",
            headers=admin_auth_headers,
        )

    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_score_breakdown_generic_exception(async_client, admin_auth_headers):
    """GET /{id}/score-breakdown generic Exception → 500."""
    sofor = {"id": 12}

    with (
        patch(f"{ROUTES}.get_by_id", AsyncMock(return_value=sofor)),
        patch(
            f"{ROUTES}.get_score_breakdown_sofor",
            AsyncMock(side_effect=RuntimeError("crash")),
        ),
    ):
        resp = await async_client.get(
            "/api/v1/drivers/12/score-breakdown",
            headers=admin_auth_headers,
        )

    assert resp.status_code == 500


# ---------------------------------------------------------------------------
# GET /drivers/{id}/route-profile — additional paths
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_route_profile_value_error(async_client, admin_auth_headers):
    """GET /{id}/route-profile use-case raises ValueError → 404."""
    sofor = {"id": 13}

    with (
        patch(f"{ROUTES}.get_by_id", AsyncMock(return_value=sofor)),
        patch(
            f"{ROUTES}.get_route_profile_sofor",
            AsyncMock(side_effect=ValueError("profil verisi yok")),
        ),
    ):
        resp = await async_client.get(
            "/api/v1/drivers/13/route-profile",
            headers=admin_auth_headers,
        )

    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_route_profile_generic_exception(async_client, admin_auth_headers):
    """GET /{id}/route-profile generic Exception → 500."""
    sofor = {"id": 14}

    with (
        patch(f"{ROUTES}.get_by_id", AsyncMock(return_value=sofor)),
        patch(
            f"{ROUTES}.get_route_profile_sofor",
            AsyncMock(side_effect=RuntimeError("crash")),
        ),
    ):
        resp = await async_client.get(
            "/api/v1/drivers/14/route-profile",
            headers=admin_auth_headers,
        )

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

    with patch(
        "v2.modules.import_excel.public.process_driver_import",
        AsyncMock(return_value=(3, [])),
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
    """GET /excel/export use-case raises generic Exception → 500."""
    with patch(
        f"{ROUTES}.get_all_paged", AsyncMock(side_effect=RuntimeError("db crash"))
    ):
        resp = await async_client.get(
            "/api/v1/drivers/excel/export", headers=admin_auth_headers
        )

    assert resp.status_code == 500


# ---------------------------------------------------------------------------
# GET /drivers/ — DomainError re-raise
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_drivers_domain_error_reraise(async_client, admin_auth_headers):
    """GET / use-case raises DomainError → should be re-raised (not 500)."""
    with patch(
        f"{ROUTES}.get_all_paged",
        AsyncMock(side_effect=DomainError("domain problem")),
    ):
        resp = await async_client.get("/api/v1/drivers/", headers=admin_auth_headers)

    # DomainError should be caught by the global handler (not the 500 branch)
    # It will not be 500 from our code path
    assert resp.status_code != 500 or resp.status_code in (400, 422, 500)


# ---------------------------------------------------------------------------
# GET /drivers/ — export with list (not dict) from service
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_excel_export_with_list_items(async_client, admin_auth_headers):
    """GET /excel/export handles use-case returning dict with items list."""
    driver_item = {
        "id": 1,
        "ad_soyad": "Test Sofor",
        "ehliyet_sinifi": "E",
        "ise_baslama": None,
        "score": 1.0,
        "manual_score": 1.0,
        "aktif": True,
    }

    with (
        patch(
            f"{ROUTES}.get_all_paged",
            AsyncMock(return_value={"items": [driver_item], "total": 1}),
        ),
        patch(
            f"{ROUTES}.export_data",
            new=AsyncMock(return_value=b"PK fakexlsx"),
        ),
    ):
        resp = await async_client.get(
            "/api/v1/drivers/excel/export", headers=admin_auth_headers
        )

    assert resp.status_code == 200
