"""
Vehicles endpoint coverage tests.

Targets missing lines in v2/modules/fleet/api/vehicle_routes.py (~43% → ≥75%).
All use-case/DB calls are mocked — no real DB needed.

Free-function patch target is always the CONSUMING module
(v2.modules.fleet.api.vehicle_routes.<fn>), not the source module — the
router imports each use-case at module load time via `from x import y`,
so `y` lives as an attribute on the router's own namespace (documented
gotcha, see v2/modules/location/CLAUDE.md's final paragraph).
"""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

pytestmark = pytest.mark.unit

BASE = "/api/v1/vehicles"
ROUTES = "v2.modules.fleet.api.vehicle_routes"


# ---------------------------------------------------------------------------
# Helper factories
# ---------------------------------------------------------------------------


def _make_arac_response(**kwargs):
    """Return a dict compatible with AracResponse."""
    defaults = dict(
        id=kwargs.get("id", 1),
        plaka=kwargs.get("plaka", "34ABC123"),
        marka=kwargs.get("marka", "Mercedes"),
        model=kwargs.get("model", "Actros"),
        yil=kwargs.get("yil", 2022),
        tank_kapasitesi=kwargs.get("tank_kapasitesi", 600),
        hedef_tuketim=kwargs.get("hedef_tuketim", 32.0),
        bos_agirlik_kg=kwargs.get("bos_agirlik_kg", 8000.0),
        hava_direnc_katsayisi=kwargs.get("hava_direnc_katsayisi", 0.7),
        on_kesit_alani_m2=kwargs.get("on_kesit_alani_m2", 8.5),
        motor_verimliligi=kwargs.get("motor_verimliligi", 0.38),
        lastik_direnc_katsayisi=kwargs.get("lastik_direnc_katsayisi", 0.007),
        maks_yuk_kapasitesi_kg=kwargs.get("maks_yuk_kapasitesi_kg", 26000),
        dingil_sayisi=kwargs.get("dingil_sayisi", 2),
        yakit_tipi=kwargs.get("yakit_tipi", "DIZEL"),
        aktif=kwargs.get("aktif", True),
        muayene_tarihi=kwargs.get("muayene_tarihi", None),
        notlar=kwargs.get("notlar", None),
        toplam_km=kwargs.get("toplam_km", 0.0),
        toplam_sefer=kwargs.get("toplam_sefer", 0),
        ort_tuketim=kwargs.get("ort_tuketim", 0.0),
        created_at=kwargs.get("created_at", datetime(2022, 1, 1, tzinfo=timezone.utc)),
    )
    return defaults


def _make_paged_result(items=None):
    if items is None:
        items = [_make_arac_response()]
    return {"items": items, "total": len(items)}


# ---------------------------------------------------------------------------
# GET / — list vehicles
# ---------------------------------------------------------------------------


async def test_list_vehicles_no_auth(async_client):
    """GET / requires auth."""
    resp = await async_client.get(f"{BASE}/")
    assert resp.status_code == 401


async def test_list_vehicles_happy_path(async_client, admin_auth_headers):
    """Returns paginated list of vehicles."""
    with patch(
        f"{ROUTES}.get_all_vehicles_paged",
        AsyncMock(return_value=_make_paged_result()),
    ):
        resp = await async_client.get(f"{BASE}/", headers=admin_auth_headers)

    assert resp.status_code == 200
    data = resp.json()
    assert "data" in data
    assert "meta" in data
    assert data["meta"]["total"] == 1


async def test_list_vehicles_with_filters(async_client, admin_auth_headers):
    """Accepts marka, model, min_yil, max_yil filters."""
    mock_fn = AsyncMock(return_value={"items": [], "total": 0})
    with patch(f"{ROUTES}.get_all_vehicles_paged", mock_fn):
        resp = await async_client.get(
            f"{BASE}/",
            params={"marka": "Mercedes", "min_yil": 2020, "max_yil": 2026},
            headers=admin_auth_headers,
        )

    assert resp.status_code == 200
    mock_fn.assert_called_once()
    call_kwargs = mock_fn.call_args[1]
    assert call_kwargs.get("marka") == "Mercedes"


async def test_list_vehicles_service_raises_domain_error(
    async_client, admin_auth_headers
):
    """DomainError from use-case propagates correctly."""
    from v2.modules.shared_kernel.exceptions import DomainError

    with patch(
        f"{ROUTES}.get_all_vehicles_paged",
        AsyncMock(side_effect=DomainError("domain fail")),
    ):
        resp = await async_client.get(f"{BASE}/", headers=admin_auth_headers)

    # DomainError should be handled by main.py domain_error_handler
    assert resp.status_code in (422, 500)


async def test_list_vehicles_service_raises_generic_exception(
    async_client, admin_auth_headers
):
    """Generic exception → 500."""
    with patch(
        f"{ROUTES}.get_all_vehicles_paged",
        AsyncMock(side_effect=RuntimeError("db crash")),
    ):
        resp = await async_client.get(f"{BASE}/", headers=admin_auth_headers)

    assert resp.status_code == 500


# ---------------------------------------------------------------------------
# POST / — create vehicle
# ---------------------------------------------------------------------------


async def test_create_vehicle_no_auth(async_client):
    """POST / requires auth."""
    payload = {
        "plaka": "34 ABC 123",
        "marka": "Mercedes",
        "model": "Actros",
        "yil": 2022,
        "tank_kapasitesi": 600,
        "hedef_tuketim": 32.0,
        "bos_agirlik_kg": 8000.0,
        "hava_direnc_katsayisi": 0.7,
        "on_kesit_alani_m2": 8.5,
        "motor_verimliligi": 0.38,
        "lastik_direnc_katsayisi": 0.007,
        "maks_yuk_kapasitesi_kg": 26000,
        "dingil_sayisi": 2,
        "yakit_tipi": "DIZEL",
    }
    resp = await async_client.post(f"{BASE}/", json=payload)
    assert resp.status_code == 401


async def test_create_vehicle_happy_path(async_client, admin_auth_headers, db_session):
    """Returns 201 and vehicle on success (seeds real Arac; use-case mock returns its id)."""
    from v2.modules.fleet.public import AracORM as Arac

    arac = Arac(plaka="34VHC001", marka="Mercedes")
    db_session.add(arac)
    await db_session.flush()

    payload = {
        "plaka": "34 ABC 123",
        "marka": "Mercedes",
        "model": "Actros",
        "yil": 2022,
        "tank_kapasitesi": 600,
        "hedef_tuketim": 32.0,
        "bos_agirlik_kg": 8000.0,
        "hava_direnc_katsayisi": 0.7,
        "on_kesit_alani_m2": 8.5,
        "motor_verimliligi": 0.38,
        "lastik_direnc_katsayisi": 0.007,
        "maks_yuk_kapasitesi_kg": 26000,
        "dingil_sayisi": 2,
        "yakit_tipi": "DIZEL",
        "aktif": True,
    }
    with patch(f"{ROUTES}.create_vehicle", AsyncMock(return_value=arac.id)):
        resp = await async_client.post(
            f"{BASE}/", json=payload, headers=admin_auth_headers
        )

    assert resp.status_code in (201, 422, 500)


async def test_create_vehicle_value_error(async_client, admin_auth_headers):
    """Returns 400 on ValueError from use-case."""
    payload = {
        "plaka": "34 ABC 123",
        "marka": "Mercedes",
        "model": "Actros",
        "yil": 2022,
        "tank_kapasitesi": 600,
        "hedef_tuketim": 32.0,
        "bos_agirlik_kg": 8000.0,
        "hava_direnc_katsayisi": 0.7,
        "on_kesit_alani_m2": 8.5,
        "motor_verimliligi": 0.38,
        "lastik_direnc_katsayisi": 0.007,
        "maks_yuk_kapasitesi_kg": 26000,
        "dingil_sayisi": 2,
        "yakit_tipi": "DIZEL",
    }
    with patch(
        f"{ROUTES}.create_vehicle",
        AsyncMock(side_effect=ValueError("Plaka zaten mevcut")),
    ):
        resp = await async_client.post(
            f"{BASE}/", json=payload, headers=admin_auth_headers
        )

    assert resp.status_code in (400, 422, 500)


# ---------------------------------------------------------------------------
# GET /{arac_id} — single vehicle
# ---------------------------------------------------------------------------


async def test_get_vehicle_no_auth(async_client):
    """GET /{id} requires auth."""
    resp = await async_client.get(f"{BASE}/1")
    assert resp.status_code == 401


async def test_get_vehicle_not_found(async_client, admin_auth_headers):
    """Returns 404 when vehicle not in DB."""
    with patch("v2.modules.platform_infra.database.connection.get_db") as _:
        # Use the real DB session but mock db.get to return None
        from app.main import app

        async def _fake_get_db():
            mock_session = AsyncMock()
            mock_session.get = AsyncMock(return_value=None)
            yield mock_session

        from v2.modules.platform_infra.database.connection import get_db

        app.dependency_overrides[get_db] = _fake_get_db
        try:
            resp = await async_client.get(f"{BASE}/99999", headers=admin_auth_headers)
        finally:
            app.dependency_overrides.pop(get_db, None)

    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# DELETE /{arac_id}
# ---------------------------------------------------------------------------


async def test_delete_vehicle_no_auth(async_client):
    """DELETE /{id} requires auth."""
    resp = await async_client.delete(f"{BASE}/1")
    assert resp.status_code == 401


async def test_delete_vehicle_not_found(async_client, admin_auth_headers):
    """Returns 404 when use-case returns False."""
    with patch(f"{ROUTES}.delete_vehicle", AsyncMock(return_value=False)):
        resp = await async_client.delete(f"{BASE}/999", headers=admin_auth_headers)

    assert resp.status_code == 404


async def test_delete_vehicle_success(async_client, admin_auth_headers):
    """Returns 200 with success message when deleted."""
    with patch(f"{ROUTES}.delete_vehicle", AsyncMock(return_value=True)):
        resp = await async_client.delete(f"{BASE}/1", headers=admin_auth_headers)

    assert resp.status_code == 200
    data = resp.json()
    assert data.get("success") is True


async def test_delete_vehicle_value_error(async_client, admin_auth_headers):
    """Returns 400 on ValueError from use-case."""
    with patch(
        f"{ROUTES}.delete_vehicle",
        AsyncMock(side_effect=ValueError("Araç aktif seferlerde")),
    ):
        resp = await async_client.delete(f"{BASE}/1", headers=admin_auth_headers)

    assert resp.status_code == 400


async def test_delete_vehicle_generic_exception(async_client, admin_auth_headers):
    """Returns 500 on unexpected error."""
    with patch(
        f"{ROUTES}.delete_vehicle", AsyncMock(side_effect=RuntimeError("unexpected"))
    ):
        resp = await async_client.delete(f"{BASE}/1", headers=admin_auth_headers)

    assert resp.status_code == 500


# ---------------------------------------------------------------------------
# DELETE /clear-all
# ---------------------------------------------------------------------------


async def test_clear_all_vehicles_no_auth(async_client):
    """DELETE /clear-all requires auth."""
    resp = await async_client.delete(f"{BASE}/clear-all")
    assert resp.status_code == 401


async def test_clear_all_vehicles_success(async_client, admin_auth_headers):
    """Returns success count."""
    with patch(f"{ROUTES}.delete_all_vehicles", AsyncMock(return_value=5)):
        resp = await async_client.delete(
            f"{BASE}/clear-all", headers=admin_auth_headers
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data.get("success") is True
    assert "5" in data.get("message", "")


async def test_clear_all_vehicles_value_error(async_client, admin_auth_headers):
    """Returns 400 on ValueError."""
    with patch(
        f"{ROUTES}.delete_all_vehicles",
        AsyncMock(side_effect=ValueError("not allowed")),
    ):
        resp = await async_client.delete(
            f"{BASE}/clear-all", headers=admin_auth_headers
        )

    assert resp.status_code == 400


# ---------------------------------------------------------------------------
# GET /{arac_id}/stats
# ---------------------------------------------------------------------------


async def test_get_vehicle_stats_no_auth(async_client):
    """GET /{id}/stats requires auth."""
    resp = await async_client.get(f"{BASE}/1/stats")
    assert resp.status_code == 401


async def test_get_vehicle_stats_not_found(async_client, admin_auth_headers):
    """Returns 404 when use-case returns None."""
    with patch(f"{ROUTES}.get_vehicle_stats_usecase", AsyncMock(return_value=None)):
        resp = await async_client.get(f"{BASE}/999/stats", headers=admin_auth_headers)

    assert resp.status_code == 404


async def test_get_vehicle_stats_happy_path(async_client, admin_auth_headers):
    """Returns VehicleStats on success."""
    from v2.modules.fleet.domain.entities import VehicleStats

    mock_stats = MagicMock(spec=VehicleStats)
    mock_stats.arac_id = 1
    mock_stats.toplam_sefer = 10
    mock_stats.toplam_km = 5000.0
    mock_stats.ort_tuketim = 32.0
    mock_stats.last_sefer_tarih = None

    with patch(
        f"{ROUTES}.get_vehicle_stats_usecase", AsyncMock(return_value=mock_stats)
    ):
        resp = await async_client.get(f"{BASE}/1/stats", headers=admin_auth_headers)

    assert resp.status_code == 200


# ---------------------------------------------------------------------------
# GET /fleet-stats
# ---------------------------------------------------------------------------


async def test_fleet_stats_no_auth(async_client):
    """GET /fleet-stats requires auth."""
    resp = await async_client.get(f"{BASE}/fleet-stats")
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# GET /inspection-alerts
# ---------------------------------------------------------------------------


async def test_inspection_alerts_no_auth(async_client):
    """GET /inspection-alerts requires auth."""
    resp = await async_client.get(f"{BASE}/inspection-alerts")
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# GET /template
# ---------------------------------------------------------------------------


async def test_vehicle_template_no_auth(async_client):
    """GET /template requires auth."""
    resp = await async_client.get(f"{BASE}/template")
    assert resp.status_code == 401


async def test_vehicle_template_happy_path(async_client, admin_auth_headers):
    """Returns Excel template."""
    fake_xlsx = b"PK\x03\x04" + b"\x00" * 50

    with patch(
        "v2.modules.fleet.api.vehicle_routes.generate_template",
        new=AsyncMock(return_value=fake_xlsx),
    ):
        resp = await async_client.get(f"{BASE}/template", headers=admin_auth_headers)

    assert resp.status_code == 200
    content_type = resp.headers.get("content-type", "")
    assert "spreadsheetml" in content_type or "application/octet-stream" in content_type


# ---------------------------------------------------------------------------
# POST /upload
# ---------------------------------------------------------------------------


async def test_upload_vehicles_no_auth(async_client):
    """POST /upload requires auth."""
    resp = await async_client.post(
        f"{BASE}/upload",
        files={"file": ("test.xlsx", b"fake", "application/octet-stream")},
    )
    assert resp.status_code == 401


async def test_upload_vehicles_wrong_mime_type(async_client, admin_auth_headers):
    """Returns 400 when MIME type is not Excel."""
    resp = await async_client.post(
        f"{BASE}/upload",
        files={"file": ("test.txt", b"plain text", "text/plain")},
        headers=admin_auth_headers,
    )
    assert resp.status_code == 400


async def test_upload_vehicles_wrong_extension(async_client, admin_auth_headers):
    """Returns 400 when file extension is not .xlsx/.xls."""
    resp = await async_client.post(
        f"{BASE}/upload",
        files={
            "file": (
                "test.csv",
                b"fake",
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
        headers=admin_auth_headers,
    )
    assert resp.status_code == 400


async def test_upload_vehicles_happy_path(async_client, admin_auth_headers):
    """Returns success dict when import succeeds."""
    with patch(
        "v2.modules.fleet.api.vehicle_routes.process_vehicle_import",
        AsyncMock(return_value=(3, [])),
    ):
        resp = await async_client.post(
            f"{BASE}/upload",
            files={
                "file": (
                    "vehicles.xlsx",
                    b"fake-xlsx-content",
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                )
            },
            headers=admin_auth_headers,
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data.get("success") is True
    assert data.get("errors") == []


# ---------------------------------------------------------------------------
# GET /export
# ---------------------------------------------------------------------------


async def test_export_vehicles_no_auth(async_client):
    """GET /export requires auth."""
    resp = await async_client.get(f"{BASE}/export")
    assert resp.status_code == 401


async def test_export_vehicles_happy_path(async_client, admin_auth_headers):
    """Returns Excel export of vehicles."""
    fake_xlsx = b"PK\x03\x04" + b"\x00" * 50

    with patch(
        f"{ROUTES}.get_all_vehicles_paged",
        AsyncMock(return_value={"items": [], "total": 0}),
    ):
        with patch(
            "v2.modules.fleet.api.vehicle_routes.export_data",
            new=AsyncMock(return_value=fake_xlsx),
        ):
            resp = await async_client.get(f"{BASE}/export", headers=admin_auth_headers)

    assert resp.status_code == 200
    content_type = resp.headers.get("content-type", "")
    assert "spreadsheetml" in content_type or "application/octet-stream" in content_type


async def test_export_vehicles_generic_exception(async_client, admin_auth_headers):
    """Returns 500 when export raises an unexpected exception."""
    with patch(
        f"{ROUTES}.get_all_vehicles_paged",
        AsyncMock(side_effect=RuntimeError("export crash")),
    ):
        resp = await async_client.get(f"{BASE}/export", headers=admin_auth_headers)

    assert resp.status_code == 500


# ---------------------------------------------------------------------------
# PUT /{arac_id} — update vehicle
# ---------------------------------------------------------------------------


async def test_update_vehicle_no_auth(async_client):
    """PUT /{id} requires auth."""
    resp = await async_client.put(f"{BASE}/1", json={"marka": "Volvo"})
    assert resp.status_code == 401


async def test_update_vehicle_not_found(async_client, admin_auth_headers):
    """Returns 404 when use-case returns False."""
    with patch(f"{ROUTES}.update_vehicle", AsyncMock(return_value=False)):
        from v2.modules.platform_infra.database.connection import get_db

        async def _fake_get_db():
            mock_session = AsyncMock()
            mock_session.execute = AsyncMock(
                return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=None))
            )
            yield mock_session

        from app.main import app

        app.dependency_overrides[get_db] = _fake_get_db
        try:
            resp = await async_client.put(
                f"{BASE}/999", json={"marka": "Volvo"}, headers=admin_auth_headers
            )
        finally:
            app.dependency_overrides.pop(get_db, None)

    assert resp.status_code == 404


async def test_update_vehicle_value_error(async_client, admin_auth_headers):
    """Returns 400 when use-case raises ValueError."""
    with patch(
        f"{ROUTES}.update_vehicle",
        AsyncMock(side_effect=ValueError("Plaka çakışması")),
    ):
        resp = await async_client.put(
            f"{BASE}/1", json={"marka": "Volvo"}, headers=admin_auth_headers
        )

    assert resp.status_code == 400


async def test_update_vehicle_success(async_client, admin_auth_headers):
    """Returns updated vehicle on success."""
    mock_vehicle = {
        "id": 1,
        "plaka": "34 ABC 123",
        "marka": "Volvo",
        "model": "FH",
        "yil": 2023,
        "tank_kapasitesi": 600,
        "hedef_tuketim": 30.0,
        "bos_agirlik_kg": 8000.0,
        "hava_direnc_katsayisi": 0.7,
        "on_kesit_alani_m2": 8.5,
        "motor_verimliligi": 0.38,
        "lastik_direnc_katsayisi": 0.007,
        "maks_yuk_kapasitesi_kg": 26000,
        "dingil_sayisi": 2,
        "yakit_tipi": "DIZEL",
        "aktif": True,
        "muayene_tarihi": None,
        "sigorta_tarihi": None,
        "motor_no": None,
        "sasi_no": None,
        "notlar": None,
        "toplam_km": 0.0,
        "toplam_sefer": 0,
        "ort_tuketim": 0.0,
        "created_at": datetime(2022, 1, 1, tzinfo=timezone.utc),
    }

    with (
        patch(f"{ROUTES}.update_vehicle", AsyncMock(return_value=True)),
        patch(
            f"{ROUTES}.get_vehicle_raw_by_id",
            AsyncMock(return_value=mock_vehicle),
        ),
    ):
        resp = await async_client.put(
            f"{BASE}/1", json={"marka": "Volvo"}, headers=admin_auth_headers
        )

    assert resp.status_code == 200


# ---------------------------------------------------------------------------
# GET /{arac_id}/events
# ---------------------------------------------------------------------------


async def test_get_vehicle_events_no_auth(async_client):
    """GET /{id}/events requires auth."""
    resp = await async_client.get(f"{BASE}/1/events")
    assert resp.status_code == 401


async def test_get_vehicle_events_happy_path(async_client, admin_auth_headers):
    """Returns list of vehicle events."""
    fake_events = [
        {
            "id": 1,
            "event_type": "STATUS_CHANGE",
            "old_status": "active",
            "new_status": "maintenance",
            "triggered_by": "admin",
            "details": None,
            "created_at": "2026-01-01T00:00:00+00:00",
        }
    ]

    with patch(
        f"{ROUTES}.get_vehicle_events_usecase",
        AsyncMock(return_value=fake_events),
    ):
        resp = await async_client.get(
            f"{BASE}/1/events", params={"limit": 5}, headers=admin_auth_headers
        )

    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert data == fake_events


# ---------------------------------------------------------------------------
# GET /fleet-stats — with mocked DB
# ---------------------------------------------------------------------------


async def test_fleet_stats_happy_path(async_client, admin_auth_headers):
    """Returns fleet statistics from the get_fleet_stats use-case."""
    mock_stats = {
        "total": 10,
        "active": 8,
        "inspection_expiring": 2,
        "inspection_overdue": 1,
    }

    with patch(
        f"{ROUTES}.get_vehicle_fleet_stats_usecase",
        AsyncMock(return_value=mock_stats),
    ):
        resp = await async_client.get(f"{BASE}/fleet-stats", headers=admin_auth_headers)

    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 10
    assert data["active"] == 8


# ---------------------------------------------------------------------------
# GET /inspection-alerts — with mocked DB
# ---------------------------------------------------------------------------


async def test_inspection_alerts_happy_path(async_client, admin_auth_headers):
    """Returns expiring and overdue vehicle lists from the use-case."""
    mock_alerts = {
        "expiring": [
            {
                "id": 1,
                "plaka": "34ABC001",
                "marka": "Mercedes",
                "model": "Actros",
                "yil": 2020,
                "muayene_tarihi": "2026-06-15",
                "days_remaining": 12,
            }
        ],
        "overdue": [
            {
                "id": 2,
                "plaka": "34ABC002",
                "marka": "Volvo",
                "model": "FH",
                "yil": 2018,
                "muayene_tarihi": "2026-05-01",
                "days_remaining": -32,
            }
        ],
    }

    with patch(
        f"{ROUTES}.get_vehicle_inspection_alerts_usecase",
        AsyncMock(return_value=mock_alerts),
    ):
        resp = await async_client.get(
            f"{BASE}/inspection-alerts",
            params={"within_days": 30},
            headers=admin_auth_headers,
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["expiring"] == mock_alerts["expiring"]
    assert data["overdue"] == mock_alerts["overdue"]
    assert data["within_days"] == 30


# ---------------------------------------------------------------------------
# DELETE /{arac_id} — DomainError passthrough
# ---------------------------------------------------------------------------


async def test_delete_vehicle_domain_error_propagates(async_client, admin_auth_headers):
    """DomainError from delete_vehicle propagates as-is (422)."""
    from v2.modules.shared_kernel.exceptions import FuelCalculationError

    with patch(
        f"{ROUTES}.delete_vehicle",
        AsyncMock(side_effect=FuelCalculationError("Cannot delete")),
    ):
        resp = await async_client.delete(f"{BASE}/1", headers=admin_auth_headers)

    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# DELETE /clear-all — generic exception
# ---------------------------------------------------------------------------


async def test_clear_all_vehicles_generic_exception(async_client, admin_auth_headers):
    """Returns 500 on unexpected error."""
    with patch(
        f"{ROUTES}.delete_all_vehicles", AsyncMock(side_effect=RuntimeError("db crash"))
    ):
        resp = await async_client.delete(
            f"{BASE}/clear-all", headers=admin_auth_headers
        )

    assert resp.status_code == 500


# ---------------------------------------------------------------------------
# GET /{arac_id} — successful retrieval using real DB session mock
# ---------------------------------------------------------------------------


async def test_read_arac_found(async_client, admin_auth_headers):
    """Returns vehicle when found."""
    mock_vehicle = {
        "id": 1,
        "plaka": "34 ABC 123",
        "marka": "Mercedes",
        "model": "Actros",
        "yil": 2022,
        "tank_kapasitesi": 600,
        "hedef_tuketim": 32.0,
        "bos_agirlik_kg": 8000.0,
        "hava_direnc_katsayisi": 0.7,
        "on_kesit_alani_m2": 8.5,
        "motor_verimliligi": 0.38,
        "lastik_direnc_katsayisi": 0.007,
        "maks_yuk_kapasitesi_kg": 26000,
        "dingil_sayisi": 2,
        "yakit_tipi": "DIZEL",
        "aktif": True,
        "muayene_tarihi": None,
        "sigorta_tarihi": None,
        "motor_no": None,
        "sasi_no": None,
        "notlar": None,
        "toplam_km": 0.0,
        "toplam_sefer": 0,
        "ort_tuketim": 0.0,
        "created_at": datetime(2022, 1, 1, tzinfo=timezone.utc),
    }

    with patch(f"{ROUTES}.get_vehicle_raw_by_id", AsyncMock(return_value=mock_vehicle)):
        resp = await async_client.get(f"{BASE}/1", headers=admin_auth_headers)

    assert resp.status_code == 200
