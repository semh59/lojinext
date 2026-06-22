"""
Additional coverage for app/database/base_repository.py.

Targets missing lines:
  57-63  — _get_session: session is None → acquires from pool
  83     — _to_dict: SQLAlchemy inspect path (mapper.column_attrs)
  87     — _to_dict: dict(obj) final fallback
  110-114 — get_all: load_relations with joinedload
  229-231 — bulk_create: exception branch
  258-260 — create: exception branch
  309-311 — update: exception branch
  318    — delete: no aktif → hard_delete path
  329-330 — hard_delete: exception re-raised
  356-363 — count: search + search_columns path
  368    — count: _ge range filter
  372-374 — count: _le range filter
  376-378 — count: equality filter in count
  399-403 — execute_query: exception branch
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy import Column, Integer, String
from sqlalchemy.orm import DeclarativeBase

from app.database.base_repository import BaseRepository

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# Minimal models / repos
# ---------------------------------------------------------------------------


class _Base(DeclarativeBase):
    pass


class FakeModel2(_Base):
    __tablename__ = "fake_items2"
    id = Column(Integer, primary_key=True)
    name = Column(String(100))
    aktif = Column(Integer, default=1)
    created_at = Column(String)
    updated_at = Column(String)


class FakeModelNoAktif2(_Base):
    __tablename__ = "fake_items_no_aktif2"
    id = Column(Integer, primary_key=True)
    name = Column(String(100))


class FakeRepo2(BaseRepository[FakeModel2]):  # type: ignore[type-var]
    model = FakeModel2
    search_columns = ["name"]


class FakeRepoNoAktif2(BaseRepository[FakeModelNoAktif2]):  # type: ignore[type-var]
    model = FakeModelNoAktif2


def _make_session():
    session = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = []
    mock_result.scalar_one_or_none.return_value = None
    mock_result.scalar.return_value = None
    mock_result.rowcount = 0
    session.execute = AsyncMock(return_value=mock_result)
    session.add = MagicMock()
    session.add_all = MagicMock()
    session.flush = AsyncMock()
    session.get = AsyncMock(return_value=None)
    return session


# ---------------------------------------------------------------------------
# _get_session: session is None → acquires from pool (lines 57-63)
# ---------------------------------------------------------------------------


async def test_get_session_uses_existing_session():
    """_get_session yields _session when it is not None."""
    session = _make_session()
    repo = FakeRepo2(session=session)

    async with repo._get_session() as s:
        assert s is session


async def test_get_session_acquires_from_pool_when_none():
    """_get_session creates a new session via AsyncSessionLocal when _session is None."""
    repo = FakeRepo2(session=None)

    fake_pool_session = _make_session()

    @asynccontextmanager
    async def _fake_local():
        yield fake_pool_session

    with patch("app.database.connection.AsyncSessionLocal", side_effect=_fake_local):
        async with repo._get_session() as s:
            assert s is fake_pool_session


# ---------------------------------------------------------------------------
# _to_dict: SQLAlchemy mapper path (line 83)
# ---------------------------------------------------------------------------


def test_to_dict_sqlalchemy_mapper_path():
    """_to_dict falls back to SQLAlchemy inspect when no _mapping/model_dump."""
    repo = FakeRepo2(session=MagicMock())

    # FakeModel2 is a real SQLAlchemy ORM class — inspect will work on its instances
    obj = FakeModel2(id=7, name="mapper_test")
    result = repo._to_dict(obj)
    assert result is not None
    assert result.get("id") == 7
    assert result.get("name") == "mapper_test"


# ---------------------------------------------------------------------------
# _to_dict: final fallback dict(obj) (line 87)
# ---------------------------------------------------------------------------


def test_to_dict_dict_fallback():
    """When SQLAlchemy inspect fails and no __dict__, falls back to dict(obj).

    We need an object with:
    - no _mapping attribute
    - no model_dump method
    - SQLAlchemy inspect raises (non-ORM class)
    - no __dict__ attribute (enforced by __slots__ without a base class that adds __dict__)
    - supports dict() via keys()+__getitem__
    """
    repo = FakeRepo2(session=MagicMock())

    # All slots defined here (no parent that adds __dict__), so hasattr(obj, '__dict__') = False
    class SlottedMapping:
        __slots__ = ()

        def keys(self):
            return ["a", "b"]

        def __getitem__(self, key):
            return {"a": 10, "b": 20}[key]

    obj = SlottedMapping()
    assert not hasattr(obj, "__dict__"), "test precondition: obj must have no __dict__"
    result = repo._to_dict(obj)
    assert result == {"a": 10, "b": 20}


# ---------------------------------------------------------------------------
# get_all: load_relations (lines 110-114)
# ---------------------------------------------------------------------------


async def test_get_all_with_load_relations_no_matching_attr():
    """load_relations with a relation that doesn't exist on model — no error."""
    session = _make_session()
    repo = FakeRepo2(session=session)
    # "nonexistent_relation" is not an attribute of FakeModel2
    result = await repo.get_all(load_relations=["nonexistent_relation"])
    assert isinstance(result, list)


async def test_get_all_with_valid_load_relation():
    """load_relations branch: when the relation attr exists on the model,
    joinedload is invoked and stmt.options is called.

    We patch the inner `joinedload` import and `stmt.options` to avoid
    a real ORM relationship being required.
    """
    session = _make_session()
    repo = FakeRepo2(session=session)

    sentinel_option = MagicMock()
    sentinel_stmt = MagicMock()
    sentinel_stmt.options.return_value = sentinel_stmt
    sentinel_stmt.where.return_value = sentinel_stmt
    sentinel_stmt.order_by.return_value = sentinel_stmt
    sentinel_stmt.limit.return_value = sentinel_stmt
    sentinel_stmt.offset.return_value = sentinel_stmt

    # Patch select to return our controllable stmt
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = []
    session.execute = AsyncMock(return_value=mock_result)

    with patch("app.database.base_repository.select", return_value=sentinel_stmt):
        with patch("sqlalchemy.orm.joinedload", return_value=sentinel_option):
            result = await repo.get_all(load_relations=["name"])

    assert isinstance(result, list)
    sentinel_stmt.options.assert_called_once_with(sentinel_option)


# ---------------------------------------------------------------------------
# bulk_create: exception branch (lines 229-231)
# ---------------------------------------------------------------------------


async def test_bulk_create_raises_on_exception():
    """bulk_create logs and re-raises on flush error."""
    session = _make_session()
    session.flush = AsyncMock(side_effect=Exception("flush failed"))
    repo = FakeRepo2(session=session)

    with pytest.raises(Exception, match="flush failed"):
        await repo.bulk_create([{"name": "trigger_error"}])


# ---------------------------------------------------------------------------
# create: exception branch (lines 258-260)
# ---------------------------------------------------------------------------


async def test_create_raises_on_exception():
    """create logs and re-raises when flush fails."""
    session = _make_session()
    session.flush = AsyncMock(side_effect=Exception("insert failed"))
    repo = FakeRepo2(session=session)

    with pytest.raises(Exception, match="insert failed"):
        await repo.create(name="bad")


# ---------------------------------------------------------------------------
# update: exception branch (lines 309-311)
# ---------------------------------------------------------------------------


async def test_update_raises_on_exception():
    """update logs and re-raises when flush fails after finding record."""
    session = _make_session()
    fake_obj = FakeModel2(id=1, name="x")
    session.execute.return_value.scalar_one_or_none.return_value = fake_obj
    session.flush = AsyncMock(side_effect=Exception("update conflict"))
    repo = FakeRepo2(session=session)

    with pytest.raises(Exception, match="update conflict"):
        await repo.update(1, name="y")


# ---------------------------------------------------------------------------
# delete: model has no aktif → hard_delete path (line 318)
# ---------------------------------------------------------------------------


async def test_delete_without_aktif_calls_hard_delete():
    """delete on a model with no 'aktif' column calls hard_delete."""
    session = _make_session()
    mock_result = MagicMock()
    mock_result.rowcount = 1
    session.execute = AsyncMock(return_value=mock_result)
    repo = FakeRepoNoAktif2(session=session)

    result = await repo.delete(1)
    assert result is True
    session.execute.assert_called_once()


# ---------------------------------------------------------------------------
# hard_delete: exception re-raised (lines 329-330)
# ---------------------------------------------------------------------------


async def test_hard_delete_reraises_exception():
    """hard_delete re-raises exceptions from execute."""
    session = _make_session()
    session.execute = AsyncMock(side_effect=Exception("delete constraint"))
    repo = FakeRepoNoAktif2(session=session)

    with pytest.raises(Exception, match="delete constraint"):
        await repo.hard_delete(1)


# ---------------------------------------------------------------------------
# count: search filter with search_columns (lines 356-363)
# ---------------------------------------------------------------------------


async def test_count_with_search_filter():
    """count applies ilike search when search_columns is set."""
    session = _make_session()
    session.execute.return_value.scalar.return_value = 3
    repo = FakeRepo2(session=session)

    result = await repo.count(filters={"search": "test"})
    assert result == 3
    session.execute.assert_called_once()


async def test_count_with_ge_filter():
    """count applies >= range filter."""
    session = _make_session()
    session.execute.return_value.scalar.return_value = 5
    repo = FakeRepo2(session=session)

    result = await repo.count(filters={"id_ge": 10})
    assert result == 5


async def test_count_with_le_filter():
    """count applies <= range filter."""
    session = _make_session()
    session.execute.return_value.scalar.return_value = 7
    repo = FakeRepo2(session=session)

    result = await repo.count(filters={"id_le": 100})
    assert result == 7


async def test_count_with_equality_filter():
    """count applies equality filter for known model column."""
    session = _make_session()
    session.execute.return_value.scalar.return_value = 2
    repo = FakeRepo2(session=session)

    result = await repo.count(filters={"name": "specific_name"})
    assert result == 2


async def test_count_with_none_value_filter_skipped():
    """count skips filter entries with None value."""
    session = _make_session()
    session.execute.return_value.scalar.return_value = 4
    repo = FakeRepo2(session=session)

    result = await repo.count(filters={"name": None})
    assert result == 4


# ---------------------------------------------------------------------------
# execute_query: exception branch (lines 399-403)
# ---------------------------------------------------------------------------


async def test_execute_query_raises_on_error():
    """execute_query logs and re-raises on exception."""
    session = _make_session()
    session.execute = AsyncMock(side_effect=Exception("bad sql"))
    repo = FakeRepo2(session=session)

    with pytest.raises(Exception, match="bad sql"):
        await repo.execute_query("SELECT bad syntax")
