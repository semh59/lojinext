"""Feature D.2 — .ics generator RFC 5545 testleri."""

from __future__ import annotations

import re
from datetime import datetime, timezone


# ── _escape_text ────────────────────────────────────────────────────────
def test_escape_text_order_backslash_first():
    """RFC 5545 §3.3.11: backslash escape önce, sonra special char."""
    from app.core.services.ics_generator import _escape_text

    # Önce gelen \ → \\, sonra \n → \n (literal) olmalı
    src = "satır1\nsatır2,virgül;noktalı"
    out = _escape_text(src)
    assert "\\n" in out  # newline literal escape
    assert "\\," in out  # comma escape
    assert "\\;" in out  # semicolon escape
    # Gerçek newline kalmamalı
    assert "\n" not in out


def test_escape_text_backslash_doubled():
    from app.core.services.ics_generator import _escape_text

    # Mevcut \ önce \\ olur, sonra newline escape edilir
    src = "a\\b\nc"
    out = _escape_text(src)
    # \ → \\, \n → \n (literal "\\n")
    assert out == "a\\\\b\\nc"


# ── _fold_line ──────────────────────────────────────────────────────────
def test_fold_line_short_unchanged():
    """75 oktet altında olan satır değişmez."""
    from app.core.services.ics_generator import _fold_line

    short = "DESCRIPTION:kısa metin"
    assert _fold_line(short) == short


def test_fold_line_long_split_with_crlf_space():
    """Uzun satır CRLF + boşluk ile katlanır."""
    from app.core.services.ics_generator import _fold_line

    long_line = "DESCRIPTION:" + ("x" * 200)
    out = _fold_line(long_line)
    # CRLF + boşluk delimiter
    assert "\r\n " in out
    # Hiçbir parça (ilk hariç) 75 byte'tan büyük olmamalı
    pieces = out.split("\r\n ")
    # Her parça (ilk dahil) 75 byte sınırını aşmamalı; devam satırlarında
    # leading SPACE de bütçeye dahil edildiği için +1 hesap
    assert len(pieces[0].encode("utf-8")) <= 75
    for p in pieces[1:]:
        # devam satırı (leading space hariç) 75-1=74 byte cap
        assert len(p.encode("utf-8")) <= 74


def test_fold_line_utf8_multibyte_not_split_midchar():
    """Türkçe karakter ortadan bölünmemeli."""
    from app.core.services.ics_generator import _fold_line

    # 50+ Türkçe karakter — her biri 2 byte → satır kesin katlanır
    long = "DESCRIPTION:" + ("ş" * 60)
    out = _fold_line(long)
    # Sonuç decode edilebilmeli (mid-char break yok)
    assert out.encode("utf-8").decode("utf-8") == out
    # Her parçanın kendi başına decode edilebilir olması gerekiyor
    for p in out.split("\r\n "):
        p.encode("utf-8").decode("utf-8")  # raises if broken


# ── generate_ics_for_maintenance ───────────────────────────────────────
class _StubBakim:
    """AracBakim ORM nesnesi yerine kullanılır."""

    def __init__(
        self,
        *,
        id,
        bakim_tarihi,
        bakim_tipi="PERIYODIK",
        km_bilgisi=250_000,
        detaylar="",
    ):
        self.id = id
        self.bakim_tarihi = bakim_tarihi
        self.bakim_tipi = bakim_tipi
        self.km_bilgisi = km_bilgisi
        self.detaylar = detaylar


class _StubArac:
    def __init__(self, plaka):
        self.plaka = plaka


def test_generate_ics_envelope_and_event():
    from app.core.services.ics_generator import generate_ics_for_maintenance

    bakim = _StubBakim(
        id=42,
        bakim_tarihi=datetime(2026, 6, 15, 10, 0, 0, tzinfo=timezone.utc),
        bakim_tipi="PERIYODIK",
        km_bilgisi=250_000,
        detaylar="Yağ + filtre değişimi",
    )
    out = generate_ics_for_maintenance(bakim, _StubArac("34 ABC 123"))

    # Zorunlu zarflar
    assert "BEGIN:VCALENDAR\r\n" in out
    assert "END:VCALENDAR\r\n" in out
    assert "BEGIN:VEVENT\r\n" in out
    assert "END:VEVENT\r\n" in out
    assert "VERSION:2.0" in out
    assert "PRODID:-//LojiNext//Maintenance//TR" in out

    # Olay alanları
    assert "DTSTART:20260615T100000Z" in out
    assert re.search(r"UID:bakim-42-[a-f0-9]{8}@lojinext", out)
    assert "SUMMARY:Bakım — 34 ABC 123 (PERIYODIK)" in out


def test_generate_ics_multiline_description_escaped():
    """Detaylar newline'lı geldiğinde tek DESCRIPTION satırında escaped."""
    from app.core.services.ics_generator import generate_ics_for_maintenance

    bakim = _StubBakim(
        id=1,
        bakim_tarihi=datetime(2026, 6, 1, 8, 0, 0, tzinfo=timezone.utc),
        detaylar="satır1\nsatır2\nsatır3",
    )
    out = generate_ics_for_maintenance(bakim, _StubArac("34 X 1"))

    # DESCRIPTION satırını çıkar (folding'li olabilir)
    desc_match = re.search(r"DESCRIPTION:.*?(?=\r\n[A-Z])", out, re.DOTALL)
    assert desc_match is not None
    desc = desc_match.group(0)
    # Literal \n escape kullanılmalı
    assert "\\n" in desc
    # Fold markerlarını ("\r\n " = CRLF + space) kaldır → mantıksal değer
    unfolded = desc.replace("\r\n ", "")
    # Logical newline (escape edilmemiş tek \n) kalmamalı
    # Sadece "\\n" (literal backslash + n) görünmeli
    assert "\n" not in unfolded
    assert "satır1\\nsatır2\\nsatır3" in unfolded


def test_generate_ics_naive_datetime_treated_as_utc():
    """tzinfo=None datetime UTC kabul edilir, ZuluZ formatı."""
    from app.core.services.ics_generator import generate_ics_for_maintenance

    naive = datetime(2026, 6, 15, 10, 0, 0)  # no tzinfo
    bakim = _StubBakim(id=99, bakim_tarihi=naive)
    out = generate_ics_for_maintenance(bakim, _StubArac("34 X 1"))
    assert "DTSTART:20260615T100000Z" in out


def test_generate_ics_handles_enum_bakim_tipi():
    """BakimTipi enum'u .value ile string'e çevrilir."""
    from app.core.services.ics_generator import generate_ics_for_maintenance
    from app.database.models import BakimTipi

    bakim = _StubBakim(
        id=1,
        bakim_tarihi=datetime(2026, 6, 1, tzinfo=timezone.utc),
        bakim_tipi=BakimTipi.PERIYODIK,
    )
    out = generate_ics_for_maintenance(bakim, _StubArac("34 X 1"))
    assert "PERIYODIK" in out
    assert "BakimTipi" not in out  # __str__ leak'i yok


def test_generate_ics_utf8_round_trip():
    """Türkçe karakterler UTF-8 round-trip'te bozulmaz."""
    from app.core.services.ics_generator import generate_ics_for_maintenance

    bakim = _StubBakim(
        id=1,
        bakim_tarihi=datetime(2026, 6, 1, tzinfo=timezone.utc),
        detaylar="ş ğ ı İ ü Ö Ç",
    )
    out = generate_ics_for_maintenance(bakim, _StubArac("06 ŞIK 99"))
    encoded = out.encode("utf-8")
    decoded = encoded.decode("utf-8")
    assert "ş" in decoded
    assert "06 ŞIK 99" in decoded


def test_generate_ics_dtend_is_one_hour_after_dtstart():
    """RFC 5545 §3.6.1 regression: DTSTART == DTEND zero-duration sayılır
    ve Google Calendar/Outlook bunu göstermez. DTEND, DTSTART'tan 1 saat
    sonra olmalı.

    Geçmiş bug: dt değişkeni hem DTSTART hem DTEND için kullanılıyordu;
    test sadece DTSTART'ı kontrol ediyordu — bu yüzden bug tarafından
    yakalanmamıştı.
    """
    from app.core.services.ics_generator import generate_ics_for_maintenance

    bakim = _StubBakim(
        id=42,
        bakim_tarihi=datetime(2026, 6, 15, 10, 0, 0, tzinfo=timezone.utc),
    )
    out = generate_ics_for_maintenance(bakim, _StubArac("34 X 1"))

    assert "DTSTART:20260615T100000Z" in out
    # 1 saat sonra
    assert "DTEND:20260615T110000Z" in out
    # Zero-duration regression — DTSTART ve DTEND aynı değer olmamalı
    assert "DTEND:20260615T100000Z" not in out


def test_generate_ics_dtend_crosses_day_boundary():
    """Gece geç saatte bakım → DTEND ertesi güne taşmalı."""
    from app.core.services.ics_generator import generate_ics_for_maintenance

    bakim = _StubBakim(
        id=43,
        bakim_tarihi=datetime(2026, 6, 15, 23, 30, 0, tzinfo=timezone.utc),
    )
    out = generate_ics_for_maintenance(bakim, _StubArac("34 X 2"))
    assert "DTSTART:20260615T233000Z" in out
    assert "DTEND:20260616T003000Z" in out  # 1 saat sonra → ertesi gün
