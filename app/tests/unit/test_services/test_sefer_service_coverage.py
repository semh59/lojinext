"""Coverage tests for app/core/services/sefer_service.py (57% → ≥75%).

SeferService is a Facade — tests verify delegation and the two methods
that contain real logic (set_onay_durumu, get_by_onay_durumu).
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from v2.modules.trip.application.trip_service import SeferService

pytestmark = pytest.mark.unit

# ---------------------------------------------------------------------------
# Helpers: fake sub-services injected via constructor
# ---------------------------------------------------------------------------


def _make_read_service():
    svc = AsyncMock()
    svc.get_by_id = AsyncMock(return_value=None)
    svc.get_sefer_by_id = AsyncMock(return_value=None)
    svc.get_by_vehicle = AsyncMock(return_value=[])
    svc.get_all_paged = AsyncMock(return_value={"items": [], "total": 0})
    svc.get_all_trips = AsyncMock(return_value=[])
    svc.get_trip_stats = AsyncMock(return_value={"total": 0})
    svc.get_fuel_performance_analytics = AsyncMock(return_value={})
    svc.get_timeline = AsyncMock(return_value=[])
    return svc


def _make_write_service():
    svc = AsyncMock()
    svc.add_sefer = AsyncMock(return_value=1)
    svc.update_sefer = AsyncMock(return_value=True)
    svc.delete_sefer = AsyncMock(return_value=True)
    svc.bulk_add_sefer = AsyncMock(return_value=3)
    svc.create_return_trip = AsyncMock(return_value=2)
    svc.bulk_update_status = AsyncMock(return_value={"updated": 2})
    svc.bulk_cancel = AsyncMock(return_value={"cancelled": 1})
    svc.bulk_delete = AsyncMock(return_value={"deleted": 2})
    return svc


def _make_analiz_service():
    svc = AsyncMock()
    svc.reconcile_costs = AsyncMock(return_value={"cost": 100.0})
    return svc


def _make_repo():
    repo = AsyncMock()
    repo.set_onay_durumu = AsyncMock(return_value={"id": 1, "onay_durumu": "onaylandi"})
    repo.get_by_onay_durumu = AsyncMock(return_value=[{"id": 1}])
    return repo


def _make_service() -> SeferService:
    repo = _make_repo()
    event_bus = MagicMock()
    event_bus.publish_async = AsyncMock()

    svc = SeferService.__new__(SeferService)
    svc.repo = repo
    svc.event_bus = event_bus
    svc.read_service = _make_read_service()
    svc.write_service = _make_write_service()
    svc.analiz_service = _make_analiz_service()
    return svc


# ---------------------------------------------------------------------------
# Delegation: READ
# ---------------------------------------------------------------------------


class TestSeferServiceReadDelegation:
    async def test_get_by_id_delegates(self):
        svc = _make_service()
        await svc.get_by_id(sefer_id=1)
        svc.read_service.get_by_id.assert_called_once_with(1, None)

    async def test_get_sefer_by_id_delegates(self):
        svc = _make_service()
        await svc.get_sefer_by_id(sefer_id=1)
        svc.read_service.get_sefer_by_id.assert_called_once_with(1, None)

    async def test_get_by_vehicle_delegates(self):
        svc = _make_service()
        await svc.get_by_vehicle(arac_id=5, limit=10)
        svc.read_service.get_by_vehicle.assert_called_once_with(5, 10)

    async def test_get_all_paged_delegates(self):
        svc = _make_service()
        await svc.get_all_paged(skip=0, limit=25)
        svc.read_service.get_all_paged.assert_called_once()

    async def test_get_all_trips_delegates(self):
        svc = _make_service()
        result = await svc.get_all_trips()
        assert isinstance(result, list)
        svc.read_service.get_all_trips.assert_called_once()

    async def test_get_trip_stats_delegates(self):
        svc = _make_service()
        result = await svc.get_trip_stats()
        assert "total" in result
        svc.read_service.get_trip_stats.assert_called_once()

    async def test_get_fuel_performance_analytics_delegates(self):
        svc = _make_service()
        await svc.get_fuel_performance_analytics()
        svc.read_service.get_fuel_performance_analytics.assert_called_once()

    async def test_get_timeline_delegates(self):
        svc = _make_service()
        await svc.get_timeline(sefer_id=3)
        svc.read_service.get_timeline.assert_called_once_with(3)


# ---------------------------------------------------------------------------
# Delegation: WRITE
# ---------------------------------------------------------------------------


class TestSeferServiceWriteDelegation:
    async def test_add_sefer_delegates(self):
        from app.core.entities.models import SeferCreate

        svc = _make_service()
        data = MagicMock(spec=SeferCreate)
        await svc.add_sefer(data, user_id=1)
        svc.write_service.add_sefer.assert_called_once_with(data, 1)

    async def test_update_sefer_delegates(self):
        from app.core.entities.models import SeferUpdate

        svc = _make_service()
        data = MagicMock(spec=SeferUpdate)
        result = await svc.update_sefer(sefer_id=1, data=data, user_id=2)
        assert result is True
        svc.write_service.update_sefer.assert_called_once_with(1, data, 2)

    async def test_delete_sefer_delegates(self):
        svc = _make_service()
        result = await svc.delete_sefer(sefer_id=1)
        assert result is True
        svc.write_service.delete_sefer.assert_called_once_with(1)

    async def test_bulk_add_sefer_delegates(self):
        svc = _make_service()
        result = await svc.bulk_add_sefer([])
        assert result == 3
        svc.write_service.bulk_add_sefer.assert_called_once_with([])

    async def test_create_return_trip_delegates(self):
        svc = _make_service()
        result = await svc.create_return_trip(sefer_id=1, user_id=5)
        assert result == 2
        svc.write_service.create_return_trip.assert_called_once_with(1, 5)

    async def test_bulk_update_status_delegates(self):
        svc = _make_service()
        result = await svc.bulk_update_status([1, 2], "Tamamlandı", user_id=1)
        assert "updated" in result
        svc.write_service.bulk_update_status.assert_called_once()

    async def test_bulk_cancel_delegates(self):
        svc = _make_service()
        result = await svc.bulk_cancel([1], "Müşteri iptal etti", user_id=1)
        assert "cancelled" in result

    async def test_bulk_delete_delegates(self):
        svc = _make_service()
        result = await svc.bulk_delete([1, 2])
        assert "deleted" in result


# ---------------------------------------------------------------------------
# Delegation: ANALYSIS
# ---------------------------------------------------------------------------


class TestSeferServiceAnalysisDelegation:
    async def test_reconcile_costs_delegates(self):
        svc = _make_service()
        result = await svc.reconcile_costs(sefer_id=1)
        assert result["cost"] == 100.0
        svc.analiz_service.reconcile_costs.assert_called_once_with(1)


# ---------------------------------------------------------------------------
# set_onay_durumu — own logic
# ---------------------------------------------------------------------------


class TestSetOnayDurumu:
    async def test_valid_onaylandi_status(self):
        svc = _make_service()
        svc.read_service.get_sefer_by_id = AsyncMock(
            side_effect=[
                {"id": 1, "onay_durumu": "beklemede"},
                {"id": 1, "onay_durumu": "onaylandi"},
            ]
        )
        svc.repo.set_onay_durumu = AsyncMock(
            return_value={"id": 1, "onay_durumu": "onaylandi"}
        )

        result = await svc.set_onay_durumu(1, "onaylandi", onaylayan_id=2)
        assert result is not None

    async def test_valid_reddedildi_status(self):
        svc = _make_service()
        svc.read_service.get_sefer_by_id = AsyncMock(
            side_effect=[
                {"id": 1, "onay_durumu": "beklemede"},
                {"id": 1, "onay_durumu": "reddedildi"},
            ]
        )
        svc.repo.set_onay_durumu = AsyncMock(
            return_value={"id": 1, "onay_durumu": "reddedildi"}
        )

        result = await svc.set_onay_durumu(1, "reddedildi", onay_notu="Eksik evrak")
        assert result is not None

    async def test_valid_beklemede_status(self):
        svc = _make_service()
        svc.read_service.get_sefer_by_id = AsyncMock(
            side_effect=[
                {"id": 1, "onay_durumu": "onaylandi"},
                {"id": 1, "onay_durumu": "beklemede"},
            ]
        )
        svc.repo.set_onay_durumu = AsyncMock(
            return_value={"id": 1, "onay_durumu": "beklemede"}
        )

        result = await svc.set_onay_durumu(1, "beklemede")
        assert result is not None

    async def test_invalid_status_raises_value_error(self):
        svc = _make_service()
        with pytest.raises(ValueError, match="Geçersiz onay durumu"):
            await svc.set_onay_durumu(1, "geçersiz_durum")

    async def test_returns_none_when_repo_returns_none(self):
        svc = _make_service()
        svc.read_service.get_sefer_by_id = AsyncMock(
            return_value={"id": 1, "onay_durumu": "beklemede"}
        )
        svc.repo.set_onay_durumu = AsyncMock(return_value=None)

        result = await svc.set_onay_durumu(1, "onaylandi")
        assert result is None

    async def test_handles_none_before_data(self):
        """If get_sefer_by_id returns None before update, no crash."""
        svc = _make_service()
        svc.read_service.get_sefer_by_id = AsyncMock(
            side_effect=[
                None,  # before state not found
                {"id": 1, "onay_durumu": "onaylandi"},
            ]
        )
        svc.repo.set_onay_durumu = AsyncMock(
            return_value={"id": 1, "onay_durumu": "onaylandi"}
        )

        result = await svc.set_onay_durumu(1, "onaylandi")
        assert result is not None


# ---------------------------------------------------------------------------
# get_by_onay_durumu — own logic
# ---------------------------------------------------------------------------


class TestGetByOnayDurumu:
    async def test_returns_list_of_enriched_data(self):
        svc = _make_service()
        svc.repo.get_by_onay_durumu = AsyncMock(return_value=[{"id": 1}, {"id": 2}])
        # read_service.get_sefer_by_id called for each row
        svc.read_service.get_sefer_by_id = AsyncMock(
            side_effect=[
                {"id": 1, "onay_durumu": "beklemede"},
                {"id": 2, "onay_durumu": "beklemede"},
            ]
        )

        result = await svc.get_by_onay_durumu("beklemede", skip=0, limit=10)

        assert len(result) == 2
        svc.repo.get_by_onay_durumu.assert_called_once_with(
            "beklemede", skip=0, limit=10
        )

    async def test_returns_repo_rows_without_reenrichment(self):
        """AUDIT-034: repo zaten dolu satır döndürdüğü için per-row re-fetch (N+1)
        kaldırıldı; sonuç doğrudan repo çıktısıdır, get_sefer_by_id çağrılmaz."""
        svc = _make_service()
        svc.repo.get_by_onay_durumu = AsyncMock(return_value=[{"id": 1}, {"id": 2}])
        svc.read_service.get_sefer_by_id = AsyncMock()

        result = await svc.get_by_onay_durumu("onaylandi")

        assert len(result) == 2
        svc.read_service.get_sefer_by_id.assert_not_called()

    async def test_returns_empty_list_when_no_rows(self):
        svc = _make_service()
        svc.repo.get_by_onay_durumu = AsyncMock(return_value=[])

        result = await svc.get_by_onay_durumu("beklemede")
        assert result == []


# ---------------------------------------------------------------------------
# get_sefer_service factory
# ---------------------------------------------------------------------------


class TestGetSeferServiceFactory:
    def test_returns_sefer_service_instance(self):
        from unittest.mock import patch

        import app.core.container as container_mod

        mock_container = MagicMock()
        mock_container.sefer_service = MagicMock(spec=SeferService)

        with patch.object(container_mod, "get_container", return_value=mock_container):
            from v2.modules.trip.application.trip_service import get_sefer_service

            result = get_sefer_service()

        assert result is mock_container.sefer_service
