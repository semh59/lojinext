from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from v2.modules.notification.application import handle_trip_events
from v2.modules.notification.application.get_user_notifications import (
    get_user_notifications,
)
from v2.modules.notification.application.mark_notification_read import mark_as_read
from v2.modules.platform_infra.events.event_bus import Event, EventType


@pytest.mark.asyncio
async def test_notification_service_handles_sefer_updated():
    """Verify that SEFER_UPDATED event triggers notification creation."""
    with patch.object(handle_trip_events, "UnitOfWork") as mock_uow_cls:
        mock_uow = MagicMock()
        mock_uow.__aenter__.return_value = mock_uow
        mock_uow_cls.return_value = mock_uow

        mock_uow.commit = AsyncMock()
        mock_uow.session = MagicMock()
        mock_uow.session.flush = AsyncMock()

        # Mock Rule
        mock_rule = MagicMock(
            olay_tipi=EventType.SEFER_UPDATED, kanallar=["UI"], alici_rol_id=2
        )
        mock_uow.notification_repo.get_rules_by_event = AsyncMock(
            return_value=[mock_rule]
        )

        # Mock Target Users
        mock_uow.kullanici_repo.get_by_rol_ids = AsyncMock(
            return_value={2: [MagicMock(id=10, email="test@test.com")]}
        )

        event = Event(
            type=EventType.SEFER_UPDATED,
            data={"sefer_id": 123, "trigger": "test_override"},
        )
        await handle_trip_events.handle_event(event)

        # Verify notifications were persisted via session.add_all and committed
        mock_uow.session.add_all.assert_called_once()
        mock_uow.commit.assert_called_once()


@pytest.mark.asyncio
async def test_mark_notification_as_read():
    """Verify status update to READ."""
    with patch(
        "v2.modules.notification.application.mark_notification_read.UnitOfWork"
    ) as mock_uow_cls:
        mock_uow = MagicMock()
        mock_uow.__aenter__.return_value = mock_uow
        mock_uow_cls.return_value = mock_uow

        mock_uow.commit = AsyncMock()
        mock_uow.notification_repo.mark_as_read_for_user = AsyncMock(return_value=True)

        success = await mark_as_read(1, user_id=7)
        assert success is True
        mock_uow.commit.assert_called_once()


@pytest.mark.asyncio
async def test_get_user_notifications():
    """Verify retrieval of notifications for a specific user."""
    with patch(
        "v2.modules.notification.application.get_user_notifications.UnitOfWork"
    ) as mock_uow_cls:
        mock_uow = MagicMock()
        mock_uow.__aenter__.return_value = mock_uow
        mock_uow_cls.return_value = mock_uow

        mock_notification = MagicMock(id=1, kullanici_id=10, baslik="Test")
        mock_uow.notification_repo.get_user_notifications = AsyncMock(
            return_value=[mock_notification]
        )

        notifications = await get_user_notifications(10)
        assert len(notifications) == 1
        assert notifications[0].id == 1
        mock_uow.notification_repo.get_user_notifications.assert_called_with(10)


@pytest.mark.asyncio
async def test_handle_event_no_rules():
    """Verify that event handling exits gracefully when no rules match."""
    with patch.object(handle_trip_events, "UnitOfWork") as mock_uow_cls:
        mock_uow = MagicMock()
        mock_uow.__aenter__.return_value = mock_uow
        mock_uow_cls.return_value = mock_uow

        mock_uow.notification_repo.get_rules_by_event = AsyncMock(return_value=[])

        event = Event(type="UNMAPPED_EVENT", data={})
        await handle_trip_events.handle_event(event)

        # Should not fetch users or add notifications
        mock_uow.kullanici_repo.get_by_rol_id.assert_not_called()
        mock_uow.notification_repo.add.assert_not_called()
