"""
Coverage tests for app/core/ml/training/scheduler_task.py
Tests weekly_retrain_all_vehicles Celery task and _run_async helper.
All DB and Trainer calls are mocked — no real DB connection needed.
"""

from __future__ import annotations

import contextlib
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_session(rows=None):
    """Return a mock session that returns rows for execute()."""
    mock_result = MagicMock()
    mock_result.mappings.return_value.all.return_value = rows or []
    mock_session = AsyncMock()
    mock_session.execute = AsyncMock(return_value=mock_result)
    return mock_session


@contextlib.contextmanager
def _patch_uow_and_trainer(rows=None, trainer=None):
    """
    Patch UnitOfWork dunders and app.core.ml.training.trainer.Trainer.
    """
    import app.core.ml.training.trainer as trainer_mod
    from app.database.unit_of_work import UnitOfWork

    mock_session = _make_session(rows)
    fake_uow = MagicMock()
    fake_uow.session = mock_session

    original_trainer = trainer_mod.Trainer
    if trainer is not None:
        trainer_mod.Trainer = lambda: trainer

    with (
        patch.object(UnitOfWork, "__aenter__", AsyncMock(return_value=fake_uow)),
        patch.object(UnitOfWork, "__aexit__", AsyncMock(return_value=False)),
    ):
        try:
            yield
        finally:
            trainer_mod.Trainer = original_trainer


# ---------------------------------------------------------------------------
# _run_async
# ---------------------------------------------------------------------------


async def test_run_async_no_vehicles_returns_zero_counts():
    """No active vehicles → success/failed/skipped all 0."""
    mock_trainer = MagicMock()
    mock_trainer.train_for_vehicle = AsyncMock(return_value={"success": True})

    with _patch_uow_and_trainer(rows=[], trainer=mock_trainer):
        from app.core.ml.training.scheduler_task import _run_async

        results = await _run_async()

    assert results["total"] == 0
    assert results["success"] == 0
    assert results["failed"] == 0
    assert results["skipped"] == 0
    mock_trainer.train_for_vehicle.assert_not_called()


async def test_run_async_all_success():
    """All vehicles succeed → success count matches total."""
    rows = [{"id": 1}, {"id": 2}, {"id": 3}]
    mock_trainer = MagicMock()
    mock_trainer.train_for_vehicle = AsyncMock(return_value={"success": True})

    with _patch_uow_and_trainer(rows=rows, trainer=mock_trainer):
        from app.core.ml.training.scheduler_task import _run_async

        results = await _run_async()

    assert results["total"] == 3
    assert results["success"] == 3
    assert results["failed"] == 0
    assert results["skipped"] == 0


async def test_run_async_insufficient_data_counted_as_skipped():
    """Error message containing 'Yetersiz veri' → skipped."""
    rows = [{"id": 10}]
    mock_trainer = MagicMock()
    mock_trainer.train_for_vehicle = AsyncMock(
        return_value={"success": False, "error": "Yetersiz veri: only 3 records"}
    )

    with _patch_uow_and_trainer(rows=rows, trainer=mock_trainer):
        from app.core.ml.training.scheduler_task import _run_async

        results = await _run_async()

    assert results["total"] == 1
    assert results["skipped"] == 1
    assert results["success"] == 0
    assert results["failed"] == 0


async def test_run_async_non_yetersiz_error_counted_as_failed():
    """Generic error (not Yetersiz veri) → failed."""
    rows = [{"id": 5}]
    mock_trainer = MagicMock()
    mock_trainer.train_for_vehicle = AsyncMock(
        return_value={"success": False, "error": "Model convergence failed"}
    )

    with _patch_uow_and_trainer(rows=rows, trainer=mock_trainer):
        from app.core.ml.training.scheduler_task import _run_async

        results = await _run_async()

    assert results["failed"] == 1
    assert results["skipped"] == 0


async def test_run_async_exception_counted_as_failed():
    """Exception raised by train_for_vehicle → failed, does not abort loop."""
    rows = [{"id": 1}, {"id": 2}]
    mock_trainer = MagicMock()

    call_count = 0

    async def train_side_effect(arac_id):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise RuntimeError("unexpected crash")
        return {"success": True}

    mock_trainer.train_for_vehicle = train_side_effect

    with _patch_uow_and_trainer(rows=rows, trainer=mock_trainer):
        from app.core.ml.training.scheduler_task import _run_async

        results = await _run_async()

    assert results["total"] == 2
    assert results["failed"] == 1
    assert results["success"] == 1


async def test_run_async_mixed_results():
    """Mix of success, skip, fail, exception."""
    rows = [{"id": 1}, {"id": 2}, {"id": 3}, {"id": 4}]
    mock_trainer = MagicMock()

    responses = [
        {"success": True},
        {"success": False, "error": "Yetersiz veri: 2 kayıt"},
        {"success": False, "error": "some other error"},
    ]
    call_index = [0]

    async def train_side_effect(arac_id):
        idx = call_index[0]
        call_index[0] += 1
        if idx < len(responses):
            return responses[idx]
        raise ValueError("unexpected")

    mock_trainer.train_for_vehicle = train_side_effect

    with _patch_uow_and_trainer(rows=rows, trainer=mock_trainer):
        from app.core.ml.training.scheduler_task import _run_async

        results = await _run_async()

    assert results["total"] == 4
    assert results["success"] == 1
    assert results["skipped"] == 1
    assert results["failed"] == 2  # failed response + exception


async def test_run_async_result_dict_keys_present():
    """Result dict always contains all four keys."""
    mock_trainer = MagicMock()

    with _patch_uow_and_trainer(rows=[], trainer=mock_trainer):
        from app.core.ml.training.scheduler_task import _run_async

        results = await _run_async()

    assert set(results.keys()) >= {"total", "success", "failed", "skipped"}


# ---------------------------------------------------------------------------
# weekly_retrain_all_vehicles Celery task
# ---------------------------------------------------------------------------


def test_weekly_retrain_task_exists():
    """Task is registered as a shared_task with the correct name."""
    from app.core.ml.training.scheduler_task import weekly_retrain_all_vehicles

    assert hasattr(weekly_retrain_all_vehicles, "name")
    assert "weekly_retrain_all_vehicles" in weekly_retrain_all_vehicles.name


def test_weekly_retrain_task_calls_run_async():
    """Task delegates to asyncio.run(_run_async())."""
    expected = {"total": 2, "success": 2, "failed": 0, "skipped": 0}

    with (
        patch(
            "app.core.ml.training.scheduler_task._run_async",
        ),
        patch(
            "app.core.ml.training.scheduler_task.asyncio.run", return_value=expected
        ) as mock_asyncio_run,
    ):
        from app.core.ml.training.scheduler_task import weekly_retrain_all_vehicles

        result = weekly_retrain_all_vehicles()

    assert result == expected
    mock_asyncio_run.assert_called_once()
