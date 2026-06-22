"""Integration test for GET /drivers/{id}/route-profile."""

import uuid
from datetime import datetime, timezone

import pytest


@pytest.mark.integration
@pytest.mark.asyncio
class TestDriverRouteProfile:
    async def _create_driver(self, async_client, admin_auth_headers) -> int:
        suffix = uuid.uuid4().hex[:4].upper()
        resp = await async_client.post(
            "/api/v1/drivers/",
            json={
                "ad_soyad": f"Rota Pilot {suffix}",
                "telefon": "05550000222",
                "ise_baslama": datetime.now(timezone.utc).date().isoformat(),
                "ehliyet_sinifi": "E",
                "aktif": True,
            },
            headers=admin_auth_headers,
        )
        assert resp.status_code == 201, resp.text
        return int(resp.json()["id"])

    async def test_returns_all_four_route_types_with_zero_trips(
        self, async_client, admin_auth_headers
    ):
        """Yeni şoförün hiç seferi yok — endpoint 4 profil de döndürür,
        hepsi trip_count=0 ve best_route_type=None."""
        driver_id = await self._create_driver(async_client, admin_auth_headers)

        resp = await async_client.get(
            f"/api/v1/drivers/{driver_id}/route-profile",
            headers=admin_auth_headers,
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()

        assert body["sofor_id"] == driver_id
        assert body["best_route_type"] is None
        assert body["min_trips_for_best"] == 5
        assert isinstance(body["profiles"], list)
        assert len(body["profiles"]) == 4
        route_types = {p["route_type"] for p in body["profiles"]}
        assert route_types == {"highway_dominant", "mountain", "urban", "mixed"}
        for p in body["profiles"]:
            assert p["trip_count"] == 0
            assert p["avg_actual"] == 0
            assert p["avg_predicted"] == 0
            assert p["deviation_pct"] == 0
            assert isinstance(p["label"], str) and p["label"]

    async def test_404_for_unknown_driver(self, async_client, admin_auth_headers):
        resp = await async_client.get(
            "/api/v1/drivers/99999/route-profile",
            headers=admin_auth_headers,
        )
        assert resp.status_code == 404
