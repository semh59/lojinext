from datetime import date

import pytest


def _unwrap_items(payload):
    if isinstance(payload, dict) and "data" in payload:
        payload = payload["data"]
    if isinstance(payload, dict) and "items" in payload:
        return payload["items"]
    return payload


@pytest.mark.asyncio
async def test_ghost_writes(async_client, async_superuser_token_headers):
    """
    Consistency Test: Verify API response matches DB state.
    """
    headers = async_superuser_token_headers

    arac_res = await async_client.get(
        "/api/v1/vehicles/", headers=headers, params={"aktif_only": True}
    )
    arac_data = _unwrap_items(arac_res.json()) or []
    if not arac_data:
        # Create a vehicle if none exists
        v_res = await async_client.post(
            "/api/v1/vehicles/",
            headers=headers,
            json={
                "plaka": "34 IG 1004",
                "marka": "Integrity",
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

    # 1. Create Record
    payload = {
        "tarih": date.today().isoformat(),
        "arac_id": target_arac_id,
        "istasyon": "Ghost Check",
        "fiyat_tl": 42.0,
        "litre": 10.0,
        "toplam_tutar": 420.0,
        "km_sayac": 888888,
        "fis_no": "GHOST-1",
        "depo_durumu": "Doldu",
    }
    res = await async_client.post("/api/v1/fuel/", json=payload, headers=headers)
    assert res.status_code in [
        200,
        201,
    ], f"Creation failed: {res.status_code} {res.text}"
    created_id = res.json()["id"]

    # 2. Verify existence in list
    list_res = await async_client.get(
        f"/api/v1/fuel/?arac_id={target_arac_id}", headers=headers
    )
    yakit_list = _unwrap_items(list_res.json()) or []
    ids = [y["id"] for y in yakit_list]
    assert created_id in ids, (
        f"Ghost Write! ID {created_id} returned 200 OK but not found in list."
    )


@pytest.mark.asyncio
async def test_zombie_records(async_client, async_superuser_token_headers):
    """
    Zombie Test: Deleted record should not appear.
    """
    headers = async_superuser_token_headers

    arac_res = await async_client.get(
        "/api/v1/vehicles/", headers=headers, params={"aktif_only": True}
    )
    arac_data = _unwrap_items(arac_res.json()) or []
    if not arac_data:
        # Create a vehicle if none exists
        v_res = await async_client.post(
            "/api/v1/vehicles/",
            headers=headers,
            json={
                "plaka": "34 ZM 1005",
                "marka": "Zombie",
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

    # 1. Create record
    payload = {
        "tarih": date.today().isoformat(),
        "arac_id": target_arac_id,
        "istasyon": "Zombie Station",
        "fiyat_tl": 10.0,
        "litre": 100.0,
        "toplam_tutar": 1000.0,
        "km_sayac": 777777,
        "fis_no": "ZOMBIE-1",
        "depo_durumu": "Doldu",
    }
    create_res = await async_client.post("/api/v1/fuel/", json=payload, headers=headers)
    if create_res.status_code not in [200, 201]:
        pytest.skip(f"Creation failed for Zombie test: {create_res.text}")
    yakit_id = create_res.json()["id"]

    # 2. Delete Record
    del_res = await async_client.delete(f"/api/v1/fuel/{yakit_id}", headers=headers)
    assert del_res.status_code == 200, "Deletion failed"

    # 3. Get List AFTER delete
    list_res = await async_client.get(
        f"/api/v1/fuel/?arac_id={target_arac_id}", headers=headers
    )
    yakit_list = _unwrap_items(list_res.json()) or []
    ids = [y["id"] for y in yakit_list]

    assert yakit_id not in ids, f"Zombie Record! ID {yakit_id} still in list."
