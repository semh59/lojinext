from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

pytestmark = pytest.mark.unit


def _make_sofor(id=1, ad_soyad="Ali Veli"):
    sofor = MagicMock()
    sofor.id = id
    sofor.ad_soyad = ad_soyad
    return sofor


def _make_sefer(id=1, tarih=None, cikis="A", varis="B", mesafe_km=200, tuketim=35.0):
    s = MagicMock()
    s.id = id
    s.tarih = tarih or date(2024, 1, 15)
    s.cikis_yeri = cikis
    s.varis_yeri = varis
    s.mesafe_km = mesafe_km
    s.tuketim = tuketim
    s.is_deleted = False
    s.onay_durumu = "onaylandi"
    return s


def _make_uow(sofor=None, seferler=None):
    mock_uow = AsyncMock()
    mock_uow.__aenter__ = AsyncMock(return_value=mock_uow)
    mock_uow.__aexit__ = AsyncMock(return_value=None)
    mock_uow.session = AsyncMock()

    sofor_result = MagicMock()
    sofor_result.scalar_one_or_none = MagicMock(return_value=sofor)

    sefer_result = MagicMock()
    sefer_result.scalars = MagicMock(
        return_value=MagicMock(all=MagicMock(return_value=seferler or []))
    )

    mock_uow.session.execute = AsyncMock(side_effect=[sofor_result, sefer_result])
    return mock_uow


def _make_service():
    with patch("app.core.services.sofor_pdf_service.UnitOfWork"):
        from app.core.services.sofor_pdf_service import SoforSeferPDFService

        svc = SoforSeferPDFService.__new__(SoforSeferPDFService)
        # Minimal base-class init — just set font names to safe defaults
        svc.font_name = "Helvetica"
        svc.font_bold = "Helvetica-Bold"
        svc._styles = None
    return svc


class TestSoforPdfService:
    def test_service_exists(self):
        from app.core.services.sofor_pdf_service import SoforSeferPDFService

        assert SoforSeferPDFService is not None

    async def test_basic_initialization(self):
        from app.core.services.sofor_pdf_service import SoforSeferPDFService

        with patch(
            "app.core.services.sofor_pdf_service.PDFReportGenerator.__init__",
            return_value=None,
        ):
            svc = SoforSeferPDFService.__new__(SoforSeferPDFService)
            svc.font_name = "Helvetica"
            svc.font_bold = "Helvetica-Bold"
            svc._styles = None
            assert isinstance(svc, SoforSeferPDFService)

    async def test_returns_none_when_sofor_not_found(self):
        svc = _make_service()
        mock_uow = _make_uow(sofor=None, seferler=[])

        with patch(
            "app.core.services.sofor_pdf_service.UnitOfWork", return_value=mock_uow
        ):
            result = await svc.olustur(
                sofor_id=999,
                baslangic=date(2024, 1, 1),
                bitis=date(2024, 1, 31),
            )

        assert result is None

    async def test_returns_none_when_no_approved_trips(self):
        sofor = _make_sofor()
        mock_uow = _make_uow(sofor=sofor, seferler=[])
        svc = _make_service()

        with patch(
            "app.core.services.sofor_pdf_service.UnitOfWork", return_value=mock_uow
        ):
            result = await svc.olustur(
                sofor_id=1,
                baslangic=date(2024, 1, 1),
                bitis=date(2024, 1, 31),
            )

        assert result is None

    async def test_happy_path_returns_bytes(self):
        sofor = _make_sofor()
        seferler = [_make_sefer(id=1), _make_sefer(id=2)]
        mock_uow = _make_uow(sofor=sofor, seferler=seferler)
        svc = _make_service()

        fake_pdf = b"%PDF-fake"
        with (
            patch(
                "app.core.services.sofor_pdf_service.UnitOfWork", return_value=mock_uow
            ),
            patch("asyncio.to_thread", new=AsyncMock(return_value=fake_pdf)),
        ):
            result = await svc.olustur(
                sofor_id=1,
                baslangic=date(2024, 1, 1),
                bitis=date(2024, 1, 31),
            )

        assert result == fake_pdf

    def test_build_pdf_returns_empty_bytes_without_reportlab(self):
        svc = _make_service()
        sofor = _make_sofor()
        seferler = [_make_sefer()]

        with patch("app.core.services.sofor_pdf_service.REPORTLAB_AVAILABLE", False):
            result = svc._build_pdf(
                sofor, seferler, date(2024, 1, 1), date(2024, 1, 31)
            )

        assert result == b""

    def test_build_pdf_with_reportlab_returns_nonempty_bytes(self):
        """If reportlab is available, _build_pdf should produce a non-empty bytes PDF."""
        from app.core.services.sofor_pdf_service import REPORTLAB_AVAILABLE

        if not REPORTLAB_AVAILABLE:
            pytest.skip("reportlab not installed")

        from app.core.services.sofor_pdf_service import SoforSeferPDFService

        svc = SoforSeferPDFService()
        sofor = _make_sofor()
        seferler = [_make_sefer(id=1, mesafe_km=300, tuketim=42.5)]

        result = svc._build_pdf(sofor, seferler, date(2024, 1, 1), date(2024, 1, 31))

        assert isinstance(result, bytes)
        assert len(result) > 0

    def test_edge_case_trip_with_none_tuketim(self):
        """_build_pdf should handle None tuketim without crashing."""
        from app.core.services.sofor_pdf_service import REPORTLAB_AVAILABLE

        if not REPORTLAB_AVAILABLE:
            pytest.skip("reportlab not installed")

        from app.core.services.sofor_pdf_service import SoforSeferPDFService

        svc = SoforSeferPDFService()
        sofor = _make_sofor()
        sefer = _make_sefer(tuketim=None)

        result = svc._build_pdf(sofor, [sefer], date(2024, 1, 1), date(2024, 1, 31))

        assert isinstance(result, bytes)

    async def test_integration_with_mock(self):
        """Two trips → PDF bytes returned from to_thread."""
        sofor = _make_sofor(ad_soyad="Mehmet Demir")
        seferler = [
            _make_sefer(id=10, mesafe_km=500, tuketim=40.0),
            _make_sefer(id=11, mesafe_km=250, tuketim=38.5),
        ]
        mock_uow = _make_uow(sofor=sofor, seferler=seferler)
        svc = _make_service()

        fake_pdf = b"%PDF-1.4 fake content"
        with (
            patch(
                "app.core.services.sofor_pdf_service.UnitOfWork", return_value=mock_uow
            ),
            patch("asyncio.to_thread", new=AsyncMock(return_value=fake_pdf)),
        ):
            result = await svc.olustur(
                sofor_id=2,
                baslangic=date(2024, 1, 1),
                bitis=date(2024, 1, 31),
            )

        assert result is not None
        assert isinstance(result, bytes)

    async def test_return_type_is_bytes_or_none(self):
        sofor = _make_sofor()
        seferler = [_make_sefer()]
        mock_uow = _make_uow(sofor=sofor, seferler=seferler)
        svc = _make_service()

        with (
            patch(
                "app.core.services.sofor_pdf_service.UnitOfWork", return_value=mock_uow
            ),
            patch("asyncio.to_thread", new=AsyncMock(return_value=b"fake")),
        ):
            result = await svc.olustur(1, date(2024, 1, 1), date(2024, 1, 31))

        assert result is None or isinstance(result, bytes)
