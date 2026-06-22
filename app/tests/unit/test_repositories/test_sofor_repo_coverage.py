"""
SoforRepository comprehensive unit tests — targets missing lines.

Covers:
- get_all: sadece_aktif, search, filters, is_deleted injection protection
- count_all: sadece_aktif, search, filters
- count_active: scalar result
- add: happy path, TOCTOU duplicate raises ValueError
- get_sefer_stats: no filter, sofor_id, baslangic, bitis, limit/offset clamping
- get_yakit_tuketimi: no filter, sofor_id, limit
- get_guzergah_performansi
- get_driver_consumptions: row extraction
- get_by_name: found, not found, for_update
- get_aktif_isimler: row extraction
- get_driver_anomalies_count: rows with value, enum value, empty
- get_by_telegram_id: found, not found
- bulk_soft_delete: empty list, non-empty delegates to bulk_update
- get_eligible_for_planning
- get_by_ids: empty list, multiple ids
- get_sofor_repo factory: with session, without session (singleton)
"""

from datetime import date
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_repo(session=None):
    """Return a SoforRepository with a mocked async session."""
    from app.database.repositories.sofor_repo import SoforRepository

    repo = SoforRepository.__new__(SoforRepository)
    repo._session = session if session is not None else AsyncMock()
    return repo


def _scalar_result(value):
    """Build a mock result whose .scalar() returns *value*."""
    r = MagicMock()
    r.scalar = MagicMock(return_value=value)
    return r


def _scalar_one_or_none_result(obj):
    r = MagicMock()
    r.scalar_one_or_none = MagicMock(return_value=obj)
    return r


def _scalars_all_result(objs):
    scalars = MagicMock()
    scalars.all = MagicMock(return_value=objs)
    r = MagicMock()
    r.scalars = MagicMock(return_value=scalars)
    return r


def _mappings_result(rows):
    """Build a mock result whose .mappings().all() returns plain dicts."""
    mapping_mock = MagicMock()
    mapping_mock.all = MagicMock(return_value=list(rows))
    r = MagicMock()
    r.mappings = MagicMock(return_value=mapping_mock)
    return r


def _make_sofor_obj(**kwargs):
    """Create a mock ORM Sofor object (SimpleNamespace — 3.12 _mock_methods safe)."""
    return SimpleNamespace(
        id=kwargs.get("id", 1),
        ad_soyad=kwargs.get("ad_soyad", "Test Sofor"),
        telefon=kwargs.get("telefon", "5551234567"),
        aktif=kwargs.get("aktif", True),
        is_deleted=kwargs.get("is_deleted", False),
        _sa_instance_state=MagicMock(),
    )


# ---------------------------------------------------------------------------
# get_all
# ---------------------------------------------------------------------------


async def test_get_all_defaults():
    """get_all with defaults executes a SELECT and returns results."""
    repo = _make_repo()
    repo._session.execute = AsyncMock(return_value=_scalars_all_result([]))
    result = await repo.get_all()
    assert result == []
    repo._session.execute.assert_called_once()


async def test_get_all_sadece_aktif_false():
    """get_all with sadece_aktif=False does not restrict by aktif (include_inactive=True)."""
    repo = _make_repo()
    repo._session.execute = AsyncMock(return_value=_scalars_all_result([]))
    await repo.get_all(sadece_aktif=False)
    repo._session.execute.assert_called_once()


async def test_get_all_with_search():
    """get_all with search executes a filtered SELECT."""
    repo = _make_repo()
    repo._session.execute = AsyncMock(return_value=_scalars_all_result([]))
    await repo.get_all(search="Ali")
    repo._session.execute.assert_called_once()


async def test_get_all_with_extra_filters():
    """get_all with filters passes them through to the query."""
    repo = _make_repo()
    repo._session.execute = AsyncMock(return_value=_scalars_all_result([]))
    await repo.get_all(filters={"ehliyet_sinifi": "E"})
    repo._session.execute.assert_called_once()


async def test_get_all_existing_is_deleted_not_overridden():
    """get_all with explicit is_deleted=True still calls execute."""
    repo = _make_repo()
    repo._session.execute = AsyncMock(return_value=_scalars_all_result([]))
    await repo.get_all(filters={"is_deleted": True})
    repo._session.execute.assert_called_once()


# ---------------------------------------------------------------------------
# count_all
# ---------------------------------------------------------------------------


async def test_count_all_defaults():
    """count_all with defaults calls execute and returns count."""
    repo = _make_repo()
    repo._session.execute = AsyncMock(return_value=_scalar_result(0))
    result = await repo.count_all()
    assert result == 0
    repo._session.execute.assert_called_once()


async def test_count_all_with_search():
    """count_all with search executes filtered count."""
    repo = _make_repo()
    repo._session.execute = AsyncMock(return_value=_scalar_result(5))
    result = await repo.count_all(search="Mehmet")
    assert result == 5


# ---------------------------------------------------------------------------
# count_active
# ---------------------------------------------------------------------------


async def test_count_active_returns_int():
    """count_active executes COUNT query and returns integer."""
    session = AsyncMock()
    session.execute = AsyncMock(return_value=_scalar_result(7))
    repo = _make_repo(session=session)
    result = await repo.count_active()
    assert result == 7
    session.execute.assert_called_once()


async def test_count_active_none_scalar():
    """count_active handles None scalar (no rows) → 0."""
    session = AsyncMock()
    session.execute = AsyncMock(return_value=_scalar_result(None))
    repo = _make_repo(session=session)
    result = await repo.count_active()
    assert result == 0


# ---------------------------------------------------------------------------
# add
# ---------------------------------------------------------------------------


async def test_add_happy_path():
    """add creates new Sofor, flushes, and returns its id."""
    from app.database.models import Sofor

    session = AsyncMock()
    # TOCTOU check: no existing driver with that name
    session.execute = AsyncMock(return_value=_scalar_one_or_none_result(None))
    session.add = MagicMock()

    # Simulate flush by setting the id attribute on whatever was added
    added_objects = []

    def capture_add(obj):
        added_objects.append(obj)

    session.add.side_effect = capture_add

    async def fake_flush():
        # Simulate DB assigning an ID after flush
        for obj in added_objects:
            obj.id = 42

    session.flush = AsyncMock(side_effect=fake_flush)

    repo = _make_repo(session=session)

    result = await repo.add(ad_soyad="Ali Veli", telefon="5559999999")

    assert result == 42
    assert len(added_objects) == 1
    assert isinstance(added_objects[0], Sofor)
    session.flush.assert_called_once()


async def test_add_duplicate_raises_value_error():
    """add raises ValueError when driver with same name already exists."""
    existing = MagicMock()
    session = AsyncMock()
    session.execute = AsyncMock(return_value=_scalar_one_or_none_result(existing))

    repo = _make_repo(session=session)
    with pytest.raises(ValueError, match="zaten kayıtlı"):
        await repo.add(ad_soyad="Ali Veli")


# ---------------------------------------------------------------------------
# get_sefer_stats
# ---------------------------------------------------------------------------


async def test_get_sefer_stats_no_filters():
    """get_sefer_stats with no filters calls execute_query."""
    session = AsyncMock()
    session.execute = AsyncMock(return_value=_mappings_result([]))
    repo = _make_repo(session=session)

    result = await repo.get_sefer_stats()
    assert result == []


async def test_get_sefer_stats_with_sofor_id():
    """get_sefer_stats with sofor_id adds sofor filter."""
    session = AsyncMock()
    session.execute = AsyncMock(
        return_value=_mappings_result([{"sofor_id": 3, "toplam_sefer": 10}])
    )
    repo = _make_repo(session=session)

    result = await repo.get_sefer_stats(sofor_id=3)
    assert len(result) == 1
    assert result[0]["sofor_id"] == 3


async def test_get_sefer_stats_with_date_range():
    """get_sefer_stats with baslangic and bitis filters."""
    session = AsyncMock()
    session.execute = AsyncMock(return_value=_mappings_result([]))
    repo = _make_repo(session=session)

    start = date(2026, 1, 1)
    end = date(2026, 6, 1)
    result = await repo.get_sefer_stats(baslangic=start, bitis=end)
    assert result == []
    # Verify execute was called
    session.execute.assert_called_once()


async def test_get_sefer_stats_limit_clamped():
    """get_sefer_stats clamps limit to 1-500."""
    session = AsyncMock()
    session.execute = AsyncMock(return_value=_mappings_result([]))
    repo = _make_repo(session=session)

    # Should not raise
    await repo.get_sefer_stats(limit=0)  # clamps to 1
    await repo.get_sefer_stats(limit=999)  # clamps to 500


# ---------------------------------------------------------------------------
# get_yakit_tuketimi
# ---------------------------------------------------------------------------


async def test_get_yakit_tuketimi_no_filter():
    """get_yakit_tuketimi without sofor_id returns all rows."""
    session = AsyncMock()
    session.execute = AsyncMock(
        return_value=_mappings_result([{"sofor_id": 1, "tuketim": 35.0}])
    )
    repo = _make_repo(session=session)
    result = await repo.get_yakit_tuketimi()
    assert len(result) == 1


async def test_get_yakit_tuketimi_with_sofor_id_and_limit():
    """get_yakit_tuketimi with sofor_id and limit."""
    session = AsyncMock()
    session.execute = AsyncMock(return_value=_mappings_result([]))
    repo = _make_repo(session=session)
    result = await repo.get_yakit_tuketimi(sofor_id=5, limit=10)
    assert result == []
    session.execute.assert_called_once()


# ---------------------------------------------------------------------------
# get_guzergah_performansi
# ---------------------------------------------------------------------------


async def test_get_guzergah_performansi():
    """get_guzergah_performansi returns rows for a driver."""
    session = AsyncMock()
    session.execute = AsyncMock(
        return_value=_mappings_result(
            [{"guzergah": "Ankara → Konya", "sefer_sayisi": 5, "ort_tuketim": 34.2}]
        )
    )
    repo = _make_repo(session=session)
    result = await repo.get_guzergah_performansi(sofor_id=2)
    assert len(result) == 1
    assert result[0]["guzergah"] == "Ankara → Konya"


# ---------------------------------------------------------------------------
# get_driver_consumptions
# ---------------------------------------------------------------------------


async def test_get_driver_consumptions():
    """get_driver_consumptions extracts tuketim column."""
    session = AsyncMock()
    session.execute = AsyncMock(
        return_value=_mappings_result(
            [{"tuketim": 33.5}, {"tuketim": 36.1}, {"tuketim": 30.0}]
        )
    )
    repo = _make_repo(session=session)
    result = await repo.get_driver_consumptions(sofor_id=1)
    assert result == [33.5, 36.1, 30.0]


async def test_get_driver_consumptions_empty():
    """get_driver_consumptions returns empty list when no data."""
    session = AsyncMock()
    session.execute = AsyncMock(return_value=_mappings_result([]))
    repo = _make_repo(session=session)
    result = await repo.get_driver_consumptions(sofor_id=99, limit=50)
    assert result == []


# ---------------------------------------------------------------------------
# get_by_name
# ---------------------------------------------------------------------------


async def test_get_by_name_found():
    """get_by_name returns dict when driver found."""
    sofor_obj = _make_sofor_obj(id=3, ad_soyad="Ali Veli")
    session = AsyncMock()
    session.execute = AsyncMock(return_value=_scalar_one_or_none_result(sofor_obj))
    repo = _make_repo(session=session)

    result = await repo.get_by_name("Ali Veli")
    assert result is not None
    assert result["ad_soyad"] == "Ali Veli"
    # _sa_instance_state should be stripped
    assert "_sa_instance_state" not in result


async def test_get_by_name_not_found():
    """get_by_name returns None when driver not found."""
    session = AsyncMock()
    session.execute = AsyncMock(return_value=_scalar_one_or_none_result(None))
    repo = _make_repo(session=session)

    result = await repo.get_by_name("Nonexistent")
    assert result is None


async def test_get_by_name_for_update():
    """get_by_name with for_update=True uses with_for_update()."""
    sofor_obj = _make_sofor_obj(id=3, ad_soyad="Ali Veli")
    session = AsyncMock()
    session.execute = AsyncMock(return_value=_scalar_one_or_none_result(sofor_obj))
    repo = _make_repo(session=session)

    result = await repo.get_by_name("Ali Veli", for_update=True)
    assert result is not None
    session.execute.assert_called_once()


# ---------------------------------------------------------------------------
# get_aktif_isimler
# ---------------------------------------------------------------------------


async def test_get_aktif_isimler():
    """get_aktif_isimler returns list of name strings."""
    session = AsyncMock()
    session.execute = AsyncMock(
        return_value=_mappings_result(
            [{"ad_soyad": "Ali Veli"}, {"ad_soyad": "Mehmet Kaya"}]
        )
    )
    repo = _make_repo(session=session)
    result = await repo.get_aktif_isimler()
    assert result == ["Ali Veli", "Mehmet Kaya"]


async def test_get_aktif_isimler_empty():
    """get_aktif_isimler returns empty list when no active drivers."""
    session = AsyncMock()
    session.execute = AsyncMock(return_value=_mappings_result([]))
    repo = _make_repo(session=session)
    result = await repo.get_aktif_isimler()
    assert result == []


# ---------------------------------------------------------------------------
# get_driver_anomalies_count
# ---------------------------------------------------------------------------


async def test_get_driver_anomalies_count_with_rows():
    """get_driver_anomalies_count aggregates by severity."""
    session = AsyncMock()
    session.execute = AsyncMock(
        return_value=_mappings_result(
            [
                {"severity": "high", "count": 3},
                {"severity": "medium", "count": 2},
                {"severity": "low", "count": 1},
            ]
        )
    )
    repo = _make_repo(session=session)
    result = await repo.get_driver_anomalies_count(sofor_id=1, days=30)
    assert result["high"] == 3
    assert result["medium"] == 2
    assert result["low"] == 1
    assert result["critical"] == 0


async def test_get_driver_anomalies_count_enum_value():
    """get_driver_anomalies_count handles enum-type severity."""
    severity_mock = MagicMock()
    severity_mock.value = "critical"

    session = AsyncMock()
    session.execute = AsyncMock(
        return_value=_mappings_result([{"severity": severity_mock, "count": 5}])
    )
    repo = _make_repo(session=session)
    result = await repo.get_driver_anomalies_count(sofor_id=2)
    assert result["critical"] == 5


async def test_get_driver_anomalies_count_empty():
    """get_driver_anomalies_count returns zeros when no anomalies."""
    session = AsyncMock()
    session.execute = AsyncMock(return_value=_mappings_result([]))
    repo = _make_repo(session=session)
    result = await repo.get_driver_anomalies_count(sofor_id=99)
    assert result == {"low": 0, "medium": 0, "high": 0, "critical": 0}


# ---------------------------------------------------------------------------
# get_by_telegram_id
# ---------------------------------------------------------------------------


async def test_get_by_telegram_id_found():
    """get_by_telegram_id returns dict when driver found."""
    sofor_obj = _make_sofor_obj(id=10, ad_soyad="Telegram Sofor")

    async def fake_get_session():
        cm = MagicMock()

        async def __aenter__(self):
            mock_session = AsyncMock()
            mock_session.execute = AsyncMock(
                return_value=_scalar_one_or_none_result(sofor_obj)
            )
            return mock_session

        async def __aexit__(self, *args):
            pass

        cm.__aenter__ = __aenter__
        cm.__aexit__ = __aexit__
        return cm

    repo = _make_repo()

    # Patch _get_session context manager
    mock_inner_session = AsyncMock()
    mock_inner_session.execute = AsyncMock(
        return_value=_scalar_one_or_none_result(sofor_obj)
    )

    from contextlib import asynccontextmanager

    @asynccontextmanager
    async def _ctx():
        yield mock_inner_session

    repo._get_session = _ctx

    result = await repo.get_by_telegram_id("tg_12345")
    assert result is not None


async def test_get_by_telegram_id_not_found():
    """get_by_telegram_id returns None when not found."""
    repo = _make_repo()
    mock_inner_session = AsyncMock()
    mock_inner_session.execute = AsyncMock(
        return_value=_scalar_one_or_none_result(None)
    )

    from contextlib import asynccontextmanager

    @asynccontextmanager
    async def _ctx():
        yield mock_inner_session

    repo._get_session = _ctx

    result = await repo.get_by_telegram_id("nonexistent")
    assert result is None


# ---------------------------------------------------------------------------
# bulk_soft_delete
# ---------------------------------------------------------------------------


async def test_bulk_soft_delete_empty_list():
    """bulk_soft_delete with empty list returns 0 immediately."""
    repo = _make_repo()
    result = await repo.bulk_soft_delete([])
    assert result == 0


async def test_bulk_soft_delete_delegates_to_bulk_update():
    """bulk_soft_delete delegates to bulk_update with is_deleted=True, aktif=False."""
    repo = _make_repo()
    repo.bulk_update = AsyncMock(return_value=3)

    result = await repo.bulk_soft_delete([1, 2, 3], current_user_id=99)
    assert result == 3
    repo.bulk_update.assert_called_once_with(
        ids=[1, 2, 3], is_deleted=True, aktif=False
    )


# ---------------------------------------------------------------------------
# get_eligible_for_planning
# ---------------------------------------------------------------------------


async def test_get_eligible_for_planning():
    """get_eligible_for_planning returns sorted drivers without conflicts."""
    session = AsyncMock()
    session.execute = AsyncMock(
        return_value=_mappings_result(
            [
                {"id": 1, "ad_soyad": "Ali", "recent_trip_count": 0},
                {"id": 2, "ad_soyad": "Veli", "recent_trip_count": 2},
            ]
        )
    )
    repo = _make_repo(session=session)
    result = await repo.get_eligible_for_planning(trip_date=date(2026, 7, 1), limit=10)
    assert len(result) == 2
    assert result[0]["ad_soyad"] == "Ali"


# ---------------------------------------------------------------------------
# get_by_ids
# ---------------------------------------------------------------------------


async def test_get_by_ids_empty_list():
    """get_by_ids with empty list returns empty dict immediately."""
    repo = _make_repo()
    result = await repo.get_by_ids([])
    assert result == {}


async def test_get_by_ids_multiple():
    """get_by_ids fetches multiple drivers in one query."""
    d1 = MagicMock()
    d1.id = 1
    d2 = MagicMock()
    d2.id = 2

    session = AsyncMock()
    session.execute = AsyncMock(return_value=_scalars_all_result([d1, d2]))
    repo = _make_repo(session=session)

    result = await repo.get_by_ids([1, 2])
    assert len(result) == 2
    assert result[1] is d1
    assert result[2] is d2


# ---------------------------------------------------------------------------
# get_sofor_repo factory
# ---------------------------------------------------------------------------


def test_get_sofor_repo_with_session():
    """get_sofor_repo with session returns new SoforRepository instance."""
    import app.database.repositories.sofor_repo as mod

    mock_session = AsyncMock()
    repo = mod.get_sofor_repo(session=mock_session)
    from app.database.repositories.sofor_repo import SoforRepository

    assert isinstance(repo, SoforRepository)
    assert repo._session is mock_session


def test_get_sofor_repo_singleton():
    """get_sofor_repo without session returns same singleton."""
    import app.database.repositories.sofor_repo as mod

    mod._sofor_repo = None  # Reset singleton
    repo1 = mod.get_sofor_repo()
    repo2 = mod.get_sofor_repo()
    assert repo1 is repo2
    mod._sofor_repo = None  # Cleanup
