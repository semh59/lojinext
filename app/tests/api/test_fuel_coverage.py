"""
Fuel endpoint coverage tests.

Targets missing lines in v2/modules/fuel/api/fuel_routes.py (20% → ≥70%).
All use-case calls are mocked — no DB needed for most tests.

Free-function patch target is always the CONSUMING module
(v2.modules.fuel.api.fuel_routes.<fn>), not the source module — the
router imports each use-case at module load time via `from x import y`,
so `y` lives as an attribute on the router's own namespace (documented
gotcha, see v2/modules/location/CLAUDE.md's final paragraph).
"""

from datetime import date, datetime, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, patch

import pytest

pytestmark = pytest.mark.unit

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

BASE_URL = "/api/v1/fuel"
ROUTES = "v2.modules.fuel.api.fuel_routes"


def _make_yakit_response_dict(**kwargs):
    defaults = dict(
        id=1,
        tarih=date.today(),
        arac_id=1,
        istasyon="Petrol Ofisi",
        fiyat_tl=Decimal("45.50"),
        litre=Decimal("200.00"),
        toplam_tutar=Decimal("9100.00"),
        km_sayac=150000,
        fis_no="FIS-001",
        depo_durumu="Doldu",
        durum="Bekliyor",
        created_at=datetime.now(timezone.utc),
        plaka="34 ABC 123",
    )
    defaults.update(kwargs)
    return defaults


def _make_yakit_response_obj(**kwargs):
    from v2.modules.fuel.schemas import YakitResponse

    return YakitResponse.model_validate(_make_yakit_response_dict(**kwargs))


def _make_list_response(items=None):
    if items is None:
        items = [_make_yakit_response_obj()]
    return {"items": items, "total": len(items)}


def _make_fuel_stats_dict(**kwargs):
    defaults = dict(
        toplam_litre=5000.0,
        toplam_maliyet=227500.0,
        ortalama_birim_fiyat=45.5,
        kayit_sayisi=25,
    )
    defaults.update(kwargs)
    return defaults


# ---------------------------------------------------------------------------
# GET /fuel/stats
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_fuel_stats_success(async_client, admin_auth_headers):
    """GET /fuel/stats → 200 with valid stats."""
    with patch(f"{ROUTES}.get_stats", AsyncMock(return_value=_make_fuel_stats_dict())):
        resp = await async_client.get(f"{BASE_URL}/stats", headers=admin_auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "kayit_sayisi" in data


@pytest.mark.asyncio
async def test_get_fuel_stats_no_auth(async_client):
    """GET /fuel/stats without auth → 401."""
    resp = await async_client.get(f"{BASE_URL}/stats")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_get_fuel_stats_with_date_range(async_client, admin_auth_headers):
    """GET /fuel/stats?baslangic_tarih=... → 200."""
    with patch(f"{ROUTES}.get_stats", AsyncMock(return_value=_make_fuel_stats_dict())):
        resp = await async_client.get(
            f"{BASE_URL}/stats?baslangic_tarih=2026-01-01&bitis_tarih=2026-03-31",
            headers=admin_auth_headers,
        )
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_get_fuel_stats_unexpected_error(async_client, admin_auth_headers):
    """GET /fuel/stats service raises RuntimeError → 500."""
    with patch(f"{ROUTES}.get_stats", AsyncMock(side_effect=RuntimeError("boom"))):
        resp = await async_client.get(f"{BASE_URL}/stats", headers=admin_auth_headers)
    assert resp.status_code == 500


# ---------------------------------------------------------------------------
# GET /fuel/  — list fuel records
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_read_yakit_alimlari_success(async_client, admin_auth_headers):
    """GET /fuel/ → 200 list."""
    with patch(
        f"{ROUTES}.get_all_paged",
        AsyncMock(return_value=_make_list_response([_make_yakit_response_obj()])),
    ):
        resp = await async_client.get(f"{BASE_URL}/", headers=admin_auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "items" in data


@pytest.mark.asyncio
async def test_read_yakit_alimlari_no_auth(async_client):
    """GET /fuel/ without auth → 401."""
    resp = await async_client.get(f"{BASE_URL}/")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_read_yakit_alimlari_with_filters(async_client, admin_auth_headers):
    """GET /fuel/ with arac_id + date filters."""
    with patch(
        f"{ROUTES}.get_all_paged", AsyncMock(return_value=_make_list_response([]))
    ):
        resp = await async_client.get(
            f"{BASE_URL}/?arac_id=1&baslangic_tarih=2026-01-01&skip=0&limit=10",
            headers=admin_auth_headers,
        )
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_read_yakit_alimlari_rejects_huge_limit(async_client, admin_auth_headers):
    """2026-07-01 prod-grade denetimi P1 (Dalga 4 madde 20): `limit` üst
    sınırı yoktu — `?limit=999999999` tüm tabloyu OOM riskiyle çekebilirdi."""
    resp = await async_client.get(
        f"{BASE_URL}/?limit=999999999", headers=admin_auth_headers
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_read_yakit_alimlari_unexpected_error(async_client, admin_auth_headers):
    """GET /fuel/ service raises RuntimeError → 500."""
    with patch(
        f"{ROUTES}.get_all_paged", AsyncMock(side_effect=RuntimeError("db error"))
    ):
        resp = await async_client.get(f"{BASE_URL}/", headers=admin_auth_headers)
    assert resp.status_code == 500


# ---------------------------------------------------------------------------
# POST /fuel/  — create fuel record
# ---------------------------------------------------------------------------

_CREATE_PAYLOAD = {
    "tarih": str(date.today()),
    "arac_id": 1,
    "istasyon": "BP Istanbul",
    "fiyat_tl": "45.50",
    "litre": "200.00",
    "toplam_tutar": "9100.00",
    "km_sayac": 150000,
    "fis_no": "FIS-001",
    "depo_durumu": "Doldu",
    "durum": "Bekliyor",
}


@pytest.mark.asyncio
async def test_create_yakit_success(async_client, admin_auth_headers):
    """POST /fuel/ → 201 created."""
    with (
        patch(f"{ROUTES}.add_yakit", AsyncMock(return_value=42)),
        patch(
            f"{ROUTES}.get_yakit_by_id",
            AsyncMock(return_value=_make_yakit_response_obj(id=42)),
        ),
    ):
        resp = await async_client.post(
            f"{BASE_URL}/", json=_CREATE_PAYLOAD, headers=admin_auth_headers
        )
    assert resp.status_code == 201


@pytest.mark.asyncio
async def test_create_yakit_no_auth(async_client):
    """POST /fuel/ without auth → 401."""
    resp = await async_client.post(f"{BASE_URL}/", json=_CREATE_PAYLOAD)
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_create_yakit_value_error(async_client, admin_auth_headers):
    """POST /fuel/ service raises ValueError → 400."""
    with patch(
        f"{ROUTES}.add_yakit", AsyncMock(side_effect=ValueError("invalid vehicle"))
    ):
        resp = await async_client.post(
            f"{BASE_URL}/", json=_CREATE_PAYLOAD, headers=admin_auth_headers
        )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_create_yakit_unexpected_error(async_client, admin_auth_headers):
    """POST /fuel/ service raises RuntimeError → 500."""
    with patch(f"{ROUTES}.add_yakit", AsyncMock(side_effect=RuntimeError("db crash"))):
        resp = await async_client.post(
            f"{BASE_URL}/", json=_CREATE_PAYLOAD, headers=admin_auth_headers
        )
    assert resp.status_code == 500


@pytest.mark.asyncio
async def test_create_yakit_missing_required_fields(async_client, admin_auth_headers):
    """POST /fuel/ missing required fields → 422."""
    resp = await async_client.post(
        f"{BASE_URL}/", json={"arac_id": 1}, headers=admin_auth_headers
    )
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# GET /fuel/{yakit_id}  — get single record
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_read_yakit_success(async_client, admin_auth_headers):
    """GET /fuel/1 → 200."""
    with patch(
        f"{ROUTES}.get_yakit_by_id",
        AsyncMock(return_value=_make_yakit_response_obj(id=1)),
    ):
        resp = await async_client.get(f"{BASE_URL}/1", headers=admin_auth_headers)
    assert resp.status_code == 200
    assert resp.json()["id"] == 1


@pytest.mark.asyncio
async def test_read_yakit_no_auth(async_client):
    """GET /fuel/1 without auth → 401."""
    resp = await async_client.get(f"{BASE_URL}/1")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_read_yakit_not_found(async_client, admin_auth_headers):
    """GET /fuel/9999 → 404."""
    with patch(f"{ROUTES}.get_yakit_by_id", AsyncMock(return_value=None)):
        resp = await async_client.get(f"{BASE_URL}/9999", headers=admin_auth_headers)
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# PUT /fuel/{yakit_id}  — update fuel record
# ---------------------------------------------------------------------------

_UPDATE_PAYLOAD = {"litre": "250.00", "fiyat_tl": "46.00"}


@pytest.mark.asyncio
async def test_update_yakit_success(async_client, admin_auth_headers):
    """PUT /fuel/1 → 200."""
    with (
        patch(f"{ROUTES}.update_yakit_usecase", AsyncMock(return_value=True)),
        patch(
            f"{ROUTES}.get_yakit_by_id",
            AsyncMock(return_value=_make_yakit_response_obj(litre=Decimal("250.00"))),
        ),
    ):
        resp = await async_client.put(
            f"{BASE_URL}/1", json=_UPDATE_PAYLOAD, headers=admin_auth_headers
        )
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_update_yakit_no_auth(async_client):
    """PUT /fuel/1 without auth → 401."""
    resp = await async_client.put(f"{BASE_URL}/1", json=_UPDATE_PAYLOAD)
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_update_yakit_not_found(async_client, admin_auth_headers):
    """PUT /fuel/9999 → 404 when service returns False."""
    with patch(f"{ROUTES}.update_yakit_usecase", AsyncMock(return_value=False)):
        resp = await async_client.put(
            f"{BASE_URL}/9999", json=_UPDATE_PAYLOAD, headers=admin_auth_headers
        )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_update_yakit_value_error(async_client, admin_auth_headers):
    """PUT /fuel/1 service raises ValueError → 400."""
    with patch(
        f"{ROUTES}.update_yakit_usecase",
        AsyncMock(side_effect=ValueError("bad value")),
    ):
        resp = await async_client.put(
            f"{BASE_URL}/1", json=_UPDATE_PAYLOAD, headers=admin_auth_headers
        )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_update_yakit_unexpected_error(async_client, admin_auth_headers):
    """PUT /fuel/1 service raises RuntimeError → 500."""
    with patch(
        f"{ROUTES}.update_yakit_usecase", AsyncMock(side_effect=RuntimeError("crash"))
    ):
        resp = await async_client.put(
            f"{BASE_URL}/1", json=_UPDATE_PAYLOAD, headers=admin_auth_headers
        )
    assert resp.status_code == 500


# ---------------------------------------------------------------------------
# DELETE /fuel/{yakit_id}  — delete fuel record
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_delete_yakit_not_found_in_db(async_client, admin_auth_headers):
    """DELETE /fuel/9999 — record not in DB → 404 (db.get returns None)."""
    # The delete endpoint calls db.get(YakitAlimi, yakit_id) before service.
    # Since the test DB is empty, the record won't be there → 404.
    resp = await async_client.delete(f"{BASE_URL}/9999", headers=admin_auth_headers)
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_delete_yakit_no_auth(async_client):
    """DELETE /fuel/1 without auth → 401."""
    resp = await async_client.delete(f"{BASE_URL}/1")
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# GET /fuel/excel/template
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_fuel_excel_template_success(async_client, admin_auth_headers):
    """GET /fuel/excel/template → 200 xlsx."""
    with patch(
        "v2.modules.import_excel.public.generate_template",
        new=AsyncMock(return_value=b"PK\x03\x04fake_xlsx_content"),
    ):
        resp = await async_client.get(
            f"{BASE_URL}/excel/template", headers=admin_auth_headers
        )
    assert resp.status_code == 200
    assert (
        resp.headers["content-type"]
        == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )


@pytest.mark.asyncio
async def test_get_fuel_excel_template_no_auth(async_client):
    """GET /fuel/excel/template without auth → 401."""
    resp = await async_client.get(f"{BASE_URL}/excel/template")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_get_fuel_excel_template_error(async_client, admin_auth_headers):
    """GET /fuel/excel/template service error → 500."""
    with patch(
        "v2.modules.import_excel.public.generate_template",
        new=AsyncMock(side_effect=RuntimeError("template error")),
    ):
        resp = await async_client.get(
            f"{BASE_URL}/excel/template", headers=admin_auth_headers
        )
    assert resp.status_code == 500


# ---------------------------------------------------------------------------
# GET /fuel/excel/export
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_export_yakit_alimlari_success(async_client, admin_auth_headers):
    """GET /fuel/excel/export → 200 xlsx content."""
    with (
        patch(
            f"{ROUTES}.get_all_paged",
            AsyncMock(return_value={"items": [], "total": 0}),
        ),
        patch(
            "v2.modules.import_excel.public.export_data",
            new=AsyncMock(return_value=b"PK\x03\x04fake_xlsx"),
        ),
    ):
        resp = await async_client.get(
            f"{BASE_URL}/excel/export", headers=admin_auth_headers
        )
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_export_yakit_alimlari_no_auth(async_client):
    """GET /fuel/excel/export without auth → 401."""
    resp = await async_client.get(f"{BASE_URL}/excel/export")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_export_yakit_alimlari_error(async_client, admin_auth_headers):
    """GET /fuel/excel/export service error → 500."""
    with patch(
        f"{ROUTES}.get_all_paged", AsyncMock(side_effect=RuntimeError("export error"))
    ):
        resp = await async_client.get(
            f"{BASE_URL}/excel/export", headers=admin_auth_headers
        )
    assert resp.status_code == 500


# ---------------------------------------------------------------------------
# POST /fuel/excel/upload
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_upload_yakit_excel_wrong_mime(async_client, admin_auth_headers):
    """POST /fuel/excel/upload with wrong content-type → 400."""
    resp = await async_client.post(
        f"{BASE_URL}/excel/upload",
        files={"file": ("test.csv", b"col1,col2", "text/csv")},
        headers=admin_auth_headers,
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_upload_yakit_excel_wrong_extension(async_client, admin_auth_headers):
    """POST /fuel/excel/upload with .csv extension → 400."""
    resp = await async_client.post(
        f"{BASE_URL}/excel/upload",
        files={
            "file": (
                "test.csv",
                b"col1,col2",
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
        headers=admin_auth_headers,
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_upload_yakit_excel_no_auth(async_client):
    """POST /fuel/excel/upload without auth → 401."""
    resp = await async_client.post(
        f"{BASE_URL}/excel/upload",
        files={
            "file": (
                "test.xlsx",
                b"PK\x03\x04",
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_upload_yakit_excel_sync_success(async_client, admin_auth_headers):
    """POST /fuel/excel/upload (sync) → 200 with import result."""
    with patch(
        "v2.modules.import_excel.public.process_yakit_import",
        AsyncMock(return_value=(10, [])),
    ):
        resp = await async_client.post(
            f"{BASE_URL}/excel/upload",
            files={
                "file": (
                    "fuel.xlsx",
                    b"PK\x03\x04fake_xlsx",
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                )
            },
            headers=admin_auth_headers,
        )
    assert resp.status_code == 200
    data = resp.json()
    assert "saved" in data or "status" in data


@pytest.mark.asyncio
async def test_upload_yakit_excel_async_mode(async_client, admin_auth_headers):
    """POST /fuel/excel/upload?async_mode=true → 200 with task_id.

    The endpoint lazily imports ``get_job_manager`` from
    app.infrastructure.background.job_manager. We patch that factory so the
    submitted job returns a deterministic task_id. (Regression: the endpoint
    previously imported the non-existent ``get_background_job_manager`` and
    crashed on this path — see test_latent_bug_regressions.py.)
    """
    mock_jm = AsyncMock()
    mock_jm.submit = AsyncMock(return_value="task-abc-123")

    with patch(
        "app.infrastructure.background.job_manager.get_job_manager",
        return_value=mock_jm,
    ):
        resp = await async_client.post(
            f"{BASE_URL}/excel/upload?async_mode=true",
            files={
                "file": (
                    "fuel.xlsx",
                    b"PK\x03\x04fake_xlsx",
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                )
            },
            headers=admin_auth_headers,
        )

    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "PROCESSING"
    assert body["task_id"] == "task-abc-123"
    mock_jm.submit.assert_awaited_once()
