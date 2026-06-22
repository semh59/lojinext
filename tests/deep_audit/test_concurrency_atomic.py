import asyncio
from datetime import date

import httpx
import pytest

# Configuration


def _unwrap_items(payload):
    if isinstance(payload, dict) and "data" in payload:
        payload = payload["data"]
    if isinstance(payload, dict) and "items" in payload:
        return payload["items"]
    return payload


@pytest.mark.asyncio
async def test_race_condition_add_fuel(async_client, async_superuser_token_headers):
    """
    Concurrency Test: 10 users adding fuel.
    """
    headers = async_superuser_token_headers

    # 1. Get active vehicle
    arac_res = await async_client.get(
        "/api/v1/vehicles/", headers=headers, params={"aktif_only": True}
    )
    assert arac_res.status_code == 200, f"Get vehicles failed: {arac_res.text}"
    araclar = _unwrap_items(arac_res.json()) or []
    if not araclar:
        # Create a vehicle if none exists
        v_res = await async_client.post(
            "/api/v1/vehicles/",
            headers=headers,
            json={
                "plaka": "34 CC 1001",
                "marka": "Concurrent",
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
        target_arac_id = araclar[0]["id"]

    # 2. Concurrent Requests
    concurrent_users = 10
    base_km = 600000

    tasks = []
    for i in range(concurrent_users):
        payload = {
            "tarih": date.today().isoformat(),
            "arac_id": target_arac_id,
            "istasyon": f"Conc Station {i}",
            "fiyat_tl": 40.0,
            "litre": 10.0,
            "km_sayac": base_km + (i * 100),
            "fis_no": f"RACE-{i}",
            "depo_durumu": "Full",
        }
        tasks.append(async_client.post("/api/v1/fuel/", json=payload, headers=headers))

    responses = await asyncio.gather(*tasks, return_exceptions=True)

    success_count = sum(
        1
        for r in responses
        if isinstance(r, httpx.Response) and r.status_code in [200, 201]
    )
    fail_count = sum(
        1
        for r in responses
        if isinstance(r, httpx.Response) and r.status_code not in [200, 201]
    )

    print(f"Concurrency Result: {success_count} Success, {fail_count} Failed")
    # Rate limiter (2 req/s) kaçını geçirirse geçirsin, en az 1 başarılı olmalı
    # ve sunucu hiç 5xx döndürmemeli (rate-limited = 429, not 500).
    assert success_count > 0, "Hiçbir eşzamanlı istek başarılı olmadı"
    server_errors = sum(
        1
        for r in responses
        if isinstance(r, Exception)
        or (hasattr(r, "status_code") and r.status_code >= 500)
    )
    assert server_errors == 0, f"{server_errors} sunucu hatası (5xx) oluştu"
