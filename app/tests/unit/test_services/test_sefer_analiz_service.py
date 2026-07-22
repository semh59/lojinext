"""Unit tests for v2/modules/trip/application/reconcile_costs.py.

``SeferAnalizService`` was dissolved (B.1) into the free function
``reconcile_costs`` — these tests call it directly, patching the module's
own ``UnitOfWork``/``get_event_bus`` (both module-level imports, so the
patch target is the consuming module itself, per convention).
"""

from unittest.mock import AsyncMock, patch

import pytest

from v2.modules.trip.application.reconcile_costs import reconcile_costs

pytestmark = pytest.mark.unit


def _make_mock_uow(
    target_trip=None, daily_fuels=None, daily_trips=None, update_result=True
):
    """Build a fully-mocked UnitOfWork."""
    mock_uow = AsyncMock()
    mock_uow.__aenter__ = AsyncMock(return_value=mock_uow)
    mock_uow.__aexit__ = AsyncMock(return_value=None)

    mock_uow.sefer_repo = AsyncMock()
    mock_uow.sefer_repo.get_by_id = AsyncMock(return_value=target_trip)
    mock_uow.sefer_repo.get_all = AsyncMock(return_value=daily_trips or [])
    mock_uow.sefer_repo.update_sefer = AsyncMock(return_value=update_result)

    mock_uow.yakit_repo = AsyncMock()
    # YakitRepository.get_all returns a paginated {"items": [...], "total": N}
    # envelope (not a plain list) — mirror the real contract.
    _fuels = daily_fuels or []
    mock_uow.yakit_repo.get_all = AsyncMock(
        return_value={"items": _fuels, "total": len(_fuels)}
    )

    mock_uow.commit = AsyncMock()
    return mock_uow


def _make_event_bus():
    event_bus = AsyncMock()
    event_bus.publish_simple_async = AsyncMock()
    return event_bus


class TestReconcileCosts:
    async def test_happy_path(self):
        target_trip = {"id": 1, "tarih": "2024-01-15", "arac_id": 10, "mesafe_km": 200}
        daily_fuels = [{"litre": "60.0"}, {"litre": "40.0"}]  # 100 L total
        daily_trips = [
            {"id": 1, "mesafe_km": 200},
            {"id": 2, "mesafe_km": 300},
        ]
        mock_uow = _make_mock_uow(target_trip, daily_fuels, daily_trips, True)

        with (
            patch(
                "v2.modules.trip.application.reconcile_costs.UnitOfWork",
                return_value=mock_uow,
            ),
            patch(
                "v2.modules.trip.application.reconcile_costs.get_event_bus",
                return_value=_make_event_bus(),
            ),
        ):
            result = await reconcile_costs(sefer_id=1)

        assert result["status"] == "success"
        assert result["total_fuel"] == 100.0
        assert result["total_km"] == 500
        assert result["trips_updated"] == 2

    async def test_error_handling_sefer_not_found(self):
        mock_uow = _make_mock_uow(target_trip=None)

        with (
            patch(
                "v2.modules.trip.application.reconcile_costs.UnitOfWork",
                return_value=mock_uow,
            ),
            patch(
                "v2.modules.trip.application.reconcile_costs.get_event_bus",
                return_value=_make_event_bus(),
            ),
        ):
            with pytest.raises(ValueError, match="Sefer bulunamadı"):
                await reconcile_costs(sefer_id=999)

    async def test_edge_case_empty_zero_km(self):
        """If total daily km is 0, return status=skipped."""
        target_trip = {"id": 1, "tarih": "2024-01-15", "arac_id": 10, "mesafe_km": 0}
        daily_fuels = [{"litre": "50.0"}]
        daily_trips = [{"id": 1, "mesafe_km": 0}]
        mock_uow = _make_mock_uow(target_trip, daily_fuels, daily_trips)

        with (
            patch(
                "v2.modules.trip.application.reconcile_costs.UnitOfWork",
                return_value=mock_uow,
            ),
            patch(
                "v2.modules.trip.application.reconcile_costs.get_event_bus",
                return_value=_make_event_bus(),
            ),
        ):
            result = await reconcile_costs(sefer_id=1)

        assert result["status"] == "skipped"
        assert result["reason"] == "Total daily distance is 0"

    async def test_edge_case_no_fuel(self):
        """AUDIT-037: yakıt kaydı yokken tüketim 0'a EZİLMEZ; reconcile atlanır."""
        target_trip = {"id": 1, "tarih": "2024-01-15", "arac_id": 10, "mesafe_km": 100}
        daily_fuels = []
        daily_trips = [{"id": 1, "mesafe_km": 100}]
        mock_uow = _make_mock_uow(target_trip, daily_fuels, daily_trips)

        with (
            patch(
                "v2.modules.trip.application.reconcile_costs.UnitOfWork",
                return_value=mock_uow,
            ),
            patch(
                "v2.modules.trip.application.reconcile_costs.get_event_bus",
                return_value=_make_event_bus(),
            ),
        ):
            result = await reconcile_costs(sefer_id=1)

        # Yakıt=0 → mevcut tüketim korunur (kalıcı veri kaybı önlenir).
        assert result["status"] == "skipped"
        assert result["total_fuel"] == 0

    async def test_anomaly_detection_fires_for_high_consumption(self):
        """When consumption > threshold, ANOMALY_DETECTED event must be published."""
        # 200 L over 100 km → 200 L/100km >> 50 threshold
        target_trip = {"id": 1, "tarih": "2024-01-15", "arac_id": 10, "mesafe_km": 100}
        daily_fuels = [{"litre": "200.0"}]
        daily_trips = [{"id": 1, "mesafe_km": 100}]
        mock_uow = _make_mock_uow(target_trip, daily_fuels, daily_trips)
        event_bus = _make_event_bus()

        with (
            patch(
                "v2.modules.trip.application.reconcile_costs.UnitOfWork",
                return_value=mock_uow,
            ),
            patch(
                "v2.modules.trip.application.reconcile_costs.get_event_bus",
                return_value=event_bus,
            ),
        ):
            await reconcile_costs(sefer_id=1)

        from v2.modules.platform_infra.events.event_bus import EventType

        calls = event_bus.publish_simple_async.call_args_list
        event_types = [c.args[0] for c in calls]
        assert EventType.ANOMALY_DETECTED in event_types

    async def test_integration_with_mock(self):
        """Multiple trips share fuel proportionally by km."""
        target_trip = {"id": 1, "tarih": "2024-01-15", "arac_id": 10, "mesafe_km": 100}
        daily_fuels = [{"litre": "50.0"}]
        # Trip 1: 100 km, Trip 2: 400 km → 1:4 ratio
        daily_trips = [
            {"id": 1, "mesafe_km": 100},
            {"id": 2, "mesafe_km": 400},
        ]
        mock_uow = _make_mock_uow(target_trip, daily_fuels, daily_trips)

        with (
            patch(
                "v2.modules.trip.application.reconcile_costs.UnitOfWork",
                return_value=mock_uow,
            ),
            patch(
                "v2.modules.trip.application.reconcile_costs.get_event_bus",
                return_value=_make_event_bus(),
            ),
        ):
            result = await reconcile_costs(sefer_id=1)

        details = {d["trip_id"]: d for d in result["details"]}
        # Trip 1 gets 10 L (100/500 * 50), Trip 2 gets 40 L
        assert abs(details[1]["allocated_liters"] - 10.0) < 0.1
        assert abs(details[2]["allocated_liters"] - 40.0) < 0.1

    async def test_return_type_validation(self):
        target_trip = {"id": 1, "tarih": "2024-01-15", "arac_id": 10, "mesafe_km": 100}
        daily_fuels = [{"litre": "30.0"}]
        daily_trips = [{"id": 1, "mesafe_km": 100}]
        mock_uow = _make_mock_uow(target_trip, daily_fuels, daily_trips)

        with (
            patch(
                "v2.modules.trip.application.reconcile_costs.UnitOfWork",
                return_value=mock_uow,
            ),
            patch(
                "v2.modules.trip.application.reconcile_costs.get_event_bus",
                return_value=_make_event_bus(),
            ),
        ):
            result = await reconcile_costs(sefer_id=1)

        assert isinstance(result, dict)
        assert "status" in result
        assert "total_km" in result
        assert "total_fuel" in result
        assert "trips_updated" in result
        assert "details" in result

    async def test_commit_called_on_success(self):
        target_trip = {"id": 1, "tarih": "2024-01-15", "arac_id": 10, "mesafe_km": 100}
        daily_fuels = [{"litre": "30.0"}]
        daily_trips = [{"id": 1, "mesafe_km": 100}]
        mock_uow = _make_mock_uow(target_trip, daily_fuels, daily_trips)

        with (
            patch(
                "v2.modules.trip.application.reconcile_costs.UnitOfWork",
                return_value=mock_uow,
            ),
            patch(
                "v2.modules.trip.application.reconcile_costs.get_event_bus",
                return_value=_make_event_bus(),
            ),
        ):
            await reconcile_costs(sefer_id=1)

        mock_uow.commit.assert_awaited_once()

    async def test_custom_consumption_threshold(self):
        """consumption_threshold param overrides the module default."""
        target_trip = {"id": 1, "tarih": "2024-01-15", "arac_id": 10, "mesafe_km": 100}
        daily_fuels = [{"litre": "20.0"}]  # 20 L/100km consumption
        daily_trips = [{"id": 1, "mesafe_km": 100}]
        mock_uow = _make_mock_uow(target_trip, daily_fuels, daily_trips)
        event_bus = _make_event_bus()

        with (
            patch(
                "v2.modules.trip.application.reconcile_costs.UnitOfWork",
                return_value=mock_uow,
            ),
            patch(
                "v2.modules.trip.application.reconcile_costs.get_event_bus",
                return_value=event_bus,
            ),
        ):
            await reconcile_costs(sefer_id=1, consumption_threshold=10.0)

        from v2.modules.platform_infra.events.event_bus import EventType

        calls = event_bus.publish_simple_async.call_args_list
        event_types = [c.args[0] for c in calls]
        assert EventType.ANOMALY_DETECTED in event_types
