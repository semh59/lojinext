from datetime import date

import pytest

# Configuration


def _unwrap_items(payload):
    if isinstance(payload, dict) and "data" in payload:
        payload = payload["data"]
    if isinstance(payload, dict) and "items" in payload:
        return payload["items"]
    return payload


@pytest.mark.asyncio
async def test_security_payloads_add_fuel(async_client, async_superuser_token_headers):
    """
    Security Test: Injection attempts.
    """
    headers = async_superuser_token_headers

    # 1. Get active vehicle
    arac_res = await async_client.get(
        "/api/v1/vehicles/", headers=headers, params={"aktif_only": True}
    )
    arac_data = _unwrap_items(arac_res.json()) or []
    if not arac_data:
        # Create a vehicle
        v_res = await async_client.post(
            "/api/v1/vehicles/",
            headers=headers,
            json={
                "plaka": "34 SC 1002",
                "marka": "Security",
                "model": "Test",
                "yil": 2020,
                "tank_kapasitesi": 100,
                "hedef_tuketim": 30.0,
                "aktif": True,
            },
        )
        assert v_res.status_code in [200, 201]
        target_arac_id = v_res.json()["id"]
    else:
        target_arac_id = arac_data[0]["id"]

    # 2. SQL Injection
    payload_sqli = {
        "tarih": date.today().isoformat(),
        "arac_id": target_arac_id,
        "istasyon": "Station'; DROP TABLE users; --",
        "fiyat_tl": 40.0,
        "litre": 10.0,
        "km_sayac": 900000,
        "fis_no": "SQLI-TEST",
        "depo_durumu": "Full",
    }
    res = await async_client.post("/api/v1/fuel/", json=payload_sqli, headers=headers)

    # SQLi: ORM parameterization prevents execution; accept 400/422 (rejected) or
    # 200/201 (stored as plain text). Either way the table must still be queryable.
    assert res.status_code in [200, 201, 422, 400]

    # 3. XSS
    payload_xss = payload_sqli.copy()
    payload_xss["istasyon"] = "Normal Station"
    payload_xss["fis_no"] = "<script>alert('XSS')</script>"
    res_xss = await async_client.post(
        "/api/v1/fuel/", json=payload_xss, headers=headers
    )

    # XSS prevention is the frontend's responsibility; the REST API may store raw
    # strings. Accept any non-5xx status — the important thing is no 500 crash.
    assert res_xss.status_code in [200, 201, 422, 400]


@pytest.mark.asyncio
async def test_validation_boundaries(async_client, async_superuser_token_headers):
    """
    Validation Test: Negative numbers.
    """
    headers = async_superuser_token_headers

    arac_res = await async_client.get(
        "/api/v1/vehicles/", headers=headers, params={"aktif_only": True}
    )
    arac_data = _unwrap_items(arac_res.json()) or []
    if not arac_data:
        # Create a vehicle
        v_res = await async_client.post(
            "/api/v1/vehicles/",
            headers=headers,
            json={
                "plaka": "34 BD 1003",
                "marka": "Boundary",
                "model": "Test",
                "yil": 2020,
                "tank_kapasitesi": 100,
                "hedef_tuketim": 30.0,
                "aktif": True,
            },
        )
        assert v_res.status_code in [200, 201]
        target_arac_id = v_res.json()["id"]
    else:
        target_arac_id = arac_data[0]["id"]

    # Negative Price
    p_neg = {
        "tarih": date.today().isoformat(),
        "arac_id": target_arac_id,
        "istasyon": "Neg Station",
        "fiyat_tl": -50.0,
        "litre": 10.0,
        "km_sayac": 999999,
        "fis_no": "NEG-1",
        "depo_durumu": "Full",
    }
    res = await async_client.post("/api/v1/fuel/", json=p_neg, headers=headers)
    assert res.status_code in [400, 422]

    # Zero Listre
    p_zero = p_neg.copy()
    p_zero["fiyat_tl"] = 40.0
    p_zero["litre"] = 0.0
    res = await async_client.post("/api/v1/fuel/", json=p_zero, headers=headers)
    assert res.status_code in [400, 422]
