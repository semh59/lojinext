from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.services.ml_service import MLService
from app.database.models import EgitimKuyrugu


@pytest.mark.asyncio
async def test_ml_schedule_training():
    """Test scheduling a new model training task."""
    mock_uow = AsyncMock()
    mock_uow.ml_training_repo = AsyncMock()
    mock_uow.model_versiyon_repo = AsyncMock()

    # Setup mocks
    mock_uow.ml_training_repo.get_active_tasks_for_vehicle.return_value = []
    # get_latest_version returns Optional[ModelVersiyon] (an ORM row), so the
    # service reads latest_version.versiyon. Mock an object, not a bare int.
    mock_uow.model_versiyon_repo.get_latest_version.return_value = MagicMock(versiyon=1)

    # Mocking session behavior
    mock_uow.session = MagicMock()
    mock_uow.__aenter__.return_value = mock_uow
    mock_uow.__aexit__.return_value = None
    mock_uow.commit = AsyncMock()

    service = MLService(uow=mock_uow)
    result = await service.schedule_training(arac_id=10)

    assert result.arac_id == 10
    assert result.hedef_versiyon == 2
    mock_uow.commit.assert_called_once()


@pytest.mark.asyncio
async def test_ml_complete_training_logic():
    """Verifies that updating progress to 100 doesn't auto-register, but updates status."""
    mock_uow = AsyncMock()
    mock_uow.ml_training_repo = AsyncMock()
    mock_uow.commit = AsyncMock()

    task = EgitimKuyrugu(id=1, arac_id=10, hedef_versiyon=5, durum="RUNNING")
    # update_task_progress fetches the session-tracked ORM row via session.get
    # (not the repo's dict projection) so attribute writes persist on commit.
    mock_uow.session.get = AsyncMock(return_value=task)

    mock_uow.__aenter__.return_value = mock_uow

    # WS broadcaster mock
    mock_ws = AsyncMock()

    with patch("app.core.services.ml_service.training_ws_manager", mock_ws):
        service = MLService(uow=mock_uow)

        await service.update_task_progress(task_id=1, ilerleme=100.0, durum="COMPLETED")

        # 1. Task fetched as the session-tracked ORM row (EgitimKuyrugu, task_id)
        mock_uow.session.get.assert_called_with(EgitimKuyrugu, 1)
        # Verify task status was set
        assert task.durum == "COMPLETED"
        assert task.ilerleme == 100.0

        # 2. WS should broadcast completion
        mock_ws.broadcast.assert_called_once()
        args = mock_ws.broadcast.call_args[0][0]
        assert args["durum"] == "COMPLETED"


@pytest.mark.asyncio
async def test_ml_register_model_version():
    """Tests model registration logic."""
    mock_uow = AsyncMock()
    mock_uow.session = MagicMock()
    mock_uow.commit = AsyncMock()
    mock_uow.__aenter__.return_value = mock_uow

    service = MLService(uow=mock_uow)
    metrics = {"r2_skoru": 0.88, "mae": 1.5}

    result = await service.register_model_version(
        arac_id=10,
        versiyon=2,
        metrics=metrics,
        model_dosya_yolu="/tmp/model_v2.bin",
        kullanilan_ozellikler={"feat1": 1},
        veri_sayisi=1000,
    )

    assert result.arac_id == 10
    assert result.versiyon == 2
    assert result.r2_skoru == 0.88
    mock_uow.session.add.assert_called_once()
    mock_uow.commit.assert_called_once()
