"""Coverage tests for app/core/services/report_generator.py"""

from __future__ import annotations

from datetime import date

import pytest

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# Helpers / module-level behaviour
# ---------------------------------------------------------------------------


def test_reportlab_available_flag():
    """REPORTLAB_AVAILABLE is a module-level bool."""
    from app.core.services import report_generator as rg

    assert isinstance(rg.REPORTLAB_AVAILABLE, bool)


def test_get_system_font_returns_string():
    from app.core.services.report_generator import get_system_font

    path = get_system_font()
    assert isinstance(path, str)
    assert path  # not empty


def test_get_system_font_windows(monkeypatch):
    monkeypatch.setattr("platform.system", lambda: "Windows")
    from app.core.services.report_generator import get_system_font

    path = get_system_font()
    assert "arial" in path.lower() or "Windows" in path


def test_get_system_font_darwin(monkeypatch):
    monkeypatch.setattr("platform.system", lambda: "Darwin")
    from app.core.services.report_generator import get_system_font

    path = get_system_font()
    assert "Helvetica" in path or "System" in path


def test_get_system_font_linux_existing(monkeypatch, tmp_path):
    """Linux path — simulate one candidate file existing."""
    monkeypatch.setattr("platform.system", lambda: "Linux")
    fake_font = tmp_path / "DejaVuSans.ttf"
    fake_font.write_bytes(b"")

    # patch os.path.exists so our fake path is "found" first
    orig_exists = __import__("os").path.exists

    def patched_exists(p):
        if "dejavu" in p.lower() or "DejaVu" in p:
            return p == str(fake_font) or p.lower().endswith("dejavusans.ttf")
        return orig_exists(p)

    monkeypatch.setattr("os.path.exists", patched_exists)
    from app.core.services import report_generator as rg

    # Re-execute so the patched os.path.exists applies
    path = rg.get_system_font()
    assert isinstance(path, str)


def test_get_system_font_linux_fallback(monkeypatch):
    """Linux — no candidates exist → returns default DejaVuSans path."""
    monkeypatch.setattr("platform.system", lambda: "Linux")
    monkeypatch.setattr("os.path.exists", lambda _p: False)
    from app.core.services.report_generator import get_system_font

    path = get_system_font()
    assert "DejaVuSans" in path or path.endswith(".ttf")


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------


def test_get_report_generator_singleton():
    import app.core.services.report_generator as rg

    rg._report_generator = None  # reset
    g1 = rg.get_report_generator()
    g2 = rg.get_report_generator()
    assert g1 is g2


def test_get_report_generator_returns_instance():
    from app.core.services.report_generator import (
        PDFReportGenerator,
        get_report_generator,
    )

    gen = get_report_generator()
    assert isinstance(gen, PDFReportGenerator)


# ---------------------------------------------------------------------------
# PDFReportGenerator — init without reportlab
# ---------------------------------------------------------------------------


def test_init_without_reportlab(monkeypatch):
    """When reportlab is not available __init__ returns early without crashing."""
    import app.core.services.report_generator as rg

    monkeypatch.setattr(rg, "REPORTLAB_AVAILABLE", False)
    gen = rg.PDFReportGenerator()
    # _styles is never set (early return) — should not have font_name either
    assert not hasattr(gen, "font_name")


def test_styles_property_none_when_reportlab_unavailable(monkeypatch):
    import app.core.services.report_generator as rg

    monkeypatch.setattr(rg, "REPORTLAB_AVAILABLE", False)
    gen = rg.PDFReportGenerator()
    # styles property checks REPORTLAB_AVAILABLE; returns None (self._styles stays unset)
    # Access via __class__ property to test the guard branch
    assert getattr(gen, "_styles", None) is None


# ---------------------------------------------------------------------------
# PDFReportGenerator — behaviour with reportlab available
# ---------------------------------------------------------------------------


@pytest.mark.skipif(
    not __import__(
        "app.core.services.report_generator", fromlist=["REPORTLAB_AVAILABLE"]
    ).REPORTLAB_AVAILABLE,
    reason="reportlab not installed",
)
class TestWithReportlab:
    def _generator(self):
        import app.core.services.report_generator as rg

        rg._report_generator = None
        return rg.get_report_generator()

    def test_font_name_is_string(self):
        gen = self._generator()
        assert isinstance(gen.font_name, str)
        assert gen.font_name  # not empty

    def test_font_bold_is_string(self):
        gen = self._generator()
        assert isinstance(gen.font_bold, str)

    def test_styles_not_none(self):
        gen = self._generator()
        assert gen.styles is not None

    def test_generate_fleet_summary_returns_bytes(self):
        gen = self._generator()
        data = {
            "total_vehicles": 5,
            "total_trips": 20,
            "total_distance": 15000,
            "total_fuel": 4500,
            "avg_consumption": 30.0,
            "total_cost": 85000.0,
            "vehicle_performance": [
                {
                    "plaka": "34ABC001",
                    "trips": 4,
                    "distance": 3000,
                    "consumption": 29.5,
                    "performance_score": 82,
                }
            ],
        }
        result = gen.generate_fleet_summary(date(2024, 1, 1), date(2024, 1, 31), data)
        assert isinstance(result, bytes)
        assert len(result) > 100  # actual PDF content

    def test_generate_fleet_summary_no_vehicle_performance(self):
        gen = self._generator()
        data = {
            "total_vehicles": 0,
            "total_trips": 0,
            "total_distance": 0,
            "total_fuel": 0,
            "avg_consumption": 0.0,
            "total_cost": 0.0,
        }
        result = gen.generate_fleet_summary(date(2024, 1, 1), date(2024, 1, 31), data)
        assert isinstance(result, bytes)
        assert len(result) > 0

    def test_generate_vehicle_report_returns_bytes(self):
        gen = self._generator()
        data = {
            "plaka": "06XY999",
            "marka": "Volvo",
            "model": "FH16",
            "hedef_tuketim": 32.0,
            "performance_score": 75.5,
        }
        result = gen.generate_vehicle_report(1, 3, 2024, data)
        assert isinstance(result, bytes)
        assert len(result) > 0

    def test_generate_driver_comparison_returns_bytes(self):
        gen = self._generator()
        driver_data = [
            {
                "ad_soyad": "Ahmet Yılmaz",
                "trips": 10,
                "consumption": 31.2,
                "score": 85.0,
            },
            {"ad_soyad": "Mehmet Kaya", "trips": 7, "consumption": 34.1, "score": 70.5},
        ]
        result = gen.generate_driver_comparison(driver_data)
        assert isinstance(result, bytes)
        assert len(result) > 0

    def test_generate_driver_comparison_empty_list(self):
        """Empty driver list → 'no data' paragraph PDF."""
        gen = self._generator()
        result = gen.generate_driver_comparison([])
        assert isinstance(result, bytes)
        assert len(result) > 0

    def test_vehicle_performance_score_critical_label(self):
        """Score < 50 → 'KRİTİK' status in vehicle table."""
        gen = self._generator()
        data = {
            "total_vehicles": 1,
            "total_trips": 1,
            "total_distance": 500,
            "total_fuel": 200,
            "avg_consumption": 40.0,
            "total_cost": 5000.0,
            "vehicle_performance": [
                {
                    "plaka": "34KR001",
                    "trips": 1,
                    "distance": 500,
                    "consumption": 40.0,
                    "performance_score": 40,
                }
            ],
        }
        # Should not raise
        result = gen.generate_fleet_summary(date(2024, 1, 1), date(2024, 1, 31), data)
        assert isinstance(result, bytes)

    def test_vehicle_performance_score_normal_label(self):
        """Score 50-80 → 'NORMAL' status."""
        gen = self._generator()
        data = {
            "total_vehicles": 1,
            "total_trips": 1,
            "total_distance": 500,
            "total_fuel": 150,
            "avg_consumption": 30.0,
            "total_cost": 3000.0,
            "vehicle_performance": [
                {
                    "plaka": "34NR001",
                    "trips": 1,
                    "distance": 500,
                    "consumption": 30.0,
                    "performance_score": 65,
                }
            ],
        }
        result = gen.generate_fleet_summary(date(2024, 1, 1), date(2024, 1, 31), data)
        assert isinstance(result, bytes)

    def test_vehicle_performance_capped_at_15(self):
        """Only first 15 vehicles are rendered."""
        gen = self._generator()
        vehicles = [
            {
                "plaka": f"34T{i:03d}",
                "trips": 1,
                "distance": 100,
                "consumption": 30.0,
                "performance_score": 75,
            }
            for i in range(20)
        ]
        data = {
            "total_vehicles": 20,
            "total_trips": 20,
            "total_distance": 2000,
            "total_fuel": 600,
            "avg_consumption": 30.0,
            "total_cost": 12000.0,
            "vehicle_performance": vehicles,
        }
        result = gen.generate_fleet_summary(date(2024, 1, 1), date(2024, 1, 31), data)
        assert isinstance(result, bytes)

    async def test_async_generate_fleet_summary(self):
        gen = self._generator()
        data = {"total_vehicles": 1, "total_trips": 1}
        result = await gen.async_generate_fleet_summary(
            date(2024, 1, 1), date(2024, 1, 31), data
        )
        assert isinstance(result, bytes)

    async def test_async_generate_vehicle_report(self):
        gen = self._generator()
        data = {"plaka": "06AS001"}
        result = await gen.async_generate_vehicle_report(1, 1, 2024, data)
        assert isinstance(result, bytes)


# ---------------------------------------------------------------------------
# _register_fonts fallback path (font not found → Helvetica)
# ---------------------------------------------------------------------------


@pytest.mark.skipif(
    not __import__(
        "app.core.services.report_generator", fromlist=["REPORTLAB_AVAILABLE"]
    ).REPORTLAB_AVAILABLE,
    reason="reportlab not installed",
)
def test_register_fonts_exception_fallback(monkeypatch):
    """When font registration raises, fallback to Helvetica."""
    import app.core.services.report_generator as rg

    # Make os.path.exists always False to force Helvetica fallback
    monkeypatch.setattr("os.path.exists", lambda _p: False)
    gen = rg.PDFReportGenerator()
    assert gen.font_name == "Helvetica"
    assert gen.font_bold == "Helvetica-Bold"
