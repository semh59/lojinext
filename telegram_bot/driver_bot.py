import html
import logging
import os

import httpx
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)
from token_resolver import resolve_bot_token

logger = logging.getLogger(__name__)

BACKEND_URL = os.environ.get("BACKEND_URL", "http://backend:8000")
_INTERNAL_SECRET = os.environ.get("INTERNAL_API_SECRET", "")
DRIVER_BOT_TOKEN = resolve_bot_token(
    "telegram_driver_bot",
    BACKEND_URL,
    _INTERNAL_SECRET,
    os.environ.get("TELEGRAM_DRIVER_BOT_TOKEN", ""),
)
if not DRIVER_BOT_TOKEN:
    raise RuntimeError(
        "Telegram driver bot token yapılandırılmamış "
        "(ne admin panelden ne TELEGRAM_DRIVER_BOT_TOKEN .env'den)"
    )


def _internal_headers() -> dict:
    """Return the shared-secret header required by /api/v1/internal/* endpoints."""
    return {"X-Internal-Token": _INTERNAL_SECRET} if _INTERNAL_SECRET else {}


# ── Yardımcılar ──────────────────────────────────────────────────────────────


async def _get_sofor(telegram_id: str) -> dict | None:
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            r = await client.get(
                f"{BACKEND_URL}/api/v1/internal/sofor-by-telegram/{telegram_id}",
                headers=_internal_headers(),
            )
        return r.json() if r.status_code == 200 else None
    except Exception:
        return None


# ── Fotoğraf işleyici ────────────────────────────────────────────────────────


async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    telegram_id = str(update.effective_user.id)  # type: ignore[union-attr]
    sofor = await _get_sofor(telegram_id)
    if not sofor:
        await update.message.reply_text(  # type: ignore[union-attr]
            "❌ Telegram ID'niz sisteme kayıtlı değil. Yöneticinizle iletişime geçin."
        )
        return

    caption = (update.message.caption or "").lower()  # type: ignore[union-attr]
    if "yakıt" in caption or "yakit" in caption:
        belge_tipi = "yakit_fisi"
    elif "sefer" in caption:
        belge_tipi = "sefer_fisi"
    else:
        belge_tipi = "tir_ekran"

    photo = update.message.photo[-1]  # type: ignore[union-attr]
    file_obj = await context.bot.get_file(photo.file_id)
    file_bytes = bytes(await file_obj.download_as_bytearray())

    try:
        async with httpx.AsyncClient(timeout=20) as client:
            r = await client.post(
                f"{BACKEND_URL}/api/v1/internal/sefer-belge",
                headers=_internal_headers(),
                files={"file": (f"{photo.file_id}.jpg", file_bytes, "image/jpeg")},
                data={
                    "telegram_id": telegram_id,
                    "belge_tipi": belge_tipi,
                    "telegram_mesaj_id": str(update.message.message_id),  # type: ignore[union-attr]
                },
            )
        if r.status_code == 200:
            tipler = {
                "yakit_fisi": "Yakıt Fişi",
                "sefer_fisi": "Sefer Fişi",
                "tir_ekran": "TIR Ekran",
            }
            await update.message.reply_text(  # type: ignore[union-attr]
                f"✅ {tipler.get(belge_tipi, belge_tipi)} alındı, OCR işleniyor...\n"
                "Tip belirtmek için fotoğrafa 'yakıt', 'sefer' veya 'ekran' yazabilirsiniz."
            )
        else:
            await update.message.reply_text("❌ Belge kaydedilemedi, tekrar deneyin.")  # type: ignore[union-attr]
    except Exception as exc:
        logger.error("Belge gönderim hatası: %s", exc)
        await update.message.reply_text("❌ Sunucuya bağlanılamadı, tekrar deneyin.")  # type: ignore[union-attr]


# ── Komutlar ─────────────────────────────────────────────────────────────────


async def cmd_pdf(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    telegram_id = str(update.effective_user.id)  # type: ignore[union-attr]
    if len(context.args or []) != 2:
        await update.message.reply_text(
            "Kullanım: /pdf YYYY-AA-GG YYYY-AA-GG\nÖrnek: /pdf 2025-01-01 2025-01-31"
        )  # type: ignore[union-attr]
        return
    try:
        async with httpx.AsyncClient(timeout=60) as client:
            r = await client.get(
                f"{BACKEND_URL}/api/v1/internal/sofor-pdf/{telegram_id}",
                headers=_internal_headers(),
                params={
                    "baslangic_tarihi": context.args[0],
                    "bitis_tarihi": context.args[1],
                },
            )
        if r.status_code == 200:
            await context.bot.send_document(
                chat_id=update.effective_chat.id,  # type: ignore[union-attr]
                document=r.content,
                filename=f"seferler_{context.args[0]}_{context.args[1]}.pdf",
                caption="Onaylanmış seferleriniz",
            )
        elif r.status_code == 404:
            await update.message.reply_text(
                "❌ Belirtilen tarih aralığında onaylanmış sefer bulunamadı."
            )  # type: ignore[union-attr]
        else:
            await update.message.reply_text("❌ PDF oluşturulamadı.")  # type: ignore[union-attr]
    except Exception as exc:
        logger.error("PDF isteği hatası: %s", exc)
        await update.message.reply_text("❌ Sunucuya bağlanılamadı.")  # type: ignore[union-attr]


async def cmd_seferlerim(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    telegram_id = str(update.effective_user.id)  # type: ignore[union-attr]
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.get(
                f"{BACKEND_URL}/api/v1/internal/sofor-seferler/{telegram_id}",
                headers=_internal_headers(),
                params={"limit": 10},
            )
        if r.status_code != 200:
            await update.message.reply_text("❌ Bilgi alınamadı.")  # type: ignore[union-attr]
            return
        seferler = r.json()
        if not seferler:
            await update.message.reply_text("Onaylanmış sefer bulunamadı.")  # type: ignore[union-attr]
            return
        lines = [
            f"{'✅' if s.get('onay_durumu') == 'onaylandi' else '⏳'} {s.get('tarih', '')} — {s.get('cikis_yeri', '?')}→{s.get('varis_yeri', '?')}"
            for s in seferler
        ]
        await update.message.reply_text("\n".join(lines))  # type: ignore[union-attr]
    except Exception as exc:
        logger.error("Sefer listesi hatası: %s", exc)
        await update.message.reply_text("❌ Sunucuya bağlanılamadı.")  # type: ignore[union-attr]


async def cmd_yardim(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    metin = (
        "🚛 LojiNext Şoför Botu\n\n"
        "📷 Fotoğraf gönderin:\n"
        "  • Başlığa 'yakıt' yazın → Yakıt Fişi\n"
        "  • Başlığa 'sefer' yazın → Sefer Fişi\n"
        "  • Başlık yok → TIR Ekran\n\n"
        "📋 Komutlar:\n"
        "  /seferlerim — Son 10 onaylı sefer\n"
        "  /pdf YYYY-AA-GG YYYY-AA-GG — PDF indir\n"
        "  /score — Skorun + bu haftanın özeti\n"
        "  /oneriler — Aktif koçluk önerileri\n"
        "  /ariza <açıklama> — Aracında arıza bildir (acil için başına 'acil')\n"
        "  /yardim — Bu mesaj"
    )
    await update.message.reply_text(metin)  # type: ignore[union-attr]


async def cmd_ariza(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Sürücünün son seferindeki araç için açık arıza/acil kaydı açar.

    Kullanım: /ariza fren sesi geliyor   → ARIZA
              /ariza acil lastik patladı → ACIL
    Araç sürücünün en son seferinden otomatik çözülür (plaka girilmez).
    """
    telegram_id = str(update.effective_user.id)  # type: ignore[union-attr]
    detaylar = " ".join(context.args).strip() if context.args else ""
    acil = detaylar.lower().startswith("acil")

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.post(
                f"{BACKEND_URL}/api/v1/internal/driver-breakdown",
                json={"telegram_id": telegram_id, "detaylar": detaylar, "acil": acil},
                headers=_internal_headers(),
            )
    except Exception as exc:
        logger.warning("Arıza bildirimi gönderilemedi: %s", exc)
        await update.message.reply_text(  # type: ignore[union-attr]
            "❌ Arıza bildirimi şu an gönderilemedi, lütfen tekrar deneyin."
        )
        return

    if r.status_code == 201:
        data = r.json()
        plaka = data.get("arac_plakasi") or f"#{data.get('arac_id')}"
        tip = "ACİL" if data.get("bakim_tipi") == "ACIL" else "Arıza"
        await update.message.reply_text(  # type: ignore[union-attr]
            f"✅ {tip} kaydı açıldı: {html.escape(str(plaka))}\n"
            "Operasyon ekibi bilgilendirildi."
        )
    elif r.status_code == 404:
        await update.message.reply_text(  # type: ignore[union-attr]
            "❌ Aracınız çözülemedi. Telegram ID'niz kayıtlı değilse veya hiç "
            "seferiniz yoksa yöneticinizle iletişime geçin."
        )
    else:
        await update.message.reply_text(  # type: ignore[union-attr]
            "❌ Arıza bildirimi alınamadı, lütfen tekrar deneyin."
        )


# ── Feature A.4 — koçluk komutları ──────────────────────────────────────────


async def _fetch_coaching_snapshot(telegram_id: str) -> dict | None:
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            r = await client.get(
                f"{BACKEND_URL}/api/v1/internal/sofor-coaching/{telegram_id}",
                headers=_internal_headers(),
            )
        return r.json() if r.status_code == 200 else None
    except Exception as exc:
        logger.warning("Coaching snapshot fetch failed: %s", exc)
        return None


_PRIORITY_LABELS = {"low": "Düşük", "medium": "Orta", "high": "Yüksek"}


async def cmd_score(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    telegram_id = str(update.effective_user.id)  # type: ignore[union-attr]
    data = await _fetch_coaching_snapshot(telegram_id)
    if data is None:
        await update.message.reply_text(  # type: ignore[union-attr]
            "❌ Skorunuza şu an ulaşılamıyor. Telegram ID'niz kayıtlı değilse "
            "yöneticinizle iletişime geçin.",
        )
        return

    skor = f"{float(data.get('skor', 0)):.2f}"
    headline = html.escape(str(data.get("headline") or ""))
    priority_label = _PRIORITY_LABELS.get(str(data.get("priority", "low")), "Düşük")
    top = data.get("top_suggestion")
    insights_count = int(data.get("insights_count") or 0)

    lines = [
        f"📊 <b>Skor</b>: {skor}",
        f"📰 <b>Bu hafta</b>: {headline}",
        f"🎯 <b>Öncelik</b>: {priority_label}",
    ]
    if top:
        lines.append("")
        lines.append(f"💡 <b>Öneri</b>: {html.escape(str(top))}")
    if insights_count > 1:
        lines.append("")
        lines.append(f"ℹ️ Tüm öneriler için /oneriler yazın ({insights_count} adet)")

    await update.message.reply_text(  # type: ignore[union-attr]
        "\n".join(lines), parse_mode="HTML"
    )


async def cmd_oneriler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    telegram_id = str(update.effective_user.id)  # type: ignore[union-attr]
    data = await _fetch_coaching_snapshot(telegram_id)
    if data is None:
        await update.message.reply_text(  # type: ignore[union-attr]
            "❌ Önerilere şu an ulaşılamıyor.",
        )
        return

    # Snapshot tek satır verir; tüm liste için engine'i tekrar çağıracak ayrı
    # endpoint açmadan, top_suggestion + insights_count ile özet veriyoruz.
    headline = html.escape(str(data.get("headline") or ""))
    top = data.get("top_suggestion")
    insights_count = int(data.get("insights_count") or 0)

    if insights_count == 0:
        await update.message.reply_text(  # type: ignore[union-attr]
            "✅ Şu an için aktif koçluk önerisi yok.\nÖzet: " + headline
        )
        return

    body = [
        f"📋 <b>Koçluk Önerileri</b> ({insights_count})",
        "",
        f"<i>{headline}</i>",
    ]
    if top:
        body.append("")
        body.append(f"1. {html.escape(str(top))}")
    if insights_count > 1:
        body.append("")
        body.append(
            "ℹ️ Detaylı liste için yöneticinizden /coaching panelini açmasını isteyin."
        )

    await update.message.reply_text(  # type: ignore[union-attr]
        "\n".join(body), parse_mode="HTML"
    )


# ── Başlatıcı ────────────────────────────────────────────────────────────────


def run_driver_bot() -> None:
    logging.basicConfig(level=logging.INFO)
    app = Application.builder().token(DRIVER_BOT_TOKEN).build()
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(CommandHandler("pdf", cmd_pdf))
    app.add_handler(CommandHandler("seferlerim", cmd_seferlerim))
    app.add_handler(CommandHandler("yardim", cmd_yardim))
    app.add_handler(CommandHandler("score", cmd_score))
    app.add_handler(CommandHandler("oneriler", cmd_oneriler))
    app.add_handler(CommandHandler("ariza", cmd_ariza))
    logger.info("Şoför botu başlatılıyor (polling modu)...")
    app.run_polling()
