"""
Coverage tests for app/infrastructure/cache/cache_invalidation.py
Tests trigger_dashboard_update, setup_cache_invalidation, and all event handlers.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_event(event_type, data=None):
    """Build a minimal Event-like object."""
    from app.infrastructure.events.event_bus import Event

    return Event(type=event_type, data=data or {})


# ---------------------------------------------------------------------------
# trigger_dashboard_update
# ---------------------------------------------------------------------------


async def test_trigger_dashboard_update_publishes():
    """Happy path — pubsub.publish is awaited."""
    mock_pubsub = AsyncMock()
    mock_pubsub.publish = AsyncMock()

    with patch(
        "v2.modules.platform_infra.cache.cache_invalidation.get_pubsub_manager",
        return_value=mock_pubsub,
    ):
        from v2.modules.platform_infra.cache.cache_invalidation import (
            trigger_dashboard_update,
        )

        await trigger_dashboard_update()

    mock_pubsub.publish.assert_called_once_with(
        "dashboard_updates", {"action": "update"}
    )


async def test_trigger_dashboard_update_handles_exception():
    """If pubsub raises, function swallows and logs warning (no re-raise)."""
    mock_pubsub = AsyncMock()
    mock_pubsub.publish = AsyncMock(side_effect=ConnectionError("redis down"))

    with patch(
        "v2.modules.platform_infra.cache.cache_invalidation.get_pubsub_manager",
        return_value=mock_pubsub,
    ):
        from v2.modules.platform_infra.cache.cache_invalidation import (
            trigger_dashboard_update,
        )

        # Must not raise
        await trigger_dashboard_update()


# ---------------------------------------------------------------------------
# setup_cache_invalidation — subscription registrations
# ---------------------------------------------------------------------------


def _setup_with_mocks():
    """Return (mock_bus, mock_cache) after calling setup_cache_invalidation."""
    mock_bus = MagicMock()
    mock_cache = MagicMock()

    with (
        patch(
            "v2.modules.platform_infra.cache.cache_invalidation.get_event_bus",
            return_value=mock_bus,
        ),
        patch(
            "v2.modules.platform_infra.cache.cache_invalidation.get_cache_manager",
            return_value=mock_cache,
        ),
    ):
        from v2.modules.platform_infra.cache.cache_invalidation import (
            setup_cache_invalidation,
        )

        setup_cache_invalidation()

    return mock_bus, mock_cache


def test_setup_registers_sefer_handlers():
    mock_bus, _ = _setup_with_mocks()
    from app.infrastructure.events.event_types import EventType

    subscribed_types = [call.args[0] for call in mock_bus.subscribe.call_args_list]
    assert EventType.SEFER_ADDED in subscribed_types
    assert EventType.SEFER_UPDATED in subscribed_types
    assert EventType.SEFER_DELETED in subscribed_types


def test_setup_registers_yakit_handlers():
    mock_bus, _ = _setup_with_mocks()
    from app.infrastructure.events.event_types import EventType

    subscribed_types = [call.args[0] for call in mock_bus.subscribe.call_args_list]
    assert EventType.YAKIT_ADDED in subscribed_types
    assert EventType.YAKIT_UPDATED in subscribed_types
    assert EventType.YAKIT_DELETED in subscribed_types


def test_setup_registers_arac_handlers():
    mock_bus, _ = _setup_with_mocks()
    from app.infrastructure.events.event_types import EventType

    subscribed_types = [call.args[0] for call in mock_bus.subscribe.call_args_list]
    assert EventType.ARAC_ADDED in subscribed_types
    assert EventType.ARAC_UPDATED in subscribed_types
    assert EventType.ARAC_DELETED in subscribed_types


def test_setup_registers_sofor_handlers():
    mock_bus, _ = _setup_with_mocks()
    from app.infrastructure.events.event_types import EventType

    subscribed_types = [call.args[0] for call in mock_bus.subscribe.call_args_list]
    assert EventType.SOFOR_ADDED in subscribed_types
    assert EventType.SOFOR_UPDATED in subscribed_types
    assert EventType.SOFOR_DELETED in subscribed_types


def test_setup_registers_calculation_and_settings_handlers():
    mock_bus, _ = _setup_with_mocks()
    from app.infrastructure.events.event_types import EventType

    subscribed_types = [call.args[0] for call in mock_bus.subscribe.call_args_list]
    assert EventType.PERIYOT_CREATED in subscribed_types
    assert EventType.YAKIT_DISTRIBUTED in subscribed_types
    assert EventType.SETTINGS_CHANGED in subscribed_types


# ---------------------------------------------------------------------------
# on_sefer_change handler (extracted via subscribe call_args)
# ---------------------------------------------------------------------------


def _get_handler_sync(event_type_name: str):
    """Extract the closure registered for event_type_name from a setup call."""
    mock_bus = MagicMock()
    mock_cache = MagicMock()

    with (
        patch(
            "v2.modules.platform_infra.cache.cache_invalidation.get_event_bus",
            return_value=mock_bus,
        ),
        patch(
            "v2.modules.platform_infra.cache.cache_invalidation.get_cache_manager",
            return_value=mock_cache,
        ),
    ):
        import v2.modules.platform_infra.cache.cache_invalidation as ci_mod

        ci_mod.setup_cache_invalidation()

    from app.infrastructure.events.event_types import EventType

    target = EventType[event_type_name]
    for call in mock_bus.subscribe.call_args_list:
        if call.args[0] == target:
            return call.args[1], mock_cache
    raise KeyError(f"No handler registered for {event_type_name}")


async def test_sefer_handler_deletes_stats_patterns():
    handler, mock_cache = _get_handler_sync("SEFER_ADDED")
    from app.infrastructure.events.event_types import EventType

    event = _make_event(EventType.SEFER_ADDED, data={})

    with patch(
        "v2.modules.platform_infra.cache.cache_invalidation.trigger_dashboard_update",
        new_callable=AsyncMock,
    ) as mock_trigger:
        await handler(event)

    deleted_patterns = [c.args[0] for c in mock_cache.delete_pattern.call_args_list]
    assert "stats:*" in deleted_patterns
    assert "report:*" in deleted_patterns
    assert "dashboard:*" in deleted_patterns
    assert "trend:*" in deleted_patterns
    mock_trigger.assert_called_once()


async def test_sefer_handler_deletes_arac_specific_pattern():
    """When event.data contains result.arac_id, the arac-specific key is deleted."""
    handler, mock_cache = _get_handler_sync("SEFER_ADDED")
    from app.infrastructure.events.event_types import EventType

    event = _make_event(EventType.SEFER_ADDED, data={"result": {"arac_id": 17}})

    with patch(
        "v2.modules.platform_infra.cache.cache_invalidation.trigger_dashboard_update",
        new_callable=AsyncMock,
    ):
        await handler(event)

    deleted_patterns = [c.args[0] for c in mock_cache.delete_pattern.call_args_list]
    assert "arac:17:*" in deleted_patterns


async def test_sefer_handler_no_arac_specific_when_result_not_dict():
    """When result is not a dict, no arac-specific key is added."""
    handler, mock_cache = _get_handler_sync("SEFER_UPDATED")
    from app.infrastructure.events.event_types import EventType

    event = _make_event(EventType.SEFER_UPDATED, data={"result": "string_value"})

    with patch(
        "v2.modules.platform_infra.cache.cache_invalidation.trigger_dashboard_update",
        new_callable=AsyncMock,
    ):
        await handler(event)

    deleted_patterns = [c.args[0] for c in mock_cache.delete_pattern.call_args_list]
    # arac-specific pattern should not be in calls
    assert not any(p.startswith("arac:") and p.endswith(":*") for p in deleted_patterns)


async def test_yakit_handler_deletes_yakit_patterns():
    handler, mock_cache = _get_handler_sync("YAKIT_ADDED")
    from app.infrastructure.events.event_types import EventType

    event = _make_event(EventType.YAKIT_ADDED)

    with patch(
        "v2.modules.platform_infra.cache.cache_invalidation.trigger_dashboard_update",
        new_callable=AsyncMock,
    ):
        await handler(event)

    deleted_patterns = [c.args[0] for c in mock_cache.delete_pattern.call_args_list]
    assert "yakit:*" in deleted_patterns
    assert "periyot:*" in deleted_patterns
    assert "anomali:*" in deleted_patterns


async def test_arac_handler_deletes_arac_and_stats():
    handler, mock_cache = _get_handler_sync("ARAC_ADDED")
    from app.infrastructure.events.event_types import EventType

    event = _make_event(EventType.ARAC_ADDED)

    with patch(
        "v2.modules.platform_infra.cache.cache_invalidation.trigger_dashboard_update",
        new_callable=AsyncMock,
    ):
        await handler(event)

    deleted_patterns = [c.args[0] for c in mock_cache.delete_pattern.call_args_list]
    assert "arac:*" in deleted_patterns
    assert "stats:filo*" in deleted_patterns


async def test_sofor_handler_deletes_sofor_patterns():
    handler, mock_cache = _get_handler_sync("SOFOR_ADDED")
    from app.infrastructure.events.event_types import EventType

    event = _make_event(EventType.SOFOR_ADDED)

    with patch(
        "v2.modules.platform_infra.cache.cache_invalidation.trigger_dashboard_update",
        new_callable=AsyncMock,
    ):
        await handler(event)

    deleted_patterns = [c.args[0] for c in mock_cache.delete_pattern.call_args_list]
    assert "sofor:*" in deleted_patterns
    assert "stats:sofor*" in deleted_patterns


async def test_calculation_handler_deletes_periyot_regression():
    handler, mock_cache = _get_handler_sync("PERIYOT_CREATED")
    from app.infrastructure.events.event_types import EventType

    event = _make_event(EventType.PERIYOT_CREATED)

    with patch(
        "v2.modules.platform_infra.cache.cache_invalidation.trigger_dashboard_update",
        new_callable=AsyncMock,
    ):
        await handler(event)

    deleted_patterns = [c.args[0] for c in mock_cache.delete_pattern.call_args_list]
    assert "periyot:*" in deleted_patterns
    assert "regression:*" in deleted_patterns


async def test_settings_handler_clears_all_cache():
    handler, mock_cache = _get_handler_sync("SETTINGS_CHANGED")
    from app.infrastructure.events.event_types import EventType

    event = _make_event(EventType.SETTINGS_CHANGED)
    await handler(event)

    mock_cache.clear.assert_called_once()
