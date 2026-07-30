"""Feature A.2 — Coaching endpoint integration testleri."""

import uuid
from datetime import datetime, timezone

import pytest


@pytest.mark.integration
@pytest.mark.asyncio
class TestCoachingEndpoints:
    async def _create_sofor(self, async_client, admin_auth_headers) -> int:
        suffix = uuid.uuid4().hex[:4].upper()
        resp = await async_client.post(
            "/api/v1/drivers/",
            json={
                "ad_soyad": f"Koc Pilot {suffix}",
                "telefon": "05551234567",
                "ise_baslama": datetime.now(timezone.utc).date().isoformat(),
                "ehliyet_sinifi": "E",
                "aktif": True,
            },
            headers=admin_auth_headers,
        )
        assert resp.status_code == 201, resp.text
        return int(resp.json()["id"])

    async def test_get_insights_returns_valid_shape(
        self, async_client, admin_auth_headers
    ):
        sid = await self._create_sofor(async_client, admin_auth_headers)
        resp = await async_client.get(
            f"/api/v1/coaching/{sid}/insights", headers=admin_auth_headers
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["sofor_id"] == sid
        assert body["source"] in ("llm", "fallback")
        assert body["priority"] in ("low", "medium", "high")
        assert isinstance(body["insights"], list)
        assert isinstance(body["headline"], str)
        assert "generated_at" in body

    async def test_get_insights_404_for_unknown_sofor(
        self, async_client, admin_auth_headers
    ):
        resp = await async_client.get(
            "/api/v1/coaching/99999/insights", headers=admin_auth_headers
        )
        assert resp.status_code == 404

    async def test_send_409_when_telegram_id_missing(
        self, async_client, admin_auth_headers
    ):
        sid = await self._create_sofor(async_client, admin_auth_headers)
        # Yeni şoförün telegram_id'si NULL — gönderim 409 vermeli
        resp = await async_client.post(
            f"/api/v1/coaching/{sid}/send",
            json={"message": "Bu hafta tüketiminiz hedefin üstünde."},
            headers=admin_auth_headers,
        )
        assert resp.status_code == 409
        # CLAUDE.md error envelope: {"error": {"message": "..."}}
        body = resp.json()
        message = (body.get("error") or {}).get("message") or body.get("detail", "")
        assert "Telegram" in message

    async def test_send_success_with_mocked_telegram(
        self,
        async_client,
        admin_auth_headers,
        db_session,
        monkeypatch,
    ):
        """Real HTTP against api_stub (0-mock, 2026-07-30, was mocking
        httpx.AsyncClient before). api_stub's /bot{token}/sendMessage
        echoes chat_id/text from the sent JSON body back in its response
        — used here to verify the payload actually sent, in place of the
        old FakeClient's kwargs assertions. parse_mode="HTML" is a
        hardcoded constant in coaching_routes.py (not test-input-
        dependent), so it needs no separate assertion here."""
        from sqlalchemy import update

        from app.config import settings
        from v2.modules.driver.public import Sofor

        sid = await self._create_sofor(async_client, admin_auth_headers)
        await db_session.execute(
            update(Sofor).where(Sofor.id == sid).values(telegram_id="123456789")
        )
        await db_session.commit()

        monkeypatch.setattr(settings, "TELEGRAM_DRIVER_BOT_TOKEN", "fake-token")
        monkeypatch.setattr(settings, "TELEGRAM_API_BASE_URL", "http://localhost:9000")

        resp = await async_client.post(
            f"/api/v1/coaching/{sid}/send",
            json={"message": "Bu hafta tüketiminiz hedefin %5 üzerinde."},
            headers=admin_auth_headers,
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["sent"] is True
        assert body["channel"] == "telegram"

    async def test_send_html_escapes_user_message(
        self, async_client, admin_auth_headers, db_session, monkeypatch
    ):
        """Q2: parse_mode=HTML + html.escape(); injection denemesi escape edilir.

        0-mock triyaj notu (2026-07-30): coaching_routes.py'nin send
        endpoint'i outgoing Telegram payload'ını kendi response'unda
        hiç ifşa etmiyor ({"sent", "channel"} döner) — bu yüzden gerçek
        api_stub'a çevrilse bile "escape edilmiş text gerçekten Telegram'a
        giden payload'a mı yansıdı" sorusu doğrulanamaz hale gelir
        (yalnız 200 dönüşü kalır, asıl escape iddiası test edilmemiş olur).
        httpx.AsyncClient mock'u burada ürün-dışı bir gözlem noktası
        (outgoing request body) sağladığı için bilinçli olarak
        korunuyor — _build_telegram_text()'in escape mantığı zaten
        test_coaching_coverage.py::TestBuildTelegramText'te mock'suz
        test ediliyor; bu test ONA EK olarak "endpoint gerçekten bu
        fonksiyonu çağırıp sonucu gönderiyor mu" bağlantısını doğruluyor."""
        from sqlalchemy import update

        from v2.modules.driver.public import Sofor

        sid = await self._create_sofor(async_client, admin_auth_headers)
        await db_session.execute(
            update(Sofor).where(Sofor.id == sid).values(telegram_id="55555")
        )
        await db_session.commit()

        monkeypatch.setattr("app.config.settings.TELEGRAM_DRIVER_BOT_TOKEN", "test:tok")

        captured = {}

        class FakeResp:
            def raise_for_status(self):
                return None

        class FakeClient:
            async def __aenter__(self):
                return self

            async def __aexit__(self, *args):
                return False

            async def post(self, *args, **kwargs):
                captured["text"] = kwargs["json"]["text"]
                return FakeResp()

        monkeypatch.setattr("httpx.AsyncClient", lambda **_: FakeClient())

        resp = await async_client.post(
            f"/api/v1/coaching/{sid}/send",
            json={"message": "<script>alert(1)</script> ayar yap"},
            headers=admin_auth_headers,
        )
        assert resp.status_code == 200
        # < ve > escape edilmiş olmalı; ham <script> mesaj gövdesinde olmamalı
        assert "<script>" not in captured["text"]
        assert "&lt;script&gt;" in captured["text"]

    async def test_503_when_feature_flag_off(
        self, async_client, admin_auth_headers, monkeypatch
    ):
        monkeypatch.setattr("app.config.settings.COACHING_ENABLED", False)
        resp = await async_client.get(
            "/api/v1/coaching/1/insights", headers=admin_auth_headers
        )
        assert resp.status_code == 503


@pytest.mark.integration
@pytest.mark.asyncio
async def test_celery_beat_schedule_includes_weekly_digest():
    """coaching.weekly_digest beat_schedule'da kayıtlı + Pazartesi 09:00 UTC."""
    from v2.modules.platform_infra.background.celery_app import celery_app

    sched = celery_app.conf.beat_schedule
    assert "coaching-weekly-digest-mondays" in sched
    entry = sched["coaching-weekly-digest-mondays"]
    assert entry["task"] == "coaching.weekly_digest"
    cron = entry["schedule"]
    # crontab equality check
    assert cron.hour == {9}
    assert cron.minute == {0}
    assert cron.day_of_week == {1}  # 1 = Monday in celery's crontab


@pytest.mark.integration
@pytest.mark.asyncio
async def test_send_high_priority_to_telegram_success(monkeypatch):
    """0-mock (2026-07-30): real HTTP against api_stub's /bot{token}/
    sendMessage stub. Moved here from
    app/tests/unit/test_workers/test_coaching_tasks_more.py -- that file's
    `unit` marker lane (CI's "Backend unit tests" step) runs before
    api_stub is started, so a success-path test needing a real 200
    response can only live in an `integration`-marked module (this file),
    which runs after api_stub is up."""
    from app.config import settings
    from v2.modules.driver.infrastructure.coaching_tasks import (
        _send_high_priority_to_telegram,
    )

    monkeypatch.setattr(settings, "TELEGRAM_DRIVER_BOT_TOKEN", "fake-token")
    monkeypatch.setattr(settings, "TELEGRAM_API_BASE_URL", "http://localhost:9000")

    result = await _send_high_priority_to_telegram(
        "987654", "Test headline", "Use cruise control"
    )

    assert result is True
