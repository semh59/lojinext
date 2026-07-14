"""
Additional coverage for v2/modules/fuel/domain/period_matcher.py +
v2/modules/fuel/application/recalculate_vehicle_periods.py.

Dalga 4 (B.1 free-function refactor): PeriodCalculationService class deleted
— these are pure module-level / free functions. ``recalculate_vehicle_periods``
takes ``yakit_repo``/``sefer_repo`` directly as kwargs (no constructor
injection) and fetches its cache manager inline via ``get_cache_manager()``
(no ``self.cache`` to assert on — patch the factory instead).

Targets missing lines (module-relative, see the two source files):
  - recalculate_vehicle_periods: default-repo-import branch (yakit_repo/
    sefer_repo=None), sync_distribute_fuel_to_trips total_factor=0 fallback
    + distance-based distribution, full recalc path (periods generated,
    trips matched, UoW used, fuel data updated), dict-shaped get_all result,
    tarih-as-date-object branch.
"""

from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.database.unit_of_work import UnitOfWork
from v2.modules.fuel.application.recalculate_vehicle_periods import (
    recalculate_vehicle_periods,
)
from v2.modules.fuel.domain.period_matcher import sync_distribute_fuel_to_trips

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _sefer(id, arac_id, tarih_str, mesafe_km=300, net_kg=15000):
    from app.core.entities.models import Sefer

    return Sefer(
        id=id,
        tarih=date.fromisoformat(tarih_str),
        arac_id=arac_id,
        sofor_id=1,
        cikis_yeri="Istanbul",
        varis_yeri="Ankara",
        mesafe_km=mesafe_km,
        net_kg=net_kg,
        durum="Planned",
    )


def _make_period(toplam_yakit=1000.0, arac_id=1):
    from app.core.entities.models import YakitPeriyodu

    return YakitPeriyodu(
        arac_id=arac_id,
        ara_mesafe=500,
        toplam_yakit=toplam_yakit,
        alim1_tarih=date(2024, 1, 1),
        alim2_tarih=date(2024, 2, 1),
        alim1_km=100000,
        alim2_km=100500,
    )


# ---------------------------------------------------------------------------
# recalculate_vehicle_periods — default repo import branch
# ---------------------------------------------------------------------------


async def test_recalculate_uses_default_repos_when_none_passed():
    """When no repos are passed, they are imported from their default locations."""
    mock_yakit_repo = MagicMock()
    mock_yakit_repo.get_all = AsyncMock(return_value=[])
    mock_sefer_repo = MagicMock()
    mock_sefer_repo.get_all = AsyncMock(return_value=[])
    mock_cache = MagicMock()
    mock_cache.delete_pattern = MagicMock()

    with (
        patch(
            "v2.modules.fuel.application.recalculate_vehicle_periods.get_cache_manager",
            return_value=mock_cache,
        ),
        patch(
            "v2.modules.fuel.infrastructure.repository.get_yakit_repo",
            return_value=mock_yakit_repo,
        ),
        patch(
            "app.database.repositories.sefer_repo.get_sefer_repo",
            return_value=mock_sefer_repo,
        ),
    ):
        await recalculate_vehicle_periods(arac_id=1)

    mock_yakit_repo.get_all.assert_awaited_once()
    mock_sefer_repo.get_all.assert_awaited_once()


# ---------------------------------------------------------------------------
# sync_distribute_fuel_to_trips: total_factor=0, distance-based fallback
# ---------------------------------------------------------------------------


def test_distribute_total_factor_zero_distance_based():
    """When all trip factors are 0 (zero mesafe * total_mass), distribute by distance."""
    period = _make_period(toplam_yakit=300.0)

    # Make trips where mesafe > 0 but need to force total_factor = 0
    # total_factor = mesafe_km * (empty_weight + load_ton)
    # We can't get factor=0 with mesafe>0 since empty_weight > 0
    # So we set mesafe=0 directly on the trip objects after creation

    t1 = _sefer(1, 1, "2024-01-05", mesafe_km=0, net_kg=0)
    t2 = _sefer(2, 1, "2024-01-10", mesafe_km=0, net_kg=0)
    # With mesafe=0: factor=0*mass=0 → total_factor=0 AND total_distance=0 → returns unchanged
    result = sync_distribute_fuel_to_trips(period, [t1, t2])
    assert result == [t1, t2]


def test_distribute_factor_zero_with_positive_distance_fallback():
    """Force total_factor=0 and total_distance>0 → distance-proportional fallback.

    We replace HGV_EMPTY_WEIGHT in settings with 0 inside the module so that
    total_mass = 0 → factor = 0 with positive mesafe_km → fallback path taken.
    """
    period = _make_period(toplam_yakit=600.0)

    import v2.modules.fuel.domain.period_matcher as mod

    t1 = _sefer(1, 1, "2024-01-05", mesafe_km=200, net_kg=0)
    t2 = _sefer(2, 1, "2024-01-10", mesafe_km=400, net_kg=0)
    # With net_kg=0 → ton=0 (computed). total_mass = empty_weight + 0.
    # We override the module-level settings to zero out empty_weight.
    orig_settings = mod.settings
    mock_settings = MagicMock()
    mock_settings.HGV_EMPTY_WEIGHT = 0.0
    mod.settings = mock_settings
    try:
        result = sync_distribute_fuel_to_trips(period, [t1, t2])
    finally:
        mod.settings = orig_settings

    total_allocated = sum(t.dagitilan_yakit for t in result)
    assert total_allocated == pytest.approx(600.0, abs=0.1)


def test_distribute_last_trip_gets_remaining_fuel():
    """Last trip in distribution gets exact remaining fuel (not rounded proportionally)."""
    period = _make_period(toplam_yakit=100.0)
    # 3 trips — last one gets remaining_fuel exactly
    trips = [
        _sefer(1, 1, "2024-01-05", mesafe_km=100, net_kg=10000),
        _sefer(2, 1, "2024-01-10", mesafe_km=100, net_kg=10000),
        _sefer(3, 1, "2024-01-15", mesafe_km=100, net_kg=10000),
    ]
    result = sync_distribute_fuel_to_trips(period, trips)
    total = sum(t.dagitilan_yakit for t in result)
    assert total == pytest.approx(100.0, abs=0.01)


# ---------------------------------------------------------------------------
# recalculate_vehicle_periods — full path
# ---------------------------------------------------------------------------


def _repos(fuel_records_data, sefer_data):
    mock_yakit_repo = MagicMock()
    mock_yakit_repo.get_all = AsyncMock(return_value=fuel_records_data)
    mock_sefer_repo = MagicMock()
    mock_sefer_repo.get_all = AsyncMock(return_value=sefer_data)
    return mock_yakit_repo, mock_sefer_repo


async def test_recalculate_vehicle_periods_with_no_periods():
    """When no periods are generated, UoW is NOT entered and cache is cleared."""
    mock_yakit_repo, mock_sefer_repo = _repos([], [])
    mock_cache = MagicMock()
    mock_cache.delete_pattern = MagicMock()

    with patch(
        "v2.modules.fuel.application.recalculate_vehicle_periods.get_cache_manager",
        return_value=mock_cache,
    ):
        await recalculate_vehicle_periods(
            arac_id=1, yakit_repo=mock_yakit_repo, sefer_repo=mock_sefer_repo
        )

    # Cache patterns should still be cleared
    assert mock_cache.delete_pattern.call_count == 3


async def test_recalculate_vehicle_periods_with_dict_result():
    """yakit_repo.get_all returning a dict is handled via .get('items', [])."""
    mock_yakit_repo, mock_sefer_repo = _repos({"items": [], "total": 0}, [])
    mock_cache = MagicMock()
    mock_cache.delete_pattern = MagicMock()

    with patch(
        "v2.modules.fuel.application.recalculate_vehicle_periods.get_cache_manager",
        return_value=mock_cache,
    ):
        await recalculate_vehicle_periods(
            arac_id=2, yakit_repo=mock_yakit_repo, sefer_repo=mock_sefer_repo
        )

    mock_cache.delete_pattern.assert_any_call("arac:2:*")


async def test_recalculate_vehicle_periods_with_periods_and_trips():
    """Full path: periods generated, trips matched, UoW used, fuel data updated.

    We mock sync_create_fuel_periods to return synthetic periods so we can test
    the if-periods branch without relying on the depo_durumu field being set in
    the internal YakitAlimi constructor (which omits it).
    """
    fuel_records_data = [
        {
            "id": 1,
            "tarih": "2024-01-01",
            "arac_id": 5,
            "istasyon": "BP",
            "fiyat_tl": "35.00",
            "litre": 400.0,
            "km_sayac": 100000,
            "fis_no": "F001",
        },
    ]

    sefer_data = [
        {
            "id": 10,
            "tarih": "2024-01-15",
            "arac_id": 5,
            "sofor_id": 1,
            "cikis_yeri": "Istanbul",
            "varis_yeri": "Ankara",
            "mesafe_km": 300,
            "net_kg": 15000,
            "durum": "Planned",
        }
    ]

    mock_yakit_repo, mock_sefer_repo = _repos(fuel_records_data, sefer_data)
    mock_cache = MagicMock()
    mock_cache.delete_pattern = MagicMock()

    # Return synthetic periods so the if-periods branch is entered
    synthetic_period = _make_period(arac_id=5)

    # Mock UnitOfWork
    mock_uow = MagicMock()
    mock_uow.__aenter__ = AsyncMock(return_value=mock_uow)
    mock_uow.__aexit__ = AsyncMock(return_value=False)
    mock_uow.yakit_repo = MagicMock()
    mock_uow.yakit_repo.save_fuel_periods = AsyncMock()
    mock_uow.sefer_repo = MagicMock()
    mock_uow.sefer_repo.update_trips_fuel_data = AsyncMock()
    mock_uow.commit = AsyncMock()

    with (
        patch(
            "v2.modules.fuel.application.recalculate_vehicle_periods.get_cache_manager",
            return_value=mock_cache,
        ),
        patch(
            "v2.modules.fuel.application.recalculate_vehicle_periods.sync_create_fuel_periods",
            MagicMock(return_value=[synthetic_period]),
        ),
        patch.object(UnitOfWork, "__aenter__", AsyncMock(return_value=mock_uow)),
        patch.object(UnitOfWork, "__aexit__", AsyncMock(return_value=False)),
    ):
        await recalculate_vehicle_periods(
            arac_id=5, yakit_repo=mock_yakit_repo, sefer_repo=mock_sefer_repo
        )

    mock_uow.yakit_repo.save_fuel_periods.assert_called_once()
    mock_uow.commit.assert_called_once()
    mock_cache.delete_pattern.assert_any_call("arac:5:*")
    mock_cache.delete_pattern.assert_any_call("fleet:avg:*")
    mock_cache.delete_pattern.assert_any_call("dashboard:*")


async def test_recalculate_vehicle_periods_no_updated_trips():
    """When periods exist but no trips match, sefer update is skipped."""
    mock_yakit_repo, mock_sefer_repo = _repos([], [])
    mock_cache = MagicMock()
    mock_cache.delete_pattern = MagicMock()

    # Return a period for vehicle 6, but no matching trips (different arac_id)
    synthetic_period = _make_period(arac_id=6)

    mock_uow = MagicMock()
    mock_uow.__aenter__ = AsyncMock(return_value=mock_uow)
    mock_uow.__aexit__ = AsyncMock(return_value=False)
    mock_uow.yakit_repo = MagicMock()
    mock_uow.yakit_repo.save_fuel_periods = AsyncMock()
    mock_uow.sefer_repo = MagicMock()
    mock_uow.sefer_repo.update_trips_fuel_data = AsyncMock()
    mock_uow.commit = AsyncMock()

    with (
        patch(
            "v2.modules.fuel.application.recalculate_vehicle_periods.get_cache_manager",
            return_value=mock_cache,
        ),
        patch(
            "v2.modules.fuel.application.recalculate_vehicle_periods.sync_create_fuel_periods",
            MagicMock(return_value=[synthetic_period]),
        ),
        patch.object(UnitOfWork, "__aenter__", AsyncMock(return_value=mock_uow)),
        patch.object(UnitOfWork, "__aexit__", AsyncMock(return_value=False)),
    ):
        await recalculate_vehicle_periods(
            arac_id=6, yakit_repo=mock_yakit_repo, sefer_repo=mock_sefer_repo
        )

    # save_fuel_periods still called but update_trips_fuel_data should NOT be called
    mock_uow.yakit_repo.save_fuel_periods.assert_called_once()
    mock_uow.sefer_repo.update_trips_fuel_data.assert_not_called()


async def test_recalculate_vehicle_periods_tarih_as_date_object():
    """tarih fields that are already date objects (not str) are passed through directly.

    Uses sync_create_fuel_periods mock so UoW branch is entered.
    """
    # tarih is already a date object, not a string — exercises the else branch
    fuel_records_data = [
        {
            "id": 1,
            "tarih": date(2024, 1, 1),  # date object, not str
            "arac_id": 7,
            "istasyon": "BP",
            "fiyat_tl": "35.00",
            "litre": 400.0,
            "km_sayac": 100000,
            "fis_no": "F001",
        },
    ]

    sefer_data = [
        {
            "id": 30,
            "tarih": date(2024, 1, 15),  # date object
            "arac_id": 7,
            "sofor_id": 1,
            "cikis_yeri": "Istanbul",
            "varis_yeri": "Ankara",
            "mesafe_km": 300,
            "net_kg": 15000,
            "durum": "Planned",
        }
    ]

    mock_yakit_repo, mock_sefer_repo = _repos(fuel_records_data, sefer_data)
    mock_cache = MagicMock()
    mock_cache.delete_pattern = MagicMock()

    synthetic_period = _make_period(arac_id=7)

    mock_uow = MagicMock()
    mock_uow.__aenter__ = AsyncMock(return_value=mock_uow)
    mock_uow.__aexit__ = AsyncMock(return_value=False)
    mock_uow.yakit_repo = MagicMock()
    mock_uow.yakit_repo.save_fuel_periods = AsyncMock()
    mock_uow.sefer_repo = MagicMock()
    mock_uow.sefer_repo.update_trips_fuel_data = AsyncMock()
    mock_uow.commit = AsyncMock()

    with (
        patch(
            "v2.modules.fuel.application.recalculate_vehicle_periods.get_cache_manager",
            return_value=mock_cache,
        ),
        patch(
            "v2.modules.fuel.application.recalculate_vehicle_periods.sync_create_fuel_periods",
            MagicMock(return_value=[synthetic_period]),
        ),
        patch.object(UnitOfWork, "__aenter__", AsyncMock(return_value=mock_uow)),
        patch.object(UnitOfWork, "__aexit__", AsyncMock(return_value=False)),
    ):
        await recalculate_vehicle_periods(
            arac_id=7, yakit_repo=mock_yakit_repo, sefer_repo=mock_sefer_repo
        )

    mock_uow.commit.assert_called_once()


# test_get_period_calculation_service_singleton removed — PeriodCalculationService
# class + get_period_calculation_service() singleton factory both deleted in
# dalga 4 (B.1 free-function refactor, v2.modules.fuel); recalculate_vehicle_periods
# is a stateless free function, no singleton to test.
