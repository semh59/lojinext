import pytest


@pytest.mark.asyncio
class TestReportsAPI:
    """Reports API Integration Tests"""

    async def test_get_dashboard_unauthorized(self, async_client):
        """Auth olmadan erişim hatası"""
        response = await async_client.get("/api/v1/reports/dashboard")
        assert response.status_code == 401

    async def test_get_dashboard_success(self, async_client, auth_headers):
        """Başarılı dashboard çekimi"""
        response = await async_client.get(
            "/api/v1/reports/dashboard", headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()

        # Beklenen alanlar
        assert "toplam_sefer" in data
        assert "trends" in data
        assert "sefer" in data["trends"]

    async def test_get_consumption_trend_success(self, async_client, auth_headers):
        """Başarılı tüketim trendi çekimi"""
        response = await async_client.get(
            "/api/v1/reports/consumption-trend", headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()

        assert isinstance(data, list)
        # Veri varsa format kontrolü
        if len(data) > 0:
            assert "month" in data[0]
            assert "consumption" in data[0]
