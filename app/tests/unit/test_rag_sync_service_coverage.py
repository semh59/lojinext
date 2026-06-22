"""
Coverage tests for app/core/ai/rag_sync_service.py
Targets: initialize subscriptions, initial_sync paths, event handlers.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

pytestmark = pytest.mark.unit


def _make_service():
    """Build a RAGSyncService with a stubbed rag engine."""
    from app.core.ai.rag_sync_service import RAGSyncService

    svc = RAGSyncService.__new__(RAGSyncService)
    import asyncio

    svc._sync_lock = asyncio.Lock()
    svc._is_syncing = False
    svc.rag = MagicMock()
    svc.rag.index_vehicle = AsyncMock()
    svc.rag.index_driver = AsyncMock()
    svc.rag.index_trip = AsyncMock()
    svc.rag.save_to_disk = MagicMock()
    return svc


def _make_event(data: dict):
    from app.infrastructure.events.event_bus import Event, EventType

    return Event(type=EventType.ARAC_ADDED, data=data)


# ---------------------------------------------------------------------------
# initialize
# ---------------------------------------------------------------------------


async def test_initialize_subscribes_events():
    svc = _make_service()
    mock_eb = MagicMock()
    mock_eb.subscribe = MagicMock()

    def _consume_coro(coro):
        coro.close()
        return MagicMock()

    with (
        patch("app.core.ai.rag_sync_service.get_event_bus", return_value=mock_eb),
        patch("asyncio.create_task", side_effect=_consume_coro),
    ):
        await svc.initialize()

    # Must subscribe to 6 events (ARAC_ADDED, ARAC_UPDATED, SOFOR_ADDED, SOFOR_UPDATED,
    # SEFER_ADDED, SEFER_UPDATED)
    assert mock_eb.subscribe.call_count == 6


async def test_initialize_creates_background_task():
    svc = _make_service()
    mock_eb = MagicMock()
    mock_eb.subscribe = MagicMock()

    created_tasks = []

    def _capture_task(coro):
        # Consume the coroutine so it doesn't leak
        coro.close()
        t = MagicMock()
        created_tasks.append(t)
        return t

    with (
        patch("app.core.ai.rag_sync_service.get_event_bus", return_value=mock_eb),
        patch("asyncio.create_task", side_effect=_capture_task),
    ):
        await svc.initialize()

    assert len(created_tasks) == 1


# ---------------------------------------------------------------------------
# initial_sync — already syncing guard
# ---------------------------------------------------------------------------


async def test_initial_sync_skips_if_already_syncing():
    svc = _make_service()
    svc._is_syncing = True

    with patch("app.database.repositories.arac_repo.get_arac_repo") as mock_repo:
        await svc.initial_sync()

    mock_repo.assert_not_called()
    # State unchanged
    assert svc._is_syncing is True


# ---------------------------------------------------------------------------
# initial_sync — happy path
# ---------------------------------------------------------------------------


async def test_initial_sync_indexes_all_entities():
    svc = _make_service()

    vehicles = [{"id": 1, "plaka": "06A1"}, {"id": 2, "plaka": "34B2"}]
    drivers = [{"id": 10, "ad": "Ali"}]
    trips = [{"id": 100, "mesafe_km": 300}]

    mock_arac_repo = MagicMock()
    mock_arac_repo.get_all = AsyncMock(return_value=vehicles)
    mock_sofor_repo = MagicMock()
    mock_sofor_repo.get_all = AsyncMock(return_value=drivers)
    mock_sefer_repo = MagicMock()
    mock_sefer_repo.get_all = AsyncMock(return_value=trips)

    with (
        patch(
            "app.database.repositories.arac_repo.get_arac_repo",
            return_value=mock_arac_repo,
        ),
        patch(
            "app.database.repositories.sofor_repo.get_sofor_repo",
            return_value=mock_sofor_repo,
        ),
        patch(
            "app.database.repositories.sefer_repo.get_sefer_repo",
            return_value=mock_sefer_repo,
        ),
    ):
        await svc.initial_sync()

    assert svc.rag.index_vehicle.call_count == 2
    assert svc.rag.index_driver.call_count == 1
    assert svc.rag.index_trip.call_count == 1
    svc.rag.save_to_disk.assert_called_once()
    assert svc._is_syncing is False


# ---------------------------------------------------------------------------
# initial_sync — exception path
# ---------------------------------------------------------------------------


async def test_initial_sync_exception_resets_syncing_flag():
    svc = _make_service()

    with patch(
        "app.database.repositories.arac_repo.get_arac_repo",
        side_effect=RuntimeError("DB exploded"),
    ):
        await svc.initial_sync()

    assert svc._is_syncing is False


# ---------------------------------------------------------------------------
# _on_arac_changed
# ---------------------------------------------------------------------------


async def test_on_arac_changed_dict_data():
    svc = _make_service()
    event = _make_event({"result": {"id": 1, "plaka": "34ABC"}})
    await svc._on_arac_changed(event)
    svc.rag.index_vehicle.assert_called_once_with({"id": 1, "plaka": "34ABC"})


async def test_on_arac_changed_int_id_fetches_from_repo():
    svc = _make_service()
    event = _make_event({"result": 42})

    mock_arac_repo = MagicMock()
    arac_data = {"id": 42, "plaka": "34XY"}
    mock_arac_repo.get_by_id = AsyncMock(return_value=arac_data)

    with patch(
        "app.database.repositories.arac_repo.get_arac_repo", return_value=mock_arac_repo
    ):
        await svc._on_arac_changed(event)

    svc.rag.index_vehicle.assert_called_once_with(arac_data)


async def test_on_arac_changed_int_id_not_found_skips():
    svc = _make_service()
    event = _make_event({"result": 99})

    mock_arac_repo = MagicMock()
    mock_arac_repo.get_by_id = AsyncMock(return_value=None)

    with patch(
        "app.database.repositories.arac_repo.get_arac_repo", return_value=mock_arac_repo
    ):
        await svc._on_arac_changed(event)

    svc.rag.index_vehicle.assert_not_called()


async def test_on_arac_changed_none_data_skips():
    svc = _make_service()
    event = _make_event({"result": None})
    await svc._on_arac_changed(event)
    svc.rag.index_vehicle.assert_not_called()


async def test_on_arac_changed_missing_result_key_skips():
    svc = _make_service()
    event = _make_event({})
    await svc._on_arac_changed(event)
    svc.rag.index_vehicle.assert_not_called()


# ---------------------------------------------------------------------------
# _on_sofor_changed
# ---------------------------------------------------------------------------


async def test_on_sofor_changed_dict_data():
    svc = _make_service()
    event = _make_event({"result": {"id": 5, "ad": "Mehmet"}})
    await svc._on_sofor_changed(event)
    svc.rag.index_driver.assert_called_once_with({"id": 5, "ad": "Mehmet"})


async def test_on_sofor_changed_non_dict_skips():
    svc = _make_service()
    event = _make_event({"result": 5})
    await svc._on_sofor_changed(event)
    svc.rag.index_driver.assert_not_called()


async def test_on_sofor_changed_none_skips():
    svc = _make_service()
    event = _make_event({"result": None})
    await svc._on_sofor_changed(event)
    svc.rag.index_driver.assert_not_called()


# ---------------------------------------------------------------------------
# _on_sefer_changed
# ---------------------------------------------------------------------------


async def test_on_sefer_changed_dict_data():
    svc = _make_service()
    event = _make_event({"result": {"id": 200, "mesafe_km": 500}})
    await svc._on_sefer_changed(event)
    svc.rag.index_trip.assert_called_once_with({"id": 200, "mesafe_km": 500})


async def test_on_sefer_changed_non_dict_skips():
    svc = _make_service()
    event = _make_event({"result": 200})
    await svc._on_sefer_changed(event)
    svc.rag.index_trip.assert_not_called()


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------


def test_get_rag_sync_service_returns_same_instance():
    import app.core.ai.rag_sync_service as mod

    # Reset singleton for test isolation
    orig = mod._rag_sync_service
    mod._rag_sync_service = None

    with patch("app.core.ai.rag_sync_service.get_rag_engine", return_value=MagicMock()):
        s1 = mod.get_rag_sync_service()
        s2 = mod.get_rag_sync_service()

    assert s1 is s2

    # Restore
    mod._rag_sync_service = orig
