import uuid
from datetime import date

import pytest


@pytest.mark.asyncio
class TestAuthentication:
    """Authentication checks."""

    async def test_protected_endpoint_without_token(self, async_client):
        response = await async_client.get("/api/v1/users/")
        assert response.status_code == 401

    async def test_invalid_token_rejected(self, async_client):
        response = await async_client.get(
            "/api/v1/users/", headers={"Authorization": "Bearer invalid_token"}
        )
        assert response.status_code == 401


@pytest.mark.asyncio
class TestInputValidation:
    """Input validation checks."""

    async def test_negative_id_rejected(self, async_client, auth_headers):
        response = await async_client.get("/api/v1/vehicles/-1", headers=auth_headers)
        assert response.status_code in [404, 422]

    async def test_sql_injection_attempt(self, async_client, auth_headers):
        response = await async_client.get(
            "/api/v1/vehicles/1;DROP TABLE users", headers=auth_headers
        )
        assert response.status_code in [404, 422]


@pytest.mark.asyncio
class TestRateLimiting:
    """Rate limiting checks."""

    async def _create_trip_dependencies(self, async_client, auth_headers):
        suffix = uuid.uuid4().hex[:6].upper()
        plate_number = int(suffix[-4:], 16) % 9000 + 1000
        vehicle_payload = {
            "plaka": f"34 AB {plate_number}",
            "marka": "Test",
            "model": "Tir",
            "yil": 2023,
            "tank_kapasitesi": 600,
            "hedef_tuketim": 30.0,
            "aktif": True,
        }
        resp_vehicle = await async_client.post(
            "/api/v1/vehicles/", json=vehicle_payload, headers=auth_headers
        )
        assert resp_vehicle.status_code == 201, resp_vehicle.text
        vehicle_id = resp_vehicle.json()["id"]

        driver_payload = {
            "ad_soyad": f"Hizli Sofor {suffix}",
            "telefon": "05551112233",
            "ise_baslama": date.today().isoformat(),
            "ehliyet_sinifi": "E",
            "aktif": True,
        }
        resp_driver = await async_client.post(
            "/api/v1/drivers/", json=driver_payload, headers=auth_headers
        )
        assert resp_driver.status_code == 201, resp_driver.text
        driver_id = resp_driver.json()["id"]

        route_payload = {
            "cikis_yeri": "Istanbul",
            "varis_yeri": "Ankara",
            "mesafe_km": 450.0,
            "tahmini_sure_saat": 5.0,
            "zorluk": "Normal",
            "notlar": f"Rate limit route {suffix}",
        }
        resp_route = await async_client.post(
            "/api/v1/locations/", json=route_payload, headers=auth_headers
        )
        assert resp_route.status_code == 201, resp_route.text
        route_id = resp_route.json()["id"]

        return vehicle_id, driver_id, route_id

    async def test_rate_limit_enforced_trips(self, async_client, auth_headers):
        vehicle_id, driver_id, route_id = await self._create_trip_dependencies(
            async_client, auth_headers
        )

        payload = {
            "arac_id": vehicle_id,
            "sofor_id": driver_id,
            "guzergah_id": route_id,
            "mesafe_km": 100,
            "tuketim": 30.0,
            "tarih": "2026-01-01",
            "cikis_yeri": "A",
            "varis_yeri": "B",
        }

        responses = []
        for _ in range(10):
            resp = await async_client.post(
                "/api/v1/trips/", json=payload, headers=auth_headers
            )
            responses.append(resp.status_code)

        assert 429 in responses

    async def test_rate_limit_enforced_for_invalid_trip_payload(
        self, async_client, auth_headers
    ):
        vehicle_id, driver_id, _route_id = await self._create_trip_dependencies(
            async_client, auth_headers
        )

        invalid_payload = {
            "arac_id": vehicle_id,
            "sofor_id": driver_id,
            "mesafe_km": 100,
            "tuketim": 30.0,
            "tarih": "2026-01-01",
            "cikis_yeri": "A",
            "varis_yeri": "B",
        }

        responses = []
        for _ in range(10):
            resp = await async_client.post(
                "/api/v1/trips/", json=invalid_payload, headers=auth_headers
            )
            responses.append(resp.status_code)

        assert 422 in responses
        assert 429 in responses


@pytest.mark.asyncio
class TestPagination:
    """Pagination checks."""

    async def test_max_limit_enforced(self, async_client, auth_headers):
        response = await async_client.get(
            "/api/v1/vehicles/?limit=1000000", headers=auth_headers
        )
        assert response.status_code == 422


@pytest.mark.asyncio
class TestFileUploadDoS:
    """File upload DoS checks."""

    async def test_large_file_upload_rejected(self, async_client, auth_headers):
        large_content = b"x" * (10 * 1024 * 1024 + 10)

        files = {
            "file": (
                "large.xlsx",
                large_content,
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        }

        response = await async_client.post(
            "/api/v1/vehicles/upload", files=files, headers=auth_headers
        )

        data = response.json()
        assert response.status_code == 413
        assert "error" in data
        assert "Dosya boyutu 10MB" in data["error"]["message"]
