"""Feature B.5 — OPS Telegram alarm broadcast testleri.

Notlar:
- `httpx.AsyncClient` monkeypatch'i ile gerçek HTTP çağrısını engelliyoruz.
- High suspicion için sapma_yuzde >= ~30 ve severity high/critical seçilmeli.
"""

from datetime import date, datetime, timezone
from typing import Any

import pytest


async def _seed_high_anomaly(db_session) -> int:
    from app.database.models import Anomaly

    row = Anomaly(
        tarih=date.today(),
        tip="tuketim",
        kaynak_tip="sefer",
        kaynak_id=1,
        deger=60.0,
        beklenen_deger=30.0,
        sapma_yuzde=45.0,
        severity="critical",
        aciklama="High suspicion test anomaly",
        created_at=datetime.now(timezone.utc),
    )
    db_session.add(row)
    await db_session.commit()
    await db_session.refresh(row)
    return int(row.id)


async def _seed_low_anomaly(db_session) -> int:
    from app.database.models import Anomaly

    row = Anomaly(
        tarih=date.today(),
        tip="tuketim",
        kaynak_tip="sefer",
        kaynak_id=1,
        deger=33.0,
        beklenen_deger=30.0,
        sapma_yuzde=8.0,
        severity="low",
        aciklama="Low suspicion test anomaly",
        created_at=datetime.now(timezone.utc),
    )
    db_session.add(row)
    await db_session.commit()
    await db_session.refresh(row)
    return int(row.id)


class _FakeResp:
    def __init__(self, status_code: int = 200) -> None:
        self.status_code = status_code

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            import httpx

            raise httpx.HTTPStatusError(
                "boom",
                request=None,
                response=self,  # type: ignore[arg-type]
            )


class _FakeAsyncClient:
    """Generic httpx.AsyncClient stub that records calls."""

    captured: dict[str, Any] = {}

    def __init__(self, *args: Any, **kwargs: Any) -> None:  # noqa: ARG002
        pass

    async def __aenter__(self) -> "_FakeAsyncClient":
        return self

    async def __aexit__(self, *exc: Any) -> None:
        return None

    async def post(
        self,
        url: str,
        json: dict | None = None,
        **kwargs: Any,  # noqa: ARG002
    ) -> _FakeResp:
        _FakeAsyncClient.captured["url"] = url
        _FakeAsyncClient.captured["json"] = json
        return _FakeResp(200)


@pytest.mark.integration
@pytest.mark.asyncio
class TestTheftAlarmBroadcast:
    async def test_high_suspicion_triggers_telegram_post(
        self, async_client, admin_auth_headers, db_session, monkeypatch
    ):
        monkeypatch.setattr("app.config.settings.THEFT_ALARM_ENABLED", True)
        monkeypatch.setattr("app.config.settings.TELEGRAM_OPS_BOT_TOKEN", "TESTTOKEN")
        monkeypatch.setattr("app.config.settings.TELEGRAM_OPS_CHAT_ID", "-100123")
        import httpx

        _FakeAsyncClient.captured = {}
        monkeypatch.setattr(httpx, "AsyncClient", _FakeAsyncClient)

        aid = await _seed_high_anomaly(db_session)
        resp = await async_client.post(
            "/api/v1/admin/investigations",
            json={"anomaly_id": aid},
            headers=admin_auth_headers,
        )
        assert resp.status_code == 201, resp.text
        body = resp.json()
        assert body["suspicion_level"] == "high"

        # Telegram çağrısı yapıldı + HTML parse_mode + chat_id
        cap = _FakeAsyncClient.captured
        assert "TESTTOKEN" in cap.get("url", "")
        assert cap["json"]["chat_id"] == "-100123"
        assert cap["json"]["parse_mode"] == "HTML"
        body_text = cap["json"]["text"]
        assert "Yüksek Şüpheli Yakıt Olayı" in body_text
        assert f"Anomali #{aid}" in body_text

    async def test_low_suspicion_does_not_broadcast(
        self, async_client, admin_auth_headers, db_session, monkeypatch
    ):
        monkeypatch.setattr("app.config.settings.THEFT_ALARM_ENABLED", True)
        monkeypatch.setattr("app.config.settings.TELEGRAM_OPS_BOT_TOKEN", "TESTTOKEN")
        monkeypatch.setattr("app.config.settings.TELEGRAM_OPS_CHAT_ID", "-100123")
        import httpx

        _FakeAsyncClient.captured = {}
        monkeypatch.setattr(httpx, "AsyncClient", _FakeAsyncClient)

        aid = await _seed_low_anomaly(db_session)
        resp = await async_client.post(
            "/api/v1/admin/investigations",
            json={"anomaly_id": aid},
            headers=admin_auth_headers,
        )
        assert resp.status_code == 201
        assert resp.json()["suspicion_level"] in ("low", "medium")
        assert _FakeAsyncClient.captured == {}  # post hiç çağrılmadı

    async def test_flag_off_skips_broadcast(
        self, async_client, admin_auth_headers, db_session, monkeypatch
    ):
        monkeypatch.setattr("app.config.settings.THEFT_ALARM_ENABLED", False)
        monkeypatch.setattr("app.config.settings.TELEGRAM_OPS_BOT_TOKEN", "TESTTOKEN")
        monkeypatch.setattr("app.config.settings.TELEGRAM_OPS_CHAT_ID", "-100123")
        import httpx

        _FakeAsyncClient.captured = {}
        monkeypatch.setattr(httpx, "AsyncClient", _FakeAsyncClient)

        aid = await _seed_high_anomaly(db_session)
        resp = await async_client.post(
            "/api/v1/admin/investigations",
            json={"anomaly_id": aid},
            headers=admin_auth_headers,
        )
        assert resp.status_code == 201
        assert _FakeAsyncClient.captured == {}

    async def test_missing_chat_id_skips_silently(
        self, async_client, admin_auth_headers, db_session, monkeypatch, caplog
    ):
        monkeypatch.setattr("app.config.settings.THEFT_ALARM_ENABLED", True)
        monkeypatch.setattr("app.config.settings.TELEGRAM_OPS_BOT_TOKEN", "TESTTOKEN")
        monkeypatch.setattr("app.config.settings.TELEGRAM_OPS_CHAT_ID", "")
        import httpx

        _FakeAsyncClient.captured = {}
        monkeypatch.setattr(httpx, "AsyncClient", _FakeAsyncClient)

        aid = await _seed_high_anomaly(db_session)
        resp = await async_client.post(
            "/api/v1/admin/investigations",
            json={"anomaly_id": aid},
            headers=admin_auth_headers,
        )
        # Yapılandırma eksik → 201 (akış kırılmaz), Telegram hiç çağrılmadı.
        assert resp.status_code == 201
        assert _FakeAsyncClient.captured == {}

    async def test_telegram_error_does_not_break_creation(
        self, async_client, admin_auth_headers, db_session, monkeypatch
    ):
        monkeypatch.setattr("app.config.settings.THEFT_ALARM_ENABLED", True)
        monkeypatch.setattr("app.config.settings.TELEGRAM_OPS_BOT_TOKEN", "TESTTOKEN")
        monkeypatch.setattr("app.config.settings.TELEGRAM_OPS_CHAT_ID", "-100123")

        import httpx

        class _BrokenClient(_FakeAsyncClient):
            async def post(
                self, url: str, json: dict | None = None, **kwargs: Any
            ) -> _FakeResp:
                raise httpx.ConnectError("net down")

        monkeypatch.setattr(httpx, "AsyncClient", _BrokenClient)

        aid = await _seed_high_anomaly(db_session)
        resp = await async_client.post(
            "/api/v1/admin/investigations",
            json={"anomaly_id": aid},
            headers=admin_auth_headers,
        )
        # Telegram hatası yutuldu — soruşturma 201
        assert resp.status_code == 201
