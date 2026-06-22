from unittest.mock import AsyncMock, MagicMock, patch


async def test_driver_comparison_uses_real_unit_of_work():
    """
    _SessionUoW kullanılmamalı — gerçek UnitOfWork context manager olmalı.
    Test: UnitOfWork mock'lanınca endpoint onu kullanmalı.
    """
    from app.api.v1.endpoints import advanced_reports as ar_mod

    uow_instance = AsyncMock()
    uow_instance.__aenter__ = AsyncMock(return_value=uow_instance)
    uow_instance.__aexit__ = AsyncMock(return_value=False)

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

    # UnitOfWork is imported inside the function body; patch at source module path
    uow_patch_path = "app.database.unit_of_work.UnitOfWork"
    sofor_patch_path = "app.core.services.sofor_analiz_service.SoforAnalizService"
    gen_patch_path = "app.api.v1.endpoints.advanced_reports.get_report_generator"

    with (
        patch(uow_patch_path, return_value=uow_instance),
        patch(sofor_patch_path, return_value=mock_sofor_service),
        patch(gen_patch_path, return_value=mock_generator),
    ):
        response = await ar_mod.get_driver_comparison_pdf(current_user=mock_user)

    assert response.status_code == 200
    # Confirm UnitOfWork was entered as context manager
    uow_instance.__aenter__.assert_called_once()
