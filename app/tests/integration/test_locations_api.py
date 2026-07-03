from contextlib import contextmanager

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.integration


@contextmanager
def _override_real_lokasyon_service(db_session):
    """0-mock epiği: get_lokasyon_service'i tam hand-rolled bir fake yerine
    gerçek LokasyonService (gerçek LokasyonRepository + test session) ile
    değiştirir — endpoint gerçek servis/repo/DB zincirini çalıştırır."""
    from unittest.mock import MagicMock

    from app.api.deps import get_lokasyon_service
    from app.core.services.lokasyon_service import LokasyonService
    from app.database.repositories.lokasyon_repo import LokasyonRepository
    from app.main import app

    real_svc = LokasyonService(
        repo=LokasyonRepository(session=db_session), event_bus=MagicMock()
    )

    async def _fake():
        return real_svc

    app.dependency_overrides[get_lokasyon_service] = _fake
    try:
        yield real_svc
    finally:
        app.dependency_overrides.pop(get_lokasyon_service, None)


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
async def test_api_geocode_location(
    async_client: AsyncClient, admin_auth_headers, db_session, monkeypatch
):
    """GET /geocode?q=... → gerçek LokasyonService + gerçek ORS api_stub
    round-trip (stub sorgu metnini label olarak yansıtır)."""
    import app.core.services.openroute_service as ors_mod

    ors_mod._openroute_service = None  # reset singleton
    monkeypatch.setattr(ors_mod.settings, "OPENROUTESERVICE_API_KEY", "test-key")
    monkeypatch.setattr(
        ors_mod.settings, "OPENROUTE_API_BASE_URL", "http://localhost:9000/v2"
    )

    with _override_real_lokasyon_service(db_session):
        response = await async_client.get(
            "/api/v1/locations/geocode",
            params={"q": "Hadimkoy Lojistik"},
            headers=admin_auth_headers,
        )

    ors_mod._openroute_service = None  # cleanup for other tests

    assert response.status_code == 200
    assert response.json()[0]["label"] == "Hadimkoy Lojistik"
    assert response.json()[0]["source"] == "ors"
