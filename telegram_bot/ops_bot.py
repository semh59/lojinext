import logging
import os
import subprocess
import threading
import time

import httpx
import uvicorn
from fastapi import FastAPI, Header, HTTPException
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

logger = logging.getLogger(__name__)

BACKEND_URL = os.environ.get("BACKEND_URL", "http://backend:8000")
PROMETHEUS_URL = os.environ.get("PROMETHEUS_URL", "http://prometheus:9090")
OPS_BOT_TOKEN = os.environ["TELEGRAM_OPS_BOT_TOKEN"]
OPS_CHAT_ID = os.environ["TELEGRAM_OPS_CHAT_ID"]

# Comma-separated Telegram user IDs allowed to run destructive commands.
# If unset, /yeniden_baslat is disabled entirely.
_raw_admin_ids = os.environ.get("OPS_ADMIN_TELEGRAM_IDS", "")
OPS_ADMIN_IDS: frozenset[int] = frozenset(
    int(x.strip()) for x in _raw_admin_ids.split(",") if x.strip().isdigit()
)

# Shared secret expected as "Authorization: Bearer <secret>" from internal
# services (Alertmanager, backend telegram_notifier.py).
WEBHOOK_SECRET = os.environ.get("OPS_WEBHOOK_SECRET", "")

# Ops bot'un başlatılmasında Application oluşturulur; webhook'tan da mesaj göndermek
# için kullanılır (global olarak tutulur).
_app: Application | None = None

# Rate limiter: aynı hata anahtarı için minimum 60 saniye bekleme
_rate_limit: dict[str, float] = {}
_rate_lock = threading.Lock()
_RATE_WINDOW_CRITICAL = 60  # saniye — critical için 1 dk
_RATE_WINDOW_DEFAULT = 300  # saniye — error/diğerleri için 5 dk


def _is_rate_limited(key: str, level: str = "error") -> bool:
    window = _RATE_WINDOW_CRITICAL if level == "critical" else _RATE_WINDOW_DEFAULT
    now = time.monotonic()
    with _rate_lock:
        # Prune stale entries
        stale = [
            k for k, v in _rate_limit.items() if now - v > _RATE_WINDOW_DEFAULT * 2
        ]
        for k in stale:
            del _rate_limit[k]
        last = _rate_limit.get(key, 0)
        if now - last < window:
            return True
        _rate_limit[key] = now
        return False


# ── Komutlar ────────────────────────────────────────────────────────────────


def _is_from_ops_chat(update: Update) -> bool:
    """2026-07-01 prod-grade denetimi P1: `/durum` ve `/uyarilar` önceden
    hiçbir kimlik kontrolü yapmıyordu — bot username'ini bulan HERHANGİ bir
    Telegram kullanıcısı backend sağlık durumunu ve tüm aktif Prometheus
    alarmlarını görebiliyordu (bilgi sızıntısı/recon). Artık yalnız
    yapılandırılmış OPS_CHAT_ID'den (ops ekibinin bulunduğu grup) gelen
    mesajlara yanıt verilir."""
    chat = update.effective_chat
    return chat is not None and str(chat.id) == OPS_CHAT_ID


async def cmd_durum(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _is_from_ops_chat(update):
        logger.warning(
            "Yetkisiz /durum girişimi: chat_id=%s",
            update.effective_chat.id if update.effective_chat else None,
        )
        return
    try:
        r = httpx.get(f"{BACKEND_URL}/api/v1/health/", timeout=5)
        durum = "✅ Çevrimiçi" if r.status_code == 200 else f"❌ HTTP {r.status_code}"
        metin = f"Backend: {durum}"
    except Exception as exc:
        metin = f"❌ Backend'e ulaşılamadı: {exc}"
    await update.message.reply_text(metin)  # type: ignore[union-attr]


async def cmd_uyarilar(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _is_from_ops_chat(update):
        logger.warning(
            "Yetkisiz /uyarilar girişimi: chat_id=%s",
            update.effective_chat.id if update.effective_chat else None,
        )
        return
    try:
        r = httpx.get(f"{PROMETHEUS_URL}/api/v1/alerts", timeout=5)
        alerts = r.json().get("data", {}).get("alerts", [])
        firing = [a for a in alerts if a["state"] == "firing"]
        if not firing:
            await update.message.reply_text("✅ Aktif uyarı yok")  # type: ignore[union-attr]
            return
        lines = [
            f"🚨 {a['labels']['alertname']} [{a['labels'].get('severity', '?')}]"
            for a in firing
        ]
        await update.message.reply_text("\n".join(lines))  # type: ignore[union-attr]
    except Exception as exc:
        await update.message.reply_text(f"❌ Prometheus'a ulaşılamadı: {exc}")  # type: ignore[union-attr]


async def cmd_yeniden_baslat(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    caller_id = update.effective_user.id if update.effective_user else None
    if not OPS_ADMIN_IDS:
        await update.message.reply_text(  # type: ignore[union-attr]
            "❌ /yeniden_baslat devre dışı (OPS_ADMIN_TELEGRAM_IDS ayarlanmamış)."
        )
        return
    if caller_id not in OPS_ADMIN_IDS:
        logger.warning("Yetkisiz /yeniden_baslat girişimi: user_id=%s", caller_id)
        await update.message.reply_text(  # type: ignore[union-attr]
            "❌ Bu komutu çalıştırma yetkiniz yok."
        )
        return
    if not context.args:
        await update.message.reply_text("Kullanım: /yeniden_baslat <servis_adı>")  # type: ignore[union-attr]
        return
    servis = context.args[0]
    IZIN_VERILEN = {"backend", "worker", "redis", "celery-exporter", "ocr-service"}
    if servis not in IZIN_VERILEN:
        await update.message.reply_text(
            f"❌ İzin verilmeyen servis: {servis}\nİzin verilenler: {', '.join(IZIN_VERILEN)}"
        )  # type: ignore[union-attr]
        return
    # Docker socket mount edilmiş olmalı: -v /var/run/docker.sock:/var/run/docker.sock
    # Container adı docker compose projesi + servis adından oluşur
    for container_pattern in [f"lojinext-{servis}-1", f"lojinext_{servis}_1"]:
        result = subprocess.run(
            ["docker", "restart", container_pattern],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode == 0:
            await update.message.reply_text(f"✅ {servis} yeniden başlatıldı")  # type: ignore[union-attr]
            return
    await update.message.reply_text(
        f"❌ {servis} yeniden başlatılamadı: container bulunamadı"
    )  # type: ignore[union-attr]


# ── Alertmanager webhook ─────────────────────────────────────────────────────

webhook_app = FastAPI()


def _check_webhook_secret(authorization: str | None) -> None:
    """Validate the shared secret sent as `Authorization: Bearer <secret>`.

    2026-07-01 prod-grade denetimi P1: önceki davranış `WEBHOOK_SECRET` boşsa
    (yapılandırılmamışsa) kontrolü tamamen atlıyordu (fail-open) — bu servisin
    portu (8080) host'a expose edildiği için harici biri secret olmadan
    doğrudan sahte alarm/hata/feedback POST'layabiliyordu. Artık
    `WEBHOOK_SECRET` yapılandırılmamışsa TÜM istekler reddedilir (fail-closed).
    Bearer şeması Alertmanager'ın `http_config.authorization` mekanizmasıyla
    ve backend'in `telegram_notifier.py`'siyle uyumlu — eski özel
    `X-Webhook-Secret` header'ı yerine standart `Authorization` kullanılıyor.
    """
    if not WEBHOOK_SECRET:
        raise HTTPException(
            status_code=503,
            detail="OPS_WEBHOOK_SECRET not configured — webhook disabled",
        )
    expected = f"Bearer {WEBHOOK_SECRET}"
    if authorization != expected:
        raise HTTPException(status_code=403, detail="Invalid webhook secret")


@webhook_app.post("/webhook/alertmanager")
async def alertmanager_webhook(
    payload: dict, authorization: str | None = Header(None)
) -> dict:
    _check_webhook_secret(authorization)
    if _app is None:
        return {"ok": False, "error": "bot not ready"}
    for alert in payload.get("alerts", []):
        status = "🚨 ALARM" if alert["status"] == "firing" else "✅ ÇÖZÜLDÜ"
        name = alert["labels"].get("alertname", "?")
        severity = alert["labels"].get("severity", "?")
        summary = alert.get("annotations", {}).get("summary", "")
        msg = f"{status} [{severity.upper()}]: {name}\n{summary}"
        try:
            await _app.bot.send_message(chat_id=OPS_CHAT_ID, text=msg)
        except Exception as exc:
            logger.error("Telegram mesaj gönderilemedi: %s", exc)
    return {"ok": True}


@webhook_app.post("/webhook/error")
async def error_webhook(
    payload: dict, authorization: str | None = Header(None)
) -> dict:
    """Backend ve servislerden gelen hata bildirimlerini Telegram'a iletir.

    Payload: {"level": "error|critical", "message": str, "path": str, "trace_id": str}
    Rate limit: aynı (level+path) kombinasyonu 60 saniyede bir.
    """
    _check_webhook_secret(authorization)
    if _app is None:
        return {"ok": False, "error": "bot not ready"}

    level = payload.get("level", "error").lower()
    message = payload.get("message", "")
    path = payload.get("path", "")
    trace_id = payload.get("trace_id", "")

    rate_key = f"{level}:{path}:{message[:80]}"
    if _is_rate_limited(rate_key, level=level):
        logger.debug("Rate-limited error notification: level=%s path=%s", level, path)
        return {"ok": True, "skipped": "rate_limited"}

    emoji = "🔴" if level == "critical" else "🟠"
    lines = [f"{emoji} [{level.upper()}] {path}"]
    if message:
        lines.append(message[:300])
    if trace_id:
        lines.append(f"trace_id: {trace_id}")

    try:
        await _app.bot.send_message(chat_id=OPS_CHAT_ID, text="\n".join(lines))
    except Exception as exc:
        logger.error("Telegram hata bildirimi gönderilemedi: %s", exc)
        return {"ok": False, "error": str(exc)}

    return {"ok": True}


@webhook_app.post("/webhook/feedback")
async def feedback_webhook(
    payload: dict, authorization: str | None = Header(None)
) -> dict:
    """Pilot kullanıcı geri bildirimlerini Telegram OPS kanalına iletir.

    Payload: {"message": str, "username": str, "page": str}
    """
    _check_webhook_secret(authorization)
    if _app is None:
        return {"ok": False, "error": "bot not ready"}

    message = str(payload.get("message", "")).strip()
    if not message:
        return {"ok": False, "error": "empty message"}
    username = payload.get("username", "")
    page = payload.get("page", "")

    lines = ["💬 [PILOT FEEDBACK]"]
    if username:
        lines.append(f"Kullanıcı: {username}")
    if page:
        lines.append(f"Sayfa: {page}")
    lines.append(message[:1000])

    try:
        await _app.bot.send_message(chat_id=OPS_CHAT_ID, text="\n".join(lines))
    except Exception as exc:
        logger.error("Telegram feedback bildirimi gönderilemedi: %s", exc)
        return {"ok": False, "error": str(exc)}
    return {"ok": True}


@webhook_app.get("/health")
def webhook_health() -> dict:
    return {"status": "ok"}


# ── Başlatıcı ────────────────────────────────────────────────────────────────


def _run_webhook_server() -> None:
    uvicorn.run(webhook_app, host="0.0.0.0", port=8080, log_level="warning")


def run_ops_bot() -> None:
    global _app
    logging.basicConfig(level=logging.INFO)
    _app = Application.builder().token(OPS_BOT_TOKEN).build()
    _app.add_handler(CommandHandler("durum", cmd_durum))
    _app.add_handler(CommandHandler("uyarilar", cmd_uyarilar))
    _app.add_handler(CommandHandler("yeniden_baslat", cmd_yeniden_baslat))

    # FastAPI webhook server'ı ayrı daemon thread'de çalıştır
    t = threading.Thread(target=_run_webhook_server, daemon=True)
    t.start()

    logger.info("Ops botu başlatılıyor (polling modu)...")
    _app.run_polling()
