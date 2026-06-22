"""Tests that notification_service uses bulk query instead of N+1."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

pytestmark = pytest.mark.asyncio


async def test_kullanici_repo_has_get_by_rol_ids():
    """KullaniciRepository must have a get_by_rol_ids bulk method."""
    from app.database.repositories.kullanici_repo import KullaniciRepository

    assert hasattr(KullaniciRepository, "get_by_rol_ids"), (
        "KullaniciRepository missing get_by_rol_ids method"
    )


async def test_notification_uses_bulk_query_not_per_rule():
    """handle_event must call get_by_rol_ids once, not get_by_rol_id per rule."""
    from app.core.services.notification_service import NotificationService

    mock_rule1 = MagicMock()
    mock_rule1.alici_rol_id = 1
    mock_rule1.kanallar = ["UI"]

    mock_rule2 = MagicMock()
    mock_rule2.alici_rol_id = 2
    mock_rule2.kanallar = ["UI"]

    mock_rule3 = MagicMock()
    mock_rule3.alici_rol_id = 1
    mock_rule3.kanallar = ["EMAIL"]

    users_by_rol = {
        1: [MagicMock(id=10), MagicMock(id=11)],
        2: [MagicMock(id=20)],
    }

    with patch("app.core.services.notification_service.UnitOfWork") as MockUoW:
        mock_uow = AsyncMock()
        MockUoW.return_value.__aenter__ = AsyncMock(return_value=mock_uow)
        MockUoW.return_value.__aexit__ = AsyncMock(return_value=False)
        mock_uow.notification_repo.get_rules_by_event = AsyncMock(
            return_value=[mock_rule1, mock_rule2, mock_rule3]
        )
        mock_uow.kullanici_repo.get_by_rol_ids = AsyncMock(return_value=users_by_rol)
        mock_uow.session.add_all = MagicMock()
        mock_uow.session.flush = AsyncMock()
        mock_uow.commit = AsyncMock()

        service = NotificationService()
        test_event = MagicMock()
        test_event.type.value = "TEST_EVENT"
        test_event.type = MagicMock()

        # Patch _format_message and WS manager to avoid side effects
        service._format_message = MagicMock(return_value=("Title", "Content"))

        import app.core.services.notification_service as ns_mod

        original_ws = ns_mod.notification_ws_manager
        mock_ws = AsyncMock()
        ns_mod.notification_ws_manager = mock_ws
        try:
            await service.handle_event(test_event)
        finally:
            ns_mod.notification_ws_manager = original_ws

        # Must call bulk method exactly once
        mock_uow.kullanici_repo.get_by_rol_ids.assert_called_once()
        # Must NOT call single-role method
        assert (
            not mock_uow.kullanici_repo.get_by_rol_id.called
            if hasattr(mock_uow.kullanici_repo, "get_by_rol_id")
            else True
        )

        # add_all should be called with notifications
        # rol_id=1 has 2 users × 2 rules (UI + EMAIL) = 4 notifs
        # rol_id=2 has 1 user × 1 rule (UI) = 1 notif
        # Total = 5
        mock_uow.session.add_all.assert_called_once()
        notifications = mock_uow.session.add_all.call_args[0][0]
        assert (
            len(notifications) == 5
        )  # (2+2) users for rol_id=1 × 2 rules + 1 user for rol_id=2
