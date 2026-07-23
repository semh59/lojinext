"""coaching_tasks.py birim testleri — gerçek kaynak yapısına göre.

0-mock (Dilim 32): patch("v2.modules.shared_kernel.infrastructure.unit_of_work.UnitOfWork") replaced with
narrow patch.object(UnitOfWork, '__aenter__'/__aexit__).
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from v2.modules.driver.infrastructure.coaching_tasks import (
    _run_digest,
    _run_evaluate_pending,
    evaluate_pending_deliveries,
    weekly_coaching_digest,
)
from v2.modules.shared_kernel.infrastructure.unit_of_work import UnitOfWork

pytestmark = pytest.mark.unit


def _uow_ctx(mock_uow):
    """Return context managers patching UnitOfWork's __aenter__/__aexit__."""
    return (
        patch.object(UnitOfWork, "__aenter__", AsyncMock(return_value=mock_uow)),
        patch.object(UnitOfWork, "__aexit__", AsyncMock(return_value=False)),
    )


# ── _run_digest ───────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_run_digest_no_drivers():
    """Aktif şoför yoksa processed=0 döner."""
    mock_uow = AsyncMock()
    mock_uow.sofor_repo.get_all = AsyncMock(return_value=[])

    mock_engine = MagicMock()

    enter_p, exit_p = _uow_ctx(mock_uow)
    with (
        patch(
            "v2.modules.driver.application.generate_coaching.get_driver_coaching_engine",
            return_value=mock_engine,
        ),
        enter_p,
        exit_p,
    ):
        result = await _run_digest()

    assert result["processed"] == 0
    assert result["total"] == 0
    assert result["timeout_partial"] is False


@pytest.mark.asyncio
async def test_run_digest_processes_driver():
    """Bir şoför için engine.generate_coaching çağrılır, sonuç sayılır."""
    mock_uow = AsyncMock()
    mock_uow.sofor_repo.get_all = AsyncMock(
        return_value=[{"id": 1, "telegram_id": None}]
    )

    mock_insights = MagicMock()
    mock_insights.priority = "low"
    mock_insights.insights = []

    mock_engine = AsyncMock()
    mock_engine.generate_coaching = AsyncMock(return_value=mock_insights)

    enter_p, exit_p = _uow_ctx(mock_uow)
    with (
        patch(
            "v2.modules.driver.application.generate_coaching.get_driver_coaching_engine",
            return_value=mock_engine,
        ),
        enter_p,
        exit_p,
    ):
        result = await _run_digest()

    assert result["processed"] == 1
    assert result["errors"] == 0


@pytest.mark.asyncio
async def test_run_digest_engine_error_counted():
    """engine.generate_coaching exception → errors sayacı artar, devam eder."""
    mock_uow = AsyncMock()
    mock_uow.sofor_repo.get_all = AsyncMock(
        return_value=[{"id": 1, "telegram_id": None}]
    )

    mock_engine = AsyncMock()
    mock_engine.generate_coaching = AsyncMock(side_effect=Exception("LLM error"))

    enter_p, exit_p = _uow_ctx(mock_uow)
    with (
        patch(
            "v2.modules.driver.application.generate_coaching.get_driver_coaching_engine",
            return_value=mock_engine,
        ),
        enter_p,
        exit_p,
    ):
        result = await _run_digest()

    assert result["errors"] == 1
    assert result["processed"] == 0


@pytest.mark.asyncio
async def test_run_digest_soft_time_limit_sets_partial():
    """SoftTimeLimitExceeded → timeout_partial=True döner."""
    from celery.exceptions import SoftTimeLimitExceeded

    mock_uow = AsyncMock()
    mock_uow.sofor_repo.get_all = AsyncMock(
        return_value=[{"id": 1, "telegram_id": None}]
    )

    mock_engine = AsyncMock()
    mock_engine.generate_coaching = AsyncMock(side_effect=SoftTimeLimitExceeded())

    enter_p, exit_p = _uow_ctx(mock_uow)
    with (
        patch(
            "v2.modules.driver.application.generate_coaching.get_driver_coaching_engine",
            return_value=mock_engine,
        ),
        enter_p,
        exit_p,
    ):
        result = await _run_digest()

    assert result["timeout_partial"] is True


@pytest.mark.asyncio
async def test_run_digest_high_priority_no_telegram():
    """high_priority insight ama telegram_id=None → sent=0."""
    mock_uow = AsyncMock()
    mock_uow.sofor_repo.get_all = AsyncMock(
        return_value=[{"id": 2, "telegram_id": None}]
    )

    mock_insights = MagicMock()
    mock_insights.priority = "high"
    mock_insights.headline = "Yakıt verimliliği düşük"
    mock_insights.insights = []

    mock_engine = AsyncMock()
    mock_engine.generate_coaching = AsyncMock(return_value=mock_insights)

    enter_p, exit_p = _uow_ctx(mock_uow)
    with (
        patch(
            "v2.modules.driver.application.generate_coaching.get_driver_coaching_engine",
            return_value=mock_engine,
        ),
        enter_p,
        exit_p,
        patch("app.config.settings") as mock_settings,
    ):
        mock_settings.COACHING_ENABLED = False
        result = await _run_digest()

    assert result["high_priority"] == 1
    assert result["sent"] == 0


# ── _run_evaluate_pending ─────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_run_evaluate_pending_no_rows():
    """14 gün + evaluated_at NULL satır yoksa evaluated=0 döner."""
    mock_uow = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = []
    mock_uow.session.execute = AsyncMock(return_value=mock_result)
    mock_uow.commit = AsyncMock()

    enter_p, exit_p = _uow_ctx(mock_uow)
    with enter_p, exit_p:
        result = await _run_evaluate_pending()

    assert result["evaluated"] == 0
    assert result["errors"] == 0


# ── Celery task smoke ─────────────────────────────────────────────────────────


def test_weekly_coaching_digest_is_celery_task():
    """Task adı beat schedule ile uyumlu."""
    assert weekly_coaching_digest.name == "coaching.weekly_digest"


def test_evaluate_pending_deliveries_is_celery_task():
    assert evaluate_pending_deliveries.name == "coaching.evaluate_pending"


@pytest.mark.asyncio
async def test_run_digest_result_keys():
    """Dönüş dict'i beklenen tüm anahtarları içerir."""
    mock_uow = AsyncMock()
    mock_uow.sofor_repo.get_all = AsyncMock(return_value=[])

    enter_p, exit_p = _uow_ctx(mock_uow)
    with (
        patch(
            "v2.modules.driver.application.generate_coaching.get_driver_coaching_engine",
            return_value=MagicMock(),
        ),
        enter_p,
        exit_p,
    ):
        result = await _run_digest()

    expected_keys = {
        "processed",
        "high_priority",
        "sent",
        "errors",
        "total",
        "timeout_partial",
    }
    assert expected_keys <= result.keys()
