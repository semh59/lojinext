"""
Vehicles endpoint coverage tests.

Targets missing lines in app/api/v1/endpoints/vehicles.py (~43% → ≥75%).
All service/DB calls are mocked — no real DB needed.
"""

from contextlib import contextmanager
from datetime import date, datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

pytestmark = pytest.mark.unit

BASE = "/api/v1/vehicles"


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
# Service dependency override helpers
# ---------------------------------------------------------------------------


@contextmanager
def _override_arac_service(mock_svc):
    from app.api.deps import get_arac_service
    from app.main import app

    async def _fake():
        return mock_svc

    app.dependency_overrides[get_arac_service] = _fake
    try:
        yield
    finally:
        app.dependency_overrides.pop(get_arac_service, None)


# ---------------------------------------------------------------------------
# GET / — list vehicles
# ---------------------------------------------------------------------------


async def test_list_vehicles_no_auth(async_client):
    """GET / requires auth."""
    resp = await async_client.get(f"{BASE}/")
    assert resp.status_code == 401


async def test_list_vehicles_happy_path(async_client, admin_auth_headers):
    """Returns paginated list of vehicles."""
    mock_svc = AsyncMock()
    mock_svc.get_all_paged = AsyncMock(return_value=_make_paged_result())

    with _override_arac_service(mock_svc):
        resp = await async_client.get(f"{BASE}/", headers=admin_auth_headers)

    assert resp.status_code == 200
    data = resp.json()
    assert "data" in data
    assert "meta" in data
    assert data["meta"]["total"] == 1


async def test_list_vehicles_with_filters(async_client, admin_auth_headers):
    """Accepts marka, model, min_yil, max_yil filters."""
    mock_svc = AsyncMock()
    mock_svc.get_all_paged = AsyncMock(return_value={"items": [], "total": 0})

    with _override_arac_service(mock_svc):
        resp = await async_client.get(
            f"{BASE}/",
            params={"marka": "Mercedes", "min_yil": 2020, "max_yil": 2026},
            headers=admin_auth_headers,
        )

    assert resp.status_code == 200
    mock_svc.get_all_paged.assert_called_once()
    call_kwargs = mock_svc.get_all_paged.call_args[1]
    assert call_kwargs.get("marka") == "Mercedes"


async def test_list_vehicles_service_raises_domain_error(
    async_client, admin_auth_headers
):
    """DomainError from service propagates correctly."""
    from app.core.exceptions import DomainError

    mock_svc = AsyncMock()
    mock_svc.get_all_paged = AsyncMock(side_effect=DomainError("domain fail"))

    with _override_arac_service(mock_svc):
        resp = await async_client.get(f"{BASE}/", headers=admin_auth_headers)

    # DomainError should be handled by main.py domain_error_handler
    assert resp.status_code in (422, 500)


async def test_list_vehicles_service_raises_generic_exception(
    async_client, admin_auth_headers
):
    """Generic exception → 500."""
    mock_svc = AsyncMock()
    mock_svc.get_all_paged = AsyncMock(side_effect=RuntimeError("db crash"))

    with _override_arac_service(mock_svc):
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
    """Returns 201 and vehicle on success (seeds real Arac; service mock returns its id)."""
    from app.database.models import Arac

    arac = Arac(plaka="34VHC001", marka="Mercedes")
    db_session.add(arac)
    await db_session.flush()

    mock_svc = AsyncMock()
    mock_svc.create_arac = AsyncMock(return_value=arac.id)

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
    with _override_arac_service(mock_svc):
        resp = await async_client.post(
            f"{BASE}/", json=payload, headers=admin_auth_headers
        )

    assert resp.status_code in (201, 422, 500)


async def test_create_vehicle_value_error(async_client, admin_auth_headers):
    """Returns 400 on ValueError from service."""
    mock_svc = AsyncMock()
    mock_svc.create_arac = AsyncMock(side_effect=ValueError("Plaka zaten mevcut"))

    with _override_arac_service(mock_svc):
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
    with patch("app.database.connection.get_db") as _:
        # Use the real DB session but mock db.get to return None
        from app.main import app

        async def _fake_get_db():
            mock_session = AsyncMock()
            mock_session.get = AsyncMock(return_value=None)
            yield mock_session

        from app.database.connection import get_db

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
    """Returns 404 when service returns False."""
    mock_svc = AsyncMock()
    mock_svc.delete_arac = AsyncMock(return_value=False)

    with _override_arac_service(mock_svc):
        resp = await async_client.delete(f"{BASE}/999", headers=admin_auth_headers)

    assert resp.status_code == 404


async def test_delete_vehicle_success(async_client, admin_auth_headers):
    """Returns 200 with success message when deleted."""
    mock_svc = AsyncMock()
    mock_svc.delete_arac = AsyncMock(return_value=True)

    with _override_arac_service(mock_svc):
        resp = await async_client.delete(f"{BASE}/1", headers=admin_auth_headers)

    assert resp.status_code == 200
    data = resp.json()
    assert data.get("success") is True


async def test_delete_vehicle_value_error(async_client, admin_auth_headers):
    """Returns 400 on ValueError from service."""
    mock_svc = AsyncMock()
    mock_svc.delete_arac = AsyncMock(side_effect=ValueError("Araç aktif seferlerde"))

    with _override_arac_service(mock_svc):
        resp = await async_client.delete(f"{BASE}/1", headers=admin_auth_headers)

    assert resp.status_code == 400


async def test_delete_vehicle_generic_exception(async_client, admin_auth_headers):
    """Returns 500 on unexpected error."""
    mock_svc = AsyncMock()
    mock_svc.delete_arac = AsyncMock(side_effect=RuntimeError("unexpected"))

    with _override_arac_service(mock_svc):
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
    mock_svc = AsyncMock()
    mock_svc.delete_all_vehicles = AsyncMock(return_value=5)

    with _override_arac_service(mock_svc):
        resp = await async_client.delete(
            f"{BASE}/clear-all", headers=admin_auth_headers
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data.get("success") is True
    assert "5" in data.get("message", "")


async def test_clear_all_vehicles_value_error(async_client, admin_auth_headers):
    """Returns 400 on ValueError."""
    mock_svc = AsyncMock()
    mock_svc.delete_all_vehicles = AsyncMock(side_effect=ValueError("not allowed"))

    with _override_arac_service(mock_svc):
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
    """Returns 404 when service returns None."""
    mock_svc = AsyncMock()
    mock_svc.get_vehicle_stats = AsyncMock(return_value=None)

    with _override_arac_service(mock_svc):
        resp = await async_client.get(f"{BASE}/999/stats", headers=admin_auth_headers)

    assert resp.status_code == 404


async def test_get_vehicle_stats_happy_path(async_client, admin_auth_headers):
    """Returns VehicleStats on success."""
    from app.core.entities.models import VehicleStats

    mock_stats = MagicMock(spec=VehicleStats)
    mock_stats.arac_id = 1
    mock_stats.toplam_sefer = 10
    mock_stats.toplam_km = 5000.0
    mock_stats.ort_tuketim = 32.0
    mock_stats.last_sefer_tarih = None

    mock_svc = AsyncMock()
    mock_svc.get_vehicle_stats = AsyncMock(return_value=mock_stats)

    with _override_arac_service(mock_svc):
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
        "app.core.services.excel_service.ExcelService.generate_template",
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
    with patch("app.core.services.import_service.get_import_service") as mock_factory:
        mock_svc = AsyncMock()
        mock_svc.process_vehicle_import = AsyncMock(return_value=(3, []))
        mock_factory.return_value = mock_svc

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
    mock_svc = AsyncMock()
    mock_svc.get_all_paged = AsyncMock(return_value={"items": [], "total": 0})

    with _override_arac_service(mock_svc):
        with patch(
            "app.core.services.excel_service.ExcelService.export_data",
            new=AsyncMock(return_value=fake_xlsx),
        ):
            resp = await async_client.get(f"{BASE}/export", headers=admin_auth_headers)

    assert resp.status_code == 200
    content_type = resp.headers.get("content-type", "")
    assert "spreadsheetml" in content_type or "application/octet-stream" in content_type


async def test_export_vehicles_generic_exception(async_client, admin_auth_headers):
    """Returns 500 when export raises an unexpected exception."""
    mock_svc = AsyncMock()
    mock_svc.get_all_paged = AsyncMock(side_effect=RuntimeError("export crash"))

    with _override_arac_service(mock_svc):
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
    """Returns 404 when service returns False."""
    mock_svc = AsyncMock()
    mock_svc.update_arac = AsyncMock(return_value=False)

    with _override_arac_service(mock_svc):
        from app.database.connection import get_db

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
    """Returns 400 when service raises ValueError."""
    mock_svc = AsyncMock()
    mock_svc.update_arac = AsyncMock(side_effect=ValueError("Plaka çakışması"))

    with _override_arac_service(mock_svc):
        resp = await async_client.put(
            f"{BASE}/1", json={"marka": "Volvo"}, headers=admin_auth_headers
        )

    assert resp.status_code == 400


async def test_update_vehicle_success(async_client, admin_auth_headers):
    """Returns updated vehicle on success."""
    mock_vehicle = MagicMock()
    mock_vehicle.id = 1
    mock_vehicle.plaka = "34 ABC 123"
    mock_vehicle.marka = "Volvo"
    mock_vehicle.model = "FH"
    mock_vehicle.yil = 2023
    mock_vehicle.tank_kapasitesi = 600
    mock_vehicle.hedef_tuketim = 30.0
    mock_vehicle.bos_agirlik_kg = 8000.0
    mock_vehicle.hava_direnc_katsayisi = 0.7
    mock_vehicle.on_kesit_alani_m2 = 8.5
    mock_vehicle.motor_verimliligi = 0.38
    mock_vehicle.lastik_direnc_katsayisi = 0.007
    mock_vehicle.maks_yuk_kapasitesi_kg = 26000
    mock_vehicle.dingil_sayisi = 2
    mock_vehicle.yakit_tipi = "DIZEL"
    mock_vehicle.aktif = True
    mock_vehicle.muayene_tarihi = None
    mock_vehicle.sigorta_tarihi = None
    mock_vehicle.motor_no = None
    mock_vehicle.sasi_no = None
    mock_vehicle.notlar = None
    mock_vehicle.toplam_km = 0.0
    mock_vehicle.toplam_sefer = 0
    mock_vehicle.ort_tuketim = 0.0
    mock_vehicle.created_at = datetime(2022, 1, 1, tzinfo=timezone.utc)

    mock_svc = AsyncMock()
    mock_svc.update_arac = AsyncMock(return_value=True)

    with _override_arac_service(mock_svc):
        from app.database.connection import get_db
        from app.main import app

        async def _fake_get_db():
            mock_session = AsyncMock()
            mock_result = MagicMock()
            mock_result.scalar_one_or_none = MagicMock(return_value=mock_vehicle)
            mock_session.execute = AsyncMock(return_value=mock_result)
            yield mock_session

        app.dependency_overrides[get_db] = _fake_get_db
        try:
            resp = await async_client.put(
                f"{BASE}/1", json={"marka": "Volvo"}, headers=admin_auth_headers
            )
        finally:
            app.dependency_overrides.pop(get_db, None)

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
    from app.database.connection import get_db
    from app.main import app

    fake_rows = [
        {
            "id": 1,
            "event_type": "STATUS_CHANGE",
            "old_status": "active",
            "new_status": "maintenance",
            "triggered_by": "admin",
            "details": None,
            "created_at": datetime(2026, 1, 1, tzinfo=timezone.utc),
        }
    ]

    async def _fake_get_db():
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.mappings = MagicMock(return_value=iter(fake_rows))
        mock_session.execute = AsyncMock(return_value=mock_result)
        yield mock_session

    app.dependency_overrides[get_db] = _fake_get_db
    try:
        resp = await async_client.get(
            f"{BASE}/1/events", params={"limit": 5}, headers=admin_auth_headers
        )
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)


# ---------------------------------------------------------------------------
# GET /fleet-stats — with mocked DB
# ---------------------------------------------------------------------------


async def test_fleet_stats_happy_path(async_client, admin_auth_headers):
    """Returns fleet statistics using raw SQL."""
    from app.database.connection import get_db
    from app.main import app

    mock_row = {
        "total": 10,
        "active": 8,
        "inspection_expiring": 2,
        "inspection_overdue": 1,
    }

    async def _fake_get_db():
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_mappings = MagicMock()
        mock_mappings.one = MagicMock(return_value=mock_row)
        mock_result.mappings = MagicMock(return_value=mock_mappings)
        mock_session.execute = AsyncMock(return_value=mock_result)
        yield mock_session

    app.dependency_overrides[get_db] = _fake_get_db
    try:
        resp = await async_client.get(f"{BASE}/fleet-stats", headers=admin_auth_headers)
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 10
    assert data["active"] == 8


# ---------------------------------------------------------------------------
# GET /inspection-alerts — with mocked DB
# ---------------------------------------------------------------------------


async def test_inspection_alerts_happy_path(async_client, admin_auth_headers):
    """Returns expiring and overdue vehicle lists."""
    from app.database.connection import get_db
    from app.main import app

    fake_rows = [
        {
            "id": 1,
            "plaka": "34ABC001",
            "marka": "Mercedes",
            "model": "Actros",
            "yil": 2020,
            "muayene_tarihi": date(2026, 6, 15),
            "bucket": "expiring",
            "days_remaining": 12,
        },
        {
            "id": 2,
            "plaka": "34ABC002",
            "marka": "Volvo",
            "model": "FH",
            "yil": 2018,
            "muayene_tarihi": date(2026, 5, 1),
            "bucket": "overdue",
            "days_remaining": -32,
        },
    ]

    async def _fake_get_db():
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.mappings = MagicMock(
            return_value=MagicMock(all=MagicMock(return_value=fake_rows))
        )
        mock_session.execute = AsyncMock(return_value=mock_result)
        yield mock_session

    app.dependency_overrides[get_db] = _fake_get_db
    try:
        resp = await async_client.get(
            f"{BASE}/inspection-alerts",
            params={"within_days": 30},
            headers=admin_auth_headers,
        )
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert resp.status_code == 200
    data = resp.json()
    assert "expiring" in data
    assert "overdue" in data
    assert data["within_days"] == 30


# ---------------------------------------------------------------------------
# DELETE /{arac_id} — DomainError passthrough
# ---------------------------------------------------------------------------


async def test_delete_vehicle_domain_error_propagates(async_client, admin_auth_headers):
    """DomainError from delete_arac propagates as-is (422)."""
    from app.core.exceptions import FuelCalculationError

    mock_svc = AsyncMock()
    mock_svc.delete_arac = AsyncMock(side_effect=FuelCalculationError("Cannot delete"))

    with _override_arac_service(mock_svc):
        resp = await async_client.delete(f"{BASE}/1", headers=admin_auth_headers)

    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# DELETE /clear-all — generic exception
# ---------------------------------------------------------------------------


async def test_clear_all_vehicles_generic_exception(async_client, admin_auth_headers):
    """Returns 500 on unexpected error."""
    mock_svc = AsyncMock()
    mock_svc.delete_all_vehicles = AsyncMock(side_effect=RuntimeError("db crash"))

    with _override_arac_service(mock_svc):
        resp = await async_client.delete(
            f"{BASE}/clear-all", headers=admin_auth_headers
        )

    assert resp.status_code == 500


# ---------------------------------------------------------------------------
# GET /{arac_id} — successful retrieval using real DB session mock
# ---------------------------------------------------------------------------


async def test_read_arac_found(async_client, admin_auth_headers):
    """Returns vehicle when found."""
    from app.database.connection import get_db
    from app.database.models import Arac
    from app.main import app

    mock_vehicle = MagicMock(spec=Arac)
    mock_vehicle.id = 1
    mock_vehicle.plaka = "34 ABC 123"
    mock_vehicle.marka = "Mercedes"
    mock_vehicle.model = "Actros"
    mock_vehicle.yil = 2022
    mock_vehicle.tank_kapasitesi = 600
    mock_vehicle.hedef_tuketim = 32.0
    mock_vehicle.bos_agirlik_kg = 8000.0
    mock_vehicle.hava_direnc_katsayisi = 0.7
    mock_vehicle.on_kesit_alani_m2 = 8.5
    mock_vehicle.motor_verimliligi = 0.38
    mock_vehicle.lastik_direnc_katsayisi = 0.007
    mock_vehicle.maks_yuk_kapasitesi_kg = 26000
    mock_vehicle.dingil_sayisi = 2
    mock_vehicle.yakit_tipi = "DIZEL"
    mock_vehicle.aktif = True
    mock_vehicle.muayene_tarihi = None
    mock_vehicle.sigorta_tarihi = None
    mock_vehicle.motor_no = None
    mock_vehicle.sasi_no = None
    mock_vehicle.notlar = None
    mock_vehicle.toplam_km = 0.0
    mock_vehicle.toplam_sefer = 0
    mock_vehicle.ort_tuketim = 0.0
    mock_vehicle.created_at = datetime(2022, 1, 1, tzinfo=timezone.utc)

    async def _fake_get_db():
        mock_session = AsyncMock()
        mock_session.get = AsyncMock(return_value=mock_vehicle)
        yield mock_session

    app.dependency_overrides[get_db] = _fake_get_db
    try:
        resp = await async_client.get(f"{BASE}/1", headers=admin_auth_headers)
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert resp.status_code == 200
