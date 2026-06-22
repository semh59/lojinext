import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_api_create_location(async_client: AsyncClient, admin_auth_headers):
    """Admin yeni lokasyon olusturabilmeli."""
    payload = {
        "cikis_yeri": "Test City A",
        "varis_yeri": "Test City B",
        "mesafe_km": 120.5,
    }
    response = await async_client.post(
        "/api/v1/locations/", json=payload, headers=admin_auth_headers
    )
    assert response.status_code == 201
    data = response.json()
    assert data["cikis_yeri"] == "Test City A"
    assert "id" in data


@pytest.mark.asyncio
async def test_api_list_locations(async_client: AsyncClient, admin_auth_headers):
    """Lokasyonlar listelenebilmeli ve pagination calismali."""
    response = await async_client.get(
        "/api/v1/locations/?limit=5&skip=0", headers=admin_auth_headers
    )
    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    assert "total" in data
    assert isinstance(data["items"], list)


@pytest.mark.asyncio
async def test_api_get_route_info(async_client: AsyncClient, admin_auth_headers):
    """Koordinatlara gore rota bilgisi alma testi."""
    params = {
        "cikis_lat": 41.0,
        "cikis_lon": 29.0,
        "varis_lat": 40.0,
        "varis_lon": 32.0,
    }
    response = await async_client.get(
        "/api/v1/locations/route-info", params=params, headers=admin_auth_headers
    )
    assert response.status_code in [200, 400, 403, 503]


@pytest.mark.asyncio
async def test_api_unauthorized_access(async_client: AsyncClient):
    """Auth olmadan erisim basarisiz olmali."""
    response = await async_client.get("/api/v1/locations/")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_api_geocode_location(async_client: AsyncClient, admin_auth_headers):
    from app.api.deps import get_lokasyon_service
    from app.main import app

    class MockLokasyonService:
        async def geocode_query(self, q: str, limit: int = 5):
            assert q == "Hadimkoy Lojistik"
            assert limit == 5
            return [
                {
                    "lat": 41.07,
                    "lon": 28.54,
                    "label": "Hadimkoy Lojistik",
                    "source": "ors",
                }
            ]

    app.dependency_overrides[get_lokasyon_service] = lambda: MockLokasyonService()
    try:
        response = await async_client.get(
            "/api/v1/locations/geocode",
            params={"q": "Hadimkoy Lojistik"},
            headers=admin_auth_headers,
        )
    finally:
        app.dependency_overrides.pop(get_lokasyon_service, None)

    assert response.status_code == 200
    assert response.json()[0]["label"] == "Hadimkoy Lojistik"
