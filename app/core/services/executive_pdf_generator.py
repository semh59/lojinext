"""Feature E.9 — CEO 1-pager A4 PDF üretici.

Mevcut PDFReportGenerator'ın font kaydı (DocFont / DejaVu) reuse edilir;
Türkçe karakter güvenli. Sayfa 1 sayfa A4 dikey; içerik:
  - Başlık + tarih
  - Filo Verimliliği Endeksi (büyük puan + trend)
  - 4 alt-skor (yakıt/bakım/şoför/anomali)
  - 90 Gün cashflow toplamı + 3 kalem
  - Cross-feature etki (D.4+A.5+B)
  - Top What-If önerisi (varsa)

Plan kaynağı: docs/superpowers/plans/2026-05-26-feature-e-strategic-cockpit-v3.md §12
"""

from __future__ import annotations

import io
import logging
from datetime import date
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


def _safe(value: Any, default: str = "—") -> str:
    """None / boş → '—'; sayı → tr formatta TL."""
    if value is None or value == "":
        return default
    return str(value)


def _format_tl(amount: Optional[float]) -> str:
    if amount is None:
        return "—"
    try:
        return f"₺{float(amount):,.0f}".replace(",", ".")
    except (TypeError, ValueError):
        return "—"


def generate_executive_pdf(
    *,
    fvi: Optional[Dict[str, Any]] = None,
    cashflow: Optional[Dict[str, Any]] = None,
    cross_feature: Optional[Dict[str, Any]] = None,
    what_if_top: Optional[Dict[str, Any]] = None,
    generated_date: Optional[date] = None,
) -> bytes:
    """CEO 1-pager A4 PDF oluştur ve binary döndür.

    Args:
        fvi: FleetEfficiencyResponse.model_dump() benzeri dict (None → tüm
             alanlar '—' gösterilir)
        cashflow: CashflowProjectionResponse dict
        cross_feature: CrossFeatureImpactResponse dict
        what_if_top: WhatIfResponse dict (top öneri varsa)
        generated_date: rapor üretim tarihi (test için injectable)

    Returns:
        PDF binary (bytes). Caller `Response(content=..., media_type='application/pdf')`.
    """
    # reportlab opsiyonel bağımlılık — production'da kayıtlı (CLAUDE.md
    # commands → reportlab her zaman var; defensive import yine de)
    try:
        from reportlab.lib.colors import HexColor
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
        from reportlab.lib.units import cm
        from reportlab.platypus import (
            Paragraph,
            SimpleDocTemplate,
            Spacer,
            Table,
            TableStyle,
        )
    except ImportError as exc:  # pragma: no cover — reportlab her zaman var
        raise RuntimeError("reportlab yüklü değil") from exc

    # Mevcut PDFReportGenerator font registration reuse — yan etki olarak
    # "DocFont" + "DocFontBold" pdfmetrics'e kayıt yapar. Generator
    # fallback yaptıysa (Helvetica) onun gerçek font_name/bold'unu kullan.
    try:
        from v2.modules.reports.infrastructure.pdf_export import PDFReportGenerator

        gen = PDFReportGenerator()  # __init__ font kaydı yapar
        font_name = gen.font_name
        font_bold = gen.font_bold
    except Exception as exc:
        logger.warning("PDFReportGenerator font reuse failed: %s", exc)
        font_name = "Helvetica"
        font_bold = "Helvetica-Bold"

    today = generated_date or date.today()
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=1.5 * cm,
        rightMargin=1.5 * cm,
        topMargin=1.5 * cm,
        bottomMargin=1.5 * cm,
        title="LojiNext Strategic Cockpit",
        author="LojiNext",
    )

    # Renk paleti
    PRIMARY = HexColor("#1e40af")
    SUCCESS = HexColor("#059669")
    BG = HexColor("#f8fafc")
    TEXT = HexColor("#0f172a")

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "title",
        parent=styles["Title"],
        fontName=font_bold,
        fontSize=18,
        textColor=PRIMARY,
        spaceAfter=4,
    )
    subtitle_style = ParagraphStyle(
        "subtitle",
        parent=styles["Normal"],
        fontName=font_name,
        fontSize=9,
        textColor=HexColor("#64748b"),
        spaceAfter=12,
    )
    h2_style = ParagraphStyle(
        "h2",
        parent=styles["Heading2"],
        fontName=font_bold,
        fontSize=11,
        textColor=PRIMARY,
        spaceAfter=4,
    )
    body_style = ParagraphStyle(
        "body",
        parent=styles["Normal"],
        fontName=font_name,
        fontSize=10,
        textColor=TEXT,
        leading=14,
    )
    metric_style = ParagraphStyle(
        "metric",
        parent=styles["Normal"],
        fontName=font_bold,
        fontSize=28,
        textColor=PRIMARY,
        alignment=1,  # center
    )
    trend_style = ParagraphStyle(
        "trend",
        parent=styles["Normal"],
        fontName=font_name,
        fontSize=10,
        textColor=SUCCESS,
        alignment=1,
    )

    flow = []

    # ── Header ───────────────────────────────────────────────────────────
    flow.append(Paragraph("LojiNext Strategic Cockpit", title_style))
    flow.append(
        Paragraph(f"CEO Görünümü · {today.strftime('%d.%m.%Y')}", subtitle_style)
    )

    # ── FVI Card ─────────────────────────────────────────────────────────
    if fvi:
        fvi_score = fvi.get("fvi", 0)
        trend = fvi.get("trend_30d")
        trend_text = (
            f"30g trend: {'+' if (trend or 0) > 0 else ''}{trend}"
            if trend is not None
            else "30g trend: —"
        )
        fvi_table_data = [
            [Paragraph(f"<b>{fvi_score}</b>", metric_style)],
            [Paragraph("/ 100", subtitle_style)],
            [Paragraph(trend_text, trend_style)],
        ]
        fvi_table = Table(fvi_table_data, colWidths=[18 * cm])
        fvi_table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, -1), BG),
                    ("BOX", (0, 0), (-1, -1), 0.5, PRIMARY),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("TOPPADDING", (0, 0), (-1, -1), 4),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ]
            )
        )
        flow.append(Paragraph("Filo Verimliliği Endeksi", h2_style))
        flow.append(fvi_table)
        flow.append(Spacer(1, 4))

        # Alt skorlar
        sub_table = Table(
            [
                ["Yakıt", "Bakım", "Şoför", "Anomali"],
                [
                    f"{fvi.get('fuel_score', '—')}",
                    f"{fvi.get('maintenance_score', '—')}",
                    f"{fvi.get('driver_score', '—')}",
                    f"{fvi.get('anomaly_quality_score', '—')}",
                ],
            ],
            colWidths=[4.5 * cm] * 4,
        )
        sub_table.setStyle(
            TableStyle(
                [
                    ("FONTNAME", (0, 0), (-1, 0), font_bold),
                    ("FONTNAME", (0, 1), (-1, 1), font_name),
                    ("FONTSIZE", (0, 0), (-1, -1), 9),
                    ("BACKGROUND", (0, 0), (-1, 0), BG),
                    ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                    ("BOX", (0, 0), (-1, -1), 0.3, HexColor("#cbd5e1")),
                    ("INNERGRID", (0, 0), (-1, -1), 0.3, HexColor("#cbd5e1")),
                    ("TOPPADDING", (0, 0), (-1, -1), 4),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ]
            )
        )
        flow.append(sub_table)
    else:
        flow.append(Paragraph("Filo Verimliliği Endeksi: veri yok", body_style))
    flow.append(Spacer(1, 14))

    # ── 90 Gün Cashflow ──────────────────────────────────────────────────
    flow.append(Paragraph("90 Gün Projeksiyon", h2_style))
    if cashflow:
        cf_table = Table(
            [
                ["Kalem", "Tutar"],
                ["Yakıt", _format_tl(cashflow.get("total_fuel_tl"))],
                ["Bakım", _format_tl(cashflow.get("total_maintenance_tl"))],
                ["Ceza", _format_tl(cashflow.get("total_penalty_tl"))],
                ["Toplam", _format_tl(cashflow.get("grand_total_tl"))],
            ],
            colWidths=[10 * cm, 8 * cm],
        )
        cf_table.setStyle(
            TableStyle(
                [
                    ("FONTNAME", (0, 0), (-1, 0), font_bold),
                    ("FONTNAME", (0, 1), (-1, -2), font_name),
                    ("FONTNAME", (0, -1), (-1, -1), font_bold),
                    ("FONTSIZE", (0, 0), (-1, -1), 10),
                    ("BACKGROUND", (0, 0), (-1, 0), PRIMARY),
                    ("TEXTCOLOR", (0, 0), (-1, 0), HexColor("#ffffff")),
                    ("BACKGROUND", (0, -1), (-1, -1), BG),
                    ("ALIGN", (1, 0), (1, -1), "RIGHT"),
                    ("BOX", (0, 0), (-1, -1), 0.3, HexColor("#cbd5e1")),
                    ("INNERGRID", (0, 0), (-1, -1), 0.3, HexColor("#cbd5e1")),
                    ("TOPPADDING", (0, 0), (-1, -1), 4),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ]
            )
        )
        flow.append(cf_table)
    else:
        flow.append(Paragraph("Cashflow verisi yok.", body_style))
    flow.append(Spacer(1, 14))

    # ── Cross-Feature Etki ───────────────────────────────────────────────
    flow.append(Paragraph("Cross-Feature Etki (90g)", h2_style))
    if cross_feature:
        flow.append(
            Paragraph(
                "<b>Bakım gecikme zararı:</b> "
                f"{_format_tl(cross_feature.get('maintenance_delay_loss_tl'))}",
                body_style,
            )
        )
        flow.append(
            Paragraph(
                "<b>Koçluk tasarrufu:</b> "
                f"{_format_tl(cross_feature.get('coaching_savings_tl'))}",
                body_style,
            )
        )
        flow.append(
            Paragraph(
                "<b>Hırsızlık zararı:</b> "
                f"{_format_tl(cross_feature.get('theft_loss_tl'))}",
                body_style,
            )
        )
    else:
        flow.append(Paragraph("Cross-feature verisi yok.", body_style))
    flow.append(Spacer(1, 14))

    # ── Top Stratejik Öneri ──────────────────────────────────────────────
    flow.append(Paragraph("Top Stratejik Öneri", h2_style))
    if what_if_top:
        scenario_label = {
            "fleet_renewal": "Filo Yenileme",
            "training": "Koçluk Programı",
            "route_portfolio": "Güzergah Portföy Optimizasyonu",
        }.get(what_if_top.get("scenario_type"), what_if_top.get("scenario_type"))
        flow.append(
            Paragraph(
                f"<b>{scenario_label}</b>: "
                f"Yıllık tasarruf {_format_tl(what_if_top.get('yearly_savings_tl'))}, "
                f"payback {_safe(what_if_top.get('payback_years'))} yıl, "
                f"5-yıl ROI {_safe(what_if_top.get('five_year_roi_pct'), '0')}%",
                body_style,
            )
        )
    else:
        flow.append(
            Paragraph(
                "What-if simülatöründen henüz öneri seçilmemiş.",
                ParagraphStyle(
                    "italic",
                    parent=body_style,
                    fontName=font_name,
                    textColor=HexColor("#64748b"),
                ),
            )
        )

    # ── Footer ───────────────────────────────────────────────────────────
    flow.append(Spacer(1, 10))
    flow.append(
        Paragraph(
            "<i>Bu rapor LojiNext Strategic Cockpit AI motorlarından üretilmiştir.</i>",
            ParagraphStyle(
                "footer",
                parent=body_style,
                fontSize=8,
                textColor=HexColor("#94a3b8"),
                alignment=1,
            ),
        )
    )

    doc.build(flow)
    return buf.getvalue()
