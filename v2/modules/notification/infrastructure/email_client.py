"""
E-posta gönderim servisi — stdlib smtplib kullanır, ek bağımlılık gerekmez.
Async: asyncio.to_thread ile event loop bloklanmaz.

Kullanım:
    await send_password_reset(email, token, name)
    await send_text(to="user@example.com", subject="...", body="...")

SMTP_HOST boşsa tüm metodlar sessizce no-op döner (dev/test uyumu).
"""

import asyncio
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Optional

from app.config import settings
from v2.modules.platform_infra.logging.logger import get_logger

logger = get_logger(__name__)


def _send_smtp_sync(
    to: str,
    subject: str,
    body_html: str,
    body_text: str,
) -> None:
    """Sync SMTP gönderim — asyncio.to_thread içinde çalışır."""
    if not settings.SMTP_HOST:
        logger.debug("SMTP_HOST ayarlanmamış — e-posta atlandı: %s → %s", subject, to)
        return

    password = (
        settings.SMTP_PASSWORD.get_secret_value() if settings.SMTP_PASSWORD else ""
    )

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = f"{settings.SMTP_FROM_NAME} <{settings.SMTP_FROM_EMAIL}>"
    msg["To"] = to
    msg.attach(MIMEText(body_text, "plain", "utf-8"))
    msg.attach(MIMEText(body_html, "html", "utf-8"))

    try:
        if settings.SMTP_USE_TLS:
            server = smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=10)
            server.ehlo()
            server.starttls()
        else:
            server = smtplib.SMTP_SSL(
                settings.SMTP_HOST, settings.SMTP_PORT, timeout=10
            )

        if settings.SMTP_USERNAME and password:
            server.login(settings.SMTP_USERNAME, password)

        server.sendmail(settings.SMTP_FROM_EMAIL, [to], msg.as_string())
        server.quit()
        logger.info("E-posta gönderildi: %s → %s", subject, to)
    except Exception as exc:
        logger.error("E-posta gönderilemedi: %s", exc)
        raise


async def send_text(to: str, subject: str, body: str) -> None:
    """Düz metin e-postası gönderir."""
    await asyncio.to_thread(_send_smtp_sync, to, subject, f"<pre>{body}</pre>", body)


async def send_password_reset(
    email: str, token: str, name: Optional[str] = None
) -> None:
    """Şifre sıfırlama e-postası gönderir."""
    display = name or email
    base_url = (
        settings.CORS_ORIGINS.split(",")[0].strip() if settings.CORS_ORIGINS else ""
    )
    reset_url = f"{base_url}/reset-password?token={token}"

    body_text = (
        f"Merhaba {display},\n\n"
        f"Şifre sıfırlama talebinizi aldık.\n\n"
        f"Bağlantı (1 saat geçerli):\n{reset_url}\n\n"
        f"Bu isteği siz yapmadıysanız bu e-postayı görmezden gelin.\n\n"
        f"LojiNext"
    )
    body_html = f"""<!DOCTYPE html>
<html lang="tr"><body style="font-family:sans-serif;max-width:480px;margin:auto">
<h2>Şifre Sıfırlama</h2>
<p>Merhaba <strong>{display}</strong>,</p>
<p>Şifre sıfırlama talebinizi aldık.</p>
<p>
  <a href="{reset_url}"
     style="display:inline-block;padding:12px 24px;background:#2563eb;color:#fff;
            border-radius:6px;text-decoration:none;font-weight:bold">
    Şifremi Sıfırla
  </a>
</p>
<p style="color:#888;font-size:12px">Bu bağlantı 1 saat geçerlidir.<br>
Bu isteği siz yapmadıysanız bu e-postayı görmezden gelin.</p>
</body></html>"""

    await asyncio.to_thread(
        _send_smtp_sync,
        email,
        "LojiNext — Şifre Sıfırlama",
        body_html,
        body_text,
    )
