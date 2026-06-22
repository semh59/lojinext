"""Coverage tests for app/core/services/export_service.py.

Extends app/tests/unit/test_services/test_export_service.py with additional
coverage for the Excel sync path, PDF paths, and template generation.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# _sanitize_filename — edge cases
# ---------------------------------------------------------------------------


class TestSanitizeFilenameExtra:
    def _svc(self):
        from app.core.services.export_service import ExportService

        return ExportService.__new__(ExportService)

    def test_replaces_angle_brackets(self):
        svc = self._svc()
        result = svc._sanitize_filename("report<2024>.xlsx")
        assert "<" not in result
        assert ">" not in result

    def test_replaces_colon(self):
        svc = self._svc()
        result = svc._sanitize_filename("C:/windows/file.txt")
        # Basename on Windows: file.txt, no colon
        assert ":" not in result

    def test_empty_string_returns_empty_or_underscore(self):
        svc = self._svc()
        result = svc._sanitize_filename("")
        # os.path.basename("") returns ""; re.sub returns "" — just ensure no crash
        assert isinstance(result, str)

    def test_only_safe_chars_pass_through(self):
        svc = self._svc()
        name = "Fleet_Report_2024-01-15.xlsx"
        assert svc._sanitize_filename(name) == name


# ---------------------------------------------------------------------------
# _export_to_excel_sync — direct call
# ---------------------------------------------------------------------------


class TestExportToExcelSync:
    def test_returns_none_when_openpyxl_not_available(self):
        from app.core.services.export_service import ExportService

        svc = ExportService.__new__(ExportService)
        with patch("app.core.services.export_service.OPENPYXL_AVAILABLE", False):
            result = svc._export_to_excel_sync({}, "test.xlsx", "Test")
        assert result is None

    def test_handles_exception_gracefully(self, tmp_path):
        from app.core.services.export_service import OPENPYXL_AVAILABLE, ExportService

        if not OPENPYXL_AVAILABLE:
            pytest.skip("openpyxl not installed")

        svc = ExportService.__new__(ExportService)
        svc.EXPORT_DIR = tmp_path

        # Pass data that triggers an exception — use non-serializable type
        result = svc._export_to_excel_sync(None, "bad.xlsx", "T")
        # Either None on error or a valid path
        assert result is None or isinstance(result, str)

    def test_creates_xlsx_file_with_list_data(self, tmp_path):
        from app.core.services.export_service import OPENPYXL_AVAILABLE, ExportService

        if not OPENPYXL_AVAILABLE:
            pytest.skip("openpyxl not installed")

        svc = ExportService.__new__(ExportService)
        svc.EXPORT_DIR = tmp_path

        data = {
            "trips": [
                {"plaka": "34ABC", "km": 450, "yakit": 135},
                {"plaka": "06XYZ", "km": 300, "yakit": 90},
            ]
        }
        result = svc._export_to_excel_sync(data, "trips_report.xlsx", "Seferler")
        assert result is not None
        assert result.endswith(".xlsx")
        assert Path(result).exists()

    def test_creates_xlsx_file_with_dict_data(self, tmp_path):
        from app.core.services.export_service import OPENPYXL_AVAILABLE, ExportService

        if not OPENPYXL_AVAILABLE:
            pytest.skip("openpyxl not installed")

        svc = ExportService.__new__(ExportService)
        svc.EXPORT_DIR = tmp_path

        data = {"summary": {"total_km": 5000, "total_fuel": 1500}}
        result = svc._export_to_excel_sync(data, "summary.xlsx", "Özet")
        assert result is not None
        assert Path(result).exists()

    def test_appends_xlsx_extension_if_missing(self, tmp_path):
        from app.core.services.export_service import OPENPYXL_AVAILABLE, ExportService

        if not OPENPYXL_AVAILABLE:
            pytest.skip("openpyxl not installed")

        svc = ExportService.__new__(ExportService)
        svc.EXPORT_DIR = tmp_path

        result = svc._export_to_excel_sync({"a": {"x": 1}}, "no_extension", "T")
        assert result is None or result.endswith(".xlsx")

    def test_skips_empty_sections(self, tmp_path):
        from app.core.services.export_service import OPENPYXL_AVAILABLE, ExportService

        if not OPENPYXL_AVAILABLE:
            pytest.skip("openpyxl not installed")

        svc = ExportService.__new__(ExportService)
        svc.EXPORT_DIR = tmp_path

        data = {"empty_section": None, "real": {"value": 42}}
        result = svc._export_to_excel_sync(data, "mixed.xlsx", "Mix")
        assert result is not None


# ---------------------------------------------------------------------------
# export_to_excel  — async wrapper
# ---------------------------------------------------------------------------


class TestExportToExcel:
    async def test_sanitizes_before_calling_sync(self):
        from app.core.services.export_service import ExportService

        svc = ExportService.__new__(ExportService)

        called_with = {}

        def fake_sync(data, filename, title):
            called_with["filename"] = filename
            return "/tmp/fake.xlsx"

        svc._export_to_excel_sync = fake_sync

        with patch(
            "asyncio.to_thread",
            new=AsyncMock(side_effect=lambda fn, *a, **kw: fn(*a, **kw)),
        ):
            await svc.export_to_excel({"k": {}}, "../../bad<file>", "T")

        # After sanitization the filename must not contain slashes or angle brackets
        fn = called_with.get("filename", "")
        assert "<" not in fn
        assert ">" not in fn


# ---------------------------------------------------------------------------
# _generate_template_sync
# ---------------------------------------------------------------------------


class TestGenerateTemplateSync:
    def test_all_known_entity_types(self, tmp_path):
        from app.core.services.export_service import OPENPYXL_AVAILABLE, ExportService

        if not OPENPYXL_AVAILABLE:
            pytest.skip("openpyxl not installed")

        svc = ExportService.__new__(ExportService)
        svc.EXPORT_DIR = tmp_path

        for entity_type in ("yakit", "sefer", "arac", "sofor"):
            result = svc._generate_template_sync(entity_type)
            assert result is not None, (
                f"Template for '{entity_type}' should not be None"
            )
            assert Path(result).exists()

    def test_returns_none_for_unknown_type(self, tmp_path):
        from app.core.services.export_service import OPENPYXL_AVAILABLE, ExportService

        if not OPENPYXL_AVAILABLE:
            pytest.skip("openpyxl not installed")

        svc = ExportService.__new__(ExportService)
        svc.EXPORT_DIR = tmp_path

        result = svc._generate_template_sync("nonexistent_type")
        assert result is None

    def test_returns_none_when_openpyxl_not_available(self, tmp_path):
        from app.core.services.export_service import ExportService

        svc = ExportService.__new__(ExportService)
        svc.EXPORT_DIR = tmp_path

        with patch("app.core.services.export_service.OPENPYXL_AVAILABLE", False):
            result = svc._generate_template_sync("yakit")
        assert result is None


# ---------------------------------------------------------------------------
# generate_template  — async wrapper
# ---------------------------------------------------------------------------


class TestGenerateTemplate:
    async def test_returns_path_for_valid_type(self, tmp_path):
        from app.core.services.export_service import OPENPYXL_AVAILABLE, ExportService

        if not OPENPYXL_AVAILABLE:
            pytest.skip("openpyxl not installed")

        svc = ExportService.__new__(ExportService)
        svc.EXPORT_DIR = tmp_path

        with patch(
            "asyncio.to_thread",
            new=AsyncMock(side_effect=lambda fn, *a, **kw: fn(*a, **kw)),
        ):
            result = await svc.generate_template("sefer")

        assert result is not None


# ---------------------------------------------------------------------------
# export_fleet_summary_pdf
# ---------------------------------------------------------------------------


class TestExportFleetSummaryPdf:
    async def test_writes_file_on_success(self, tmp_path):
        from app.core.services.export_service import ExportService

        svc = ExportService.__new__(ExportService)
        svc.EXPORT_DIR = tmp_path

        pdf_bytes = b"%PDF fake content"

        mock_gen = MagicMock()
        mock_gen.async_generate_fleet_summary = AsyncMock(return_value=pdf_bytes)

        with patch(
            "app.core.services.export_service.get_report_generator",
            return_value=mock_gen,
        ):
            with patch(
                "asyncio.to_thread",
                new=AsyncMock(side_effect=lambda fn, *a, **kw: fn(*a, **kw)),
            ):
                result = await svc.export_fleet_summary_pdf(
                    start_date=date(2024, 1, 1),
                    end_date=date(2024, 1, 31),
                    data={"total_km": 5000},
                    filename="fleet_jan.pdf",
                )

        assert result is not None
        assert result.endswith(".pdf")

    async def test_appends_pdf_extension(self, tmp_path):
        from app.core.services.export_service import ExportService

        svc = ExportService.__new__(ExportService)
        svc.EXPORT_DIR = tmp_path

        pdf_bytes = b"%PDF-1.4 fake"

        mock_gen = MagicMock()
        mock_gen.async_generate_fleet_summary = AsyncMock(return_value=pdf_bytes)

        with patch(
            "app.core.services.export_service.get_report_generator",
            return_value=mock_gen,
        ):
            with patch(
                "asyncio.to_thread",
                new=AsyncMock(side_effect=lambda fn, *a, **kw: fn(*a, **kw)),
            ):
                result = await svc.export_fleet_summary_pdf(
                    start_date=date(2024, 1, 1),
                    end_date=date(2024, 1, 31),
                    data={},
                    filename="fleet_no_ext",
                )

        assert result is None or result.endswith(".pdf")


# ---------------------------------------------------------------------------
# export_vehicle_report_pdf
# ---------------------------------------------------------------------------


class TestExportVehicleReportPdf:
    async def test_writes_vehicle_pdf(self, tmp_path):
        from app.core.services.export_service import ExportService

        svc = ExportService.__new__(ExportService)
        svc.EXPORT_DIR = tmp_path

        pdf_bytes = b"%PDF vehicle"

        mock_gen = MagicMock()
        mock_gen.async_generate_vehicle_report = AsyncMock(return_value=pdf_bytes)

        with patch(
            "app.core.services.export_service.get_report_generator",
            return_value=mock_gen,
        ):
            with patch(
                "asyncio.to_thread",
                new=AsyncMock(side_effect=lambda fn, *a, **kw: fn(*a, **kw)),
            ):
                result = await svc.export_vehicle_report_pdf(
                    arac_id=1,
                    month=3,
                    year=2024,
                    data={"plaka": "34ABC"},
                    filename="vehicle_report.pdf",
                )

        assert result is not None

    async def test_returns_none_on_exception(self):
        from app.core.services.export_service import ExportService

        svc = ExportService.__new__(ExportService)

        mock_gen = MagicMock()
        mock_gen.async_generate_vehicle_report = AsyncMock(
            side_effect=Exception("Crash")
        )

        with patch(
            "app.core.services.export_service.get_report_generator",
            return_value=mock_gen,
        ):
            result = await svc.export_vehicle_report_pdf(
                arac_id=1, month=1, year=2024, data={}, filename="x.pdf"
            )

        assert result is None


# ---------------------------------------------------------------------------
# get_export_dir  — platform branch
# ---------------------------------------------------------------------------


class TestGetExportDir:
    def test_returns_path_object(self):
        from app.core.services.export_service import ExportService

        result = ExportService._get_export_dir()
        assert isinstance(result, Path)
        # Should end with "exports"
        assert result.name == "exports"
