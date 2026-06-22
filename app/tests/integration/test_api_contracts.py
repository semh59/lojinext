"""
Layer 2 — API Contract Tests
Asserts every critical endpoint returns the documented response shape with
correct types. No NaN, no missing required fields.

StandardResponse envelope: {"data": ..., "meta": {...}, "errors": null}
Paginated list endpoints: {"data": [...], "meta": {"total": int, ...}}
"""

import math
import uuid
from datetime import date

import pytest

pytestmark = pytest.mark.integration


# ── Helpers ──────────────────────────────────────────────────────────────────


def _is_finite_float(v) -> bool:
    try:
        return math.isfinite(float(v))
    except (TypeError, ValueError):
        return False


def _unique_num() -> int:
    return int(uuid.uuid4().hex[:4], 16) % 9000 + 1000


async def _create_vehicle(client, headers) -> int:
    num = _unique_num()
    r = await client.post(
        "/api/v1/vehicles/",
        json={
            "plaka": f"34 CT {num}",
            "marka": "Mercedes",
            "model": "Actros",
            "yil": 2023,
            "tank_kapasitesi": 600,
            "hedef_tuketim": 31.5,
            "aktif": True,
        },
        headers=headers,
    )
    assert r.status_code == 201, f"Vehicle create failed: {r.text}"
    return r.json()["id"]


async def _create_driver(client, headers, suffix: str) -> int:
    r = await client.post(
        "/api/v1/drivers/",
        json={
            "ad_soyad": f"CT Sofor {suffix}",
            "ehliyet_sinifi": "E",
            "ise_baslama": date.today().isoformat(),
            "aktif": True,
        },
        headers=headers,
    )
    assert r.status_code == 201, f"Driver create failed: {r.text}"
    return r.json()["id"]


async def _create_location(client, headers, suffix: str) -> int:
    r = await client.post(
        "/api/v1/locations/",
        json={
            "cikis_yeri": f"CT City {suffix}",
            "varis_yeri": f"CT Dest {suffix}",
            "mesafe_km": 350.0,
            "zorluk": "Normal",
        },
        headers=headers,
    )
    assert r.status_code == 201, f"Location create failed: {r.text}"
    return r.json()["id"]


def _unwrap(body):
    """Extract list/items from StandardResponse, paginated, or plain list."""
    if isinstance(body, list):
        return body
    if isinstance(body, dict):
        # StandardResponse: {"data": [...]}
        if "data" in body and isinstance(body["data"], list):
            return body["data"]
        # Paginated: {"items": [...]}
        if "items" in body:
            return body["items"]
    return []


# ── Contract Tests ────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_vehicle_create_response_shape(async_client, admin_auth_headers):
    """POST /vehicles/ — id(int), plaka(str), aktif(bool), tank_kapasitesi(int>0), hedef_tuketim(float>0)."""
    num = _unique_num()
    r = await async_client.post(
        "/api/v1/vehicles/",
        json={
            "plaka": f"06 AB {num}",
            "marka": "MAN",
            "model": "TGX",
            "yil": 2022,
            "tank_kapasitesi": 500,
            "hedef_tuketim": 32.0,
            "aktif": True,
        },
        headers=admin_auth_headers,
    )
    assert r.status_code == 201, f"Vehicle create failed: {r.text}"
    body = r.json()
    assert isinstance(body["id"], int) and body["id"] > 0
    assert isinstance(body["plaka"], str) and body["plaka"]
    assert isinstance(body["aktif"], bool)
    assert isinstance(body["tank_kapasitesi"], int) and body["tank_kapasitesi"] > 0
    assert _is_finite_float(body["hedef_tuketim"]) and float(body["hedef_tuketim"]) > 0


@pytest.mark.asyncio
async def test_driver_create_response_shape(async_client, admin_auth_headers):
    """POST /drivers/ — id(int), ad_soyad(str), aktif(bool), ehliyet_sinifi(str)."""
    suffix = uuid.uuid4().hex[:8].upper()
    r = await async_client.post(
        "/api/v1/drivers/",
        json={
            "ad_soyad": f"Contract Test {suffix}",
            "ehliyet_sinifi": "E",
            "ise_baslama": date.today().isoformat(),
            "aktif": True,
        },
        headers=admin_auth_headers,
    )
    assert r.status_code == 201, f"Driver create failed: {r.text}"
    body = r.json()
    assert isinstance(body["id"], int) and body["id"] > 0
    assert isinstance(body["ad_soyad"], str) and body["ad_soyad"]
    assert isinstance(body["aktif"], bool)
    assert isinstance(body["ehliyet_sinifi"], str) and body["ehliyet_sinifi"]


@pytest.mark.asyncio
async def test_trip_detail_flat_fields(async_client, admin_auth_headers):
    """
    GET /trips/{id} returns flat fields: plaka(str), sofor_adi(str) — not nested objects.
    Both must be non-null strings after a trip is created with valid references.
    """
    suffix = uuid.uuid4().hex[:8].upper()
    arac_id = await _create_vehicle(async_client, admin_auth_headers)
    sofor_id = await _create_driver(async_client, admin_auth_headers, suffix)
    guzergah_id = await _create_location(async_client, admin_auth_headers, suffix)

    trip_r = await async_client.post(
        "/api/v1/trips/",
        json={
            "tarih": date.today().isoformat(),
            "arac_id": arac_id,
            "sofor_id": sofor_id,
            "guzergah_id": guzergah_id,
            "cikis_yeri": f"CT City {suffix}",
            "varis_yeri": f"CT Dest {suffix}",
            "mesafe_km": 350.0,
            "net_kg": 0,
            "durum": "Planlandı",
        },
        headers=admin_auth_headers,
    )
    assert trip_r.status_code == 201, f"Trip create failed: {trip_r.text}"
    sefer_id = trip_r.json()["id"]

    r = await async_client.get(f"/api/v1/trips/{sefer_id}", headers=admin_auth_headers)
    assert r.status_code == 200
    body = r.json()

    assert isinstance(body["id"], int)
    assert body["arac_id"] == arac_id
    assert body["sofor_id"] == sofor_id
    assert isinstance(body["cikis_yeri"], str) and body["cikis_yeri"]
    assert isinstance(body["varis_yeri"], str) and body["varis_yeri"]
    assert _is_finite_float(body["mesafe_km"])

    assert isinstance(body.get("plaka"), str) and body["plaka"], (
        f"'plaka' must be non-empty str in trip detail — got: {body.get('plaka')!r}"
    )
    assert isinstance(body.get("sofor_adi"), str) and body["sofor_adi"], (
        f"'sofor_adi' must be non-empty str in trip detail — got: {body.get('sofor_adi')!r}"
    )


@pytest.mark.asyncio
async def test_fuel_list_response_shape(async_client, admin_auth_headers):
    """
    GET /fuel/?arac_id=X returns {items:[...], total:int}.
    Items must have litre and fiyat_tl as finite positive numbers.
    """
    arac_id = await _create_vehicle(async_client, admin_auth_headers)

    r_create = await async_client.post(
        "/api/v1/fuel/",
        json={
            "tarih": date.today().isoformat(),
            "arac_id": arac_id,
            "litre": "150.00",
            "fiyat_tl": "42.50",
            "toplam_tutar": "6375.00",
            "km_sayac": 150000,
            "depo_durumu": "Dolu",
            "durum": "Bekliyor",
        },
        headers=admin_auth_headers,
    )
    assert r_create.status_code == 201, f"Fuel create failed: {r_create.text}"

    r = await async_client.get(
        f"/api/v1/fuel/?arac_id={arac_id}", headers=admin_auth_headers
    )
    assert r.status_code == 200
    body = r.json()
    assert "items" in body and "total" in body, (
        f"Fuel list must have 'items' and 'total'. Got keys: {list(body.keys())}"
    )
    assert isinstance(body["total"], int) and body["total"] >= 1
    for item in body["items"]:
        assert _is_finite_float(item["litre"]), f"litre is not finite: {item['litre']}"
        assert _is_finite_float(item["fiyat_tl"]), (
            f"fiyat_tl is not finite: {item['fiyat_tl']}"
        )
        assert float(item["litre"]) > 0, f"litre must be > 0: {item['litre']}"
        assert float(item["fiyat_tl"]) > 0, f"fiyat_tl must be > 0: {item['fiyat_tl']}"


@pytest.mark.asyncio
async def test_dashboard_report_no_nan(async_client, admin_auth_headers):
    """
    GET /reports/dashboard — toplam_sefer(int), toplam_km(float), toplam_yakit(float),
    filo_ortalama(float). None must be NaN.
    """
    r = await async_client.get("/api/v1/reports/dashboard", headers=admin_auth_headers)
    assert r.status_code == 200, f"Dashboard failed: {r.text}"
    body = r.json()

    for field in ("toplam_sefer", "toplam_km", "toplam_yakit", "filo_ortalama"):
        assert field in body, f"'{field}' missing from dashboard response"

    assert isinstance(body["toplam_sefer"], int) and body["toplam_sefer"] >= 0
    assert _is_finite_float(body["toplam_km"]), f"toplam_km is NaN: {body['toplam_km']}"
    assert _is_finite_float(body["toplam_yakit"]), (
        f"toplam_yakit is NaN: {body['toplam_yakit']}"
    )
    assert _is_finite_float(body["filo_ortalama"]), (
        f"filo_ortalama is NaN: {body['filo_ortalama']}"
    )


@pytest.mark.asyncio
async def test_prediction_response_shape(async_client, admin_auth_headers):
    """
    POST /predictions/predict — tahmini_tuketim(float>0), model_used(str), status='success'.
    confidence_low/high when present must be finite floats.
    """
    r = await async_client.post(
        "/api/v1/predictions/predict",
        json={
            "arac_id": 1,
            "mesafe_km": 450.0,
            "ton": 20.0,
            "ascent_m": 0.0,
            "descent_m": 0.0,
            "flat_distance_km": 450.0,
            "zorluk": "Normal",
            "model_type": "ensemble",
        },
        headers=admin_auth_headers,
    )
    assert r.status_code != 500, f"Prediction must not 500: {r.text}"
    assert r.status_code in (
        200,
        404,
        422,
    ), f"Unexpected status {r.status_code}: {r.text}"
    if r.status_code == 200:
        body = r.json()
        assert (
            _is_finite_float(body["tahmini_tuketim"])
            and float(body["tahmini_tuketim"]) > 0
        ), f"tahmini_tuketim invalid: {body.get('tahmini_tuketim')}"
        assert isinstance(body["model_used"], str) and body["model_used"]
        assert body["status"] == "success"
        for field in ("confidence_low", "confidence_high"):
            if body.get(field) is not None:
                assert _is_finite_float(body[field]), f"{field} is NaN: {body[field]}"


@pytest.mark.asyncio
async def test_vehicle_list_pagination_envelope(async_client, admin_auth_headers):
    """GET /vehicles/ returns StandardResponse: {"data": [...], "meta": {"total": int}}."""
    r = await async_client.get(
        "/api/v1/vehicles/?skip=0&limit=5", headers=admin_auth_headers
    )
    assert r.status_code == 200
    body = r.json()

    # StandardResponse wraps data at body["data"]
    assert "data" in body, (
        f"StandardResponse 'data' key missing. Got keys: {list(body.keys())}"
    )
    assert isinstance(body["data"], list)
    # meta may carry total
    meta = body.get("meta") or {}
    if "total" in meta:
        assert isinstance(meta["total"], int) and meta["total"] >= 0


@pytest.mark.asyncio
async def test_not_found_returns_structured_error(async_client, admin_auth_headers):
    """GET /trips/99999999 must return 404 with a structured error body."""
    r = await async_client.get("/api/v1/trips/99999999", headers=admin_auth_headers)
    assert r.status_code == 404
    body = r.json()
    # Accept either FastAPI default "detail" or custom "error" envelope
    has_error_key = "error" in body or "detail" in body
    assert has_error_key, f"404 response must have 'error' or 'detail'. Got: {body}"
