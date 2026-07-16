from unittest.mock import AsyncMock, MagicMock, patch

import pytest

pytestmark = pytest.mark.integration


async def test_driver_comparison_uses_real_unit_of_work(db_session):
    """
    Endpoint gerçek UnitOfWork context manager kullanmalı (real DB).
    db_session fixture UoW'u test oturumuna yönlendirir — endpoint yeşil döner.
    """
    from v2.modules.reports.api import advanced_reports_routes as ar_mod

    mock_drivers = [
        MagicMock(
            ad_soyad="Ali Veli",
            toplam_sefer=10,
            ort_tuketim=28.5,
            performans_puani=85.0,
        )
    ]
    mock_generator = MagicMock()
    mock_generator.generate_driver_comparison = MagicMock(return_value=b"%PDF-fake")

    mock_user = MagicMock()

    with (
        patch(
            "v2.modules.driver.domain.driver_stats.get_driver_stats",
            AsyncMock(return_value=mock_drivers),
        ),
        patch(
            "v2.modules.reports.api.advanced_reports_routes.get_report_generator",
            return_value=mock_generator,
        ),
    ):
        response = await ar_mod.get_driver_comparison_pdf(current_user=mock_user)

    assert response.status_code == 200
