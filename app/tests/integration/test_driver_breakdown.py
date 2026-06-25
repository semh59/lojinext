"""Dilim 5 — Sürücü botu /ariza köprü endpoint'i (POST /internal/driver-breakdown).

Araç çözümü ürün kararı A: sürücünün EN YENİ seferindeki araç. Plaka girilmez.
Shared-secret (X-Internal-Token) zorunlu; gerçek DB üzerinde açık ARIZA/ACIL
kaydı oluşturulur (mock yok).
"""

from datetime import date, timedelta

import pytest
from sqlalchemy import text

from app.tests._helpers.seed import seed_arac, seed_sefer, seed_sofor

_SECRET = "test-secret"
_HEADERS = {"X-Internal-Token": _SECRET}


@pytest.mark.integration
@pytest.mark.asyncio
class TestDriverBreakdown:
    async def test_404_unknown_telegram_id(self, async_client, monkeypatch):
        monkeypatch.setattr("app.config.settings.INTERNAL_API_SECRET", _SECRET)
        resp = await async_client.post(
            "/api/v1/internal/driver-breakdown",
            json={"telegram_id": "9999999999", "detaylar": "x"},
            headers=_HEADERS,
        )
        assert resp.status_code == 404, resp.text

    async def test_404_driver_without_sefer(
        self, async_client, db_session, monkeypatch
    ):
        """Sürücü var ama hiç seferi yok → araç çözülemez → 404."""
        monkeypatch.setattr("app.config.settings.INTERNAL_API_SECRET", _SECRET)
        await seed_sofor(db_session, ad_soyad="Sefersiz Şoför", telegram_id="111000")
        await db_session.commit()

        resp = await async_client.post(
            "/api/v1/internal/driver-breakdown",
            json={"telegram_id": "111000", "detaylar": "fren"},
            headers=_HEADERS,
        )
        assert resp.status_code == 404, resp.text

    async def test_201_creates_open_ariza_on_latest_sefer_arac(
        self, async_client, db_session, monkeypatch
    ):
        """En yeni seferin aracına açık ARIZA kaydı açılır."""
        monkeypatch.setattr("app.config.settings.INTERNAL_API_SECRET", _SECRET)
        arac = await seed_arac(db_session, plaka="34 ARZ 001")
        sofor = await seed_sofor(db_session, ad_soyad="Arızacı", telegram_id="222000")
        await seed_sefer(
            db_session, arac_id=arac.id, sofor_id=sofor.id, tarih=date.today()
        )
        await db_session.commit()

        resp = await async_client.post(
            "/api/v1/internal/driver-breakdown",
            json={"telegram_id": "222000", "detaylar": "fren sesi geliyor"},
            headers=_HEADERS,
        )
        assert resp.status_code == 201, resp.text
        body = resp.json()
        assert body["arac_id"] == arac.id
        assert body["arac_plakasi"] == "34 ARZ 001"
        assert body["bakim_tipi"] == "ARIZA"

        # DB'de gerçek açık ARIZA kaydı var mı?
        row = (
            (
                await db_session.execute(
                    text(
                        "SELECT bakim_tipi, tamamlandi, detaylar FROM arac_bakimlari "
                        "WHERE id = :bid"
                    ),
                    {"bid": body["bakim_id"]},
                )
            )
            .mappings()
            .one()
        )
        assert row["bakim_tipi"] == "ARIZA"
        assert row["tamamlandi"] is False
        assert "fren" in row["detaylar"]

    async def test_201_acil_flag_creates_acil(
        self, async_client, db_session, monkeypatch
    ):
        monkeypatch.setattr("app.config.settings.INTERNAL_API_SECRET", _SECRET)
        arac = await seed_arac(db_session, plaka="34 ACL 002")
        sofor = await seed_sofor(db_session, ad_soyad="Acilci", telegram_id="333000")
        await seed_sefer(db_session, arac_id=arac.id, sofor_id=sofor.id)
        await db_session.commit()

        resp = await async_client.post(
            "/api/v1/internal/driver-breakdown",
            json={"telegram_id": "333000", "detaylar": "lastik patladı", "acil": True},
            headers=_HEADERS,
        )
        assert resp.status_code == 201, resp.text
        assert resp.json()["bakim_tipi"] == "ACIL"

    async def test_resolves_most_recent_sefer_arac(
        self, async_client, db_session, monkeypatch
    ):
        """İki farklı araçlı sefer → en yeni tarihli seferin aracı seçilir."""
        monkeypatch.setattr("app.config.settings.INTERNAL_API_SECRET", _SECRET)
        eski_arac = await seed_arac(db_session, plaka="34 ESK 003")
        yeni_arac = await seed_arac(db_session, plaka="34 YNI 004")
        sofor = await seed_sofor(
            db_session, ad_soyad="Çok Seferli", telegram_id="444000"
        )
        await seed_sefer(
            db_session,
            arac_id=eski_arac.id,
            sofor_id=sofor.id,
            tarih=date.today() - timedelta(days=10),
        )
        await seed_sefer(
            db_session,
            arac_id=yeni_arac.id,
            sofor_id=sofor.id,
            tarih=date.today(),
        )
        await db_session.commit()

        resp = await async_client.post(
            "/api/v1/internal/driver-breakdown",
            json={"telegram_id": "444000", "detaylar": "motor"},
            headers=_HEADERS,
        )
        assert resp.status_code == 201, resp.text
        assert resp.json()["arac_id"] == yeni_arac.id
