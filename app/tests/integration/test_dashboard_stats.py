"""Integration tests for /api/v1/reports/dashboard.

Verifies that the dashboard endpoint surfaces the previously-missing
`aktif_arac`, `aktif_sofor`, `bugun_sefer`, and `trends` fields rather
than the placeholder zeros that the legacy implementation returned.
"""

import uuid
from datetime import datetime, timezone

import pytest


@pytest.mark.integration
@pytest.mark.asyncio
class TestDashboardStats:
    async def _seed_minimal_fleet(self, async_client, admin_auth_headers) -> dict:
        """Create one active vehicle + one active driver + one trip dated today."""
        suffix = uuid.uuid4().hex[:4].upper()
        plaka = f"34 DS {int(uuid.uuid4().hex[:4], 16) % 10000:04d}"

        resp_arac = await async_client.post(
            "/api/v1/vehicles/",
            json={
                "plaka": plaka,
                "marka": "Volvo",
                "model": "FH16",
                "yil": 2022,
                "tank_kapasitesi": 600,
                "hedef_tuketim": 31.0,
                "aktif": True,
            },
            headers=admin_auth_headers,
        )
        assert resp_arac.status_code == 201, resp_arac.text
        arac_id = resp_arac.json()["id"]

        resp_sofor = await async_client.post(
            "/api/v1/drivers/",
            json={
                "ad_soyad": f"Dashboard Pilot {suffix}",
                "telefon": "05551112233",
                "ise_baslama": datetime.now(timezone.utc).date().isoformat(),
                "ehliyet_sinifi": "E",
                "aktif": True,
            },
            headers=admin_auth_headers,
        )
        assert resp_sofor.status_code == 201, resp_sofor.text
        sofor_id = resp_sofor.json()["id"]

        resp_loc = await async_client.post(
            "/api/v1/locations/",
            json={
                "cikis_yeri": "Istanbul",
                "varis_yeri": "Ankara",
                "mesafe_km": 450.0,
                "tahmini_sure_saat": 5.0,
                "zorluk": "Normal",
                "notlar": f"Dashboard rota {suffix}",
            },
            headers=admin_auth_headers,
        )
        assert resp_loc.status_code == 201, resp_loc.text
        lokasyon_id = resp_loc.json()["id"]

        resp_sefer = await async_client.post(
            "/api/v1/trips/",
            json={
                "tarih": datetime.now(timezone.utc).date().isoformat(),
                "arac_id": arac_id,
                "sofor_id": sofor_id,
                "guzergah_id": lokasyon_id,
                "cikis_yeri": "Istanbul",
                "varis_yeri": "Ankara",
                "mesafe_km": 450.0,
                "net_kg": 22000,
                "bos_sefer": False,
                "durum": "Planlandı",
            },
            headers=admin_auth_headers,
        )
        assert resp_sefer.status_code in (200, 201), resp_sefer.text

        return {"arac_id": arac_id, "sofor_id": sofor_id, "lokasyon_id": lokasyon_id}

    async def test_dashboard_returns_all_required_fields(
        self, async_client, admin_auth_headers
    ):
        await self._seed_minimal_fleet(async_client, admin_auth_headers)

        resp = await async_client.get(
            "/api/v1/reports/dashboard", headers=admin_auth_headers
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()

        # Required keys must be present (previously absent / always-zero defaults).
        for key in (
            "toplam_sefer",
            "toplam_km",
            "toplam_yakit",
            "filo_ortalama",
            "aktif_arac",
            "toplam_arac",
            "aktif_sofor",
            "bugun_sefer",
            "trends",
        ):
            assert key in data, f"Dashboard yanıtında {key!r} alanı yok"

        assert data["aktif_arac"] >= 1
        assert data["aktif_sofor"] >= 1
        assert data["bugun_sefer"] >= 1

        trends = data["trends"]
        assert isinstance(trends, dict)
        for trend_key in ("sefer", "km", "tuketim"):
            assert trend_key in trends
            assert isinstance(trends[trend_key], (int, float))

    async def test_dashboard_trends_default_to_zero_with_empty_history(
        self, async_client, admin_auth_headers
    ):
        """When there is no prior-month data the previous baseline is 0 and the
        trend helper must return 0% rather than divide-by-zero."""
        resp = await async_client.get(
            "/api/v1/reports/dashboard", headers=admin_auth_headers
        )
        assert resp.status_code == 200, resp.text
        trends = resp.json()["trends"]
        assert trends["sefer"] == 0.0
        assert trends["km"] == 0.0
        assert trends["tuketim"] == 0.0
