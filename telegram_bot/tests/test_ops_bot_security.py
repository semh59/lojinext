"""ops_bot.py security fixes — webhook secret fail-closed + command chat gating.

2026-07-01 prod-grade denetimi P1 (dalga 2, madde 9):
  1. `_check_webhook_secret` önceden `WEBHOOK_SECRET` boşsa (yapılandırılmamışsa)
     kontrolü tamamen atlıyordu (fail-open). Artık boşsa TÜM istekler
     reddedilir (fail-closed) ve doğrulama standart `Authorization: Bearer`
     header'ı üzerinden yapılır (Alertmanager'ın http_config.authorization ve
     backend'in telegram_notifier.py'siyle uyumlu).
  2. `/durum` ve `/uyarilar` komutları hiçbir kimlik kontrolü yapmıyordu —
     artık yalnız yapılandırılmış OPS_CHAT_ID'den gelen mesajlara yanıt verir.

`telegram_bot/ops_bot.py` modül-seviyesinde `os.environ["TELEGRAM_OPS_BOT_TOKEN"]`
gibi zorunlu env var okumaları yaptığı için, bu dosya import edilmeden ÖNCE
gerekli env var'lar set edilir.

Token artık modül-seviyesinde `token_resolver.resolve_bot_token()` üzerinden
(admin-configured DB override + gerçek HTTP çağrısı, .env fallback'li)
çözülüyor — bu dosyanın amacı o çözümleme değil, `_check_webhook_secret`/chat
gating testleri, o yüzden import ÖNCESİ `resolve_bot_token`'ı sahte bir
fonksiyonla değiştiriyoruz: gerçek ağ çağrısı (backend:8000'e erişilemez,
retry+sleep ile testi yavaşlatır) yerine anında env fallback'i döndürür.
"""

import os
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
import respx
from fastapi import HTTPException

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

os.environ.setdefault("TELEGRAM_OPS_BOT_TOKEN", "test-token-123")
os.environ.setdefault("TELEGRAM_OPS_CHAT_ID", "-100123456789")

# 2026-07-30 fix: this used to do `token_resolver.resolve_bot_token = lambda
# ...` as a permanent, unscoped module-attribute mutation -- since test
# modules are only imported once per pytest session and this file collects
# alphabetically before test_token_resolver.py, that later file's `from
# token_resolver import resolve_bot_token` picked up THIS dummy lambda
# instead of the real function, silently breaking 2 of its tests whenever
# the whole `tests/` directory ran together (never caught before: these
# tests had zero CI wiring, so `pytest tests/` as a package was never
# actually run until now). Scoping the patch to only the `import ops_bot`
# statement (which is what actually needs it, since ops_bot.py calls
# resolve_bot_token() at its own module-import time) restores the real
# function immediately afterward.
with patch(
    "token_resolver.resolve_bot_token",
    lambda servis_adi, backend_url, internal_secret, env_fallback: env_fallback,
):
    import ops_bot  # noqa: E402


class TestWebhookSecretFailClosed:
    def test_rejects_when_secret_not_configured(self, monkeypatch):
        """WEBHOOK_SECRET boşsa (yapılandırılmamışsa) TÜM istekler
        reddedilmeli — önceki fail-open davranışın tam tersi."""
        monkeypatch.setattr(ops_bot, "WEBHOOK_SECRET", "")
        with pytest.raises(HTTPException) as exc_info:
            ops_bot._check_webhook_secret("Bearer anything")
        assert exc_info.value.status_code == 503

    def test_rejects_when_secret_not_configured_even_with_no_header(self, monkeypatch):
        monkeypatch.setattr(ops_bot, "WEBHOOK_SECRET", "")
        with pytest.raises(HTTPException) as exc_info:
            ops_bot._check_webhook_secret(None)
        assert exc_info.value.status_code == 503

    def test_rejects_wrong_bearer_token(self, monkeypatch):
        monkeypatch.setattr(ops_bot, "WEBHOOK_SECRET", "real-secret")
        with pytest.raises(HTTPException) as exc_info:
            ops_bot._check_webhook_secret("Bearer wrong-secret")
        assert exc_info.value.status_code == 403

    def test_rejects_missing_bearer_prefix(self, monkeypatch):
        """Eski özel X-Webhook-Secret şeması (çıplak değer, Bearer prefiksiz)
        artık kabul edilmemeli — standart Authorization: Bearer şemasına
        geçildi."""
        monkeypatch.setattr(ops_bot, "WEBHOOK_SECRET", "real-secret")
        with pytest.raises(HTTPException) as exc_info:
            ops_bot._check_webhook_secret("real-secret")
        assert exc_info.value.status_code == 403

    def test_accepts_correct_bearer_token(self, monkeypatch):
        monkeypatch.setattr(ops_bot, "WEBHOOK_SECRET", "real-secret")
        # Should not raise.
        ops_bot._check_webhook_secret("Bearer real-secret")


class TestOpsCommandChatGating:
    def _make_update(self, chat_id):
        update = MagicMock()
        update.effective_chat.id = chat_id
        update.message.reply_text = AsyncMock()
        return update

    def test_is_from_ops_chat_true_for_configured_chat(self):
        assert ops_bot._is_from_ops_chat(self._make_update(int(ops_bot.OPS_CHAT_ID)))

    def test_is_from_ops_chat_false_for_other_chat(self):
        assert not ops_bot._is_from_ops_chat(self._make_update(999999999))

    def test_is_from_ops_chat_false_when_no_chat(self):
        update = MagicMock()
        update.effective_chat = None
        assert not ops_bot._is_from_ops_chat(update)

    @pytest.mark.asyncio
    async def test_cmd_durum_ignores_unauthorized_chat(self):
        """2026-07-01 fix: /durum, yapılandırılmamış bir sohbetten gelirse
        hiçbir backend sağlık bilgisi sızdırmadan sessizce döner."""
        update = self._make_update(999999999)
        await ops_bot.cmd_durum(update, MagicMock())
        update.message.reply_text.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_cmd_uyarilar_ignores_unauthorized_chat(self):
        """2026-07-01 fix: /uyarilar, yapılandırılmamış bir sohbetten gelirse
        hiçbir Prometheus alarm bilgisi sızdırmadan sessizce döner."""
        update = self._make_update(999999999)
        await ops_bot.cmd_uyarilar(update, MagicMock())
        update.message.reply_text.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_cmd_durum_responds_for_authorized_chat(self):
        """Kontrol testi: yetkili sohbetten gelen /durum hâlâ yanıt vermeli
        (regresyon guard'ı — kimlik kontrolü meşru trafiği bloklamamalı)."""
        with respx.mock:
            respx.get(f"{ops_bot.BACKEND_URL}/api/v1/health/").mock(
                return_value=httpx.Response(200)
            )
            update = self._make_update(int(ops_bot.OPS_CHAT_ID))
            await ops_bot.cmd_durum(update, MagicMock())
        update.message.reply_text.assert_awaited_once()


class TestRestartCommand:
    """cmd_yeniden_baslat -- 2026-07-30 fix: previously shelled out to a
    `docker` CLI binary that was never installed in this image (always
    raised FileNotFoundError), and did so via a blocking subprocess.run()
    inside an async handler. Now talks to docker-socket-proxy-ops (a
    write-scoped-to-restart-only proxy) over async httpx."""

    def _make_context(self, args):
        ctx = MagicMock()
        ctx.args = args
        return ctx

    def _make_update(self, user_id):
        update = MagicMock()
        update.effective_user.id = user_id
        update.message.reply_text = AsyncMock()
        return update

    @pytest.mark.asyncio
    async def test_disabled_when_no_admin_ids_configured(self, monkeypatch):
        monkeypatch.setattr(ops_bot, "OPS_ADMIN_IDS", frozenset())
        update = self._make_update(12345)
        await ops_bot.cmd_yeniden_baslat(update, self._make_context(["backend"]))
        update.message.reply_text.assert_awaited_once()
        assert "devre dışı" in update.message.reply_text.await_args.args[0]

    @pytest.mark.asyncio
    async def test_rejects_non_admin_caller(self, monkeypatch):
        monkeypatch.setattr(ops_bot, "OPS_ADMIN_IDS", frozenset({111}))
        update = self._make_update(999)
        await ops_bot.cmd_yeniden_baslat(update, self._make_context(["backend"]))
        update.message.reply_text.assert_awaited_once()
        assert "yetkiniz yok" in update.message.reply_text.await_args.args[0]

    @pytest.mark.asyncio
    async def test_rejects_disallowed_service_name(self, monkeypatch):
        monkeypatch.setattr(ops_bot, "OPS_ADMIN_IDS", frozenset({111}))
        update = self._make_update(111)
        await ops_bot.cmd_yeniden_baslat(update, self._make_context(["db"]))
        update.message.reply_text.assert_awaited_once()
        assert "İzin verilmeyen servis" in update.message.reply_text.await_args.args[0]

    @pytest.mark.asyncio
    async def test_restarts_via_proxy_on_dash_name(self, monkeypatch):
        monkeypatch.setattr(ops_bot, "OPS_ADMIN_IDS", frozenset({111}))
        update = self._make_update(111)
        with respx.mock:
            respx.post(
                f"{ops_bot.DOCKER_RESTART_PROXY_URL}/containers/lojinext-backend-1/restart"
            ).mock(return_value=httpx.Response(204))
            await ops_bot.cmd_yeniden_baslat(update, self._make_context(["backend"]))
        update.message.reply_text.assert_awaited_once()
        assert "yeniden başlatıldı" in update.message.reply_text.await_args.args[0]

    @pytest.mark.asyncio
    async def test_falls_back_to_underscore_name_then_reports_not_found(
        self, monkeypatch
    ):
        monkeypatch.setattr(ops_bot, "OPS_ADMIN_IDS", frozenset({111}))
        update = self._make_update(111)
        with respx.mock:
            respx.post(
                f"{ops_bot.DOCKER_RESTART_PROXY_URL}/containers/lojinext-backend-1/restart"
            ).mock(return_value=httpx.Response(404))
            respx.post(
                f"{ops_bot.DOCKER_RESTART_PROXY_URL}/containers/lojinext_backend_1/restart"
            ).mock(return_value=httpx.Response(404))
            await ops_bot.cmd_yeniden_baslat(update, self._make_context(["backend"]))
        update.message.reply_text.assert_awaited_once()
        assert "container bulunamadı" in update.message.reply_text.await_args.args[0]

    @pytest.mark.asyncio
    async def test_reports_error_when_proxy_unreachable(self, monkeypatch):
        monkeypatch.setattr(ops_bot, "OPS_ADMIN_IDS", frozenset({111}))
        update = self._make_update(111)
        with respx.mock:
            respx.post(url__regex=r".*/restart$").mock(
                side_effect=httpx.ConnectError("refused")
            )
            await ops_bot.cmd_yeniden_baslat(update, self._make_context(["backend"]))
        update.message.reply_text.assert_awaited_once()
        assert "proxy'ye ulaşılamadı" in update.message.reply_text.await_args.args[0]
