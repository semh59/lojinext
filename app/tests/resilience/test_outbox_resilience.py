from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.database.unit_of_work import UnitOfWork
from v2.modules.shared_kernel.infrastructure.outbox import OutboxService


@pytest.mark.asyncio
async def test_outbox_relay_graceful_shutdown():
    """Verify outbox relay stops mid-batch upon shutdown signal."""
    service = OutboxService()

    # Mock events
    mock_events = [
        MagicMock(id=i, event_type="arac_added", payload={}, correlation_id="id")
        for i in range(10)
    ]

    # Mock UOW and Session
    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = mock_events
    mock_session.execute.return_value = mock_result

    mock_uow = AsyncMock()
    mock_uow.session = mock_session

    with (
        patch.object(UnitOfWork, "__aenter__", AsyncMock(return_value=mock_uow)),
        patch.object(UnitOfWork, "__aexit__", AsyncMock(return_value=False)),
        patch(
            "v2.modules.shared_kernel.infrastructure.outbox.get_event_bus"
        ) as mock_bus_func,
        patch(
            "v2.modules.shared_kernel.infrastructure.outbox.is_stopping"
        ) as mock_is_stopping,
    ):
        # Mock bus
        mock_bus = AsyncMock()
        mock_bus_func.return_value = mock_bus

        # Simulate shutdown after 3 messages
        # is_stopping returns False for first 3 checks, then True
        mock_is_stopping.side_effect = [
            False,
            False,
            False,
            True,
            True,
            True,
            True,
            True,
            True,
            True,
        ]

        processed_count = await service.relay_pending_events(limit=10)

        # Should have processed exactly 3 events before breaking
        assert processed_count == 3
        assert mock_bus.publish_async.call_count == 3
        # Should have committed the partial batch
        mock_uow.commit.assert_called_once()
