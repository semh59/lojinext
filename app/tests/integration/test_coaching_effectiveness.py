"""Feature A.5 — CoachingDelivery INSERT + /effectiveness + evaluate_pending task."""

import uuid
from datetime import datetime, timedelta, timezone

import pytest


@pytest.mark.integration
@pytest.mark.asyncio
class TestCoachingEffectiveness:
    async def _create_sofor_with_telegram(
        self, async_client, admin_auth_headers, db_session
    ) -> int:
        from sqlalchemy import update

        from app.database.models import Sofor

        suffix = uuid.uuid4().hex[:4].upper()
        resp = await async_client.post(
            "/api/v1/drivers/",
            json={
                "ad_soyad": f"Eff Pilot {suffix}",
                "telefon": "05550009999",
                "ise_baslama": datetime.now(timezone.utc).date().isoformat(),
                "ehliyet_sinifi": "E",
                "aktif": True,
            },
            headers=admin_auth_headers,
        )
        assert resp.status_code == 201
        sid = int(resp.json()["id"])
        await db_session.execute(
            update(Sofor).where(Sofor.id == sid).values(telegram_id="111000111")
        )
        await db_session.commit()
        return sid

    async def test_send_creates_coaching_delivery(
        self, async_client, admin_auth_headers, db_session, monkeypatch
    ):
        """POST /send başarılı → CoachingDelivery satırı oluşur, delivery_id döner."""
        from sqlalchemy import select

        from app.database.models import CoachingDelivery

        sid = await self._create_sofor_with_telegram(
            async_client, admin_auth_headers, db_session
        )
        monkeypatch.setattr(
            "app.config.settings.TELEGRAM_DRIVER_BOT_TOKEN", "test:fake"
        )

        class FakeResp:
            def raise_for_status(self):
                return None

        class FakeClient:
            async def __aenter__(self):
                return self

            async def __aexit__(self, *args):
                return False

            async def post(self, *args, **kwargs):
                return FakeResp()

        monkeypatch.setattr("httpx.AsyncClient", lambda **_: FakeClient())

        resp = await async_client.post(
            f"/api/v1/coaching/{sid}/send",
            json={
                "message": "Hız sınırına uyun ve vites geçişlerini optimize edin.",
                "insight_category": "sofor_pratigi",
            },
            headers=admin_auth_headers,
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["sent"] is True
        assert body["delivery_id"] is not None

        # DB'de kayıt var mı?
        stmt = select(CoachingDelivery).where(
            CoachingDelivery.id == body["delivery_id"]
        )
        row = (await db_session.execute(stmt)).scalar_one()
        assert row.sofor_id == sid
        assert row.score_before > 0
        assert row.score_after_2w is None  # Henüz değerlendirilmedi
        assert row.evaluated_at is None
        assert row.channel == "telegram"
        assert row.insight_category == "sofor_pratigi"
        assert row.message_excerpt and len(row.message_excerpt) <= 500

    async def test_effectiveness_endpoint_returns_caveat(
        self, async_client, admin_auth_headers
    ):
        """/effectiveness her zaman geçerli payload + caveat string döner."""
        resp = await async_client.get(
            "/api/v1/coaching/effectiveness?days=30",
            headers=admin_auth_headers,
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["window_days"] == 30
        assert "total_sent" in body
        assert "improved" in body
        assert "caveat" in body
        assert "istatistiksel kanıt değil" in body["caveat"]

    async def test_evaluate_pending_fills_delta(
        self, async_client, admin_auth_headers, db_session, monkeypatch
    ):
        """Manuel olarak sent_at'ı 15 gün geriye it → evaluate_pending task'ı
        çağrılınca score_after_2w + score_delta_pct + evaluated_at dolar."""
        from sqlalchemy import select, update

        from app.database.models import CoachingDelivery

        sid = await self._create_sofor_with_telegram(
            async_client, admin_auth_headers, db_session
        )
        # Telegram gönderimi mock'la
        monkeypatch.setattr(
            "app.config.settings.TELEGRAM_DRIVER_BOT_TOKEN", "test:fake"
        )

        class FakeResp:
            def raise_for_status(self):
                return None

        class FakeClient:
            async def __aenter__(self):
                return self

            async def __aexit__(self, *args):
                return False

            async def post(self, *args, **kwargs):
                return FakeResp()

        monkeypatch.setattr("httpx.AsyncClient", lambda **_: FakeClient())

        resp = await async_client.post(
            f"/api/v1/coaching/{sid}/send",
            json={"message": "Test koçluk mesajı, 14 gün sonra ölç."},
            headers=admin_auth_headers,
        )
        assert resp.status_code == 200
        delivery_id = resp.json()["delivery_id"]

        # sent_at'ı 15 gün geriye it
        past = datetime.now(timezone.utc) - timedelta(days=15)
        await db_session.execute(
            update(CoachingDelivery)
            .where(CoachingDelivery.id == delivery_id)
            .values(sent_at=past)
        )
        await db_session.commit()

        # evaluate_pending'i doğrudan çağır
        from v2.modules.driver.infrastructure.coaching_tasks import (
            _run_evaluate_pending,
        )

        result = await _run_evaluate_pending()
        assert result["evaluated"] >= 1

        # Kayıt güncellenmiş mi?
        stmt = select(CoachingDelivery).where(CoachingDelivery.id == delivery_id)
        row = (await db_session.execute(stmt)).scalar_one()
        await db_session.refresh(row)
        assert row.evaluated_at is not None
        assert row.score_after_2w is not None
        assert row.score_delta_pct is not None
