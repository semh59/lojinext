"""Integration test for POST /maintenance/report-breakdown (operator arıza)."""

import uuid
from datetime import date, timedelta

import pytest


@pytest.mark.integration
@pytest.mark.asyncio
class TestReportBreakdown:
    async def _create_vehicle(self, async_client, admin_auth_headers) -> int:
        plaka = f"34 BD {int(uuid.uuid4().hex[:4], 16) % 10000:04d}"
        resp = await async_client.post(
            "/api/v1/vehicles/",
            json={
                "plaka": plaka,
                "marka": "MAN",
                "model": "TGX",
                "yil": 2020,
                "tank_kapasitesi": 600,
                "hedef_tuketim": 30.0,
                "aktif": True,
                "muayene_tarihi": (date.today() + timedelta(days=200)).isoformat(),
            },
            headers=admin_auth_headers,
        )
        assert resp.status_code == 201, resp.text
        return int(resp.json()["id"])

    async def test_report_breakdown_creates_open_record(
        self, async_client, admin_auth_headers
    ):
        arac_id = await self._create_vehicle(async_client, admin_auth_headers)
        resp = await async_client.post(
            "/api/v1/maintenance/report-breakdown",
            json={
                "arac_id": arac_id,
                "bakim_tipi": "ARIZA",
                "detaylar": "Fren sesi geliyor",
                "km_bilgisi": 152000,
            },
            headers=admin_auth_headers,
        )
        assert resp.status_code == 201, resp.text
        body = resp.json()
        assert body["arac_id"] == arac_id
        assert body["bakim_tipi"] == "ARIZA"
        assert body["tamamlandi"] is False  # açık kayıt

    async def test_periyodik_rejected(self, async_client, admin_auth_headers):
        arac_id = await self._create_vehicle(async_client, admin_auth_headers)
        resp = await async_client.post(
            "/api/v1/maintenance/report-breakdown",
            json={"arac_id": arac_id, "bakim_tipi": "PERIYODIK", "detaylar": "x"},
            headers=admin_auth_headers,
        )
        # Sadece ARIZA/ACIL kabul edilir.
        assert resp.status_code == 422, resp.text

    async def test_unknown_vehicle_404(self, async_client, admin_auth_headers):
        resp = await async_client.post(
            "/api/v1/maintenance/report-breakdown",
            json={"arac_id": 99999999, "bakim_tipi": "ACIL", "detaylar": "x"},
            headers=admin_auth_headers,
        )
        assert resp.status_code == 404, resp.text
