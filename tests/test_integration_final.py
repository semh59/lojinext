from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from v2.modules.notification.application import handle_trip_events
from v2.modules.platform_infra.events.event_bus import Event, EventType


@pytest.mark.asyncio
async def test_end_to_end_flow_sefer_update_to_notification():
    with (
        patch.object(handle_trip_events, "UnitOfWork") as mock_uow_cls,
        patch(
            "v2.modules.notification.infrastructure.ws_broadcaster."
            "notification_ws_manager.send_personal_message",
            new_callable=AsyncMock,
        ) as mock_send_ws,
    ):
        mock_uow = MagicMock()
        mock_uow.__aenter__.return_value = mock_uow
        mock_uow_cls.return_value = mock_uow
        mock_uow.commit = AsyncMock()
        mock_uow.session = MagicMock()
        mock_uow.session.flush = AsyncMock()

        mock_rule = MagicMock(
            olay_tipi=EventType.SEFER_UPDATED, kanallar=["UI"], alici_rol_id=2
        )
        mock_uow.notification_repo.get_rules_by_event = AsyncMock(
            return_value=[mock_rule]
        )
        mock_user = MagicMock(id=50, email="fleet@lojinext.com")
        mock_uow.kullanici_repo.get_by_rol_ids = AsyncMock(
            return_value={2: [mock_user]}
        )

        event = Event(
            type=EventType.SEFER_UPDATED,
            data={"sefer_id": 999, "status": "COMPLETED", "trigger": "test_e2e"},
        )

        await handle_trip_events.handle_event(event)

    mock_uow.commit.assert_awaited_once()
    mock_send_ws.assert_awaited_once()

    # Verify notification content via session.add_all call
    mock_uow.session.add_all.assert_called_once()
    notifications = mock_uow.session.add_all.call_args.args[0]
    assert len(notifications) == 1
    notif = notifications[0]
    assert "999" in notif.icerik or "999" in notif.baslik
    assert notif.kullanici_id == 50
