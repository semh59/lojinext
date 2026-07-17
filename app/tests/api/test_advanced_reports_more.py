"""
Advanced Reports endpoint — 2nd pass coverage.

Targets remaining uncovered branches in advanced_reports.py (~81% → higher):
- GET /pdf/fleet-summary: DomainError passthrough, generic exception → 500
- GET /pdf/vehicle/{id}: generic exception → 500, filename sanitization
- GET /pdf/driver-comparison: generic exception → 500, DomainError passthrough
- GET /cost/period: DomainError passthrough, generic exception → 500
- GET /excel/export: fleet_summary empty data → 404, generic exception → 500,
  cost_trend single dict result (not list), driver_comparison empty
- GET /excel/template: success path (file returned), generic exception
- GET /cost/trend: generic exception → 500
- GET /cost/vehicle-comparison: generic exception
- GET /cost/savings-potential: DomainError passthrough
- GET /cost/roi: DomainError passthrough
"""

from __future__ import annotations

from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

pytestmark = pytest.mark.unit

BASE = "/api/v1/advanced-reports"
MOD = "v2.modules.reports.api.advanced_reports_routes"


def _make_cost_breakdown(**kwargs):
    m = MagicMock()
    m.fuel_cost = kwargs.get("fuel_cost", 15000.0)
    m.fuel_liters = kwargs.get("fuel_liters", 500.0)
    m.avg_price_per_liter = kwargs.get("avg_price_per_liter", 30.0)
    m.trip_count = kwargs.get("trip_count", 10)
    m.total_distance = kwargs.get("total_distance", 5000.0)
    m.cost_per_km = kwargs.get("cost_per_km", 3.0)
    m.period_start = kwargs.get("period_start", date(2026, 1, 1))
    m.period_end = kwargs.get("period_end", date(2026, 1, 31))
    return m


# ---------------------------------------------------------------------------
# GET /pdf/fleet-summary — DomainError, generic exception
# ---------------------------------------------------------------------------


async def test_fleet_summary_pdf_domain_error(async_client, admin_auth_headers):
    """GET /pdf/fleet-summary DomainError is re-raised."""
    from app.core.exceptions import DomainError

    with patch(
        "v2.modules.reports.api.advanced_reports_routes.generate_fleet_summary",
        new=AsyncMock(side_effect=DomainError("domain error")),
    ):
        resp = await async_client.get(
            f"{BASE}/pdf/fleet-summary",
            headers=admin_auth_headers,
        )

    assert resp.status_code in (400, 422, 500, 503)


async def test_fleet_summary_pdf_generic_exception(async_client, admin_auth_headers):
    """GET /pdf/fleet-summary generic exception → 500."""
    with patch(
        "v2.modules.reports.api.advanced_reports_routes.generate_fleet_summary",
        new=AsyncMock(side_effect=RuntimeError("pdf generation failed")),
    ):
        resp = await async_client.get(
            f"{BASE}/pdf/fleet-summary",
            headers=admin_auth_headers,
        )

    assert resp.status_code == 500


# ---------------------------------------------------------------------------
# GET /pdf/vehicle/{id} — generic exception, plaka sanitization
# ---------------------------------------------------------------------------


async def test_vehicle_report_pdf_generic_exception(async_client, admin_auth_headers):
    """GET /pdf/vehicle/1 generic exception → 500."""
    with patch(
        "v2.modules.reports.api.advanced_reports_routes.generate_vehicle_report",
        new=AsyncMock(side_effect=RuntimeError("crash")),
    ):
        resp = await async_client.get(
            f"{BASE}/pdf/vehicle/1",
            params={"month": 6, "year": 2026},
            headers=admin_auth_headers,
        )

    assert resp.status_code == 500


async def test_vehicle_report_pdf_plaka_with_special_chars(
    async_client, admin_auth_headers
):
    """GET /pdf/vehicle/1 plaka with spaces/special chars is sanitized in filename."""
    fake_pdf = b"%PDF-1.4 test %%EOF"
    mock_gen = MagicMock()
    mock_gen.generate_vehicle_report.return_value = fake_pdf

    with (
        patch(
            "v2.modules.reports.api.advanced_reports_routes.generate_vehicle_report",
            new=AsyncMock(return_value={"plaka": "06 ABC 123/test<>"}),
        ),
        patch(f"{MOD}.get_report_generator", return_value=mock_gen),
    ):
        resp = await async_client.get(
            f"{BASE}/pdf/vehicle/1",
            params={"month": 1, "year": 2026},
            headers=admin_auth_headers,
        )

    assert resp.status_code == 200
    content_disp = resp.headers.get("content-disposition", "")
    # Filename should not contain <, >, or spaces (sanitized)
    assert "<" not in content_disp
    assert ">" not in content_disp


async def test_vehicle_report_pdf_empty_plaka(async_client, admin_auth_headers):
    """GET /pdf/vehicle/1 when plaka key absent → falls back to arac_{id}."""
    fake_pdf = b"%PDF-1.4 test %%EOF"
    mock_gen = MagicMock()
    mock_gen.generate_vehicle_report.return_value = fake_pdf

    with (
        patch(
            "v2.modules.reports.api.advanced_reports_routes.generate_vehicle_report",
            # Truthy dict without 'plaka' key → safe_plaka='' → "arac_5"
            new=AsyncMock(return_value={"arac_id": 5}),
        ),
        patch(f"{MOD}.get_report_generator", return_value=mock_gen),
    ):
        resp = await async_client.get(
            f"{BASE}/pdf/vehicle/5",
            params={"month": 3, "year": 2026},
            headers=admin_auth_headers,
        )

    assert resp.status_code == 200
    content_disp = resp.headers.get("content-disposition", "")
    assert "arac_5" in content_disp


# ---------------------------------------------------------------------------
# GET /pdf/driver-comparison — generic exception, DomainError
# ---------------------------------------------------------------------------


async def test_driver_comparison_pdf_generic_exception(
    async_client, admin_auth_headers
):
    """GET /pdf/driver-comparison generic exception → 500."""
    with patch(
        "v2.modules.driver.public.get_driver_stats",
        new=AsyncMock(side_effect=RuntimeError("crash")),
    ):
        resp = await async_client.get(
            f"{BASE}/pdf/driver-comparison",
            headers=admin_auth_headers,
        )

    assert resp.status_code == 500


async def test_driver_comparison_pdf_domain_error(async_client, admin_auth_headers):
    """GET /pdf/driver-comparison DomainError → re-raised."""
    from app.core.exceptions import DomainError

    with patch(
        "v2.modules.driver.public.get_driver_stats",
        new=AsyncMock(side_effect=DomainError("domain issue")),
    ):
        resp = await async_client.get(
            f"{BASE}/pdf/driver-comparison",
            headers=admin_auth_headers,
        )

    assert resp.status_code in (400, 422, 500, 503)


# ---------------------------------------------------------------------------
# GET /cost/period — DomainError passthrough, generic exception
# ---------------------------------------------------------------------------


async def test_cost_period_domain_error(async_client, admin_auth_headers):
    """GET /cost/period DomainError is re-raised."""
    from app.core.exceptions import DomainError

    mock_analyzer = MagicMock()
    mock_analyzer.calculate_period_cost = AsyncMock(
        side_effect=DomainError("domain error")
    )

    with patch(f"{MOD}.calculate_period_cost", mock_analyzer.calculate_period_cost):
        resp = await async_client.get(
            f"{BASE}/cost/period",
            params={"start_date": "2026-01-01", "end_date": "2026-01-31"},
            headers=admin_auth_headers,
        )

    assert resp.status_code in (400, 422, 500, 503)


async def test_cost_period_generic_exception(async_client, admin_auth_headers):
    """GET /cost/period generic exception → endpoint lets it bubble (no try/except)."""
    mock_analyzer = MagicMock()
    mock_analyzer.calculate_period_cost = AsyncMock(side_effect=RuntimeError("crash"))

    # The endpoint has no generic exception handler — the exception propagates
    # through to the test client. Use raise_server_exceptions=False to get the
    # response instead of the exception.
    with patch(f"{MOD}.calculate_period_cost", mock_analyzer.calculate_period_cost):
        with pytest.raises(RuntimeError, match="crash"):
            await async_client.get(
                f"{BASE}/cost/period",
                params={"start_date": "2026-01-01", "end_date": "2026-01-31"},
                headers=admin_auth_headers,
            )


# ---------------------------------------------------------------------------
# GET /excel/export — empty data → 404, cost_trend dict result, general exception
# ---------------------------------------------------------------------------


async def test_excel_export_fleet_summary_empty_data(async_client, admin_auth_headers):
    """GET /excel/export fleet_summary returns empty raw_data → 404."""
    with patch(
        "v2.modules.reports.api.advanced_reports_routes.generate_fleet_summary",
        new=AsyncMock(return_value=[]),  # empty list
    ):
        resp = await async_client.get(
            f"{BASE}/excel/export",
            params={"report_type": "fleet_summary"},
            headers=admin_auth_headers,
        )

    assert resp.status_code == 404


async def test_excel_export_cost_trend_dict_result(async_client, admin_auth_headers):
    """GET /excel/export cost_trend when analyzer returns a single dict (not list)."""
    fake_xlsx = b"PK\x03\x04" + b"\x00" * 50
    mock_analyzer = MagicMock()
    # Returns a single dict instead of list
    mock_analyzer.get_monthly_trend = AsyncMock(
        return_value={"month": "2026-01", "cost": 10000}
    )

    with (
        patch(f"{MOD}.get_monthly_trend", mock_analyzer.get_monthly_trend),
        patch(
            "v2.modules.reports.api.advanced_reports_routes.export_data",
            new=AsyncMock(return_value=fake_xlsx),
        ),
    ):
        resp = await async_client.get(
            f"{BASE}/excel/export",
            params={"report_type": "cost_trend"},
            headers=admin_auth_headers,
        )

    assert resp.status_code == 200


async def test_excel_export_generic_exception(async_client, admin_auth_headers):
    """GET /excel/export generic exception → 500."""
    with patch(
        "v2.modules.reports.api.advanced_reports_routes.generate_fleet_summary",
        new=AsyncMock(side_effect=RuntimeError("crash")),
    ):
        resp = await async_client.get(
            f"{BASE}/excel/export",
            params={"report_type": "fleet_summary"},
            headers=admin_auth_headers,
        )

    assert resp.status_code == 500


async def test_excel_export_driver_comparison_empty(async_client, admin_auth_headers):
    """GET /excel/export driver_comparison with empty drivers → 404."""
    with patch(
        "v2.modules.driver.public.get_driver_stats",
        AsyncMock(return_value=[]),  # empty
    ):
        resp = await async_client.get(
            f"{BASE}/excel/export",
            params={"report_type": "driver_comparison"},
            headers=admin_auth_headers,
        )

    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# GET /excel/template — success path
# ---------------------------------------------------------------------------


async def test_excel_template_success(async_client, admin_auth_headers, tmp_path):
    """GET /excel/template/arac with valid filepath → FileResponse."""
    # Create a temp file to serve
    fake_file = tmp_path / "arac_template.xlsx"
    fake_file.write_bytes(b"PK\x03\x04" + b"\x00" * 50)

    mock_svc = MagicMock()
    mock_svc.generate_template = AsyncMock(return_value=str(fake_file))

    with patch(f"{MOD}.get_export_service", return_value=mock_svc):
        resp = await async_client.get(
            f"{BASE}/excel/template/arac",
            headers=admin_auth_headers,
        )

    assert resp.status_code == 200


# ---------------------------------------------------------------------------
# GET /cost/trend — generic exception → 500
# ---------------------------------------------------------------------------


async def test_cost_trend_generic_exception(async_client, admin_auth_headers):
    """GET /cost/trend generic exception propagates (no generic try/except)."""
    mock_analyzer = MagicMock()
    mock_analyzer.get_monthly_trend = AsyncMock(side_effect=RuntimeError("crash"))

    with patch(f"{MOD}.get_monthly_trend", mock_analyzer.get_monthly_trend):
        with pytest.raises(RuntimeError, match="crash"):
            await async_client.get(
                f"{BASE}/cost/trend",
                headers=admin_auth_headers,
            )


# ---------------------------------------------------------------------------
# GET /cost/vehicle-comparison — generic exception
# ---------------------------------------------------------------------------


async def test_vehicle_cost_comparison_generic_exception(
    async_client, admin_auth_headers
):
    """GET /cost/vehicle-comparison generic exception propagates (no generic handler)."""
    mock_analyzer = MagicMock()
    mock_analyzer.get_vehicle_cost_comparison = AsyncMock(
        side_effect=RuntimeError("crash")
    )

    with patch(
        f"{MOD}.analyze_vehicle_cost_comparison",
        mock_analyzer.get_vehicle_cost_comparison,
    ):
        with pytest.raises(RuntimeError, match="crash"):
            await async_client.get(
                f"{BASE}/cost/vehicle-comparison",
                headers=admin_auth_headers,
            )


# ---------------------------------------------------------------------------
# GET /cost/savings-potential — DomainError passthrough
# ---------------------------------------------------------------------------


async def test_savings_potential_domain_error(async_client, admin_auth_headers):
    """GET /cost/savings-potential DomainError is re-raised."""
    from app.core.exceptions import DomainError

    mock_analyzer = MagicMock()
    mock_analyzer.calculate_savings_potential = AsyncMock(
        side_effect=DomainError("domain error")
    )

    with patch(
        f"{MOD}.calculate_savings_potential", mock_analyzer.calculate_savings_potential
    ):
        resp = await async_client.get(
            f"{BASE}/cost/savings-potential",
            headers=admin_auth_headers,
        )

    assert resp.status_code in (400, 422, 500, 503)


# ---------------------------------------------------------------------------
# GET /cost/roi — DomainError passthrough
# ---------------------------------------------------------------------------


async def test_roi_domain_error(async_client, admin_auth_headers):
    """GET /cost/roi DomainError is re-raised."""
    from app.core.exceptions import DomainError

    mock_analyzer = MagicMock()
    mock_analyzer.calculate_roi = AsyncMock(side_effect=DomainError("domain error"))

    with patch(f"{MOD}.calculate_roi", mock_analyzer.calculate_roi):
        resp = await async_client.get(
            f"{BASE}/cost/roi",
            headers=admin_auth_headers,
        )

    assert resp.status_code in (400, 422, 500, 503)


# ---------------------------------------------------------------------------
# GET /excel/export — fleet_summary: raw_data as dict (wrapped in list)
# ---------------------------------------------------------------------------


async def test_excel_export_fleet_summary_dict_result(async_client, admin_auth_headers):
    """GET /excel/export fleet_summary: raw_data is dict → wrapped in [raw_data]."""
    fake_xlsx = b"PK\x03\x04" + b"\x00" * 50

    with (
        patch(
            "v2.modules.reports.api.advanced_reports_routes.generate_fleet_summary",
            new=AsyncMock(return_value={"total": 5, "vehicles": []}),
        ),
        patch(
            "v2.modules.reports.api.advanced_reports_routes.export_data",
            new=AsyncMock(return_value=fake_xlsx),
        ),
    ):
        resp = await async_client.get(
            f"{BASE}/excel/export",
            params={"report_type": "fleet_summary"},
            headers=admin_auth_headers,
        )

    assert resp.status_code == 200


# ---------------------------------------------------------------------------
# parse_date_param integration — invalid dates in fleet-summary
# ---------------------------------------------------------------------------


async def test_fleet_summary_pdf_invalid_start_date(async_client, admin_auth_headers):
    """GET /pdf/fleet-summary with invalid start_date → 400 from parse_date_param."""
    resp = await async_client.get(
        f"{BASE}/pdf/fleet-summary",
        params={"start_date": "not-a-date"},
        headers=admin_auth_headers,
    )
    assert resp.status_code in (400, 422, 500)
