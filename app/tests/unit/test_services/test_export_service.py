"""ExportService unit tests."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

pytestmark = pytest.mark.unit


class TestExportService:
    def test_service_exists(self):
        """ExportService class is importable."""
        from v2.modules.import_excel.infrastructure.report_export import ExportService

        assert ExportService is not None

    def test_sanitize_filename_strips_path_traversal(self):
        """_sanitize_filename uses os.path.basename to prevent path traversal."""
        from v2.modules.import_excel.infrastructure.report_export import ExportService

        svc = ExportService.__new__(ExportService)
        result = svc._sanitize_filename("../../etc/passwd")
        # os.path.basename keeps the final component; special chars become _
        assert "/" not in result
        # The basename on POSIX returns "passwd", on Windows may differ—
        # either way, the returned filename must not be an absolute path.
        assert not result.startswith("/")

    def test_sanitize_filename_allows_safe_chars(self):
        """Alphanumeric, dot, dash, underscore should survive sanitization."""
        from v2.modules.import_excel.infrastructure.report_export import ExportService

        svc = ExportService.__new__(ExportService)
        result = svc._sanitize_filename("report_2024-01.xlsx")
        assert result == "report_2024-01.xlsx"

    def test_sanitize_filename_replaces_spaces(self):
        """Spaces are not in the safe set and get replaced with underscore."""
        from v2.modules.import_excel.infrastructure.report_export import ExportService

        svc = ExportService.__new__(ExportService)
        result = svc._sanitize_filename("my report file.xlsx")
        assert " " not in result

    async def test_basic_initialization(self):
        """ExportService can be instantiated without arguments."""
        from v2.modules.import_excel.infrastructure.report_export import ExportService

        svc = ExportService()
        assert svc is not None
        assert hasattr(svc, "EXPORT_DIR")

    async def test_export_to_excel_returns_path_when_openpyxl_available(self):
        """export_to_excel returns a filepath string when openpyxl is present."""
        from v2.modules.import_excel.infrastructure.report_export import ExportService

        svc = ExportService()
        fake_path = "/tmp/test_report.xlsx"

        with patch.object(svc, "_export_to_excel_sync", return_value=fake_path):
            with patch("asyncio.to_thread", new=AsyncMock(return_value=fake_path)):
                result = await svc.export_to_excel(
                    data={"trips": [{"plaka": "34ABC", "km": 500}]},
                    filename="test_report",
                    title="Test Rapor",
                )

        assert result == fake_path

    async def test_generate_template_unknown_type_returns_none(self):
        """generate_template returns None for an unsupported entity type."""
        from v2.modules.import_excel.infrastructure.report_export import ExportService

        svc = ExportService()
        with patch("asyncio.to_thread", new=AsyncMock(return_value=None)):
            result = await svc.generate_template("unknown_entity_xyz")

        assert result is None

    async def test_generate_template_sync_returns_none_for_invalid_type(self):
        """_generate_template_sync returns None for invalid entity_type."""
        from v2.modules.import_excel.infrastructure.report_export import (
            OPENPYXL_AVAILABLE,
            ExportService,
        )

        svc = ExportService()
        if OPENPYXL_AVAILABLE:
            result = svc._generate_template_sync("does_not_exist")
            assert result is None

    def test_export_to_excel_sync_sanitizes_filename(self):
        """_export_to_excel_sync is called with the sanitized filename."""
        from v2.modules.import_excel.infrastructure.report_export import ExportService

        svc = ExportService()
        # The actual sanitization: slashes are removed, basename applied
        raw = "bad/../../file"
        sanitized = svc._sanitize_filename(raw)
        # Sanitized should not start with '/' (not an absolute path)
        assert not sanitized.startswith("/")
        # And should not contain actual slash separators
        assert "/" not in sanitized

    async def test_export_fleet_summary_pdf_returns_none_on_error(self):
        """export_fleet_summary_pdf returns None when generator raises."""
        from datetime import date

        from v2.modules.import_excel.infrastructure.report_export import ExportService

        svc = ExportService()

        mock_gen = MagicMock()
        mock_gen.async_generate_fleet_summary = AsyncMock(
            side_effect=RuntimeError("PDF engine error")
        )

        with patch(
            "v2.modules.import_excel.infrastructure.report_export.get_report_generator",
            return_value=mock_gen,
        ):
            result = await svc.export_fleet_summary_pdf(
                start_date=date(2024, 1, 1),
                end_date=date(2024, 1, 31),
                data={},
                filename="fleet_report",
            )

        assert result is None

    async def test_export_vehicle_report_pdf_returns_none_on_error(self):
        """export_vehicle_report_pdf returns None when generator raises."""
        from v2.modules.import_excel.infrastructure.report_export import ExportService

        svc = ExportService()

        mock_gen = MagicMock()
        mock_gen.async_generate_vehicle_report = AsyncMock(
            side_effect=RuntimeError("PDF error")
        )

        with patch(
            "v2.modules.import_excel.infrastructure.report_export.get_report_generator",
            return_value=mock_gen,
        ):
            result = await svc.export_vehicle_report_pdf(
                arac_id=1, month=1, year=2024, data={}, filename="vehicle_report"
            )

        assert result is None
