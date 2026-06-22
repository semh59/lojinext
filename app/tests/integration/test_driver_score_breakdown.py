"""Integration test for GET /drivers/{id}/score-breakdown."""

import uuid
from datetime import datetime, timezone

import pytest


@pytest.mark.integration
@pytest.mark.asyncio
class TestDriverScoreBreakdown:
    async def _create_driver(self, async_client, admin_auth_headers) -> int:
        suffix = uuid.uuid4().hex[:4].upper()
        resp = await async_client.post(
            "/api/v1/drivers/",
            json={
                "ad_soyad": f"Skor Pilot {suffix}",
                "telefon": "05550000111",
                "ise_baslama": datetime.now(timezone.utc).date().isoformat(),
                "ehliyet_sinifi": "E",
                "manual_score": 1.2,
                "aktif": True,
            },
            headers=admin_auth_headers,
        )
        assert resp.status_code == 201, resp.text
        return int(resp.json()["id"])

    async def test_returns_full_breakdown_for_driver_without_trips(
        self, async_client, admin_auth_headers
    ):
        driver_id = await self._create_driver(async_client, admin_auth_headers)
        resp = await async_client.get(
            f"/api/v1/drivers/{driver_id}/score-breakdown",
            headers=admin_auth_headers,
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()

        # Tüm alanlar dolu döner
        assert body["sofor_id"] == driver_id
        assert body["manual"] == pytest.approx(1.2, rel=1e-2)
        assert body["manual_weight"] == pytest.approx(0.4)
        assert body["auto_weight"] == pytest.approx(0.6)
        assert body["has_trips"] is False
        # Sefer yokken auto = manual fallback
        assert body["auto"] == pytest.approx(body["manual"], rel=1e-2)
        # Toplam: manual × 0.4 + auto × 0.6, has_trips False ise = manual
        assert body["total"] == pytest.approx(body["manual"], rel=1e-2)
        assert body["trip_count"] == 0

    async def test_404_for_unknown_driver(self, async_client, admin_auth_headers):
        resp = await async_client.get(
            "/api/v1/drivers/99999/score-breakdown",
            headers=admin_auth_headers,
        )
        assert resp.status_code == 404
