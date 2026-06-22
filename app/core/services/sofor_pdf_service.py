"""PDF raporu: şofora ait onaylanmış seferler."""

import asyncio
import io
from datetime import date
from typing import Optional
from xml.sax.saxutils import escape as xml_escape

from sqlalchemy import select

from app.core.services.report_generator import PDFReportGenerator
from app.database.models import Sefer, Sofor
from app.database.unit_of_work import UnitOfWork
from app.infrastructure.logging.logger import get_logger

logger = get_logger(__name__)

try:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import cm
    from reportlab.platypus import (
        Paragraph,
        SimpleDocTemplate,
        Spacer,
        Table,
        TableStyle,
    )

    REPORTLAB_AVAILABLE = True
except ImportError:
    REPORTLAB_AVAILABLE = False


class SoforSeferPDFService(PDFReportGenerator):
    """
    Şofora ait onaylanmış seferleri PDF olarak üretir.
    Sadece onay_durumu='onaylandi' olan seferler dahil edilir.
    """

    def __init__(self) -> None:
        super().__init__()

    async def olustur(
        self, sofor_id: int, baslangic: date, bitis: date
    ) -> Optional[bytes]:
        async with UnitOfWork() as uow:
            sofor_stmt = select(Sofor).where(Sofor.id == sofor_id)
            sofor_result = await uow.session.execute(sofor_stmt)
            sofor = sofor_result.scalar_one_or_none()
            if sofor is None:
                return None

            stmt = (
                select(Sefer)
                .where(
                    Sefer.sofor_id == sofor_id,
                    Sefer.onay_durumu == "onaylandi",
                    ~Sefer.is_deleted,
                    Sefer.tarih >= baslangic,
                    Sefer.tarih <= bitis,
                )
                .order_by(Sefer.tarih.asc())
            )
            result = await uow.session.execute(stmt)
            seferler = list(result.scalars().all())

        if not seferler:
            return None

        return await asyncio.to_thread(
            self._build_pdf, sofor, seferler, baslangic, bitis
        )

    def _build_pdf(
        self, sofor: Sofor, seferler: list, baslangic: date, bitis: date
    ) -> bytes:
        if not REPORTLAB_AVAILABLE:
            logger.error("reportlab yüklü değil, PDF üretilemiyor")
            return b""

        buf = io.BytesIO()
        doc = SimpleDocTemplate(
            buf,
            pagesize=A4,
            leftMargin=2 * cm,
            rightMargin=2 * cm,
            topMargin=2 * cm,
            bottomMargin=2 * cm,
        )
        story = []

        # Başlık
        story.append(
            Paragraph(
                f"Sefer Raporu — {xml_escape(str(sofor.ad_soyad))}",
                self.styles["DocTitle"],
            )
        )
        story.append(
            Paragraph(
                f"{baslangic} — {bitis} arası onaylı seferler",
                self.styles["DocSection"],
            )
        )
        story.append(Spacer(1, 0.5 * cm))

        # Tablo başlıkları
        headers = ["Tarih", "Çıkış", "Varış", "Mesafe (km)", "Yakıt (L)", "Durum"]
        rows = [headers]
        for s in seferler:
            rows.append(
                [
                    str(s.tarih or ""),
                    str(s.cikis_yeri or ""),
                    str(s.varis_yeri or ""),
                    str(s.mesafe_km or ""),
                    str(round(s.tuketim, 1) if s.tuketim else ""),
                    "Onaylandı",
                ]
            )

        tablo = Table(rows, repeatRows=1)
        tablo.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), self.PRIMARY),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                    ("FONTNAME", (0, 0), (-1, 0), self.font_bold),
                    ("FONTSIZE", (0, 0), (-1, 0), 10),
                    ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                    ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, self.BG_LIGHT]),
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.lightgrey),
                    ("FONTNAME", (0, 1), (-1, -1), self.font_name),
                    ("FONTSIZE", (0, 1), (-1, -1), 9),
                ]
            )
        )
        story.append(tablo)
        story.append(Spacer(1, 0.5 * cm))

        # Özet
        toplam_km = sum((s.mesafe_km or 0) for s in seferler)
        toplam_yakit = sum((s.tuketim or 0) for s in seferler)
        story.append(
            Paragraph(
                f"Toplam: {len(seferler)} sefer | {toplam_km:.0f} km | {toplam_yakit:.1f} L yakıt",
                self.styles["Normal"],
            )
        )

        doc.build(story)
        return buf.getvalue()
