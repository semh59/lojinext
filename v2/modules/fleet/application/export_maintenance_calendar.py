"""Feature D.2 — RFC 5545 (iCalendar) .ics üretici.

İki sert RFC kuralı:
  1. Her satır CRLF (`\\r\\n`) ile biter; TEXT değerlerde
     `\\` → `\\\\`, `\\n` → `\\n` (literal), `,` → `\\,`, `;` → `\\;`.
  2. Satırlar 75 oktet'i geçemez; uzun değerler CRLF + tek BOŞLUK ile katlanır.

UTF-8 multi-byte karakterleri (Türkçe ş/ğ/ı/ü) ortadan kırılmaz.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

LINE_MAX_BYTES = 75


def _escape_text(s: str) -> str:
    """RFC 5545 §3.3.11 — TEXT value escape.

    Sıra önemli: backslash önce, sonra special char'lar.
    """
    return (
        s.replace("\\", "\\\\")
        .replace("\r\n", "\\n")
        .replace("\n", "\\n")
        .replace("\r", "")
        .replace(",", "\\,")
        .replace(";", "\\;")
    )


def _fold_line(line: str, max_bytes: int = LINE_MAX_BYTES) -> str:
    """RFC 5545 §3.1 — satır katlama.

    UTF-8 multi-byte karakter ortadan ayrılmaz; en yakın güvenli bayttan
    kesilir, devam satırına TEK boşluk eklenir.
    """
    raw = line.encode("utf-8")
    if len(raw) <= max_bytes:
        return line

    parts: list[str] = []
    buf = b""
    for ch in line:
        ch_bytes = ch.encode("utf-8")
        # İlk satır max_bytes; devam satırları leading SPACE için 1 bayt eksiltilir
        budget = max_bytes if not parts else max_bytes - 1
        if len(buf) + len(ch_bytes) > budget:
            parts.append(buf.decode("utf-8"))
            buf = ch_bytes
        else:
            buf += ch_bytes
    if buf:
        parts.append(buf.decode("utf-8"))
    return "\r\n ".join(parts)


def _line(name: str, value: str) -> str:
    """`NAME:VALUE` satırı katla + CRLF'le bitir."""
    return _fold_line(f"{name}:{value}") + "\r\n"


def generate_ics_for_maintenance(bakim, arac) -> str:
    """Bir AracBakim + Arac kaydından RFC 5545 uyumlu .ics body üret.

    Args:
        bakim: AracBakim ORM nesnesi (id, bakim_tarihi, bakim_tipi,
               km_bilgisi, detaylar alanlarına erişilir).
        arac: Arac ORM nesnesi veya None (None ise plaka "?").

    Returns:
        CRLF satır sonlu, UTF-8 string. Caller `.encode('utf-8')` yapmalı.
    """
    # bakim_tarihi naive olabilir; UTC'e çevir
    bt = bakim.bakim_tarihi
    if bt.tzinfo is None:
        bt = bt.replace(tzinfo=timezone.utc)
    else:
        bt = bt.astimezone(timezone.utc)
    dt = bt.strftime("%Y%m%dT%H%M%SZ")
    # RFC 5545 §3.6.1: DTSTART == DTEND zero-duration event sayılır ve
    # Google Calendar/Outlook bunu göstermez. Bakım randevusu için
    # varsayılan 1 saatlik blok.
    dt_end = (bt + timedelta(hours=1)).strftime("%Y%m%dT%H%M%SZ")

    plaka = getattr(arac, "plaka", None) or "?"
    bakim_tipi = getattr(bakim, "bakim_tipi", None)
    # Enum'un .value alanını al; düz string ise olduğu gibi
    if hasattr(bakim_tipi, "value"):
        bakim_tipi = bakim_tipi.value
    bakim_tipi_s = str(bakim_tipi or "?")

    description_raw = (
        f"Plaka: {plaka}\n"
        f"Bakım tipi: {bakim_tipi_s}\n"
        f"Km: {bakim.km_bilgisi}\n"
        f"Detaylar: {(bakim.detaylar or '').strip()}"
    )
    summary = f"Bakım — {plaka} ({bakim_tipi_s})"

    parts = [
        "BEGIN:VCALENDAR\r\n",
        "VERSION:2.0\r\n",
        "PRODID:-//LojiNext//Maintenance//TR\r\n",
        "CALSCALE:GREGORIAN\r\n",
        "BEGIN:VEVENT\r\n",
        _line("UID", f"bakim-{bakim.id}-{uuid4().hex[:8]}@lojinext"),
        _line(
            "DTSTAMP",
            datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"),
        ),
        _line("DTSTART", dt),
        _line("DTEND", dt_end),
        _line("SUMMARY", _escape_text(summary)),
        _line("DESCRIPTION", _escape_text(description_raw)),
        "END:VEVENT\r\n",
        "END:VCALENDAR\r\n",
    ]
    return "".join(parts)
