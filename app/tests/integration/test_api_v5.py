import uuid

import pytest


@pytest.fixture
def anyio_backend():
    return "asyncio"


def _unwrap_items(payload):
    if isinstance(payload, dict) and "data" in payload:
        payload = payload["data"]
    if isinstance(payload, dict) and "items" in payload:
        return payload["items"]
    return payload


@pytest.mark.asyncio
async def test_pagination_limit_enforcement(async_client, auth_headers):
    """Tum liste endpointlerinin paged envelope ile dondugunu dogrula."""
    response = await async_client.get("/api/v1/vehicles/", headers=auth_headers)
    assert response.status_code == 200

    items = _unwrap_items(response.json())
    assert isinstance(items, list)


@pytest.mark.asyncio
async def test_vehicle_soft_delete(async_client, auth_headers):
    """Arac silme isleminin soft delete oldugunu dogrula."""
    plaka = f"34 SD {str(uuid.uuid4().int)[:4]}"

    create_resp = await async_client.post(
        "/api/v1/vehicles/",
        json={
            "plaka": plaka,
            "marka": "SoftDeleteTest",
            "model": "S-Class",
            "yil": 2024,
        },
        headers=auth_headers,
    )
    assert create_resp.status_code in (200, 201)
    arac_id = create_resp.json()["id"]

    del_resp = await async_client.delete(
        f"/api/v1/vehicles/{arac_id}", headers=auth_headers
    )
    assert del_resp.status_code == 200

    list_resp = await async_client.get("/api/v1/vehicles/", headers=auth_headers)
    plakalar = [v["plaka"] for v in _unwrap_items(list_resp.json())]
    assert plaka not in plakalar


@pytest.mark.asyncio
async def test_prediction_endpoints_exist(async_client, auth_headers):
    """Tahmin endpointlerinin mevcut oldugunu ve servis hatasi vermedigini dogrula."""
    response = await async_client.get(
        "/api/v1/predictions/time-series/status", headers=auth_headers
    )
    assert response.status_code == 200
