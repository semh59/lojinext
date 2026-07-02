"""Integration test for GET /trailers/inspection-alerts (dorse muayene)."""

import uuid
from datetime import date, timedelta

import pytest


@pytest.mark.integration
@pytest.mark.asyncio
class TestDorseInspectionAlerts:
    async def _create_dorse(
        self, async_client, admin_auth_headers, *, muayene_tarihi: date
    ) -> int:
        plaka = f"34 DI {int(uuid.uuid4().hex[:4], 16) % 10000:04d}"
        resp = await async_client.post(
            "/api/v1/trailers/",
            json={
                "plaka": plaka,
                "marka": "Kassbohrer",
                "tipi": "Tenteli",
                "yil": 2021,
                "bos_agirlik_kg": 7000.0,
                "maks_yuk_kapasitesi_kg": 27000,
                "lastik_sayisi": 6,
                "muayene_tarihi": muayene_tarihi.isoformat(),
            },
            headers=admin_auth_headers,
        )
        assert resp.status_code == 201, resp.text
        # trailers POST returns a StandardResponse envelope: {data: {...}, meta}
        return int(resp.json()["data"]["id"])

    async def test_expiring_within_30_days(self, async_client, admin_auth_headers):
        future = date.today() + timedelta(days=15)
        dorse_id = await self._create_dorse(
            async_client, admin_auth_headers, muayene_tarihi=future
        )
        resp = await async_client.get(
            "/api/v1/trailers/inspection-alerts?within_days=30",
            headers=admin_auth_headers,
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        ids_expiring = [d["id"] for d in body["expiring"]]
        assert dorse_id in ids_expiring
        assert dorse_id not in [d["id"] for d in body["overdue"]]
        item = next(d for d in body["expiring"] if d["id"] == dorse_id)
        assert item["tipi"] == "Tenteli"
        assert 13 <= int(item["days_remaining"]) <= 17

    async def test_overdue(self, async_client, admin_auth_headers):
        past = date.today() - timedelta(days=10)
        dorse_id = await self._create_dorse(
            async_client, admin_auth_headers, muayene_tarihi=past
        )
        resp = await async_client.get(
            "/api/v1/trailers/inspection-alerts?within_days=30",
            headers=admin_auth_headers,
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert dorse_id in [d["id"] for d in body["overdue"]]
        item = next(d for d in body["overdue"] if d["id"] == dorse_id)
        assert int(item["days_remaining"]) < 0

    async def test_far_future_excluded(self, async_client, admin_auth_headers):
        far_future = date.today() + timedelta(days=120)
        dorse_id = await self._create_dorse(
            async_client, admin_auth_headers, muayene_tarihi=far_future
        )
        resp = await async_client.get(
            "/api/v1/trailers/inspection-alerts?within_days=30",
            headers=admin_auth_headers,
        )
        assert resp.status_code == 200
        all_ids = [d["id"] for d in resp.json()["expiring"]] + [
            d["id"] for d in resp.json()["overdue"]
        ]
        assert dorse_id not in all_ids


@pytest.mark.integration
@pytest.mark.asyncio
class TestDorseFleetStats:
    """2026-07-02 prod-grade denetimi P2 (Tier A madde 6): `GET /trailers/fleet-stats`
    `vehicles.py`'nin neredeyse birebir kopyası ama muayene uyarı sayısını hiç
    hesaplamıyordu (sadece total/active) — dashboard'da dorse muayene uyarı
    sayısı hiç görünmüyordu, gerçek veri kaybı."""

    async def _create_dorse(
        self, async_client, admin_auth_headers, *, muayene_tarihi: date
    ) -> int:
        plaka = f"34 FS {int(uuid.uuid4().hex[:4], 16) % 10000:04d}"
        resp = await async_client.post(
            "/api/v1/trailers/",
            json={
                "plaka": plaka,
                "marka": "Kassbohrer",
                "tipi": "Tenteli",
                "yil": 2021,
                "bos_agirlik_kg": 7000.0,
                "maks_yuk_kapasitesi_kg": 27000,
                "lastik_sayisi": 6,
                "muayene_tarihi": muayene_tarihi.isoformat(),
            },
            headers=admin_auth_headers,
        )
        assert resp.status_code == 201, resp.text
        return int(resp.json()["data"]["id"])

    async def test_fleet_stats_includes_inspection_counts(
        self, async_client, admin_auth_headers
    ):
        await self._create_dorse(
            async_client,
            admin_auth_headers,
            muayene_tarihi=date.today() + timedelta(days=15),
        )
        await self._create_dorse(
            async_client,
            admin_auth_headers,
            muayene_tarihi=date.today() - timedelta(days=10),
        )

        resp = await async_client.get(
            "/api/v1/trailers/fleet-stats", headers=admin_auth_headers
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert "inspection_expiring" in body, (
            f"fleet-stats yanıtı 'inspection_expiring' içermiyor: {body!r} — "
            "vehicles.py'nin fleet-stats'ı bu alanı zaten döndürüyor."
        )
        assert "inspection_overdue" in body, (
            f"fleet-stats yanıtı 'inspection_overdue' içermiyor: {body!r}"
        )
        assert body["inspection_expiring"] >= 1
        assert body["inspection_overdue"] >= 1
