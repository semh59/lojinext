"""Unit tests for v2.modules.notification.infrastructure.email_client."""

import smtplib
from unittest.mock import MagicMock, patch

import pytest


@pytest.mark.unit
class TestSendSmtpSync:
    def test_noop_when_smtp_host_empty(self):
        """No SMTP host configured → function returns without sending."""
        from v2.modules.notification.infrastructure import email_client as email_service

        with patch.object(email_service.settings, "SMTP_HOST", ""):
            # Should not raise and should not call smtplib
            with (
                patch("smtplib.SMTP") as mock_smtp,
                patch("smtplib.SMTP_SSL") as mock_ssl,
            ):
                email_service._send_smtp_sync(
                    "to@example.com", "subj", "<p>html</p>", "text"
                )
                mock_smtp.assert_not_called()
                mock_ssl.assert_not_called()

    def test_sends_via_starttls_when_use_tls_true(self):
        """SMTP_USE_TLS=True uses SMTP + starttls."""
        from v2.modules.notification.infrastructure import email_client as email_service

        mock_server = MagicMock()
        mock_server.starttls = MagicMock()
        mock_server.sendmail = MagicMock()
        mock_server.quit = MagicMock()

        with (
            patch.object(email_service.settings, "SMTP_HOST", "smtp.example.com"),
            patch.object(email_service.settings, "SMTP_PORT", 587),
            patch.object(email_service.settings, "SMTP_USE_TLS", True),
            patch.object(email_service.settings, "SMTP_USERNAME", ""),
            patch.object(email_service.settings, "SMTP_FROM_EMAIL", "from@example.com"),
            patch.object(email_service.settings, "SMTP_FROM_NAME", "Test"),
            patch("smtplib.SMTP", return_value=mock_server),
        ):
            email_service._send_smtp_sync("to@example.com", "subj", "<p>hi</p>", "hi")

        mock_server.starttls.assert_called_once()
        mock_server.sendmail.assert_called_once()
        mock_server.quit.assert_called_once()

    def test_sends_via_ssl_when_use_tls_false(self):
        """SMTP_USE_TLS=False uses SMTP_SSL directly."""
        from v2.modules.notification.infrastructure import email_client as email_service

        mock_server = MagicMock()

        with (
            patch.object(email_service.settings, "SMTP_HOST", "smtp.example.com"),
            patch.object(email_service.settings, "SMTP_PORT", 465),
            patch.object(email_service.settings, "SMTP_USE_TLS", False),
            patch.object(email_service.settings, "SMTP_USERNAME", ""),
            patch.object(email_service.settings, "SMTP_FROM_EMAIL", "from@example.com"),
            patch.object(email_service.settings, "SMTP_FROM_NAME", "Test"),
            patch("smtplib.SMTP_SSL", return_value=mock_server),
        ):
            email_service._send_smtp_sync("to@example.com", "subj", "<p>hi</p>", "hi")

        mock_server.sendmail.assert_called_once()

    def test_raises_on_smtp_error(self):
        """SMTP connection failure propagates the exception."""
        from v2.modules.notification.infrastructure import email_client as email_service

        with (
            patch.object(email_service.settings, "SMTP_HOST", "smtp.example.com"),
            patch.object(email_service.settings, "SMTP_PORT", 587),
            patch.object(email_service.settings, "SMTP_USE_TLS", True),
            patch.object(email_service.settings, "SMTP_FROM_EMAIL", "from@example.com"),
            patch.object(email_service.settings, "SMTP_FROM_NAME", "Test"),
            patch("smtplib.SMTP", side_effect=smtplib.SMTPConnectError(500, "refused")),
        ):
            with pytest.raises(smtplib.SMTPConnectError):
                email_service._send_smtp_sync(
                    "to@example.com", "subj", "<p>hi</p>", "hi"
                )

    def test_logs_in_when_credentials_provided(self):
        """SMTP_USERNAME + SMTP_PASSWORD → server.login() called."""
        from unittest.mock import MagicMock, patch

        from v2.modules.notification.infrastructure import email_client as email_service

        mock_server = MagicMock()
        fake_secret = MagicMock()
        fake_secret.get_secret_value.return_value = "secret123"

        with (
            patch.object(email_service.settings, "SMTP_HOST", "smtp.example.com"),
            patch.object(email_service.settings, "SMTP_PORT", 587),
            patch.object(email_service.settings, "SMTP_USE_TLS", True),
            patch.object(email_service.settings, "SMTP_USERNAME", "user@example.com"),
            patch.object(email_service.settings, "SMTP_PASSWORD", fake_secret),
            patch.object(email_service.settings, "SMTP_FROM_EMAIL", "from@example.com"),
            patch.object(email_service.settings, "SMTP_FROM_NAME", "Test"),
            patch("smtplib.SMTP", return_value=mock_server),
        ):
            email_service._send_smtp_sync("to@example.com", "subj", "<p>hi</p>", "hi")

        mock_server.login.assert_called_once_with("user@example.com", "secret123")


@pytest.mark.unit
class TestSendText:
    @pytest.mark.asyncio
    async def test_send_text_noop_when_no_smtp_host(self):
        """send_text with no SMTP host completes without error."""
        from v2.modules.notification.infrastructure import email_client as email_service

        with patch.object(email_service.settings, "SMTP_HOST", ""):
            await email_service.send_text("to@example.com", "Hello", "body text")


@pytest.mark.unit
class TestSendPasswordReset:
    @pytest.mark.asyncio
    async def test_password_reset_noop_when_no_smtp_host(self):
        """send_password_reset with no SMTP host completes without error."""
        from v2.modules.notification.infrastructure import email_client as email_service

        with patch.object(email_service.settings, "SMTP_HOST", ""):
            await email_service.send_password_reset("user@example.com", "tok123", "Ali")

    @pytest.mark.asyncio
    async def test_password_reset_builds_reset_url(self):
        """Reset URL includes the token and is passed to _send_smtp_sync."""
        from v2.modules.notification.infrastructure import email_client as email_service

        calls = []

        def capture(to, subject, html, text):
            calls.append((to, subject, html, text))

        with (
            patch.object(email_service.settings, "SMTP_HOST", "smtp.example.com"),
            patch.object(email_service.settings, "SMTP_PORT", 587),
            patch.object(email_service.settings, "SMTP_USE_TLS", True),
            patch.object(email_service.settings, "SMTP_USERNAME", ""),
            patch.object(
                email_service.settings, "SMTP_FROM_EMAIL", "noreply@example.com"
            ),
            patch.object(email_service.settings, "SMTP_FROM_NAME", "LojiNext"),
            patch.object(
                email_service.settings, "CORS_ORIGINS", "https://app.example.com"
            ),
            patch(
                "v2.modules.notification.infrastructure.email_client._send_smtp_sync",
                side_effect=capture,
            ),
        ):
            await email_service.send_password_reset(
                "user@example.com", "tok-xyz", "Ali"
            )

        assert len(calls) == 1
        to, subject, html, text = calls[0]
        assert to == "user@example.com"
        assert "tok-xyz" in html
        assert "tok-xyz" in text
        assert "Ali" in html
