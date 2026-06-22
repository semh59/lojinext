"""Integration test for GET /vehicles/inspection-alerts."""

import uuid
from datetime import date, timedelta

import pytest


@pytest.mark.integration
@pytest.mark.asyncio
class TestInspectionAlerts:
    async def _create_vehicle(
        self, async_client, admin_auth_headers, *, muayene_tarihi: date
    ) -> int:
        suffix = uuid.uuid4().hex[:4].upper()
        plaka = f"34 IN {int(uuid.uuid4().hex[:4], 16) % 10000:04d}"
        resp = await async_client.post(
            "/api/v1/vehicles/",
            json={
                "plaka": plaka,
                "marka": "Volvo",
                "model": f"FH16-{suffix}",
                "yil": 2022,
                "tank_kapasitesi": 600,
                "hedef_tuketim": 31.0,
                "aktif": True,
                "muayene_tarihi": muayene_tarihi.isoformat(),
            },
            headers=admin_auth_headers,
        )
        assert resp.status_code == 201, resp.text
        return int(resp.json()["id"])

    async def test_expiring_within_30_days(self, async_client, admin_auth_headers):
        future = date.today() + timedelta(days=15)
        vehicle_id = await self._create_vehicle(
            async_client, admin_auth_headers, muayene_tarihi=future
        )
        resp = await async_client.get(
            "/api/v1/vehicles/inspection-alerts?within_days=30",
            headers=admin_auth_headers,
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        ids_expiring = [v["id"] for v in body["expiring"]]
        ids_overdue = [v["id"] for v in body["overdue"]]
        assert vehicle_id in ids_expiring
        assert vehicle_id not in ids_overdue
        # days_remaining yaklaşıkça +15
        item = next(v for v in body["expiring"] if v["id"] == vehicle_id)
        assert 13 <= int(item["days_remaining"]) <= 17

    async def test_overdue(self, async_client, admin_auth_headers):
        past = date.today() - timedelta(days=10)
        vehicle_id = await self._create_vehicle(
            async_client, admin_auth_headers, muayene_tarihi=past
        )
        resp = await async_client.get(
            "/api/v1/vehicles/inspection-alerts?within_days=30",
            headers=admin_auth_headers,
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        ids_overdue = [v["id"] for v in body["overdue"]]
        assert vehicle_id in ids_overdue
        item = next(v for v in body["overdue"] if v["id"] == vehicle_id)
        assert int(item["days_remaining"]) < 0

    async def test_far_future_excluded(self, async_client, admin_auth_headers):
        far_future = date.today() + timedelta(days=120)
        vehicle_id = await self._create_vehicle(
            async_client, admin_auth_headers, muayene_tarihi=far_future
        )
        resp = await async_client.get(
            "/api/v1/vehicles/inspection-alerts?within_days=30",
            headers=admin_auth_headers,
        )
        assert resp.status_code == 200
        all_ids = [v["id"] for v in resp.json()["expiring"]] + [
            v["id"] for v in resp.json()["overdue"]
        ]
        assert vehicle_id not in all_ids
