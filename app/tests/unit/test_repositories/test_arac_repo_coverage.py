"""AracRepository comprehensive unit tests — targets missing lines 19-429.

Covers:
- get_all (delegates to get_all_with_stats_paged)
- count_all: all filter branches (sadece_aktif, search, marka, model, yil_ge, yil_le)
- count_active
- get_all_with_stats_paged: base + all filter branches + pagination
- get_by_plaka: found, not found, for_update
- add: happy path, duplicate plaka raises ValueError
- get_arac_with_stats: found, not found
- get_aktif_plakalar
- get_maintenance_candidates: severity branches (critical/high/medium), no-reason skip,
  date-aware son_bakim, None son_bakim
- get_eligible_for_planning
- hard_delete_all: success and error path
- get_by_ids: empty list, multiple ids
- get_arac_repo: session-less singleton, session arg returns new instance
"""

from datetime import datetime, timezone
from types import SimpleNamespace
from typing import Any, Dict, List
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_repo(session=None):
    """Return an AracRepository with a mocked async session."""
    from app.database.repositories.arac_repo import AracRepository

    repo = AracRepository.__new__(AracRepository)
    repo._session = session if session is not None else AsyncMock()
    return repo


def _scalar_result(value):
    """Build a mock result whose .scalar() returns *value*."""
    r = MagicMock()
    r.scalar = MagicMock(return_value=value)
    return r


def _mappings_result(rows: List[Dict[str, Any]]):
    """Build a mock result whose mappings().all() returns plain dicts.

    ``execute_query`` does ``[dict(row) for row in result.mappings().all()]``,
    so we just return the dicts directly — ``dict(d)`` on a plain dict is a no-op copy.
    """
    mapping_mock = MagicMock()
    mapping_mock.all = MagicMock(return_value=list(rows))

    r = MagicMock()
    r.mappings = MagicMock(return_value=mapping_mock)
    return r


def _scalars_all_result(objs):
    """Build a mock result whose .scalars().all() returns *objs*."""
    scalars = MagicMock()
    scalars.all = MagicMock(return_value=objs)
    r = MagicMock()
    r.scalars = MagicMock(return_value=scalars)
    return r


def _scalar_one_or_none_result(obj):
    r = MagicMock()
    r.scalar_one_or_none = MagicMock(return_value=obj)
    return r


# ---------------------------------------------------------------------------
# count_all
# ---------------------------------------------------------------------------


class TestAracRepoCountAll:
    async def test_count_all_basic(self):
        """count_all with no filters returns scalar result."""
        repo = _make_repo()
        repo._session.execute = AsyncMock(return_value=_scalar_result(5))
        result = await repo.count_all()
        assert result == 5

    async def test_count_all_sadece_aktif_false(self):
        """count_all with sadece_aktif=False skips aktif filter."""
        repo = _make_repo()
        repo._session.execute = AsyncMock(return_value=_scalar_result(10))
        result = await repo.count_all(sadece_aktif=False)
        assert result == 10

    async def test_count_all_with_search(self):
        """count_all with search adds ILIKE clause."""
        repo = _make_repo()
        repo._session.execute = AsyncMock(return_value=_scalar_result(3))
        result = await repo.count_all(search="34 ABC")
        assert result == 3

    async def test_count_all_with_marka_filter(self):
        """count_all with marka filter in filters dict."""
        repo = _make_repo()
        repo._session.execute = AsyncMock(return_value=_scalar_result(2))
        result = await repo.count_all(filters={"marka": "MAN"})
        assert result == 2

    async def test_count_all_with_model_filter(self):
        """count_all with model filter in filters dict."""
        repo = _make_repo()
        repo._session.execute = AsyncMock(return_value=_scalar_result(1))
        result = await repo.count_all(filters={"model": "TGX"})
        assert result == 1

    async def test_count_all_with_yil_ge_filter(self):
        """count_all with yil_ge filter in filters dict."""
        repo = _make_repo()
        repo._session.execute = AsyncMock(return_value=_scalar_result(4))
        result = await repo.count_all(filters={"yil_ge": 2018})
        assert result == 4

    async def test_count_all_with_yil_le_filter(self):
        """count_all with yil_le filter in filters dict."""
        repo = _make_repo()
        repo._session.execute = AsyncMock(return_value=_scalar_result(7))
        result = await repo.count_all(filters={"yil_le": 2022})
        assert result == 7

    async def test_count_all_returns_zero_when_none(self):
        """count_all returns 0 when scalar is None."""
        repo = _make_repo()
        repo._session.execute = AsyncMock(return_value=_scalar_result(None))
        result = await repo.count_all()
        assert result == 0


# ---------------------------------------------------------------------------
# count_active
# ---------------------------------------------------------------------------


class TestAracRepoCountActive:
    async def test_count_active_returns_int(self):
        """count_active returns integer from raw query."""
        repo = _make_repo()
        repo._session.execute = AsyncMock(return_value=_scalar_result(8))
        result = await repo.count_active()
        assert result == 8

    async def test_count_active_returns_zero_when_none(self):
        """count_active returns 0 when DB returns NULL."""
        repo = _make_repo()
        repo._session.execute = AsyncMock(return_value=_scalar_result(None))
        result = await repo.count_active()
        assert result == 0


# ---------------------------------------------------------------------------
# get_all_with_stats_paged
# ---------------------------------------------------------------------------


class TestAracRepoGetAllWithStatsPaged:
    async def test_basic_query_returns_dicts(self):
        """get_all_with_stats_paged returns list of dicts from mappings."""
        repo = _make_repo()
        rows = [{"id": 1, "plaka": "34 ABC 001"}]
        repo._session.execute = AsyncMock(return_value=_mappings_result(rows))
        result = await repo.get_all_with_stats_paged()
        assert len(result) == 1
        assert result[0]["plaka"] == "34 ABC 001"

    async def test_with_search_filter(self):
        """get_all_with_stats_paged adds search clause when search provided."""
        repo = _make_repo()
        repo._session.execute = AsyncMock(return_value=_mappings_result([]))
        result = await repo.get_all_with_stats_paged(search="34")
        assert result == []

    async def test_sadece_aktif_false_skips_filter(self):
        """get_all_with_stats_paged with sadece_aktif=False excludes aktif filter."""
        repo = _make_repo()
        repo._session.execute = AsyncMock(return_value=_mappings_result([]))
        result = await repo.get_all_with_stats_paged(sadece_aktif=False)
        assert result == []

    async def test_with_marka_and_model_filters(self):
        """Marka and model filters are applied."""
        repo = _make_repo()
        repo._session.execute = AsyncMock(return_value=_mappings_result([]))
        result = await repo.get_all_with_stats_paged(
            filters={"marka": "MAN", "model": "TGX"}
        )
        assert result == []

    async def test_with_yil_range_filters(self):
        """yil_ge and yil_le filters are applied."""
        repo = _make_repo()
        repo._session.execute = AsyncMock(return_value=_mappings_result([]))
        result = await repo.get_all_with_stats_paged(
            filters={"yil_ge": 2015, "yil_le": 2023}
        )
        assert result == []

    async def test_pagination_params_passed(self):
        """limit and offset are forwarded to query params."""
        repo = _make_repo()
        call_args = {}

        async def capture_execute(stmt, params=None):
            call_args.update(params or {})
            return _mappings_result([])

        repo._session.execute = capture_execute
        await repo.get_all_with_stats_paged(limit=25, offset=50)
        assert call_args.get("limit") == 25
        assert call_args.get("offset") == 50


# ---------------------------------------------------------------------------
# get_all (delegates)
# ---------------------------------------------------------------------------


class TestAracRepoGetAll:
    async def test_get_all_delegates_to_paged(self):
        """get_all calls get_all_with_stats_paged and returns result."""
        repo = _make_repo()
        rows = [{"id": 1, "plaka": "06 ZZ 999"}]
        repo._session.execute = AsyncMock(return_value=_mappings_result(rows))
        result = await repo.get_all()
        assert result == rows

    async def test_get_all_with_search(self):
        """get_all passes search into filters correctly."""
        repo = _make_repo()
        repo._session.execute = AsyncMock(return_value=_mappings_result([]))
        result = await repo.get_all(search="06", sadece_aktif=False)
        assert result == []


# ---------------------------------------------------------------------------
# get_by_plaka
# ---------------------------------------------------------------------------


class TestAracRepoGetByPlaka:
    async def test_found_returns_dict(self):
        """get_by_plaka returns dict for existing plaka."""
        repo = _make_repo()
        mock_arac = SimpleNamespace(
            **{"id": 1, "plaka": "34 ABC 001", "_sa_instance_state": "x"}
        )
        repo._session.execute = AsyncMock(
            return_value=_scalar_one_or_none_result(mock_arac)
        )
        result = await repo.get_by_plaka("34 ABC 001")
        assert result is not None
        assert result["plaka"] == "34 ABC 001"
        assert "_sa_instance_state" not in result

    async def test_not_found_returns_none(self):
        """get_by_plaka returns None when not found."""
        repo = _make_repo()
        repo._session.execute = AsyncMock(return_value=_scalar_one_or_none_result(None))
        result = await repo.get_by_plaka("NONEXISTENT")
        assert result is None

    async def test_for_update_flag(self):
        """get_by_plaka with for_update=True sends WITH FOR UPDATE."""
        repo = _make_repo()
        mock_arac = SimpleNamespace(**{"id": 2, "plaka": "35 DEF 002"})
        repo._session.execute = AsyncMock(
            return_value=_scalar_one_or_none_result(mock_arac)
        )
        result = await repo.get_by_plaka("35 DEF 002", for_update=True)
        assert result is not None


# ---------------------------------------------------------------------------
# add
# ---------------------------------------------------------------------------


class TestAracRepoAdd:
    async def test_add_creates_vehicle(self):
        """add creates and flushes a new Arac object."""
        from app.database.models import Arac

        repo = _make_repo()
        # First execute: no duplicate found
        no_dup = _scalar_one_or_none_result(None)
        repo._session.execute = AsyncMock(return_value=no_dup)
        repo._session.add = MagicMock()
        repo._session.flush = AsyncMock()

        with patch("app.database.repositories.arac_repo.AracRepository.model", Arac):
            new_arac = await repo.add(
                plaka="34 NEW 001",
                marka="MAN",
                model="TGX",
            )
        assert new_arac is not None
        repo._session.add.assert_called_once()
        repo._session.flush.assert_called_once()

    async def test_add_duplicate_raises_value_error(self):
        """add raises ValueError when plaka already exists."""
        from app.database.models import Arac

        repo = _make_repo()
        existing = MagicMock(spec=Arac)
        dup = _scalar_one_or_none_result(existing)
        repo._session.execute = AsyncMock(return_value=dup)

        with pytest.raises(ValueError, match="zaten kayıtlı"):
            await repo.add(plaka="34 DUP 001", marka="MAN")


# ---------------------------------------------------------------------------
# get_arac_with_stats
# ---------------------------------------------------------------------------


class TestAracRepoGetAracWithStats:
    async def test_found_returns_first_row(self):
        """get_arac_with_stats returns first row dict."""
        repo = _make_repo()
        rows = [{"arac_id": 1, "plaka": "34 ABC 001", "toplam_sefer": 10}]
        repo._session.execute = AsyncMock(return_value=_mappings_result(rows))
        result = await repo.get_arac_with_stats(1)
        assert result == rows[0]

    async def test_not_found_returns_none(self):
        """get_arac_with_stats returns None when no rows."""
        repo = _make_repo()
        repo._session.execute = AsyncMock(return_value=_mappings_result([]))
        result = await repo.get_arac_with_stats(999)
        assert result is None


# ---------------------------------------------------------------------------
# get_aktif_plakalar
# ---------------------------------------------------------------------------


class TestAracRepoGetAktifPlakalar:
    async def test_returns_list_of_strings(self):
        """get_aktif_plakalar returns list of plaka strings."""
        repo = _make_repo()
        rows = [{"plaka": "34 AA 001"}, {"plaka": "06 BB 002"}]
        repo._session.execute = AsyncMock(return_value=_mappings_result(rows))
        result = await repo.get_aktif_plakalar()
        assert result == ["34 AA 001", "06 BB 002"]

    async def test_returns_empty_list_when_none(self):
        """get_aktif_plakalar returns [] when table is empty."""
        repo = _make_repo()
        repo._session.execute = AsyncMock(return_value=_mappings_result([]))
        result = await repo.get_aktif_plakalar()
        assert result == []


# ---------------------------------------------------------------------------
# get_maintenance_candidates
# ---------------------------------------------------------------------------


class TestAracRepoGetMaintenanceCandidates:
    def _make_row(self, yil=2005, ort_tuketim=36.0, toplam_km=600_000, son_bakim=None):
        return {
            "id": 1,
            "plaka": "34 TEST 001",
            "marka": "MAN",
            "model": "TGX",
            "yil": yil,
            "ort_tuketim": ort_tuketim,
            "toplam_km": toplam_km,
            "son_bakim": son_bakim,
        }

    async def test_critical_severity_three_reasons(self):
        """3+ criteria → severity 'critical'."""
        repo = _make_repo()
        row = self._make_row(
            yil=2005, ort_tuketim=36.0, toplam_km=600_000, son_bakim=None
        )
        repo._session.execute = AsyncMock(return_value=_mappings_result([row]))
        result = await repo.get_maintenance_candidates()
        vehicle = result["vehicles"][0]
        assert vehicle["severity"] == "critical"
        assert result["urgent_count"] >= 1

    async def test_high_severity_two_reasons(self):
        """Exactly 2 criteria → severity 'high'.

        Use: old vehicle (age>15) + high consumption (>35), no maintenance record
        would add a 3rd reason so we provide a recent_maintenance date.
        son_bakim set to a date < 365 days ago to avoid triggering old-maintenance reason.
        """
        repo = _make_repo()
        from datetime import timedelta

        recent_bakim = datetime.now(timezone.utc) - timedelta(days=30)
        row = self._make_row(
            yil=2005,  # age > 15 → reason 1
            ort_tuketim=36.0,  # > 35    → reason 2
            toplam_km=100_000,  # < 500k  → no reason
            son_bakim=recent_bakim,  # < 365 days → no reason
        )
        repo._session.execute = AsyncMock(return_value=_mappings_result([row]))
        result = await repo.get_maintenance_candidates()
        vehicle = result["vehicles"][0]
        assert vehicle["severity"] == "high"

    async def test_medium_severity_one_reason(self):
        """1 criterion → severity 'medium'."""
        repo = _make_repo()
        row = self._make_row(
            yil=2015, ort_tuketim=20.0, toplam_km=100_000, son_bakim=None
        )
        repo._session.execute = AsyncMock(return_value=_mappings_result([row]))
        result = await repo.get_maintenance_candidates()
        vehicle = result["vehicles"][0]
        assert vehicle["severity"] == "medium"

    async def test_no_criteria_row_skipped(self):
        """Row with no trigger criteria is skipped."""
        repo = _make_repo()
        future_date = datetime.now(timezone.utc)
        row = self._make_row(
            yil=2020, ort_tuketim=25.0, toplam_km=50_000, son_bakim=future_date
        )
        repo._session.execute = AsyncMock(return_value=_mappings_result([row]))
        result = await repo.get_maintenance_candidates()
        assert result["vehicles"] == []

    async def test_son_bakim_old_adds_reason(self):
        """son_bakim > 365 days ago adds a reason."""
        repo = _make_repo()
        old_date = datetime(2020, 1, 1, tzinfo=timezone.utc)
        row = self._make_row(
            yil=2018, ort_tuketim=30.0, toplam_km=200_000, son_bakim=old_date
        )
        repo._session.execute = AsyncMock(return_value=_mappings_result([row]))
        result = await repo.get_maintenance_candidates()
        vehicle = result["vehicles"][0]
        assert "gun once" in vehicle["reason"]

    async def test_son_bakim_naive_datetime_handled(self):
        """son_bakim without tzinfo is made UTC-aware."""
        repo = _make_repo()
        naive_date = datetime(2020, 1, 1)  # no tzinfo
        row = self._make_row(
            yil=2018, ort_tuketim=30.0, toplam_km=200_000, son_bakim=naive_date
        )
        repo._session.execute = AsyncMock(return_value=_mappings_result([row]))
        result = await repo.get_maintenance_candidates()
        # Should not crash; should produce a vehicle entry
        assert len(result["vehicles"]) == 1

    async def test_empty_result_returns_zero_counts(self):
        """No candidates → urgent_count=0, warning_count=0."""
        repo = _make_repo()
        repo._session.execute = AsyncMock(return_value=_mappings_result([]))
        result = await repo.get_maintenance_candidates()
        assert result["urgent_count"] == 0
        assert result["warning_count"] == 0
        assert result["vehicles"] == []


# ---------------------------------------------------------------------------
# get_eligible_for_planning
# ---------------------------------------------------------------------------


class TestAracRepoGetEligibleForPlanning:
    async def test_returns_list_of_candidates(self):
        """get_eligible_for_planning returns list of vehicle dicts."""
        repo = _make_repo()
        rows = [
            {"id": 1, "plaka": "34 AA 001", "recent_trip_count": 0},
            {"id": 2, "plaka": "34 BB 002", "recent_trip_count": 2},
        ]
        repo._session.execute = AsyncMock(return_value=_mappings_result(rows))
        from datetime import date

        result = await repo.get_eligible_for_planning(trip_date=date.today(), limit=10)
        assert len(result) == 2

    async def test_empty_result_returns_empty_list(self):
        """No available vehicles → empty list."""
        repo = _make_repo()
        repo._session.execute = AsyncMock(return_value=_mappings_result([]))
        from datetime import date

        result = await repo.get_eligible_for_planning(trip_date=date.today())
        assert result == []


# ---------------------------------------------------------------------------
# hard_delete_all
# ---------------------------------------------------------------------------


class TestAracRepoHardDeleteAll:
    async def test_returns_deleted_row_count(self):
        """hard_delete_all returns rowcount."""
        repo = _make_repo()
        delete_result = MagicMock()
        delete_result.rowcount = 5
        repo._session.execute = AsyncMock(return_value=delete_result)
        repo._session.flush = AsyncMock()
        result = await repo.hard_delete_all()
        assert result == 5

    async def test_propagates_exception(self):
        """hard_delete_all re-raises DB errors."""
        repo = _make_repo()
        repo._session.execute = AsyncMock(side_effect=RuntimeError("DB error"))
        repo._session.flush = AsyncMock()
        with pytest.raises(RuntimeError, match="DB error"):
            await repo.hard_delete_all()


# ---------------------------------------------------------------------------
# get_by_ids
# ---------------------------------------------------------------------------


class TestAracRepoGetByIds:
    async def test_empty_ids_returns_empty_dict(self):
        """get_by_ids with empty list returns {} without hitting DB."""
        repo = _make_repo()
        result = await repo.get_by_ids([])
        assert result == {}
        repo._session.execute.assert_not_called()

    async def test_returns_dict_keyed_by_id(self):
        """get_by_ids returns {id: Arac} mapping."""
        repo = _make_repo()
        arac1 = MagicMock()
        arac1.id = 1
        arac2 = MagicMock()
        arac2.id = 2
        repo._session.execute = AsyncMock(
            return_value=_scalars_all_result([arac1, arac2])
        )
        result = await repo.get_by_ids([1, 2])
        assert result[1] is arac1
        assert result[2] is arac2


# ---------------------------------------------------------------------------
# get_arac_repo (module-level factory)
# ---------------------------------------------------------------------------


class TestGetAracRepo:
    def test_session_arg_returns_new_instance(self):
        """Passing session always returns a fresh AracRepository."""
        from app.database.repositories.arac_repo import get_arac_repo

        mock_session = MagicMock()
        repo = get_arac_repo(session=mock_session)
        assert repo._session is mock_session

    def test_no_session_returns_singleton(self):
        """Calling twice without session returns same singleton."""
        import app.database.repositories.arac_repo as mod
        from app.database.repositories.arac_repo import get_arac_repo

        # Reset singleton for clean test
        mod._arac_repo = None
        repo1 = get_arac_repo()
        repo2 = get_arac_repo()
        assert repo1 is repo2
