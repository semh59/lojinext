"""
Layer 3 — Business Lifecycle
Full TIR lifecycle: vehicle → driver → location → trip → fuel →
anomaly dashboard → report → soft-delete. Cleanup in finally block.
"""

import uuid
from datetime import date

import pytest

pytestmark = pytest.mark.integration


@pytest.mark.asyncio
async def test_full_tir_lifecycle(async_client, admin_auth_headers):
    """
    Sequential lifecycle — 9 steps, each depends on the previous output.
    Cleanup runs in finally even on failure.

    DELETE /trips/{id} returns 200 + {"soft_deleted": True} (not 204).
    Fuel is linked to arac_id, not sefer_id.
    Anomaly endpoint: GET /anomalies/fleet/insights?days=7
    """
    unique = uuid.uuid4().hex[:6].upper()
    num = int(uuid.uuid4().hex[:4], 16) % 9000 + 1000
    arac_id = sofor_id = guzergah_id = sefer_id = yakit_id = None

    try:
        # ── Step 1: Vehicle ──────────────────────────────────────────────────
        r1 = await async_client.post(
            "/api/v1/vehicles/",
            json={
                "plaka": f"06 LC {num}",
                "marka": "Mercedes",
                "model": "Actros",
                "yil": 2023,
                "tank_kapasitesi": 700,
                "hedef_tuketim": 31.5,
                "aktif": True,
            },
            headers=admin_auth_headers,
        )
        assert r1.status_code == 201, f"[Step 1] Vehicle create failed: {r1.text}"
        arac_id = r1.json()["id"]
        assert isinstance(arac_id, int) and arac_id > 0

        # ── Step 2: Driver ───────────────────────────────────────────────────
        r2 = await async_client.post(
            "/api/v1/drivers/",
            json={
                "ad_soyad": f"Lifecycle Sofor {unique}",
                "ehliyet_sinifi": "E",
                "ise_baslama": date.today().isoformat(),
                "aktif": True,
            },
            headers=admin_auth_headers,
        )
        assert r2.status_code == 201, f"[Step 2] Driver create failed: {r2.text}"
        sofor_id = r2.json()["id"]
        assert isinstance(sofor_id, int) and sofor_id > 0

        # ── Step 3: Location ─────────────────────────────────────────────────
        r3 = await async_client.post(
            "/api/v1/locations/",
            json={
                "cikis_yeri": f"LC City {unique}",
                "varis_yeri": f"LC Dest {unique}",
                "mesafe_km": 450.0,
                "tahmini_sure_saat": 5.0,
                "zorluk": "Normal",
            },
            headers=admin_auth_headers,
        )
        assert r3.status_code == 201, f"[Step 3] Location create failed: {r3.text}"
        guzergah_id = r3.json()["id"]
        assert isinstance(guzergah_id, int) and guzergah_id > 0

        # ── Step 4: Trip ─────────────────────────────────────────────────────
        r4 = await async_client.post(
            "/api/v1/trips/",
            json={
                "tarih": date.today().isoformat(),
                "arac_id": arac_id,
                "sofor_id": sofor_id,
                "guzergah_id": guzergah_id,
                "cikis_yeri": f"LC City {unique}",
                "varis_yeri": f"LC Dest {unique}",
                "mesafe_km": 450.0,
                "net_kg": 0,
                "bos_sefer": True,
                "durum": "Planlandı",
            },
            headers=admin_auth_headers,
        )
        assert r4.status_code == 201, f"[Step 4] Trip create failed: {r4.text}"
        sefer_id = r4.json()["id"]
        assert isinstance(sefer_id, int) and sefer_id > 0
        # Cross-reference: IDs must match
        assert r4.json()["arac_id"] == arac_id, "[Step 4] arac_id mismatch"
        assert r4.json()["sofor_id"] == sofor_id, "[Step 4] sofor_id mismatch"

        # ── Step 5: Fuel (linked to arac_id, not sefer_id) ──────────────────
        r5 = await async_client.post(
            "/api/v1/fuel/",
            json={
                "tarih": date.today().isoformat(),
                "arac_id": arac_id,
                "litre": "180.00",
                "fiyat_tl": "43.00",
                "toplam_tutar": "7740.00",
                "km_sayac": 200000,
                "depo_durumu": "Dolu",
                "durum": "Bekliyor",
            },
            headers=admin_auth_headers,
        )
        assert r5.status_code == 201, f"[Step 5] Fuel create failed: {r5.text}"
        yakit_id = r5.json()["id"]
        assert isinstance(yakit_id, int) and yakit_id > 0
        assert r5.json()["arac_id"] == arac_id, "[Step 5] arac_id mismatch in fuel"

        # ── Step 6: Anomaly dashboard ─────────────────────────────────────────
        r6 = await async_client.get(
            "/api/v1/anomalies/fleet/insights?days=7",
            headers=admin_auth_headers,
        )
        assert r6.status_code == 200, f"[Step 6] Anomaly endpoint failed: {r6.text}"
        body6 = r6.json()
        assert isinstance(body6, dict), "[Step 6] Anomaly response must be a dict"
        # Must have status or data key — never an unhandled exception
        assert "status" in body6 or "data" in body6, (
            f"[Step 6] Unexpected anomaly shape: {body6}"
        )

        # ── Step 7: Dashboard report ─────────────────────────────────────────
        r7 = await async_client.get(
            "/api/v1/reports/dashboard",
            headers=admin_auth_headers,
        )
        assert r7.status_code == 200, f"[Step 7] Dashboard report failed: {r7.text}"
        body7 = r7.json()
        assert body7.get("toplam_sefer", -1) >= 0, "[Step 7] toplam_sefer must be >= 0"
        assert body7.get("aktif_arac", -1) >= 0, "[Step 7] aktif_arac must be >= 0"

        # ── Step 8: Soft-delete trip ──────────────────────────────────────────
        r8 = await async_client.delete(
            f"/api/v1/trips/{sefer_id}",
            headers=admin_auth_headers,
        )
        assert r8.status_code == 200, (
            f"[Step 8] Trip soft-delete must return 200, got {r8.status_code}: {r8.text}"
        )
        body8 = r8.json()
        assert body8.get("soft_deleted") is True, (
            f"[Step 8] soft_deleted must be True, got: {body8}"
        )

        # ── Step 9: Verify 404 after soft-delete ──────────────────────────────
        r9 = await async_client.get(
            f"/api/v1/trips/{sefer_id}",
            headers=admin_auth_headers,
        )
        assert r9.status_code == 404, (
            f"[Step 9] Soft-deleted trip must return 404, got {r9.status_code}"
        )

    finally:
        # ── Cleanup (best-effort) ─────────────────────────────────────────────
        if yakit_id:
            await async_client.delete(
                f"/api/v1/fuel/{yakit_id}", headers=admin_auth_headers
            )
        if guzergah_id:
            await async_client.delete(
                f"/api/v1/locations/{guzergah_id}", headers=admin_auth_headers
            )
        if sofor_id:
            await async_client.delete(
                f"/api/v1/drivers/{sofor_id}", headers=admin_auth_headers
            )
        if arac_id:
            await async_client.delete(
                f"/api/v1/vehicles/{arac_id}", headers=admin_auth_headers
            )
