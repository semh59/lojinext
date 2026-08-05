"""
PhysicsRecalculationHandler tests.

Moved from tests/test_attribution.py (missed in the original Task 5 test-fix
punch list, caught by a real CI hard-gates run 2026-08-05): the handler was
rewritten during the extraction to fetch sefer/vehicle/trailer data via
cross_module_client (HTTP) instead of an in-process UnitOfWork with
sefer_repo/arac_repo/dorse_repo — this microservice has no direct DB access
to the trip/fleet modules' tables. Test rewritten to match the real
HTTP-based data flow, not a mechanical import-path fix.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from prediction_ml_service.application.physics_handler import (
    PhysicsRecalculationHandler,
)

from v2.modules.platform_infra.events.event_bus import Event, EventType


@pytest.mark.asyncio
async def test_physics_handler_execution():
    """Verify physics handler recalculates consumption via cross_module_client."""
    mock_event_bus = MagicMock()
    mock_event_bus.publish_async = AsyncMock()

    with patch(
        "prediction_ml_service.application.physics_handler.get_event_bus",
        return_value=mock_event_bus,
    ):
        handler = PhysicsRecalculationHandler()

    with (
        patch(
            "prediction_ml_service.application.physics_handler.cross_module_client.get_sefer",
            new=AsyncMock(
                return_value={
                    "id": 123,
                    "arac_id": 1,
                    "dorse_id": None,
                    "mesafe_km": 100.0,
                    "ton": 20.0,
                    "bos_sefer": False,
                    "ascent_m": 0.0,
                    "descent_m": 0.0,
                    "flat_distance_km": 100.0,
                }
            ),
        ),
        patch(
            "prediction_ml_service.application.physics_handler.cross_module_client.get_vehicle",
            new=AsyncMock(
                return_value={
                    "yil": 2020,
                    "bos_agirlik_kg": 8000.0,
                    "hava_direnc_katsayisi": 0.7,
                    "on_kesit_alani_m2": 8.5,
                    "lastik_direnc_katsayisi": 0.007,
                    "motor_verimliligi": 0.38,
                }
            ),
        ),
        patch(
            "prediction_ml_service.application.physics_handler.cross_module_client.update_tahmini_tuketim",
            new=AsyncMock(),
        ) as mock_update,
    ):
        event = Event(
            type=EventType.SEFER_UPDATED, data={"sefer_id": 123, "trigger": "test"}
        )
        await handler.on_sefer_updated(event)

    mock_update.assert_awaited_once()
    assert mock_update.call_args[0][0] == 123
    assert mock_update.call_args[0][1] > 0
    mock_event_bus.publish_async.assert_awaited_once()
