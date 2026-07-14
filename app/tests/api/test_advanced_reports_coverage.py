"""
Advanced Reports endpoint coverage tests.

Targets missing lines in app/api/v1/endpoints/advanced_reports.py (~33% → ≥70%).
All service/DB calls are mocked — no real DB needed.

Patch rule: patch at the point of USE (the endpoint module's namespace), not
at the point of DEFINITION.
"""

from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

pytestmark = pytest.mark.unit

BASE = "/api/v1/advanced-reports"
ENDPOINT_MOD = "app.api.v1.endpoints.advanced_reports"


# ---------------------------------------------------------------------------
# Helper: cost analyzer mock
# ---------------------------------------------------------------------------


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
# Authentication guard tests
# ---------------------------------------------------------------------------


async def test_fleet_summary_pdf_no_auth(async_client):
    """GET /pdf/fleet-summary requires auth."""
    resp = await async_client.get(f"{BASE}/pdf/fleet-summary")
    assert resp.status_code == 401


async def test_vehicle_report_pdf_no_auth(async_client):
    """GET /pdf/vehicle/{id} requires auth."""
    resp = await async_client.get(f"{BASE}/pdf/vehicle/1?month=1&year=2026")
    assert resp.status_code == 401


async def test_driver_comparison_pdf_no_auth(async_client):
    """GET /pdf/driver-comparison requires auth."""
    resp = await async_client.get(f"{BASE}/pdf/driver-comparison")
    assert resp.status_code == 401


async def test_cost_period_no_auth(async_client):
    """GET /cost/period requires auth."""
    resp = await async_client.get(
        f"{BASE}/cost/period?start_date=2026-01-01&end_date=2026-01-31"
    )
    assert resp.status_code == 401


async def test_cost_trend_no_auth(async_client):
    """GET /cost/trend requires auth."""
    resp = await async_client.get(f"{BASE}/cost/trend")
    assert resp.status_code == 401


async def test_cost_savings_no_auth(async_client):
    """GET /cost/savings-potential requires auth."""
    resp = await async_client.get(f"{BASE}/cost/savings-potential")
    assert resp.status_code == 401


async def test_cost_roi_no_auth(async_client):
    """GET /cost/roi requires auth."""
    resp = await async_client.get(f"{BASE}/cost/roi")
    assert resp.status_code == 401


async def test_excel_export_no_auth(async_client):
    """GET /excel/export requires auth."""
    resp = await async_client.get(f"{BASE}/excel/export?report_type=fleet_summary")
    assert resp.status_code == 401


async def test_excel_template_no_auth(async_client):
    """GET /excel/template/{entity_type} requires auth."""
    resp = await async_client.get(f"{BASE}/excel/template/arac")
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# GET /cost/period — happy path & validation
# ---------------------------------------------------------------------------


async def test_cost_period_happy_path(async_client, admin_auth_headers):
    """Returns CostBreakdownResponse on success."""
    breakdown = _make_cost_breakdown()
    mock_analyzer = MagicMock()
    mock_analyzer.calculate_period_cost = AsyncMock(return_value=breakdown)

    with patch(f"{ENDPOINT_MOD}.get_cost_analyzer", return_value=mock_analyzer):
        resp = await async_client.get(
            f"{BASE}/cost/period",
            params={"start_date": "2026-01-01", "end_date": "2026-01-31"},
            headers=admin_auth_headers,
        )

    assert resp.status_code == 200
    data = resp.json()
    assert "fuel_cost" in data
    assert data["trip_count"] == 10


async def test_cost_period_invalid_date_format(async_client, admin_auth_headers):
    """Returns 400 when date format is invalid."""
    resp = await async_client.get(
        f"{BASE}/cost/period",
        params={"start_date": "01-01-2026", "end_date": "31-01-2026"},
        headers=admin_auth_headers,
    )
    assert resp.status_code == 400


async def test_cost_period_with_arac_id(async_client, admin_auth_headers):
    """Passes arac_id query param to analyzer."""
    breakdown = _make_cost_breakdown()
    mock_analyzer = MagicMock()
    mock_analyzer.calculate_period_cost = AsyncMock(return_value=breakdown)

    with patch(f"{ENDPOINT_MOD}.get_cost_analyzer", return_value=mock_analyzer):
        resp = await async_client.get(
            f"{BASE}/cost/period",
            params={
                "start_date": "2026-01-01",
                "end_date": "2026-01-31",
                "arac_id": 5,
            },
            headers=admin_auth_headers,
        )

    assert resp.status_code == 200
    mock_analyzer.calculate_period_cost.assert_called_once()


# ---------------------------------------------------------------------------
# GET /cost/trend
# ---------------------------------------------------------------------------


async def test_cost_trend_happy_path(async_client, admin_auth_headers):
    """Returns trend data from analyzer."""
    # Tier E madde 33: shape matches CostAnalyzer.get_monthly_trend's real
    # return dict (app/core/services/cost_analyzer.py) — the endpoint now has
    # response_model=List[CostTrendPoint], so a mismatched mock 422s instead
    # of silently passing through untyped.
    fake_trend = [
        {
            "month": 1,
            "year": 2026,
            "label": "01/2026",
            "fuel_cost": 15000.0,
            "fuel_liters": 4200.0,
            "trip_count": 12,
            "total_distance": 8000.0,
            "cost_per_km": 1.88,
        }
    ]
    mock_analyzer = MagicMock()
    mock_analyzer.get_monthly_trend = AsyncMock(return_value=fake_trend)

    with patch(f"{ENDPOINT_MOD}.get_cost_analyzer", return_value=mock_analyzer):
        resp = await async_client.get(
            f"{BASE}/cost/trend",
            params={"months": 6},
            headers=admin_auth_headers,
        )

    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)


async def test_cost_trend_months_default(async_client, admin_auth_headers):
    """Uses default months=12 when not provided."""
    mock_analyzer = MagicMock()
    mock_analyzer.get_monthly_trend = AsyncMock(return_value=[])

    with patch(f"{ENDPOINT_MOD}.get_cost_analyzer", return_value=mock_analyzer):
        resp = await async_client.get(
            f"{BASE}/cost/trend",
            headers=admin_auth_headers,
        )

    assert resp.status_code == 200
    mock_analyzer.get_monthly_trend.assert_called_once_with(12)


# ---------------------------------------------------------------------------
# GET /cost/vehicle-comparison
# ---------------------------------------------------------------------------


async def test_vehicle_cost_comparison_happy_path(async_client, admin_auth_headers):
    """Returns vehicle comparison data."""
    # Tier E madde 33: real shape from
    # CostAnalyzer.get_vehicle_cost_comparison's calculate_for_vehicle()
    # success branch — endpoint now has
    # response_model=List[VehicleCostComparisonItem].
    fake_data = [
        {
            "arac_id": 1,
            "plaka": "34ABC123",
            "fuel_cost": 5000.0,
            "total_distance": 2500.0,
            "cost_per_km": 2.0,
            "avg_consumption": 32.5,
        }
    ]
    mock_analyzer = MagicMock()
    mock_analyzer.get_vehicle_cost_comparison = AsyncMock(return_value=fake_data)

    with patch(f"{ENDPOINT_MOD}.get_cost_analyzer", return_value=mock_analyzer):
        resp = await async_client.get(
            f"{BASE}/cost/vehicle-comparison",
            params={"months": 3},
            headers=admin_auth_headers,
        )

    assert resp.status_code == 200


# ---------------------------------------------------------------------------
# GET /cost/savings-potential
# ---------------------------------------------------------------------------


async def test_savings_potential_happy_path(async_client, admin_auth_headers):
    """Returns SavingsPotentialResponse on success."""
    fake_result = {
        "current_consumption": 35.0,
        "target_consumption": 30.0,
        "current_cost": 20000.0,
        "target_cost": 17000.0,
        "potential_savings": 3000.0,
        "savings_percentage": 15.0,
        "annual_projection": 36000.0,
    }
    mock_analyzer = MagicMock()
    mock_analyzer.calculate_savings_potential = AsyncMock(return_value=fake_result)

    with patch(f"{ENDPOINT_MOD}.get_cost_analyzer", return_value=mock_analyzer):
        resp = await async_client.get(
            f"{BASE}/cost/savings-potential",
            params={"target_consumption": 30.0},
            headers=admin_auth_headers,
        )

    assert resp.status_code == 200
    data = resp.json()
    assert "potential_savings" in data


async def test_savings_potential_with_error_key(async_client, admin_auth_headers):
    """Returns 409 when analyzer returns an error key."""
    mock_analyzer = MagicMock()
    mock_analyzer.calculate_savings_potential = AsyncMock(
        return_value={"error": "Veri yetersiz"}
    )

    with patch(f"{ENDPOINT_MOD}.get_cost_analyzer", return_value=mock_analyzer):
        resp = await async_client.get(
            f"{BASE}/cost/savings-potential",
            headers=admin_auth_headers,
        )

    assert resp.status_code == 409


# ---------------------------------------------------------------------------
# GET /cost/roi
# ---------------------------------------------------------------------------


async def test_roi_happy_path(async_client, admin_auth_headers):
    """Returns ROIResponse on success."""
    fake_result = {
        "investment": 50000.0,
        "monthly_savings": 1000.0,
        "annual_savings": 12000.0,
        "payback_months": 50.0,
        "annual_roi_percentage": 24.0,
        "cost_improvement_pct": 10.0,
    }
    mock_analyzer = MagicMock()
    mock_analyzer.calculate_roi = AsyncMock(return_value=fake_result)

    with patch(f"{ENDPOINT_MOD}.get_cost_analyzer", return_value=mock_analyzer):
        resp = await async_client.get(
            f"{BASE}/cost/roi",
            params={"investment": 50000, "months": 12, "target_consumption": 30.0},
            headers=admin_auth_headers,
        )

    assert resp.status_code == 200
    data = resp.json()
    assert "annual_roi_percentage" in data


async def test_roi_with_error_key(async_client, admin_auth_headers):
    """Returns 409 when ROI analyzer returns error."""
    mock_analyzer = MagicMock()
    mock_analyzer.calculate_roi = AsyncMock(
        return_value={"error": "Sefer verisi bulunamadı"}
    )

    with patch(f"{ENDPOINT_MOD}.get_cost_analyzer", return_value=mock_analyzer):
        resp = await async_client.get(
            f"{BASE}/cost/roi",
            headers=admin_auth_headers,
        )

    assert resp.status_code == 409


# ---------------------------------------------------------------------------
# GET /excel/export — report type variants
# ---------------------------------------------------------------------------


async def test_excel_export_fleet_summary(async_client, admin_auth_headers):
    """Exports fleet_summary Excel successfully."""
    fake_xlsx = b"PK\x03\x04" + b"\x00" * 50

    with (
        patch(
            "app.core.services.report_service.ReportService.generate_fleet_summary",
            new=AsyncMock(return_value={"total": 5, "vehicles": []}),
        ),
        patch(
            "app.core.services.excel_service.ExcelService.export_data",
            new=AsyncMock(return_value=fake_xlsx),
        ),
    ):
        resp = await async_client.get(
            f"{BASE}/excel/export",
            params={"report_type": "fleet_summary"},
            headers=admin_auth_headers,
        )

    assert resp.status_code == 200


async def test_excel_export_driver_comparison(async_client, admin_auth_headers):
    """Exports driver_comparison Excel successfully."""
    fake_driver = MagicMock()
    fake_driver.ad_soyad = "Test Driver"
    fake_driver.toplam_sefer = 5
    fake_driver.ort_tuketim = 32.0
    fake_driver.performans_puani = 80.0
    fake_xlsx = b"PK\x03\x04" + b"\x00" * 50

    # driver_comparison uses an inline import: get_driver_stats (free function)
    with (
        patch(
            "v2.modules.driver.domain.driver_stats.get_driver_stats",
            AsyncMock(return_value=[fake_driver]),
        ),
        patch(
            "app.core.services.excel_service.ExcelService.export_data",
            new=AsyncMock(return_value=fake_xlsx),
        ),
    ):
        resp = await async_client.get(
            f"{BASE}/excel/export",
            params={"report_type": "driver_comparison"},
            headers=admin_auth_headers,
        )

    assert resp.status_code == 200


async def test_excel_export_cost_trend(async_client, admin_auth_headers):
    """Exports cost_trend Excel successfully."""
    fake_trend = [{"month": "2026-01", "cost": 10000}]
    fake_xlsx = b"PK\x03\x04" + b"\x00" * 50
    mock_analyzer = MagicMock()
    mock_analyzer.get_monthly_trend = AsyncMock(return_value=fake_trend)

    with (
        patch(f"{ENDPOINT_MOD}.get_cost_analyzer", return_value=mock_analyzer),
        patch(
            "app.core.services.excel_service.ExcelService.export_data",
            new=AsyncMock(return_value=fake_xlsx),
        ),
    ):
        resp = await async_client.get(
            f"{BASE}/excel/export",
            params={"report_type": "cost_trend", "months": 6},
            headers=admin_auth_headers,
        )

    assert resp.status_code == 200


async def test_excel_export_invalid_type(async_client, admin_auth_headers):
    """Returns 400 for unknown report_type."""
    resp = await async_client.get(
        f"{BASE}/excel/export",
        params={"report_type": "unknown_type"},
        headers=admin_auth_headers,
    )
    assert resp.status_code == 400


async def test_excel_export_missing_report_type(async_client, admin_auth_headers):
    """Returns 422 when report_type param is missing."""
    resp = await async_client.get(
        f"{BASE}/excel/export",
        headers=admin_auth_headers,
    )
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# GET /excel/template/{entity_type}
# ---------------------------------------------------------------------------


async def test_excel_template_not_found(async_client, admin_auth_headers):
    """Returns 404 when export service can't generate the template."""
    mock_svc = MagicMock()
    mock_svc.generate_template = AsyncMock(return_value=None)

    with patch(f"{ENDPOINT_MOD}.get_export_service", return_value=mock_svc):
        resp = await async_client.get(
            f"{BASE}/excel/template/arac",
            headers=admin_auth_headers,
        )

    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# GET /pdf/fleet-summary
# ---------------------------------------------------------------------------


async def test_fleet_summary_pdf_happy_path(async_client, admin_auth_headers):
    """Returns PDF bytes on success."""
    fake_pdf = b"%PDF-1.4 fake-content %%EOF"
    mock_gen = MagicMock()
    mock_gen.generate_fleet_summary.return_value = fake_pdf

    with (
        patch(
            "app.core.services.report_service.ReportService.generate_fleet_summary",
            new=AsyncMock(return_value={"total_km": 5000}),
        ),
        patch(f"{ENDPOINT_MOD}.get_report_generator", return_value=mock_gen),
    ):
        resp = await async_client.get(
            f"{BASE}/pdf/fleet-summary",
            headers=admin_auth_headers,
        )

    assert resp.status_code == 200
    assert "application/pdf" in resp.headers.get("content-type", "")
    assert resp.content[:4] == b"%PDF"


async def test_fleet_summary_pdf_with_date_params(async_client, admin_auth_headers):
    """Accepts start_date and end_date params."""
    fake_pdf = b"%PDF-1.4 fake %%EOF"
    mock_gen = MagicMock()
    mock_gen.generate_fleet_summary.return_value = fake_pdf

    with (
        patch(
            "app.core.services.report_service.ReportService.generate_fleet_summary",
            new=AsyncMock(return_value={}),
        ),
        patch(f"{ENDPOINT_MOD}.get_report_generator", return_value=mock_gen),
    ):
        resp = await async_client.get(
            f"{BASE}/pdf/fleet-summary",
            params={"start_date": "2026-01-01", "end_date": "2026-01-31"},
            headers=admin_auth_headers,
        )

    assert resp.status_code == 200


# ---------------------------------------------------------------------------
# GET /pdf/vehicle/{arac_id}
# ---------------------------------------------------------------------------


async def test_vehicle_report_pdf_happy_path(async_client, admin_auth_headers):
    """Returns PDF for a specific vehicle."""
    fake_pdf = b"%PDF-1.4 vehicle-report %%EOF"
    mock_gen = MagicMock()
    mock_gen.generate_vehicle_report.return_value = fake_pdf

    with (
        patch(
            "app.core.services.report_service.ReportService.generate_vehicle_report",
            new=AsyncMock(return_value={"plaka": "34ABC123"}),
        ),
        patch(f"{ENDPOINT_MOD}.get_report_generator", return_value=mock_gen),
    ):
        resp = await async_client.get(
            f"{BASE}/pdf/vehicle/1",
            params={"month": 1, "year": 2026},
            headers=admin_auth_headers,
        )

    assert resp.status_code == 200
    assert "application/pdf" in resp.headers.get("content-type", "")


async def test_vehicle_report_pdf_not_found(async_client, admin_auth_headers):
    """Returns 404 when vehicle data has error key."""
    with patch(
        "app.core.services.report_service.ReportService.generate_vehicle_report",
        new=AsyncMock(return_value={"error": "not found"}),
    ):
        resp = await async_client.get(
            f"{BASE}/pdf/vehicle/999",
            params={"month": 1, "year": 2026},
            headers=admin_auth_headers,
        )

    assert resp.status_code == 404


async def test_vehicle_report_pdf_no_data(async_client, admin_auth_headers):
    """Returns 404 when generate_vehicle_report returns falsy."""
    with patch(
        "app.core.services.report_service.ReportService.generate_vehicle_report",
        new=AsyncMock(return_value=None),
    ):
        resp = await async_client.get(
            f"{BASE}/pdf/vehicle/999",
            params={"month": 1, "year": 2026},
            headers=admin_auth_headers,
        )

    assert resp.status_code == 404


async def test_vehicle_report_pdf_invalid_month(async_client, admin_auth_headers):
    """Returns 422 when month is out of range."""
    resp = await async_client.get(
        f"{BASE}/pdf/vehicle/1",
        params={"month": 13, "year": 2026},
        headers=admin_auth_headers,
    )
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# GET /pdf/driver-comparison
# ---------------------------------------------------------------------------


async def test_driver_comparison_pdf_happy_path(async_client, admin_auth_headers):
    """Returns PDF for driver comparison."""
    fake_driver = MagicMock()
    fake_driver.ad_soyad = "Ali Veli"
    fake_driver.toplam_sefer = 8
    fake_driver.ort_tuketim = 31.5
    fake_driver.performans_puani = 90.0

    fake_pdf = b"%PDF-1.4 driver-comparison %%EOF"
    mock_gen = MagicMock()
    mock_gen.generate_driver_comparison.return_value = fake_pdf

    with (
        patch(
            "v2.modules.driver.domain.driver_stats.get_driver_stats",
            AsyncMock(return_value=[fake_driver]),
        ),
        patch(f"{ENDPOINT_MOD}.get_report_generator", return_value=mock_gen),
    ):
        resp = await async_client.get(
            f"{BASE}/pdf/driver-comparison",
            headers=admin_auth_headers,
        )

    assert resp.status_code == 200
    assert resp.content[:4] == b"%PDF"


# ---------------------------------------------------------------------------
# GET /pdf/vehicle-comparison
# ---------------------------------------------------------------------------


async def test_vehicle_comparison_pdf_happy_path(async_client, admin_auth_headers):
    """Returns PDF for vehicle comparison.

    Regression: the frontend's "Vehicle Comparison" template used to call
    /pdf/vehicle/{id} (id required) and report_type=vehicle_report on the
    excel endpoint — neither existed, so this template 404'd/400'd on every
    download. This endpoint is the real fix.
    """
    fake_vehicle = {
        "arac_id": 1,
        "plaka": "34 TEST 001",
        "fuel_cost": 5000.0,
        "total_distance": 12000.0,
        "cost_per_km": 0.42,
        "avg_consumption": 32.0,
    }
    fake_pdf = b"%PDF-1.4 vehicle-comparison %%EOF"
    mock_analyzer = MagicMock()
    mock_analyzer.get_vehicle_cost_comparison = AsyncMock(return_value=[fake_vehicle])
    mock_gen = MagicMock()
    mock_gen.generate_vehicle_comparison.return_value = fake_pdf

    with (
        patch(f"{ENDPOINT_MOD}.get_cost_analyzer", return_value=mock_analyzer),
        patch(f"{ENDPOINT_MOD}.get_report_generator", return_value=mock_gen),
    ):
        resp = await async_client.get(
            f"{BASE}/pdf/vehicle-comparison",
            headers=admin_auth_headers,
        )

    assert resp.status_code == 200
    assert resp.content[:4] == b"%PDF"
    mock_gen.generate_vehicle_comparison.assert_called_once_with([fake_vehicle])


async def test_excel_export_vehicle_comparison(async_client, admin_auth_headers):
    """Exports vehicle_comparison Excel successfully."""
    fake_vehicle = {
        "arac_id": 1,
        "plaka": "34 TEST 001",
        "fuel_cost": 5000.0,
        "total_distance": 12000.0,
        "cost_per_km": 0.42,
        "avg_consumption": 32.0,
    }
    fake_xlsx = b"PK\x03\x04" + b"\x00" * 50
    mock_analyzer = MagicMock()
    mock_analyzer.get_vehicle_cost_comparison = AsyncMock(return_value=[fake_vehicle])

    with (
        patch(f"{ENDPOINT_MOD}.get_cost_analyzer", return_value=mock_analyzer),
        patch(
            "app.core.services.excel_service.ExcelService.export_data",
            new=AsyncMock(return_value=fake_xlsx),
        ),
    ):
        resp = await async_client.get(
            f"{BASE}/excel/export",
            params={"report_type": "vehicle_comparison"},
            headers=admin_auth_headers,
        )

    assert resp.status_code == 200
