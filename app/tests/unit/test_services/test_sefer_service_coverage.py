"""Coverage tests for v2/modules/trip/application/trip_service.py.

SeferService is a thin facade (ARCH-006) that delegates every operation to
a free function in a sibling ``application/*.py`` module — it holds no
CQRS sub-service instances. These tests verify that delegation: each
facade method is patched at its call site and asserted to forward the
right arguments to the underlying free function.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from v2.modules.trip.application import list_trips, onay, trip_service
from v2.modules.trip.application.trip_service import SeferService

pytestmark = pytest.mark.unit


def _make_service() -> SeferService:
    repo = MagicMock()
    event_bus = MagicMock()
    event_bus.publish_async = AsyncMock()
    return SeferService(repo=repo, event_bus=event_bus)


# ---------------------------------------------------------------------------
# Delegation: READ
# ---------------------------------------------------------------------------


class TestSeferServiceReadDelegation:
    async def test_get_by_id_delegates(self):
        svc = _make_service()
        with patch.object(
            list_trips, "get_by_id", new=AsyncMock(return_value=None)
        ) as mock_fn:
            await svc.get_by_id(sefer_id=1)
        mock_fn.assert_called_once_with(1, None, repo=svc.repo)

    async def test_get_sefer_by_id_delegates(self):
        svc = _make_service()
        with patch.object(
            list_trips, "get_sefer_by_id", new=AsyncMock(return_value=None)
        ) as mock_fn:
            await svc.get_sefer_by_id(sefer_id=1)
        mock_fn.assert_called_once_with(1, None, repo=svc.repo)

    async def test_get_by_vehicle_delegates(self):
        svc = _make_service()
        with patch.object(
            list_trips, "get_by_vehicle", new=AsyncMock(return_value=[])
        ) as mock_fn:
            await svc.get_by_vehicle(arac_id=5, limit=10)
        mock_fn.assert_called_once_with(5, 10, repo=svc.repo)

    async def test_get_all_paged_delegates(self):
        svc = _make_service()
        with patch.object(
            list_trips,
            "get_all_paged",
            new=AsyncMock(return_value={"items": [], "total": 0}),
        ) as mock_fn:
            await svc.get_all_paged(skip=0, limit=25)
        mock_fn.assert_called_once()

    async def test_get_all_trips_delegates(self):
        svc = _make_service()
        with patch.object(
            list_trips, "get_all_trips", new=AsyncMock(return_value=[])
        ) as mock_fn:
            result = await svc.get_all_trips()
        assert isinstance(result, list)
        mock_fn.assert_called_once()

    async def test_get_trip_stats_delegates(self):
        svc = _make_service()
        with patch(
            "v2.modules.trip.application.trip_stats.get_trip_stats",
            new=AsyncMock(return_value={"total": 0}),
        ) as mock_fn:
            result = await svc.get_trip_stats()
        assert "total" in result
        mock_fn.assert_called_once()

    async def test_get_fuel_performance_analytics_delegates(self):
        svc = _make_service()
        with patch(
            "v2.modules.trip.application.trip_stats.get_fuel_performance_analytics",
            new=AsyncMock(return_value={}),
        ) as mock_fn:
            await svc.get_fuel_performance_analytics()
        mock_fn.assert_called_once()

    async def test_get_timeline_delegates(self):
        svc = _make_service()
        with patch.object(
            list_trips, "get_timeline", new=AsyncMock(return_value=[])
        ) as mock_fn:
            await svc.get_timeline(sefer_id=3)
        mock_fn.assert_called_once_with(3)


# ---------------------------------------------------------------------------
# Delegation: WRITE
# ---------------------------------------------------------------------------


class TestSeferServiceWriteDelegation:
    async def test_add_sefer_delegates(self):
        from v2.modules.trip.schemas import SeferCreate

        svc = _make_service()
        data = MagicMock(spec=SeferCreate)
        with patch.object(
            trip_service, "_add_sefer", new=AsyncMock(return_value=1)
        ) as mock_fn:
            await svc.add_sefer(data, user_id=1)
        mock_fn.assert_called_once_with(data, 1)

    async def test_update_sefer_delegates(self):
        from v2.modules.trip.schemas import SeferUpdate

        svc = _make_service()
        data = MagicMock(spec=SeferUpdate)
        with patch.object(
            trip_service, "_update_sefer", new=AsyncMock(return_value=True)
        ) as mock_fn:
            result = await svc.update_sefer(sefer_id=1, data=data, user_id=2)
        assert result is True
        mock_fn.assert_called_once_with(1, data, 2)

    async def test_delete_sefer_delegates(self):
        svc = _make_service()
        with patch.object(
            trip_service, "_delete_sefer", new=AsyncMock(return_value=True)
        ) as mock_fn:
            result = await svc.delete_sefer(sefer_id=1)
        assert result is True
        mock_fn.assert_called_once_with(1)

    async def test_bulk_add_sefer_delegates(self):
        svc = _make_service()
        with patch.object(
            trip_service, "_bulk_add_sefer", new=AsyncMock(return_value=3)
        ) as mock_fn:
            result = await svc.bulk_add_sefer([])
        assert result == 3
        mock_fn.assert_called_once_with([])

    async def test_create_return_trip_delegates(self):
        svc = _make_service()
        with patch.object(
            trip_service, "_create_return", new=AsyncMock(return_value=2)
        ) as mock_fn:
            result = await svc.create_return_trip(sefer_id=1, user_id=5)
        assert result == 2
        mock_fn.assert_called_once_with(1, 5)

    async def test_bulk_update_status_delegates(self):
        svc = _make_service()
        with patch.object(
            trip_service,
            "_bulk_update_status",
            new=AsyncMock(return_value={"updated": 2}),
        ) as mock_fn:
            result = await svc.bulk_update_status([1, 2], "Tamamlandı", user_id=1)
        assert "updated" in result
        mock_fn.assert_called_once()

    async def test_bulk_cancel_delegates(self):
        svc = _make_service()
        with patch.object(
            trip_service,
            "_bulk_cancel",
            new=AsyncMock(return_value={"cancelled": 1}),
        ) as mock_fn:
            result = await svc.bulk_cancel([1], "Müşteri iptal etti", user_id=1)
        assert "cancelled" in result
        mock_fn.assert_called_once()

    async def test_bulk_delete_delegates(self):
        svc = _make_service()
        with patch.object(
            trip_service, "_bulk_delete", new=AsyncMock(return_value={"deleted": 2})
        ) as mock_fn:
            result = await svc.bulk_delete([1, 2])
        assert "deleted" in result
        mock_fn.assert_called_once()


# ---------------------------------------------------------------------------
# Delegation: ANALYSIS
# ---------------------------------------------------------------------------


class TestSeferServiceAnalysisDelegation:
    async def test_reconcile_costs_delegates(self):
        svc = _make_service()
        with patch.object(
            trip_service, "_reconcile", new=AsyncMock(return_value={"cost": 100.0})
        ) as mock_fn:
            result = await svc.reconcile_costs(sefer_id=1)
        assert result["cost"] == 100.0
        mock_fn.assert_called_once_with(1)


# ---------------------------------------------------------------------------
# Approval workflow delegation (onay.py)
# ---------------------------------------------------------------------------


class TestApprovalDelegation:
    async def test_set_onay_durumu_delegates(self):
        svc = _make_service()
        with patch.object(
            onay,
            "set_onay_durumu",
            new=AsyncMock(return_value={"id": 1, "onay_durumu": "onaylandi"}),
        ) as mock_fn:
            result = await svc.set_onay_durumu(1, "onaylandi", onaylayan_id=2)
        assert result is not None
        mock_fn.assert_called_once_with(1, "onaylandi", None, 2, repo=svc.repo)

    async def test_get_by_onay_durumu_delegates(self):
        svc = _make_service()
        with patch.object(
            onay,
            "get_by_onay_durumu",
            new=AsyncMock(return_value=[{"id": 1}, {"id": 2}]),
        ) as mock_fn:
            result = await svc.get_by_onay_durumu("beklemede", skip=0, limit=10)
        assert len(result) == 2
        mock_fn.assert_called_once_with("beklemede", 0, 10, repo=svc.repo)


# ---------------------------------------------------------------------------
# get_sefer_service factory
# ---------------------------------------------------------------------------


class TestGetSeferServiceFactory:
    def test_returns_sefer_service_instance(self):
        import v2.modules.platform_infra.container as container_mod

        mock_container = MagicMock()
        mock_container.sefer_service = MagicMock(spec=SeferService)

        with patch.object(container_mod, "get_container", return_value=mock_container):
            from v2.modules.trip.application.trip_service import get_sefer_service

            result = get_sefer_service()

        assert result is mock_container.sefer_service
