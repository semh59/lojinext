"""Integration tests for advanced reports endpoint — /api/v1/advanced-reports/"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

pytestmark = [pytest.mark.asyncio, pytest.mark.integration]

BASE = "/api/v1/advanced-reports"


# ---------------------------------------------------------------------------
# GET /api/v1/advanced-reports/pdf/driver-comparison — PDF report
# ---------------------------------------------------------------------------


async def test_driver_comparison_pdf_returns_pdf(async_client, admin_auth_headers):
    """
    Driver comparison PDF endpoint returns 200 with application/pdf content.
    SoforAnalizService and the report generator are mocked to avoid DB/IO deps.
    """
    # Minimal fake driver stats object
    fake_driver = MagicMock()
    fake_driver.ad_soyad = "Test Sofor"
    fake_driver.toplam_sefer = 10
    fake_driver.ort_tuketim = 30.5
    fake_driver.performans_puani = 85.0

    # Minimal valid PDF bytes (PDF header + EOF marker)
    fake_pdf = b"%PDF-1.4 fake-pdf-content %%EOF"

    with (
        patch(
            "v2.modules.driver.domain.driver_stats.get_driver_stats",
            AsyncMock(return_value=[fake_driver]),
        ),
        patch(
            "app.core.services.report_generator.get_report_generator"
        ) as mock_gen_factory,
    ):
        mock_generator = MagicMock()
        mock_generator.generate_driver_comparison.return_value = fake_pdf
        mock_gen_factory.return_value = mock_generator

        response = await async_client.get(
            f"{BASE}/pdf/driver-comparison", headers=admin_auth_headers
        )

    assert response.status_code == 200, response.text
    assert "application/pdf" in response.headers.get("content-type", "")
    # First 4 bytes of a PDF file start with %PDF
    assert response.content[:4] == b"%PDF", (
        f"Response does not start with PDF magic bytes: {response.content[:8]!r}"
    )


async def test_driver_comparison_pdf_no_auth_gets_401(async_client):
    """Unauthenticated request is rejected with 401."""
    response = await async_client.get(f"{BASE}/pdf/driver-comparison")
    assert response.status_code == 401, response.text


# ---------------------------------------------------------------------------
# GET /api/v1/advanced-reports/pdf/fleet-summary — unexpected error leak
# ---------------------------------------------------------------------------


async def test_fleet_summary_pdf_unexpected_error_does_not_leak_internal_message(
    async_client, admin_auth_headers
):
    """2026-07-02 prod-grade denetimi P2 (Tier A madde 3): fleet-summary PDF
    ucunda beklenmeyen bir hata ham `str(e)` ile client'a sızmamalı."""
    sensitive_detail = (
        "psycopg2.OperationalError: FATAL: password authentication failed"
    )
    with patch(
        "app.core.services.report_service.ReportService.generate_fleet_summary",
        new=AsyncMock(side_effect=RuntimeError(sensitive_detail)),
    ):
        response = await async_client.get(
            f"{BASE}/pdf/fleet-summary", headers=admin_auth_headers
        )
    assert response.status_code == 500
    assert sensitive_detail not in response.text, (
        f"Ham hata mesajı client'a sızdı: {response.text[:300]}"
    )


# ---------------------------------------------------------------------------
# GET /api/v1/advanced-reports/pdf/vehicle/{arac_id} — unexpected error leak
# ---------------------------------------------------------------------------


async def test_vehicle_pdf_unexpected_error_does_not_leak_internal_message(
    async_client, admin_auth_headers
):
    """2026-07-02 prod-grade denetimi P2 (Tier A madde 3): vehicle PDF ucunda
    beklenmeyen bir hata ham `str(e)` ile client'a sızmamalı."""
    sensitive_detail = (
        "internal stack trace with secret config path /etc/lojinext/secret.key"
    )
    with patch(
        "app.core.services.report_service.ReportService.generate_vehicle_report",
        new=AsyncMock(side_effect=RuntimeError(sensitive_detail)),
    ):
        response = await async_client.get(
            f"{BASE}/pdf/vehicle/1",
            params={"month": 1, "year": 2026},
            headers=admin_auth_headers,
        )
    assert response.status_code == 500
    assert sensitive_detail not in response.text, (
        f"Ham hata mesajı client'a sızdı: {response.text[:300]}"
    )


# ---------------------------------------------------------------------------
# GET /api/v1/advanced-reports/excel/export — Excel export
# ---------------------------------------------------------------------------


async def test_excel_export_returns_xlsx(async_client, admin_auth_headers):
    """
    Excel export endpoint returns 200 with XLSX content.
    The first 4 bytes of an XLSX file are the ZIP magic: PK\\x03\\x04.
    ReportService and ExcelService are mocked to avoid real DB queries.
    """
    # Minimal XLSX magic bytes (ZIP local file header)
    xlsx_magic = b"PK\x03\x04"
    fake_xlsx = xlsx_magic + b"\x00" * 100  # stub content after magic

    with (
        patch(
            "app.core.services.report_service.ReportService.generate_fleet_summary",
            new=AsyncMock(return_value={"total": 0, "trips": []}),
        ),
        patch(
            "app.api.v1.endpoints.advanced_reports.export_data",
            new=AsyncMock(return_value=fake_xlsx),
        ),
    ):
        response = await async_client.get(
            f"{BASE}/excel/export",
            params={"report_type": "fleet_summary"},
            headers=admin_auth_headers,
        )

    assert response.status_code == 200, response.text
    content_type = response.headers.get("content-type", "")
    assert (
        "spreadsheetml" in content_type or "application/octet-stream" in content_type
    ), f"Unexpected content-type: {content_type}"
    assert response.content[:4] == xlsx_magic, (
        f"Response does not start with XLSX magic bytes: {response.content[:8]!r}"
    )


async def test_excel_export_no_auth_gets_401(async_client):
    """Unauthenticated request is rejected with 401."""
    response = await async_client.get(
        f"{BASE}/excel/export", params={"report_type": "fleet_summary"}
    )
    assert response.status_code == 401, response.text


async def test_excel_export_invalid_report_type_returns_error(
    async_client, admin_auth_headers
):
    """Bilinmeyen report_type 400 döndürmelidir."""
    response = await async_client.get(
        f"{BASE}/excel/export",
        params={"report_type": "nonexistent_report"},
        headers=admin_auth_headers,
    )
    assert response.status_code == 400


async def test_excel_export_unexpected_error_does_not_leak_internal_message(
    async_client, admin_auth_headers
):
    """2026-07-02 prod-grade denetimi P2 (Tier A madde 3): beklenmeyen bir hata
    oluştuğunda ham `str(e)` client'a sızmamalı (bilgi sızıntısı) — genel bir
    mesaj dönmeli, gerçek detay yalnızca sunucu log'una yazılmalı."""
    sensitive_detail = "connection to postgresql://lojinext_user:s3cr3t@10.0.0.5/db failed"  # pragma: allowlist secret
    with patch(
        "app.core.services.report_service.ReportService.generate_fleet_summary",
        new=AsyncMock(side_effect=RuntimeError(sensitive_detail)),
    ):
        response = await async_client.get(
            f"{BASE}/excel/export",
            params={"report_type": "fleet_summary"},
            headers=admin_auth_headers,
        )
    assert response.status_code == 500
    assert sensitive_detail not in response.text, (
        f"Ham hata mesajı client'a sızdı: {response.text[:300]}"
    )


# ---------------------------------------------------------------------------
# GET /api/v1/advanced-reports/excel/template/{entity_type}
# ---------------------------------------------------------------------------


async def test_excel_template_no_auth_gets_401(async_client):
    """Unauthenticated request for a template is rejected with 401."""
    response = await async_client.get(f"{BASE}/excel/template/arac")
    assert response.status_code == 401, response.text
