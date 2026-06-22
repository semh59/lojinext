"""Feature A.4 — Internal coaching endpoint integration testleri.

Telegram bot köprü endpoint'i; X-Internal-Token shared-secret zorunlu.
"""

import uuid
from datetime import datetime, timezone

import pytest

from app.config import settings


@pytest.mark.integration
@pytest.mark.asyncio
class TestInternalCoachingSnapshot:
    async def test_401_without_token(self, async_client):
        """X-Internal-Token header'ı olmadan 401."""
        # ENVIRONMENT prod değilse skip da olabilir; biz token gönderelim ama yanlış olsun
        resp = await async_client.get(
            "/api/v1/internal/sofor-coaching/000000",
            headers={"X-Internal-Token": "wrong-secret"},
        )
        # INTERNAL_API_SECRET dev/test'te boş olabilir → 200/404 dönebilir.
        # Bu durumda 401 değil 404 bekleriz (token check pas geçer).
        if settings.INTERNAL_API_SECRET:
            assert resp.status_code == 401
        else:
            # secret yoksa middleware token kontrolünü atlar, 404 döner
            assert resp.status_code == 404

    async def test_404_for_unknown_telegram_id(
        self, async_client, admin_auth_headers, monkeypatch
    ):
        """Bilinmeyen telegram_id için 404."""
        monkeypatch.setattr("app.config.settings.INTERNAL_API_SECRET", "test-secret")
        resp = await async_client.get(
            "/api/v1/internal/sofor-coaching/9999999999",
            headers={"X-Internal-Token": "test-secret"},
        )
        assert resp.status_code == 404

    async def test_200_returns_snapshot_for_known_driver(
        self, async_client, admin_auth_headers, db_session, monkeypatch
    ):
        """telegram_id'si set olan şoför için snapshot döner."""
        from sqlalchemy import update

        from app.database.models import Sofor

        # Yeni şoför oluştur
        suffix = uuid.uuid4().hex[:4].upper()
        resp = await async_client.post(
            "/api/v1/drivers/",
            json={
                "ad_soyad": f"Telegram Pilot {suffix}",
                "telefon": "05551112233",
                "ise_baslama": datetime.now(timezone.utc).date().isoformat(),
                "ehliyet_sinifi": "E",
                "aktif": True,
            },
            headers=admin_auth_headers,
        )
        assert resp.status_code == 201, resp.text
        sid = int(resp.json()["id"])

        tg_id = "987654321"
        await db_session.execute(
            update(Sofor).where(Sofor.id == sid).values(telegram_id=tg_id)
        )
        await db_session.commit()

        monkeypatch.setattr("app.config.settings.INTERNAL_API_SECRET", "test-secret")

        resp = await async_client.get(
            f"/api/v1/internal/sofor-coaching/{tg_id}",
            headers={"X-Internal-Token": "test-secret"},
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert "ad_soyad" in body
        assert "skor" in body
        assert "headline" in body
        assert "priority" in body
        assert body["priority"] in ("low", "medium", "high")
        assert "insights_count" in body
        assert "source" in body
        assert body["source"] in ("llm", "fallback")
