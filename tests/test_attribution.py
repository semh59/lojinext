from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.services.attribution_service import AttributionService
from app.infrastructure.events.event_bus import Event, EventType


@pytest.mark.asyncio
async def test_attribution_override_publishes_event():
    """Verify attribution override publishes event."""
    uow = AsyncMock()
    uow.__aenter__.return_value = uow
    uow.__aexit__.return_value = None
    uow.sefer_repo.get_by_id = AsyncMock(
        return_value={"id": 123, "arac_id": 1, "sofor_id": 1}
    )
    uow.sefer_repo.update = AsyncMock(return_value=True)
    uow.commit = AsyncMock()

    with patch("app.core.services.attribution_service.get_event_bus") as mock_get_eb:
        mock_eb = MagicMock()
        mock_eb.publish_async = AsyncMock()
        mock_get_eb.return_value = mock_eb

        service = AttributionService(uow)
        success = await service.override_attribution(123, 2, 2, "Reason")

    assert success is True
    uow.sefer_repo.update.assert_awaited_once_with(
        123, is_corrected=True, correction_reason="Reason", arac_id=2, sofor_id=2
    )
    mock_eb.publish_async.assert_awaited_once()


@pytest.mark.asyncio
async def test_physics_handler_execution():
    """Verify physics handler recalculation."""
    from app.core.handlers.physics_handler import PhysicsRecalculationHandler

    with (
        patch("app.core.handlers.physics_handler.get_event_bus") as mock_get_event_bus,
        patch("app.core.handlers.physics_handler.UnitOfWork") as mock_uow_cls,
    ):
        mock_event_bus = MagicMock()
        mock_event_bus.publish_async = AsyncMock()
        mock_get_event_bus.return_value = mock_event_bus

        mock_uow = MagicMock()
        mock_uow.__aenter__.return_value = mock_uow
        mock_uow_cls.return_value = mock_uow
        mock_uow.commit = AsyncMock()
        mock_uow.sefer_repo.get_by_id = AsyncMock(
            return_value={
                "id": 123,
                "arac_id": 1,
                "mesafe_km": 100.0,
                "ton": 20.0,
                "bos_sefer": False,
                "ascent_m": 0.0,
                "descent_m": 0.0,
                "flat_distance_km": 100.0,
            }
        )
        mock_uow.arac_repo.get_by_id = AsyncMock(
            return_value={
                "bos_agirlik_kg": 8000.0,
                "hava_direnc_katsayisi": 0.7,
                "on_kesit_alani_m2": 8.5,
                "lastik_direnc_katsayisi": 0.007,
                "motor_verimliligi": 0.38,
            }
        )
        mock_uow.dorse_repo.get_by_id = AsyncMock(return_value=None)
        mock_uow.sefer_repo.update = AsyncMock()

        handler = PhysicsRecalculationHandler()
        event = Event(
            type=EventType.SEFER_UPDATED, data={"sefer_id": 123, "trigger": "test"}
        )
        await handler.on_sefer_updated(event)

    mock_uow.sefer_repo.update.assert_awaited_once()
    mock_event_bus.publish_async.assert_awaited_once()
