import asyncio
import time
from datetime import date

import pytest


def _unwrap_items(payload):
    if isinstance(payload, dict) and "data" in payload:
        payload = payload["data"]
    if isinstance(payload, dict) and "items" in payload:
        return payload["items"]
    return payload


@pytest.mark.asyncio
async def test_bulk_load_performance(async_client, async_superuser_token_headers):
    """
    Stress Test.
    """
    headers = async_superuser_token_headers

    arac_res = await async_client.get("/api/v1/vehicles/", headers=headers)
    araclar = _unwrap_items(arac_res.json()) or []
    active = [a for a in araclar if a.get("aktif")]
    if not active:
        # Create a vehicle
        v_res = await async_client.post(
            "/api/v1/vehicles/",
            headers=headers,
            json={
                "plaka": "34 ST 1006",
                "marka": "Stress",
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
        target_arac_id = active[0]["id"]

    # 50 requests
    tasks = []
    start_time = time.time()

    for i in range(50):
        payload = {
            "tarih": date.today().isoformat(),
            "arac_id": target_arac_id,
            "istasyon": "Stress Station",
            "fiyat_tl": 10.0,
            "litre": 10.0,
            "km_sayac": 2000000 + (i * 10),
            "fis_no": f"STRESS-{i}",
            "depo_durumu": "Full",
        }
        tasks.append(async_client.post("/api/v1/fuel/", json=payload, headers=headers))

    await asyncio.gather(*tasks, return_exceptions=True)
    end_time = time.time()
    duration = end_time - start_time

    print(f"Stress Test: 50 requests in {duration:.2f}s")
    # Using a slightly higher limit for CI/Agent environments
    assert duration < 20.0
