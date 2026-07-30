"""driver_bot.py -- 2026-07-30: previously had ZERO test coverage (338
lines, 7 commands + a photo handler). Covers the real behaviors: sofor
lookup (found/not-found/backend-error), photo-caption-based belge_tipi
classification, and each command's happy/unregistered/backend-error paths.

Same env-var + resolve_bot_token bootstrap pattern as
test_ops_bot_security.py -- driver_bot.py reads
TELEGRAM_DRIVER_BOT_TOKEN at module import time via token_resolver.
"""

import os
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
import respx

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

os.environ.setdefault("TELEGRAM_DRIVER_BOT_TOKEN", "test-driver-token-123")

# Scoped patch, not a permanent module-attribute mutation -- see the
# matching comment in test_ops_bot_security.py (2026-07-30 fix) for why:
# an unscoped assignment here would leak into test_token_resolver.py's
# tests whenever the whole tests/ directory runs together.
with patch(
    "token_resolver.resolve_bot_token",
    lambda servis_adi, backend_url, internal_secret, env_fallback: env_fallback,
):
    import driver_bot  # noqa: E402

TELEGRAM_ID = "555555"


def _make_update(with_message=True, caption=None, message_id=42):
    update = MagicMock()
    update.effective_user.id = TELEGRAM_ID
    if with_message:
        update.message.reply_text = AsyncMock()
        update.message.caption = caption
        update.message.message_id = message_id
    return update


def _make_context(args=None):
    ctx = MagicMock()
    ctx.args = args or []
    return ctx


class TestGetSofor:
    @pytest.mark.asyncio
    async def test_returns_dict_on_200(self):
        with respx.mock:
            respx.get(
                f"{driver_bot.BACKEND_URL}/api/v1/internal/sofor-by-telegram/{TELEGRAM_ID}"
            ).mock(return_value=httpx.Response(200, json={"id": 1, "ad_soyad": "Test"}))
            result = await driver_bot._get_sofor(TELEGRAM_ID)
        assert result == {"id": 1, "ad_soyad": "Test"}

    @pytest.mark.asyncio
    async def test_returns_none_on_404(self):
        with respx.mock:
            respx.get(
                f"{driver_bot.BACKEND_URL}/api/v1/internal/sofor-by-telegram/{TELEGRAM_ID}"
            ).mock(return_value=httpx.Response(404))
            result = await driver_bot._get_sofor(TELEGRAM_ID)
        assert result is None

    @pytest.mark.asyncio
    async def test_returns_none_and_logs_on_backend_error(self, caplog):
        """2026-07-30 fix: previously a bare except-return-None with NO
        logging -- a real backend error was silently indistinguishable
        from a genuine not-registered driver, with no trace to debug it."""
        with respx.mock:
            respx.get(
                f"{driver_bot.BACKEND_URL}/api/v1/internal/sofor-by-telegram/{TELEGRAM_ID}"
            ).mock(side_effect=httpx.ConnectError("refused"))
            with caplog.at_level("WARNING"):
                result = await driver_bot._get_sofor(TELEGRAM_ID)
            assert result is None
            assert any(
                "sofor-by-telegram lookup failed" in rec.message
                for rec in caplog.records
            )


class TestHandlePhoto:
    @pytest.mark.asyncio
    async def test_unregistered_driver_gets_rejection_message(self):
        with respx.mock:
            respx.get(
                f"{driver_bot.BACKEND_URL}/api/v1/internal/sofor-by-telegram/{TELEGRAM_ID}"
            ).mock(return_value=httpx.Response(404))
            update = _make_update()
            await driver_bot.handle_photo(update, _make_context())
        update.message.reply_text.assert_awaited_once()
        assert "kayıtlı değil" in update.message.reply_text.await_args.args[0]

    @pytest.mark.asyncio
    async def test_registered_driver_yakit_caption_uploads_and_confirms(self):
        with respx.mock:
            respx.get(
                f"{driver_bot.BACKEND_URL}/api/v1/internal/sofor-by-telegram/{TELEGRAM_ID}"
            ).mock(return_value=httpx.Response(200, json={"id": 1}))
            respx.post(f"{driver_bot.BACKEND_URL}/api/v1/internal/sefer-belge").mock(
                return_value=httpx.Response(200)
            )
            update = _make_update(caption="yakit fisi")
            photo = MagicMock()
            photo.file_id = "file123"
            update.message.photo = [photo]
            file_obj = AsyncMock()
            file_obj.download_as_bytearray = AsyncMock(
                return_value=bytearray(b"jpgdata")
            )
            context = _make_context()
            context.bot.get_file = AsyncMock(return_value=file_obj)
            await driver_bot.handle_photo(update, context)
        update.message.reply_text.assert_awaited_once()
        assert "Yakıt Fişi" in update.message.reply_text.await_args.args[0]

    @pytest.mark.asyncio
    async def test_no_caption_classified_as_tir_ekran(self):
        with respx.mock:
            respx.get(
                f"{driver_bot.BACKEND_URL}/api/v1/internal/sofor-by-telegram/{TELEGRAM_ID}"
            ).mock(return_value=httpx.Response(200, json={"id": 1}))
            respx.post(f"{driver_bot.BACKEND_URL}/api/v1/internal/sefer-belge").mock(
                return_value=httpx.Response(200)
            )
            update = _make_update(caption=None)
            photo = MagicMock()
            photo.file_id = "file456"
            update.message.photo = [photo]
            file_obj = AsyncMock()
            file_obj.download_as_bytearray = AsyncMock(
                return_value=bytearray(b"jpgdata")
            )
            context = _make_context()
            context.bot.get_file = AsyncMock(return_value=file_obj)
            await driver_bot.handle_photo(update, context)
        update.message.reply_text.assert_awaited_once()
        assert "TIR Ekran" in update.message.reply_text.await_args.args[0]

    @pytest.mark.asyncio
    async def test_backend_upload_failure_reports_error(self):
        with respx.mock:
            respx.get(
                f"{driver_bot.BACKEND_URL}/api/v1/internal/sofor-by-telegram/{TELEGRAM_ID}"
            ).mock(return_value=httpx.Response(200, json={"id": 1}))
            respx.post(f"{driver_bot.BACKEND_URL}/api/v1/internal/sefer-belge").mock(
                return_value=httpx.Response(500)
            )
            update = _make_update(caption="sefer")
            photo = MagicMock()
            photo.file_id = "file789"
            update.message.photo = [photo]
            file_obj = AsyncMock()
            file_obj.download_as_bytearray = AsyncMock(
                return_value=bytearray(b"jpgdata")
            )
            context = _make_context()
            context.bot.get_file = AsyncMock(return_value=file_obj)
            await driver_bot.handle_photo(update, context)
        update.message.reply_text.assert_awaited_once()
        assert "kaydedilemedi" in update.message.reply_text.await_args.args[0]


class TestCmdPdf:
    @pytest.mark.asyncio
    async def test_wrong_arg_count_shows_usage(self):
        update = _make_update()
        await driver_bot.cmd_pdf(update, _make_context(["2026-01-01"]))
        update.message.reply_text.assert_awaited_once()
        assert "Kullanım" in update.message.reply_text.await_args.args[0]

    @pytest.mark.asyncio
    async def test_no_trips_in_range_reports_404(self):
        with respx.mock:
            respx.get(
                f"{driver_bot.BACKEND_URL}/api/v1/internal/sofor-pdf/{TELEGRAM_ID}"
            ).mock(return_value=httpx.Response(404))
            update = _make_update()
            await driver_bot.cmd_pdf(
                update, _make_context(["2026-01-01", "2026-01-31"])
            )
        update.message.reply_text.assert_awaited_once()
        assert "bulunamadı" in update.message.reply_text.await_args.args[0]

    @pytest.mark.asyncio
    async def test_success_sends_document(self):
        with respx.mock:
            respx.get(
                f"{driver_bot.BACKEND_URL}/api/v1/internal/sofor-pdf/{TELEGRAM_ID}"
            ).mock(return_value=httpx.Response(200, content=b"%PDF-fake"))
            update = _make_update()
            update.effective_chat.id = 999
            context = _make_context(["2026-01-01", "2026-01-31"])
            context.bot.send_document = AsyncMock()
            await driver_bot.cmd_pdf(update, context)
        context.bot.send_document.assert_awaited_once()


class TestCmdAriza:
    @pytest.mark.asyncio
    async def test_success_reports_case_opened(self):
        with respx.mock:
            respx.post(
                f"{driver_bot.BACKEND_URL}/api/v1/internal/driver-breakdown"
            ).mock(
                return_value=httpx.Response(
                    201, json={"arac_plakasi": "34 AB 123", "bakim_tipi": "ARIZA"}
                )
            )
            update = _make_update()
            await driver_bot.cmd_ariza(update, _make_context(["fren", "sesi"]))
        update.message.reply_text.assert_awaited_once()
        assert "34 AB 123" in update.message.reply_text.await_args.args[0]

    @pytest.mark.asyncio
    async def test_unresolvable_vehicle_reports_404(self):
        with respx.mock:
            respx.post(
                f"{driver_bot.BACKEND_URL}/api/v1/internal/driver-breakdown"
            ).mock(return_value=httpx.Response(404))
            update = _make_update()
            await driver_bot.cmd_ariza(update, _make_context(["acil", "lastik"]))
        update.message.reply_text.assert_awaited_once()
        assert "çözülemedi" in update.message.reply_text.await_args.args[0]


class TestCmdScore:
    @pytest.mark.asyncio
    async def test_unreachable_reports_error(self):
        with respx.mock:
            respx.get(
                f"{driver_bot.BACKEND_URL}/api/v1/internal/sofor-coaching/{TELEGRAM_ID}"
            ).mock(return_value=httpx.Response(404))
            update = _make_update()
            await driver_bot.cmd_score(update, _make_context())
        update.message.reply_text.assert_awaited_once()
        assert "ulaşılamıyor" in update.message.reply_text.await_args.args[0]

    @pytest.mark.asyncio
    async def test_success_shows_score(self):
        with respx.mock:
            respx.get(
                f"{driver_bot.BACKEND_URL}/api/v1/internal/sofor-coaching/{TELEGRAM_ID}"
            ).mock(
                return_value=httpx.Response(
                    200,
                    json={
                        "skor": 0.87,
                        "headline": "İyi gidiyor",
                        "priority": "high",
                        "top_suggestion": "Yavaşla",
                        "insights_count": 2,
                    },
                )
            )
            update = _make_update()
            await driver_bot.cmd_score(update, _make_context())
        update.message.reply_text.assert_awaited_once()
        text = update.message.reply_text.await_args.args[0]
        assert "0.87" in text
        assert "Yüksek" in text
