"""Feature E.9 — Executive PDF generator tests (plan §12)."""

from __future__ import annotations

from datetime import date


# ── Helpers ────────────────────────────────────────────────────────────
def _sample_fvi() -> dict:
    return {
        "fvi": 78.5,
        "fuel_score": 82.0,
        "maintenance_score": 75.0,
        "driver_score": 80.0,
        "anomaly_quality_score": 73.0,
        "trend_30d": 4.2,
    }


def _sample_cashflow() -> dict:
    return {
        "total_fuel_tl": 2_800_000,
        "total_maintenance_tl": 320_000,
        "total_penalty_tl": 80_000,
        "grand_total_tl": 3_200_000,
    }


def _sample_cross_feature() -> dict:
    return {
        "maintenance_delay_loss_tl": 145_000,
        "coaching_savings_tl": 30_000,
        "theft_loss_tl": 12_000,
    }


def _sample_what_if() -> dict:
    return {
        "scenario_type": "fleet_renewal",
        "yearly_savings_tl": 697_500,
        "payback_years": 8.6,
        "five_year_roi_pct": -42.0,
    }


def _is_pdf_bytes(b: bytes) -> bool:
    """RFC: PDF dosya signature '%PDF-' ile başlar."""
    return isinstance(b, bytes) and b.startswith(b"%PDF-")


# ── _safe + _format_tl ─────────────────────────────────────────────────
def test_safe_handles_none_and_empty():
    from v2.modules.analytics_executive.infrastructure.pdf_export import _safe

    assert _safe(None) == "—"
    assert _safe("") == "—"
    assert _safe(0) == "0"
    assert _safe("test") == "test"


def test_format_tl_basic():
    from v2.modules.analytics_executive.infrastructure.pdf_export import _format_tl

    assert _format_tl(1_000_000) == "₺1.000.000"
    assert _format_tl(0) == "₺0"
    assert _format_tl(None) == "—"
    assert _format_tl("invalid") == "—"  # graceful


# ── generate_executive_pdf ─────────────────────────────────────────────
def test_generate_pdf_with_full_data():
    """Tüm 4 bölüm dolu → geçerli PDF döner."""
    from v2.modules.analytics_executive.infrastructure.pdf_export import (
        generate_executive_pdf,
    )

    pdf = generate_executive_pdf(
        fvi=_sample_fvi(),
        cashflow=_sample_cashflow(),
        cross_feature=_sample_cross_feature(),
        what_if_top=_sample_what_if(),
        generated_date=date(2026, 5, 27),
    )
    assert _is_pdf_bytes(pdf)
    assert len(pdf) > 1000  # 1KB altı PDF beklenmez (en az başlık+font)


def test_generate_pdf_with_all_none_graceful():
    """Tüm input None → graceful '—' gösterimi, yine geçerli PDF döner."""
    from v2.modules.analytics_executive.infrastructure.pdf_export import (
        generate_executive_pdf,
    )

    pdf = generate_executive_pdf()
    assert _is_pdf_bytes(pdf)


def test_generate_pdf_with_only_fvi():
    """Sadece FVI var → diğer bölümler '—' veya 'veri yok' gösterilir."""
    from v2.modules.analytics_executive.infrastructure.pdf_export import (
        generate_executive_pdf,
    )

    pdf = generate_executive_pdf(fvi=_sample_fvi())
    assert _is_pdf_bytes(pdf)


def test_generate_pdf_with_only_cashflow():
    from v2.modules.analytics_executive.infrastructure.pdf_export import (
        generate_executive_pdf,
    )

    pdf = generate_executive_pdf(cashflow=_sample_cashflow())
    assert _is_pdf_bytes(pdf)


def test_generate_pdf_contains_turkish_characters_safely():
    """Türkçe karakter güvenli üretim — exception fırlamaz."""
    from v2.modules.analytics_executive.infrastructure.pdf_export import (
        generate_executive_pdf,
    )

    fvi_turkish = {
        **_sample_fvi(),
        # Reasons + breakdown'da Türkçe yer alıyor (zaten Paragraph'larda var)
    }
    pdf = generate_executive_pdf(fvi=fvi_turkish, cashflow=_sample_cashflow())
    assert _is_pdf_bytes(pdf)
    # Görsel inceleme test'te yapılmaz; binary integrity yeterli.


def test_generate_pdf_what_if_unknown_scenario_type():
    """what_if_top içinde bilinmeyen scenario_type → label fallback."""
    from v2.modules.analytics_executive.infrastructure.pdf_export import (
        generate_executive_pdf,
    )

    pdf = generate_executive_pdf(
        what_if_top={
            "scenario_type": "unknown_scenario",
            "yearly_savings_tl": 100_000,
            "payback_years": None,
            "five_year_roi_pct": 0,
        }
    )
    assert _is_pdf_bytes(pdf)


def test_generate_pdf_generated_date_injectable():
    """Test determinizmi için generated_date geçirilebilir."""
    from v2.modules.analytics_executive.infrastructure.pdf_export import (
        generate_executive_pdf,
    )

    pdf1 = generate_executive_pdf(generated_date=date(2026, 1, 1))
    pdf2 = generate_executive_pdf(generated_date=date(2026, 6, 30))
    assert _is_pdf_bytes(pdf1)
    assert _is_pdf_bytes(pdf2)
    # Farklı tarih → farklı binary
    assert pdf1 != pdf2
