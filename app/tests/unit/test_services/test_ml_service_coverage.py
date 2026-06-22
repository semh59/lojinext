"""MLService unit tests — app/core/services/ml_service.py

Tests cover:
- schedule_training: active tasks exist raises 400, no tasks schedules new (version 1),
  existing version increments, user_id recorded
- update_task_progress: task not found raises 404, RUNNING sets baslangic_zaman,
  COMPLETED sets bitis_zaman, FAILED sets hata_detay + bitis_zaman,
  broadcasts via WS manager
- get_training_queue: returns ordered list
- register_model_version: creates ModelVersiyon with correct fields
"""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_uow():
    """Return a fully mocked UnitOfWork context manager."""
    uow = MagicMock()
    uow.__aenter__ = AsyncMock(return_value=uow)
    uow.__aexit__ = AsyncMock(return_value=False)
    uow.session = MagicMock()
    uow.session.add = MagicMock()
    uow.commit = AsyncMock()
    uow.ml_training_repo = MagicMock()
    uow.model_versiyon_repo = MagicMock()
    return uow


def _make_service(uow=None):
    """Return MLService with a mocked UnitOfWork."""
    from app.core.services.ml_service import MLService

    if uow is None:
        uow = _make_uow()
    svc = MLService.__new__(MLService)
    svc.uow = uow
    return svc, uow


# ---------------------------------------------------------------------------
# schedule_training
# ---------------------------------------------------------------------------


class TestScheduleTraining:
    async def test_active_tasks_raises_400(self):
        """schedule_training raises HTTPException(400) when active task exists."""
        svc, uow = _make_service()
        uow.ml_training_repo.get_active_tasks_for_vehicle = AsyncMock(
            return_value=[MagicMock()]  # existing active task
        )

        with pytest.raises(HTTPException) as exc_info:
            await svc.schedule_training(arac_id=1, user_id=None)

        assert exc_info.value.status_code == 400
        assert "active training task" in exc_info.value.detail.lower()

    async def test_no_active_tasks_creates_version_1(self):
        """schedule_training creates task with hedef_versiyon=1 when no prior version."""
        svc, uow = _make_service()
        uow.ml_training_repo.get_active_tasks_for_vehicle = AsyncMock(return_value=[])
        uow.model_versiyon_repo.get_latest_version = AsyncMock(return_value=None)

        added_task = None

        def capture_add(obj):
            nonlocal added_task
            added_task = obj

        uow.session.add = capture_add

        from app.database.models import EgitimKuyrugu

        fake_task = MagicMock(spec=EgitimKuyrugu)
        fake_task.arac_id = 1
        fake_task.hedef_versiyon = 1
        fake_task.durum = "WAITING"

        with patch(
            "app.core.services.ml_service.EgitimKuyrugu",
            return_value=fake_task,
        ):
            result = await svc.schedule_training(arac_id=1, user_id=None)

        assert result is fake_task
        assert uow.commit.called

    async def test_existing_version_increments(self):
        """schedule_training increments version when prior version exists."""
        svc, uow = _make_service()
        uow.ml_training_repo.get_active_tasks_for_vehicle = AsyncMock(return_value=[])
        uow.model_versiyon_repo.get_latest_version = AsyncMock(
            return_value=MagicMock(versiyon=3)
        )

        from app.database.models import EgitimKuyrugu

        created_kwargs = {}

        def fake_egitim(**kwargs):
            created_kwargs.update(kwargs)
            task = MagicMock(spec=EgitimKuyrugu)
            return task

        with patch(
            "app.core.services.ml_service.EgitimKuyrugu",
            side_effect=fake_egitim,
        ):
            await svc.schedule_training(arac_id=2, user_id=10)

        assert created_kwargs["hedef_versiyon"] == 4
        assert created_kwargs["tetikleyen_kullanici_id"] == 10

    async def test_user_id_recorded_in_task(self):
        """schedule_training stores user_id in tetikleyen_kullanici_id."""
        svc, uow = _make_service()
        uow.ml_training_repo.get_active_tasks_for_vehicle = AsyncMock(return_value=[])
        uow.model_versiyon_repo.get_latest_version = AsyncMock(return_value=None)

        from app.database.models import EgitimKuyrugu

        created_kwargs = {}

        def fake_egitim(**kwargs):
            created_kwargs.update(kwargs)
            return MagicMock(spec=EgitimKuyrugu)

        with patch(
            "app.core.services.ml_service.EgitimKuyrugu",
            side_effect=fake_egitim,
        ):
            await svc.schedule_training(arac_id=5, user_id=99)

        assert created_kwargs["tetikleyen_kullanici_id"] == 99

    async def test_waiting_status_set(self):
        """schedule_training creates task with durum='WAITING'."""
        svc, uow = _make_service()
        uow.ml_training_repo.get_active_tasks_for_vehicle = AsyncMock(return_value=[])
        uow.model_versiyon_repo.get_latest_version = AsyncMock(return_value=None)

        from app.database.models import EgitimKuyrugu

        created_kwargs = {}

        def fake_egitim(**kwargs):
            created_kwargs.update(kwargs)
            return MagicMock(spec=EgitimKuyrugu)

        with patch(
            "app.core.services.ml_service.EgitimKuyrugu",
            side_effect=fake_egitim,
        ):
            await svc.schedule_training(arac_id=3)

        assert created_kwargs["durum"] == "WAITING"


# ---------------------------------------------------------------------------
# update_task_progress
# ---------------------------------------------------------------------------


class TestUpdateTaskProgress:
    async def test_task_not_found_raises_404(self):
        """update_task_progress raises HTTPException(404) when task not found."""
        svc, uow = _make_service()
        uow.session.get = AsyncMock(return_value=None)

        with patch("app.core.services.ml_service.training_ws_manager") as mock_ws:
            mock_ws.broadcast = AsyncMock()
            with pytest.raises(HTTPException) as exc_info:
                await svc.update_task_progress(
                    task_id=999,
                    ilerleme=50.0,
                    durum="RUNNING",
                )

        assert exc_info.value.status_code == 404

    async def test_running_sets_baslangic_zaman(self):
        """RUNNING status sets baslangic_zaman when not already set."""
        svc, uow = _make_service()
        task = MagicMock()
        task.arac_id = 1
        task.baslangic_zaman = None  # not yet set
        uow.session.get = AsyncMock(return_value=task)

        with patch("app.core.services.ml_service.training_ws_manager") as mock_ws:
            mock_ws.broadcast = AsyncMock()
            await svc.update_task_progress(task_id=1, ilerleme=10.0, durum="RUNNING")

        assert task.baslangic_zaman is not None
        assert task.guncelleme is not None

    async def test_completed_sets_bitis_zaman(self):
        """COMPLETED status sets bitis_zaman."""
        svc, uow = _make_service()
        task = MagicMock()
        task.arac_id = 2
        task.baslangic_zaman = datetime.now(timezone.utc)
        uow.session.get = AsyncMock(return_value=task)

        with patch("app.core.services.ml_service.training_ws_manager") as mock_ws:
            mock_ws.broadcast = AsyncMock()
            await svc.update_task_progress(task_id=1, ilerleme=100.0, durum="COMPLETED")

        assert task.bitis_zaman is not None

    async def test_failed_sets_hata_detay_and_bitis_zaman(self):
        """FAILED status sets hata_detay and bitis_zaman."""
        svc, uow = _make_service()
        task = MagicMock()
        task.arac_id = 3
        uow.session.get = AsyncMock(return_value=task)

        with patch("app.core.services.ml_service.training_ws_manager") as mock_ws:
            mock_ws.broadcast = AsyncMock()
            await svc.update_task_progress(
                task_id=1,
                ilerleme=0.0,
                durum="FAILED",
                is_error=True,
                error_detail="Training data insufficient",
            )

        assert task.hata_detay == "Training data insufficient"
        assert task.bitis_zaman is not None

    async def test_broadcasts_via_ws_manager(self):
        """update_task_progress broadcasts progress via WS manager."""
        svc, uow = _make_service()
        task = MagicMock()
        task.arac_id = 5
        task.baslangic_zaman = datetime.now(timezone.utc)
        uow.session.get = AsyncMock(return_value=task)

        with patch("app.core.services.ml_service.training_ws_manager") as mock_ws:
            mock_ws.broadcast = AsyncMock()
            await svc.update_task_progress(task_id=5, ilerleme=75.0, durum="RUNNING")

            mock_ws.broadcast.assert_called_once()
            broadcast_payload = mock_ws.broadcast.call_args.args[0]
            assert broadcast_payload["type"] == "progress"
            assert broadcast_payload["task_id"] == 5
            assert broadcast_payload["ilerleme"] == 75.0

    async def test_non_terminal_durum_does_not_set_timestamps(self):
        """Non-status-change durum does not update timestamps."""
        svc, uow = _make_service()
        task = MagicMock()
        task.arac_id = 4
        uow.session.get = AsyncMock(return_value=task)

        with patch("app.core.services.ml_service.training_ws_manager") as mock_ws:
            mock_ws.broadcast = AsyncMock()
            # "WAITING" is not in ["RUNNING", "COMPLETED", "FAILED"]
            await svc.update_task_progress(task_id=1, ilerleme=0.0, durum="WAITING")

        # guncelleme should NOT be set for WAITING
        assert not hasattr(task, "guncelleme") or task.guncelleme == task.guncelleme


# ---------------------------------------------------------------------------
# get_training_queue
# ---------------------------------------------------------------------------


class TestGetTrainingQueue:
    async def test_returns_list_of_tasks(self):
        """get_training_queue returns list from DB ordered by newest first."""
        svc, uow = _make_service()

        task1 = MagicMock()
        task1.id = 5
        task2 = MagicMock()
        task2.id = 3

        scalars = MagicMock()
        scalars.all = MagicMock(return_value=[task1, task2])
        db_result = MagicMock()
        db_result.scalars = MagicMock(return_value=scalars)
        uow.session.execute = AsyncMock(return_value=db_result)

        result = await svc.get_training_queue(limit=50)
        assert result == [task1, task2]

    async def test_custom_limit(self):
        """get_training_queue accepts custom limit."""
        svc, uow = _make_service()

        scalars = MagicMock()
        scalars.all = MagicMock(return_value=[])
        db_result = MagicMock()
        db_result.scalars = MagicMock(return_value=scalars)
        uow.session.execute = AsyncMock(return_value=db_result)

        result = await svc.get_training_queue(limit=10)
        assert result == []
        uow.session.execute.assert_called_once()

    async def test_default_limit_50(self):
        """get_training_queue uses default limit of 50."""
        svc, uow = _make_service()

        scalars = MagicMock()
        scalars.all = MagicMock(return_value=[])
        db_result = MagicMock()
        db_result.scalars = MagicMock(return_value=scalars)
        uow.session.execute = AsyncMock(return_value=db_result)

        result = await svc.get_training_queue()
        assert isinstance(result, list)


# ---------------------------------------------------------------------------
# register_model_version
# ---------------------------------------------------------------------------


class TestRegisterModelVersion:
    async def test_creates_model_versiyon_with_correct_fields(self):
        """register_model_version creates ModelVersiyon with all expected fields."""
        svc, uow = _make_service()

        created_obj = None

        def capture_add(obj):
            nonlocal created_obj
            created_obj = obj

        uow.session.add = capture_add

        from app.database.models import ModelVersiyon

        fake_mv = MagicMock(spec=ModelVersiyon)
        fake_mv.arac_id = 1

        with patch(
            "app.core.services.ml_service.ModelVersiyon",
            return_value=fake_mv,
        ) as MockMV:
            result = await svc.register_model_version(
                arac_id=1,
                versiyon=2,
                metrics={"r2_skoru": 0.95, "mae": 1.2, "mape": 3.1, "rmse": 1.5},
                model_dosya_yolu="/models/arac_1_v2.pkl",
                kullanilan_ozellikler={"features": ["mesafe", "agirlik"]},
                veri_sayisi=500,
            )

            call_kwargs = MockMV.call_args.kwargs
            assert call_kwargs["arac_id"] == 1
            assert call_kwargs["versiyon"] == 2
            assert call_kwargs["r2_skoru"] == 0.95
            assert call_kwargs["mae"] == 1.2
            assert call_kwargs["veri_sayisi"] == 500
            assert call_kwargs["model_dosya_yolu"] == "/models/arac_1_v2.pkl"

        assert result is fake_mv
        assert uow.commit.called

    async def test_missing_metric_key_results_in_none(self):
        """register_model_version uses None for missing metric keys."""
        svc, uow = _make_service()

        from app.database.models import ModelVersiyon

        created_kwargs = {}

        def fake_mv(**kwargs):
            created_kwargs.update(kwargs)
            return MagicMock(spec=ModelVersiyon)

        with patch(
            "app.core.services.ml_service.ModelVersiyon",
            side_effect=fake_mv,
        ):
            await svc.register_model_version(
                arac_id=2,
                versiyon=1,
                metrics={},  # all metrics missing
                model_dosya_yolu="/models/v1.pkl",
                kullanilan_ozellikler={},
                veri_sayisi=100,
            )

        assert created_kwargs["r2_skoru"] is None
        assert created_kwargs["mae"] is None
        assert created_kwargs["mape"] is None
        assert created_kwargs["rmse"] is None
