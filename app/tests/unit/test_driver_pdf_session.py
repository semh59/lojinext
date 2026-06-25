from unittest.mock import AsyncMock, MagicMock, patch


async def test_driver_comparison_uses_real_unit_of_work(db_session):
    """
    Endpoint gerçek UnitOfWork context manager kullanmalı (real DB).
    db_session fixture UoW'u test oturumuna yönlendirir — endpoint yeşil döner.
    """
    from app.api.v1.endpoints import advanced_reports as ar_mod

    mock_drivers = [
        MagicMock(
            ad_soyad="Ali Veli",
            toplam_sefer=10,
            ort_tuketim=28.5,
            performans_puani=85.0,
        )
    ]
    mock_sofor_service = AsyncMock()
    mock_sofor_service.get_driver_stats = AsyncMock(return_value=mock_drivers)

    mock_generator = MagicMock()
    mock_generator.generate_driver_comparison = MagicMock(return_value=b"%PDF-fake")

    mock_user = MagicMock()

    with (
        patch(
            "app.core.services.sofor_analiz_service.SoforAnalizService",
            return_value=mock_sofor_service,
        ),
        patch(
            "app.api.v1.endpoints.advanced_reports.get_report_generator",
            return_value=mock_generator,
        ),
    ):
        response = await ar_mod.get_driver_comparison_pdf(current_user=mock_user)

    assert response.status_code == 200
