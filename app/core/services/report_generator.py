import io
import os
from datetime import date, datetime, timezone
from typing import Any, Dict, List, Optional

try:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import cm
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
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


def get_system_font() -> str:
    """Return a best-guess system TrueType font path for PDF generation."""
    import platform

    system = platform.system()
    if system == "Windows":
        return r"C:\Windows\Fonts\arial.ttf"
    elif system == "Darwin":
        return "/System/Library/Fonts/Helvetica.ttc"
    else:  # Linux / Docker
        for path in (
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
            "/usr/share/fonts/liberation/LiberationSans-Regular.ttf",
        ):
            import os as _os

            if _os.path.exists(path):
                return path
        return "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"


from app.infrastructure.logging.logger import get_logger  # noqa: E402

logger = get_logger(__name__)


class PDFReportGenerator:
    """
    PDF Rapor Motoru (ReportLab tabanlı)

    Özellikler:
    - %100 Türkçe Karakter Desteği (TrueType)
    - Kurumsal Tasarım (Modern Palette)
    - Dinamik Tablo ve Grafik Alanları
    """

    # Kurumsal Renk Paleti (ReportLab varsa HexColor, yoksa string)
    PRIMARY = None
    SECONDARY = None
    SUCCESS = None
    WARNING = None
    DANGER = None
    BG_LIGHT = None
    TEXT_DARK = None

    def __init__(self):
        if not REPORTLAB_AVAILABLE:
            logger.error("reportlab kütüphanesi yüklü değil, PDF üretimi yapılamaz!")
            return

        # Renkleri burada ata (HexColor'ın import kontrolü geçmiş olduğu garanti)
        from reportlab.lib.colors import HexColor

        PDFReportGenerator.PRIMARY = HexColor("#1e40af")  # Indigo 800
        PDFReportGenerator.SECONDARY = HexColor("#64748b")  # Slate 500
        PDFReportGenerator.SUCCESS = HexColor("#059669")  # Emerald 600
        PDFReportGenerator.WARNING = HexColor("#d97706")  # Amber 600
        PDFReportGenerator.DANGER = HexColor("#dc2626")  # Red 600
        PDFReportGenerator.BG_LIGHT = HexColor("#f8fafc")  # Slate 50
        PDFReportGenerator.TEXT_DARK = HexColor("#0f172a")  # Slate 900

        self._register_fonts()
        self._styles = None

    def _register_fonts(self):
        """Türkçe karakterler için font kaydı"""
        try:
            # 1. Öncelik: Proje içindeki gömülü fontlar (Taşınabilirlik için)
            current_dir = os.path.dirname(
                os.path.abspath(__file__)
            )  # app/core/services
            app_dir = os.path.dirname(os.path.dirname(current_dir))  # app
            asset_font = os.path.join(app_dir, "assets", "fonts", "DocFont.ttf")
            asset_font_bold = os.path.join(
                app_dir, "assets", "fonts", "DocFont-Bold.ttf"
            )

            if os.path.exists(asset_font):
                pdfmetrics.registerFont(TTFont("DocFont", asset_font))
                pdfmetrics.registerFont(
                    TTFont(
                        "DocFontBold",
                        asset_font_bold
                        if os.path.exists(asset_font_bold)
                        else asset_font,
                    )
                )
                # ReportLab Paragraph `<b>` tag'i font ailesi mapping'i ister;
                # aksi halde "docfontbold" lowercase'ini arar ve fail eder.
                pdfmetrics.registerFontFamily(
                    "DocFont",
                    normal="DocFont",
                    bold="DocFontBold",
                    italic="DocFont",
                    boldItalic="DocFontBold",
                )
                self.font_name = "DocFont"
                self.font_bold = "DocFontBold"
                logger.info("Gömülü fontlar başarıyla yüklendi.")
                return

            # 2. Öncelik: Sistem fontları
            font_path = get_system_font()
            if os.path.exists(font_path):
                pdfmetrics.registerFont(TTFont("DocFont", font_path))
                # Bold sürümü için bilinen Linux + Windows konvansiyonları:
                # DejaVuSans.ttf → DejaVuSans-Bold.ttf  (Linux/Docker)
                # arial.ttf      → arialbd.ttf          (Windows)
                bold_candidates = [
                    font_path.replace(".ttf", "-Bold.ttf"),
                    font_path.replace(".ttf", "bd.ttf"),
                ]
                bold_path = next(
                    (p for p in bold_candidates if os.path.exists(p)),
                    font_path,  # bulunamazsa regular font ile fallback
                )
                pdfmetrics.registerFont(TTFont("DocFontBold", bold_path))
                pdfmetrics.registerFontFamily(
                    "DocFont",
                    normal="DocFont",
                    bold="DocFontBold",
                    italic="DocFont",
                    boldItalic="DocFontBold",
                )
                self.font_name = "DocFont"
                self.font_bold = "DocFontBold"
            else:
                self.font_name = "Helvetica"
                self.font_bold = "Helvetica-Bold"
        except Exception as e:
            logger.warning(f"Font kaydı yapılamadı: {e}. Standart font kullanılacak.")
            self.font_name = "Helvetica"
            self.font_bold = "Helvetica-Bold"

    @property
    def styles(self):
        if self._styles is None and REPORTLAB_AVAILABLE:
            self._styles = getSampleStyleSheet()
            # PDF Styles
            self._styles.add(
                ParagraphStyle(
                    name="DocTitle",
                    parent=self._styles["Heading1"],
                    fontName=self.font_bold,
                    fontSize=22,
                    textColor=self.PRIMARY,
                    spaceAfter=20,
                    alignment=1,  # Center
                )
            )
            self._styles.add(
                ParagraphStyle(
                    name="DocSection",
                    parent=self._styles["Heading2"],
                    fontName=self.font_bold,
                    fontSize=14,
                    textColor=self.SECONDARY,
                    spaceBefore=15,
                    spaceAfter=10,
                    borderPadding=(0, 0, 5, 0),
                    borderWidth=0,
                    borderColor=self.PRIMARY,  # Bottom border simulated via styling if needed
                )
            )
            self._styles.add(
                ParagraphStyle(
                    name="DocBody",
                    parent=self._styles["Normal"],
                    fontName=self.font_name,
                    fontSize=10,
                    textColor=self.TEXT_DARK,
                    leading=14,
                )
            )
            self._styles.add(
                ParagraphStyle(
                    name="DocFooter",
                    parent=self._styles["Normal"],
                    fontName=self.font_name,
                    fontSize=8,
                    textColor=self.SECONDARY,
                    alignment=1,  # Center
                )
            )
        return self._styles

    def _create_header(
        self, elements: List, title: str, subtitle: Optional[str] = None
    ):
        """Rapor başlığı oluştur"""
        elements.append(Paragraph(title.upper(), self.styles["DocTitle"]))
        if subtitle:
            elements.append(Paragraph(subtitle, self.styles["DocBody"]))
        elements.append(Spacer(1, 0.8 * cm))

    def _create_metric_box(self, label: str, value: str, color: Any = None) -> Table:
        """Dashboard tipi metrik kutusu"""
        data = [
            [
                Paragraph(f"<b>{label}</b>", self.styles["DocBody"]),
                Paragraph(
                    f"<font color='{color.hexval() if color else '#000000'}'>{value}</font>",
                    self.styles["DocBody"],
                ),
            ]
        ]
        t = Table(data, colWidths=[4 * cm, 4 * cm])
        t.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, -1), self.BG_LIGHT),
                    ("BOX", (0, 0), (-1, -1), 1, self.SECONDARY),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 10),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 10),
                ]
            )
        )
        return t

    def generate_fleet_summary(
        self, start_date: date, end_date: date, data: Dict
    ) -> bytes:
        """Filo Özet Raporu"""
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=A4,
            rightMargin=2 * cm,
            leftMargin=2 * cm,
            topMargin=2 * cm,
            bottomMargin=2 * cm,
        )
        elements: List[Any] = []

        # 1. Header
        self._create_header(
            elements,
            "Filo Performans Raporu",
            f"Sefer Dönemi: {start_date.strftime('%d.%m.%Y')} - {end_date.strftime('%d.%m.%Y')}",
        )

        # 2. Özet Metrikler (2x3 Grid)
        elements.append(Paragraph("GENEL ÖZET", self.styles["DocSection"]))
        m_data = [
            [
                self._create_metric_box(
                    "Toplam Araç", str(data.get("total_vehicles", 0))
                ),
                self._create_metric_box(
                    "Toplam Sefer", str(data.get("total_trips", 0))
                ),
            ],
            [
                self._create_metric_box(
                    "Toplam Mesafe", f"{data.get('total_distance', 0):,.0f} km"
                ),
                self._create_metric_box(
                    "Yakıt Tüketimi", f"{data.get('total_fuel', 0):,.0f} L"
                ),
            ],
            [
                self._create_metric_box(
                    "Ort. Tüketim",
                    f"{data.get('avg_consumption', 0):.2f} L/100km",
                    self.SUCCESS,
                ),
                self._create_metric_box(
                    "Toplam Maliyet",
                    f"{data.get('total_cost', 0):,.2f} TL",
                    self.PRIMARY,
                ),
            ],
        ]
        metrics_grid = Table(m_data, colWidths=[8.5 * cm, 8.5 * cm])
        metrics_grid.setStyle(
            TableStyle(
                [
                    ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                    ("TOPPADDING", (0, 0), (-1, -1), 5),
                ]
            )
        )
        elements.append(metrics_grid)
        elements.append(Spacer(1, 1 * cm))

        # 3. Araç Performans Tablosu
        if data.get("vehicle_performance"):
            elements.append(Paragraph("ARAÇ BAZLI ANALİZ", self.styles["DocSection"]))
            v_data = [["Plaka", "Sefer", "KM", "Tüketim", "Puan", "Durum"]]
            for v in data["vehicle_performance"][:15]:
                puan = v.get("performance_score", 0)
                status = "KRİTİK" if puan < 50 else "İYİ" if puan > 80 else "NORMAL"
                v_data.append(
                    [
                        v.get("plaka", "-"),
                        str(v.get("trips", 0)),
                        f"{v.get('distance', 0):,.0f}",
                        f"{v.get('consumption', 0):.2f}",
                        f"{puan:.1f}",
                        status,
                    ]
                )

            v_table = Table(
                v_data, colWidths=[3 * cm, 2 * cm, 3 * cm, 4 * cm, 2 * cm, 3 * cm]
            )
            v_table.setStyle(
                TableStyle(
                    [
                        ("BACKGROUND", (0, 0), (-1, 0), self.PRIMARY),
                        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                        ("FONTNAME", (0, 0), (-1, 0), self.font_bold),
                        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                        (
                            "ROWBACKGROUNDS",
                            (0, 1),
                            (-1, -1),
                            [colors.white, self.BG_LIGHT],
                        ),
                        ("GRID", (0, 0), (-1, -1), 0.5, self.SECONDARY),
                    ]
                )
            )
            elements.append(v_table)

        # 4. Footer
        elements.append(Spacer(1, 2 * cm))
        elements.append(
            Paragraph(
                f"LojiNext AI Zekası Tarafından {datetime.now(timezone.utc).strftime('%d.%m.%Y %H:%M')} tarihinde oluşturulmuştur.",  # noqa: E501
                self.styles["DocFooter"],
            )
        )

        doc.build(elements)
        return buffer.getvalue()

    def generate_vehicle_report(
        self, arac_id: int, month: int, year: int, data: Dict
    ) -> bytes:
        """Araç Detay Raporu"""
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=A4)
        elements: List[Any] = []

        plaka = data.get("plaka", f"#{arac_id}")
        self._create_header(
            elements,
            f"ARAÇ ANALİZ DOSYASI: {plaka}",
            f"Rapor Dönemi: {month:02d}/{year}",
        )

        # 1. Teknik Bilgiler Kartı
        elements.append(Paragraph("TEKNİK ÖZELLİKLER", self.styles["DocSection"]))
        tech_data = [
            ["Marka / Model", f"{data.get('marka', '-')} {data.get('model', '')}"],
            ["Hedef Tüketim", f"{data.get('hedef_tuketim', 32.0):.1f} L/100km"],
            ["Performans Skoru", f"{data.get('performance_score', 0):.1f} / 100"],
        ]
        t_table = Table(tech_data, colWidths=[6 * cm, 10 * cm])
        t_table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (0, -1), self.BG_LIGHT),
                    ("GRID", (0, 0), (-1, -1), 0.5, self.SECONDARY),
                ]
            )
        )
        elements.append(t_table)
        elements.append(Spacer(1, 0.5 * cm))

        # 2. Dönem Performans İstatistikleri
        istat = data.get("istatistikler") or {}
        elements.append(Paragraph("DÖNEM PERFORMANSI", self.styles["DocSection"]))
        perf_data = [
            ["Toplam Sefer", str(istat.get("toplam_sefer", "-"))],
            ["Toplam Mesafe", f"{istat.get('toplam_km', 0):,.0f} km"],
            ["Toplam Yakıt", f"{istat.get('toplam_yakit', 0):,.1f} L"],
            [
                "Ortalama Tüketim",
                f"{istat.get('ort_tuketim', 0):.2f} L/100km"
                if istat.get("ort_tuketim")
                else "-",
            ],
            [
                "Toplam Maliyet",
                f"{istat.get('toplam_maliyet', 0):,.2f} ₺"
                if istat.get("toplam_maliyet")
                else "-",
            ],
        ]
        p_table = Table(perf_data, colWidths=[6 * cm, 10 * cm])
        p_table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (0, -1), self.BG_LIGHT),
                    ("GRID", (0, 0), (-1, -1), 0.5, self.SECONDARY),
                    ("FONTNAME", (0, 0), (-1, -1), self.font_name),
                ]
            )
        )
        elements.append(p_table)
        elements.append(Spacer(1, 0.5 * cm))

        # 3. En Çok Kullanılan Güzergahlar
        guzergahlar = data.get("top_guzergahlar") or []
        if guzergahlar:
            elements.append(
                Paragraph("EN ÇOK KULLANILAN GÜZERGAHLAR", self.styles["DocSection"])
            )
            route_header = [["Güzergah", "Sefer Sayısı", "Ort. Tüketim (L/100km)"]]
            route_rows = [
                [
                    str(g.get("guzergah", g.get("rota", "-"))),
                    str(g.get("sefer_sayisi", g.get("count", "-"))),
                    f"{g.get('ort_tuketim', g.get('avg_consumption', 0)):.2f}"
                    if g.get("ort_tuketim") or g.get("avg_consumption")
                    else "-",
                ]
                for g in guzergahlar[:5]
            ]
            r_table = Table(
                route_header + route_rows,
                colWidths=[8 * cm, 4 * cm, 4 * cm],
            )
            r_table.setStyle(
                TableStyle(
                    [
                        ("BACKGROUND", (0, 0), (-1, 0), self.PRIMARY),
                        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                        ("FONTNAME", (0, 0), (-1, -1), self.font_name),
                        ("GRID", (0, 0), (-1, -1), 0.5, self.SECONDARY),
                        (
                            "ROWBACKGROUNDS",
                            (0, 1),
                            (-1, -1),
                            [colors.white, self.BG_LIGHT],
                        ),
                    ]
                )
            )
            elements.append(r_table)
            elements.append(Spacer(1, 0.5 * cm))

        doc.build(elements)
        return buffer.getvalue()

    async def async_generate_fleet_summary(
        self, start_date: date, end_date: date, data: Dict
    ) -> bytes:
        """Asenkron wrapper: Filo Özet Raporu"""
        import asyncio

        return await asyncio.to_thread(
            self.generate_fleet_summary, start_date, end_date, data
        )

    async def async_generate_vehicle_report(
        self, arac_id: int, month: int, year: int, data: Dict
    ) -> bytes:
        """Asenkron wrapper: Araç Detay Raporu"""
        import asyncio

        return await asyncio.to_thread(
            self.generate_vehicle_report, arac_id, month, year, data
        )

    def generate_driver_comparison(self, driver_data: List[Dict]) -> bytes:
        """Şoför karşılaştırma PDF raporu."""
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=A4,
            rightMargin=2 * cm,
            leftMargin=2 * cm,
            topMargin=2 * cm,
            bottomMargin=2 * cm,
        )
        elements: List[Any] = []

        self._create_header(
            elements,
            "Şoför Karşılaştırma Raporu",
            f"Oluşturulma: {datetime.now(timezone.utc).strftime('%d.%m.%Y %H:%M')}",
        )

        if not driver_data:
            elements.append(
                Paragraph(
                    "Gösterilecek şoför verisi bulunamadı.", self.styles["Normal"]
                )
            )
            doc.build(elements)
            return buffer.getvalue()

        headers = ["Şoför", "Sefer", "Ort. Tüketim (L/100km)", "Skor"]
        table_data = [headers] + [
            [
                str(d.get("ad_soyad") or "-"),
                str(d.get("trips") or 0),
                f"{d.get('consumption') or 0:.1f}",
                f"{d.get('score') or 0:.2f}",
            ]
            for d in driver_data
        ]
        col_widths = [7 * cm, 3 * cm, 5 * cm, 3 * cm]
        table = Table(table_data, colWidths=col_widths)
        table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), self.PRIMARY),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                    ("FONTNAME", (0, 0), (-1, 0), self.font_name),
                    ("FONTSIZE", (0, 0), (-1, 0), 10),
                    ("GRID", (0, 0), (-1, -1), 0.5, self.SECONDARY),
                    ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, self.BG_LIGHT]),
                ]
            )
        )
        elements.append(table)
        doc.build(elements)
        return buffer.getvalue()

    def generate_vehicle_comparison(self, vehicle_data: List[Dict]) -> bytes:
        """Araç maliyet karşılaştırma PDF raporu."""
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=A4,
            rightMargin=2 * cm,
            leftMargin=2 * cm,
            topMargin=2 * cm,
            bottomMargin=2 * cm,
        )
        elements: List[Any] = []

        self._create_header(
            elements,
            "Araç Karşılaştırma Raporu",
            f"Oluşturulma: {datetime.now(timezone.utc).strftime('%d.%m.%Y %H:%M')}",
        )

        if not vehicle_data:
            elements.append(
                Paragraph("Gösterilecek araç verisi bulunamadı.", self.styles["Normal"])
            )
            doc.build(elements)
            return buffer.getvalue()

        headers = ["Plaka", "Mesafe (km)", "Yakıt (TL)", "TL/km", "L/100km"]
        table_data = [headers] + [
            [
                str(v.get("plaka") or "-"),
                f"{v.get('total_distance') or 0:.0f}",
                f"{v.get('fuel_cost') or 0:.2f}",
                f"{v.get('cost_per_km') or 0:.2f}",
                f"{v.get('avg_consumption') or 0:.1f}",
            ]
            for v in vehicle_data
        ]
        col_widths = [4 * cm, 4 * cm, 4 * cm, 3 * cm, 3 * cm]
        table = Table(table_data, colWidths=col_widths)
        table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), self.PRIMARY),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                    ("FONTNAME", (0, 0), (-1, 0), self.font_name),
                    ("FONTSIZE", (0, 0), (-1, 0), 10),
                    ("GRID", (0, 0), (-1, -1), 0.5, self.SECONDARY),
                    ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, self.BG_LIGHT]),
                ]
            )
        )
        elements.append(table)
        doc.build(elements)
        return buffer.getvalue()


# Thread-safe Singleton
import threading  # noqa: E402

_report_generator: Optional[PDFReportGenerator] = None
_report_generator_lock = threading.Lock()


def get_report_generator() -> PDFReportGenerator:
    """Thread-safe singleton getter"""
    global _report_generator
    if _report_generator is None:
        with _report_generator_lock:
            if _report_generator is None:
                _report_generator = PDFReportGenerator()
    return _report_generator
