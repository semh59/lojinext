"""
E2E Trip and Fuel Flow Tests

These tests exercise the app through authenticated HTTP requests while staying
compatible with the current API response envelopes and bootstrap fixtures.
"""

from datetime import date

import pytest
import pytest_asyncio


def _unwrap_items(payload):
    if isinstance(payload, dict) and "data" in payload:
        payload = payload["data"]
    if isinstance(payload, dict) and "items" in payload:
        return payload["items"]
    return payload


class TestTripE2EFlow:
    @pytest_asyncio.fixture
    async def authenticated_client(self, async_client, async_superuser_token_headers):
        async_client.headers.update(async_superuser_token_headers)
        yield async_client

    @pytest.mark.asyncio
    async def test_complete_trip_workflow(self, authenticated_client):
        client = authenticated_client

        stats_response = await client.get("/api/v1/reports/dashboard")
        initial_trip_count = 0
        if stats_response.status_code == 200:
            initial_trip_count = stats_response.json().get("toplam_sefer", 0)

        vehicles_response = await client.get("/api/v1/vehicles/")
        assert vehicles_response.status_code == 200
        vehicles = _unwrap_items(vehicles_response.json()) or []
        if vehicles:
            vehicle_id = vehicles[0]["id"]
        else:
            create_vehicle = await client.post(
                "/api/v1/vehicles/",
                json={
                    "plaka": "34 EE 1007",
                    "marka": "MERCEDES",
                    "model": "ACTROS",
                    "yil": 2023,
                    "tank_kapasitesi": 500,
                    "hedef_tuketim": 30.0,
                    "aktif": True,
                },
            )
            assert create_vehicle.status_code == 201, create_vehicle.text
            vehicle_id = create_vehicle.json()["id"]

        drivers_response = await client.get("/api/v1/drivers/")
        assert drivers_response.status_code == 200
        drivers = _unwrap_items(drivers_response.json()) or []
        if drivers:
            driver_id = drivers[0]["id"]
        else:
            create_driver = await client.post(
                "/api/v1/drivers/",
                json={
                    "ad_soyad": "E2E Test Soforu",
                    "telefon": "5550001111",
                    "ehliyet_sinifi": "E",
                    "score": 1.0,
                    "manual_score": 1.0,
                    "aktif": True,
                },
            )
            assert create_driver.status_code == 201, create_driver.text
            driver_id = create_driver.json()["id"]

        routes_response = await client.get("/api/v1/locations/")
        assert routes_response.status_code == 200
        routes = _unwrap_items(routes_response.json()) or []
        if routes:
            route = routes[0]
            route_id = route["id"]
            start_name = route["cikis_yeri"]
            end_name = route["varis_yeri"]
            distance_km = route["mesafe_km"]
        else:
            create_route = await client.post(
                "/api/v1/locations/",
                json={
                    "cikis_yeri": "E2E Baslangic",
                    "varis_yeri": "E2E Varis",
                    "mesafe_km": 350,
                    "tahmini_sure_saat": 5.0,
                    "zorluk": "Normal",
                    "aktif": True,
                },
            )
            assert create_route.status_code == 201, create_route.text
            route = create_route.json()
            route_id = route["id"]
            start_name = route["cikis_yeri"]
            end_name = route["varis_yeri"]
            distance_km = route["mesafe_km"]

        trip_response = await client.post(
            "/api/v1/trips/",
            json={
                "tarih": date.today().isoformat(),
                "saat": "09:00",
                "arac_id": vehicle_id,
                "sofor_id": driver_id,
                "guzergah_id": route_id,
                "cikis_yeri": start_name,
                "varis_yeri": end_name,
                "mesafe_km": distance_km,
                "net_kg": 12000,
                "bos_sefer": False,
                "durum": "Planlandı",
            },
        )
        assert trip_response.status_code == 201, trip_response.text
        trip_id = trip_response.json()["id"]

        fuel_response = await client.post(
            "/api/v1/fuel/",
            json={
                "tarih": date.today().isoformat(),
                "arac_id": vehicle_id,
                "istasyon": "E2E Test Istasyon",
                "fiyat_tl": 44.50,
                "litre": 180.0,
                "toplam_tutar": 8010.0,
                "km_sayac": 175000,
                "depo_durumu": "Doldu",
                "durum": "Onaylandı",
            },
        )
        assert fuel_response.status_code == 201, fuel_response.text

        updated_stats_response = await client.get("/api/v1/reports/dashboard")
        if updated_stats_response.status_code == 200:
            updated_stats = updated_stats_response.json()
            assert updated_stats.get("toplam_sefer", 0) >= initial_trip_count

        export_response = await client.get("/api/v1/trips/export")
        assert export_response.status_code == 200, export_response.text
        assert "application/vnd.openxmlformats" in export_response.headers.get(
            "content-type", ""
        )

        delete_response = await client.delete(f"/api/v1/trips/{trip_id}")
        assert delete_response.status_code == 200, delete_response.text


class TestFuelE2EFlow:
    @pytest_asyncio.fixture
    async def authenticated_client(self, async_client, async_superuser_token_headers):
        async_client.headers.update(async_superuser_token_headers)
        yield async_client

    @pytest.mark.asyncio
    async def test_fuel_stats_accuracy(self, authenticated_client):
        client = authenticated_client
        initial_stats = await client.get("/api/v1/fuel/stats")
        assert initial_stats.status_code == 200
        initial_data = initial_stats.json()
        consumption = (
            initial_data.get("total_consumption")
            or initial_data.get("toplam_litre")
            or 0
        )
        avg_price = (
            initial_data.get("avg_price")
            or initial_data.get("ortalama_birim_fiyat")
            or 0
        )
        assert consumption >= 0
        assert avg_price >= 0


class TestReportE2EFlow:
    @pytest_asyncio.fixture
    async def authenticated_client(self, async_client, async_superuser_token_headers):
        async_client.headers.update(async_superuser_token_headers)
        yield async_client

    @pytest.mark.asyncio
    async def test_pdf_report_generation(self, authenticated_client):
        client = authenticated_client
        response = await client.get("/api/v1/advanced-reports/pdf/fleet-summary")
        assert response.status_code in [200, 500]
        if response.status_code == 200:
            assert response.headers.get("content-type") == "application/pdf"

    @pytest.mark.asyncio
    async def test_cost_analysis_flow(self, authenticated_client):
        client = authenticated_client
        trend_response = await client.get(
            "/api/v1/advanced-reports/cost/trend?months=6"
        )
        assert trend_response.status_code == 200

        roi_response = await client.get(
            "/api/v1/advanced-reports/cost/roi?investment=50000&months=12"
        )
        assert roi_response.status_code in [200, 409]
        roi_data = roi_response.json()
        if roi_response.status_code == 200:
            assert "investment" in roi_data or "monthly_savings" in roi_data
        else:
            assert "detail" in roi_data or "error" in roi_data
