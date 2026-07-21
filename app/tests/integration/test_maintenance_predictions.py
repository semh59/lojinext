"""Feature D.2 — Bakım tahmin endpoint'leri integration testleri."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest


async def _seed_arac(db_session, *, plaka: str = "34 ABC 123", yil: int = 2020) -> int:
    from v2.modules.fleet.public import AracORM as Arac

    row = Arac(
        plaka=plaka,
        marka="Test",
        model="X",
        yil=yil,
        tank_kapasitesi=600,
        hedef_tuketim=32.0,
        bos_agirlik_kg=8000.0,
        aktif=True,
        is_deleted=False,
    )
    db_session.add(row)
    await db_session.commit()
    await db_session.refresh(row)
    return int(row.id)


async def _seed_periyodik_bakim(
    db_session,
    *,
    arac_id: int,
    days_ago: int = 100,
    km_bilgisi: int = 200_000,
    tamamlandi: bool = True,
) -> int:
    from v2.modules.fleet.public import AracBakim, BakimTipi

    row = AracBakim(
        arac_id=arac_id,
        bakim_tipi=BakimTipi.PERIYODIK,
        km_bilgisi=km_bilgisi,
        bakim_tarihi=datetime.now(timezone.utc) - timedelta(days=days_ago),
        maliyet=1000.0,
        detaylar="Yağ + filtre",
        tamamlandi=tamamlandi,
    )
    db_session.add(row)
    await db_session.commit()
    await db_session.refresh(row)
    return int(row.id)


@pytest.mark.integration
@pytest.mark.asyncio
class TestPredictionsEndpoint:
    async def test_get_all_predictions_returns_list(
        self, async_client, admin_auth_headers, db_session
    ):
        await _seed_arac(db_session, plaka="34 AAA 11")
        resp = await async_client.get(
            "/api/v1/admin/maintenance/predictions", headers=admin_auth_headers
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert isinstance(body, list)
        # Yeni eklenen araç (bakım/sefer yok) → predictable=False
        plakas = [p["plaka"] for p in body]
        assert "34 AAA 11" in plakas
        item = next(p for p in body if p["plaka"] == "34 AAA 11")
        assert item["predictable"] is False
        assert any("Yeterli veri yok" in r for r in item["reasons"])

    async def test_get_predictions_503_when_flag_off(
        self, async_client, admin_auth_headers, monkeypatch
    ):
        monkeypatch.setattr("app.config.settings.MAINTENANCE_PREDICTOR_ENABLED", False)
        resp = await async_client.get(
            "/api/v1/admin/maintenance/predictions", headers=admin_auth_headers
        )
        assert resp.status_code == 503

    async def test_get_predictions_403_for_non_admin(
        self, async_client, normal_auth_headers
    ):
        resp = await async_client.get(
            "/api/v1/admin/maintenance/predictions", headers=normal_auth_headers
        )
        assert resp.status_code == 403

    async def test_get_prediction_for_arac_happy_path(
        self, async_client, admin_auth_headers, db_session
    ):
        aid = await _seed_arac(db_session, plaka="34 BBB 22")
        resp = await async_client.get(
            f"/api/v1/admin/maintenance/predictions/{aid}",
            headers=admin_auth_headers,
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["arac_id"] == aid
        assert body["plaka"] == "34 BBB 22"
        assert body["bakim_tipi"] == "PERIYODIK"

    async def test_get_prediction_for_arac_404(self, async_client, admin_auth_headers):
        resp = await async_client.get(
            "/api/v1/admin/maintenance/predictions/999999",
            headers=admin_auth_headers,
        )
        assert resp.status_code == 404


@pytest.mark.integration
@pytest.mark.asyncio
class TestIcsDownload:
    async def test_ics_returns_calendar_content(
        self, async_client, admin_auth_headers, db_session
    ):
        aid = await _seed_arac(db_session, plaka="06 ŞIK 99")
        bid = await _seed_periyodik_bakim(db_session, arac_id=aid)
        resp = await async_client.get(
            f"/api/v1/admin/maintenance/{bid}/ics", headers=admin_auth_headers
        )
        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith("text/calendar")
        assert "charset=utf-8" in resp.headers["content-type"].lower()
        assert "attachment" in resp.headers["content-disposition"]
        assert f"bakim-{bid}.ics" in resp.headers["content-disposition"]
        body = resp.content.decode("utf-8")
        assert "BEGIN:VCALENDAR" in body
        assert "END:VCALENDAR" in body
        # Türkçe karakter korunmalı
        assert "06 ŞIK 99" in body
        assert "PERIYODIK" in body

    async def test_ics_404_for_unknown_bakim(self, async_client, admin_auth_headers):
        resp = await async_client.get(
            "/api/v1/admin/maintenance/999999/ics", headers=admin_auth_headers
        )
        assert resp.status_code == 404

    async def test_ics_403_for_non_admin(
        self, async_client, normal_auth_headers, db_session
    ):
        aid = await _seed_arac(db_session, plaka="34 CCC 33")
        bid = await _seed_periyodik_bakim(db_session, arac_id=aid)
        resp = await async_client.get(
            f"/api/v1/admin/maintenance/{bid}/ics", headers=normal_auth_headers
        )
        assert resp.status_code == 403


@pytest.mark.integration
@pytest.mark.asyncio
class TestCacheInvalidation:
    async def test_create_invalidates_predictions_cache(
        self, async_client, admin_auth_headers, db_session, monkeypatch
    ):
        """Yeni bakım eklenince /predictions cache miss → fresh hesap."""
        from v2.modules.fleet.application import create_maintenance_record as cmr_mod

        invalidation_count = {"n": 0}

        async def _fake_invalidate():
            invalidation_count["n"] += 1

        monkeypatch.setattr(cmr_mod, "invalidate_predictions_cache", _fake_invalidate)

        aid = await _seed_arac(db_session, plaka="34 DDD 44")
        resp = await async_client.post(
            "/api/v1/admin/maintenance/",
            json={
                "arac_id": aid,
                "bakim_tipi": "PERIYODIK",
                "km_bilgisi": 200_000,
                "bakim_tarihi": (
                    datetime.now(timezone.utc) - timedelta(days=5)
                ).isoformat(),
                "maliyet": 500.0,
                "detaylar": "test",
            },
            headers=admin_auth_headers,
        )
        assert resp.status_code == 200, resp.text
        assert invalidation_count["n"] == 1
