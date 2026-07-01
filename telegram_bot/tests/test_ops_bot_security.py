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
"""

import os
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

os.environ.setdefault("TELEGRAM_OPS_BOT_TOKEN", "test-token-123")
os.environ.setdefault("TELEGRAM_OPS_CHAT_ID", "-100123456789")

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
    async def test_cmd_durum_responds_for_authorized_chat(self, monkeypatch):
        """Kontrol testi: yetkili sohbetten gelen /durum hâlâ yanıt vermeli
        (regresyon guard'ı — kimlik kontrolü meşru trafiği bloklamamalı)."""
        mock_response = MagicMock(status_code=200)
        monkeypatch.setattr(ops_bot.httpx, "get", MagicMock(return_value=mock_response))
        update = self._make_update(int(ops_bot.OPS_CHAT_ID))
        await ops_bot.cmd_durum(update, MagicMock())
        update.message.reply_text.assert_awaited_once()
