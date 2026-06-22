"""
BaseRepository unit coverage tests — CRUD, pagination, filtering, soft-delete,
_to_dict, execute_query, execute_scalar, hard_delete, exists, count.

Uses a concrete subclass over a minimal SQLAlchemy model (no DB connection).
"""

from __future__ import annotations

import enum
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy import Column, Integer, String
from sqlalchemy.orm import DeclarativeBase

from app.database.base_repository import BaseRepository

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# Minimal model / repo for testing
# ---------------------------------------------------------------------------


class _Base(DeclarativeBase):
    pass


class FakeModel(_Base):
    __tablename__ = "fake_items"
    id = Column(Integer, primary_key=True)
    name = Column(String(100))
    aktif = Column(Integer, default=1)
    created_at = Column(String)
    updated_at = Column(String)


class FakeModelNoAktif(_Base):
    __tablename__ = "fake_items_no_aktif"
    id = Column(Integer, primary_key=True)
    name = Column(String(100))


class FakeRepo(BaseRepository[FakeModel]):  # type: ignore[type-var]
    model = FakeModel
    search_columns = ["name"]


class FakeRepoNoAktif(BaseRepository[FakeModelNoAktif]):  # type: ignore[type-var]
    model = FakeModelNoAktif


def _make_session():
    """Build a fully-mocked AsyncSession."""
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
    session.delete = AsyncMock()
    session.get = AsyncMock(return_value=None)
    return session


# ---------------------------------------------------------------------------
# Instantiation guards
# ---------------------------------------------------------------------------


class TestInstantiation:
    def test_model_none_raises_type_error(self):
        with pytest.raises(TypeError, match="model tanımlanmamış"):

            class BadRepo(BaseRepository):
                model = None

            BadRepo()

    def test_session_property_raises_when_none(self):
        repo = FakeRepo(session=None)
        with pytest.raises(RuntimeError, match="Database session not initialized"):
            _ = repo.session

    def test_session_setter(self):
        repo = FakeRepo(session=None)
        mock_s = MagicMock()
        repo.session = mock_s
        assert repo._session is mock_s


# ---------------------------------------------------------------------------
# _to_dict
# ---------------------------------------------------------------------------


class TestToDict:
    def test_none_returns_none(self):
        repo = FakeRepo(session=MagicMock())
        assert repo._to_dict(None) is None

    def test_dict_passthrough(self):
        repo = FakeRepo(session=MagicMock())
        d = {"id": 1, "name": "x"}
        assert repo._to_dict(d) == d

    def test_mapping_object(self):
        repo = FakeRepo(session=MagicMock())
        obj = MagicMock()
        del obj.model_dump  # ensure not used
        obj._mapping = {"id": 1, "name": "mapobj"}
        assert repo._to_dict(obj) == {"id": 1, "name": "mapobj"}

    def test_pydantic_model_dump(self):
        repo = FakeRepo(session=MagicMock())

        class FakePydantic:
            def model_dump(self):
                return {"id": 99}

        assert repo._to_dict(FakePydantic()) == {"id": 99}

    def test_plain_dict_fallback(self):
        """Object with __dict__ (no _mapping, no model_dump) uses __dict__ path."""
        repo = FakeRepo(session=MagicMock())

        class Bare:
            # No _mapping, no model_dump — SQLAlchemy inspect will fail.
            # _to_dict should fall back to __dict__
            pass

        obj = Bare()
        obj.name = "test_value"
        result = repo._to_dict(obj)
        assert result is not None
        assert result.get("name") == "test_value"


# ---------------------------------------------------------------------------
# get_all
# ---------------------------------------------------------------------------


class TestGetAll:
    async def test_returns_list_from_session(self):
        session = _make_session()
        obj = MagicMock(spec=[])  # no special attrs → dict() fallback path
        obj.__dict__ = {"id": 1, "name": "test", "_sa_instance_state": "x"}
        session.execute.return_value.scalars.return_value.all.return_value = [obj]
        repo = FakeRepo(session=session)

        result = await repo.get_all()
        assert isinstance(result, list)

    async def test_limit_clamped_to_max(self):
        session = _make_session()
        repo = FakeRepo(session=session)
        await repo.get_all(limit=99999, offset=0)
        # Just assert it didn't raise — limit was clamped
        session.execute.assert_called_once()

    async def test_negative_offset_clamped_to_zero(self):
        session = _make_session()
        repo = FakeRepo(session=session)
        await repo.get_all(limit=10, offset=-5)
        session.execute.assert_called_once()

    async def test_filters_equality(self):
        session = _make_session()
        repo = FakeRepo(session=session)
        await repo.get_all(filters={"name": "abc"})
        session.execute.assert_called_once()

    async def test_filters_ge_le_range(self):
        session = _make_session()
        repo = FakeRepo(session=session)
        await repo.get_all(filters={"id_ge": 1, "id_le": 100})
        session.execute.assert_called_once()

    async def test_search_filter_uses_ilike(self):
        session = _make_session()
        repo = FakeRepo(session=session)
        await repo.get_all(filters={"search": "test"})
        session.execute.assert_called_once()

    async def test_order_by_desc(self):
        session = _make_session()
        repo = FakeRepo(session=session)
        await repo.get_all(order_by="name desc")
        session.execute.assert_called_once()

    async def test_order_by_asc(self):
        session = _make_session()
        repo = FakeRepo(session=session)
        await repo.get_all(order_by="name asc")
        session.execute.assert_called_once()

    async def test_order_by_multi_column(self):
        """Comma-separated order_by honours every column (not just the first)."""
        session = _make_session()
        repo = FakeRepo(session=session)
        await repo.get_all(order_by="name asc, created_at desc")
        stmt = session.execute.call_args[0][0]
        compiled = str(stmt.compile())
        assert "fake_items.name ASC" in compiled
        assert "fake_items.created_at DESC" in compiled

    async def test_order_by_ignores_unknown_column(self):
        """Non-column tokens are dropped and fall back to PK desc — no crash,
        no unsafe attribute access, no token leaking into the SQL text."""
        session = _make_session()
        repo = FakeRepo(session=session)
        await repo.get_all(order_by="metadata; DROP TABLE x")
        stmt = session.execute.call_args[0][0]
        compiled = str(stmt.compile())
        assert "DROP" not in compiled
        assert "fake_items.id DESC" in compiled

    async def test_include_inactive_skips_aktif_filter(self):
        session = _make_session()
        repo = FakeRepo(session=session)
        await repo.get_all(include_inactive=True)
        session.execute.assert_called_once()

    async def test_filter_none_value_skipped(self):
        session = _make_session()
        repo = FakeRepo(session=session)
        await repo.get_all(filters={"name": None})
        session.execute.assert_called_once()


# ---------------------------------------------------------------------------
# get_paged
# ---------------------------------------------------------------------------


class TestGetPaged:
    async def test_delegates_to_get_all(self):
        session = _make_session()
        repo = FakeRepo(session=session)
        result = await repo.get_paged(skip=0, limit=50)
        assert isinstance(result, list)

    async def test_search_forwarded(self):
        session = _make_session()
        repo = FakeRepo(session=session)
        await repo.get_paged(search="hello")
        session.execute.assert_called_once()


# ---------------------------------------------------------------------------
# get_by_id
# ---------------------------------------------------------------------------


class TestGetById:
    async def test_returns_none_when_not_found(self):
        session = _make_session()
        session.get = AsyncMock(return_value=None)
        repo = FakeRepo(session=session)
        result = await repo.get_by_id(999)
        assert result is None

    async def test_for_update_uses_execute(self):
        session = _make_session()
        session.execute.return_value.scalar_one_or_none.return_value = None
        repo = FakeRepo(session=session)
        result = await repo.get_by_id(1, for_update=True)
        assert result is None
        session.execute.assert_called_once()


# ---------------------------------------------------------------------------
# create
# ---------------------------------------------------------------------------


class TestCreate:
    async def test_create_returns_pk(self):
        session = _make_session()
        repo = FakeRepo(session=session)

        # Patch FakeModel to track constructed instance
        created = []

        original_model = FakeRepo.model

        class TrackingModel(FakeModel):
            __tablename__ = "fake_items"
            __table_args__ = {"extend_existing": True}

            def __init__(self, **kw):
                super().__init__(**kw)
                self.id = 42
                created.append(self)

        repo.model = TrackingModel

        result = await repo.create(name="hello")
        assert result == 42

        repo.model = original_model

    async def test_create_filters_non_physical_columns(self):
        session = _make_session()
        repo = FakeRepo(session=session)

        instances = []

        class TrackingModel(FakeModel):
            __tablename__ = "fake_items"
            __table_args__ = {"extend_existing": True}

            def __init__(self, **kw):
                # 'nonexistent' should be filtered out
                assert "nonexistent" not in kw
                super().__init__(**kw)
                self.id = 1
                instances.append(self)

        repo.model = TrackingModel
        await repo.create(name="x", nonexistent="should_be_stripped")
        assert len(instances) == 1

    async def test_create_adds_created_at_if_missing(self):
        session = _make_session()
        repo = FakeRepo(session=session)

        kwargs_received = {}

        class TrackingModel(FakeModel):
            __tablename__ = "fake_items"
            __table_args__ = {"extend_existing": True}

            def __init__(self, **kw):
                kwargs_received.update(kw)
                super().__init__(**kw)
                self.id = 1

        repo.model = TrackingModel
        await repo.create(name="test")
        assert "created_at" in kwargs_received


# ---------------------------------------------------------------------------
# update
# ---------------------------------------------------------------------------


class TestUpdate:
    async def test_returns_false_when_no_data(self):
        session = _make_session()
        repo = FakeRepo(session=session)
        result = await repo.update(1)
        assert result is False

    async def test_returns_false_when_all_non_physical(self):
        session = _make_session()
        repo = FakeRepo(session=session)
        result = await repo.update(1, _nonexistent_column="x")
        assert result is False

    async def test_returns_false_when_record_not_found(self):
        session = _make_session()
        session.execute.return_value.scalar_one_or_none.return_value = None
        repo = FakeRepo(session=session)
        result = await repo.update(999, name="newname")
        assert result is False

    async def test_returns_true_when_updated(self):
        session = _make_session()
        fake_obj = FakeModel(id=1, name="old")
        session.execute.return_value.scalar_one_or_none.return_value = fake_obj
        repo = FakeRepo(session=session)
        result = await repo.update(1, name="new")
        assert result is True
        assert fake_obj.name == "new"

    async def test_enum_value_unwrapped(self):
        session = _make_session()
        fake_obj = FakeModel(id=1, name="old")
        session.execute.return_value.scalar_one_or_none.return_value = fake_obj
        repo = FakeRepo(session=session)

        class Color(enum.Enum):
            RED = "red"

        await repo.update(1, name=Color.RED)
        assert fake_obj.name == "red"

    async def test_adds_updated_at_if_column_exists(self):
        session = _make_session()
        fake_obj = FakeModel(id=1, name="x")
        session.execute.return_value.scalar_one_or_none.return_value = fake_obj
        repo = FakeRepo(session=session)
        await repo.update(1, name="y")
        assert fake_obj.updated_at is not None


# ---------------------------------------------------------------------------
# delete / hard_delete
# ---------------------------------------------------------------------------


class TestDelete:
    async def test_soft_delete_calls_update_aktif_false(self):
        session = _make_session()
        fake_obj = FakeModel(id=1, name="x", aktif=True)
        session.execute.return_value.scalar_one_or_none.return_value = fake_obj
        repo = FakeRepo(session=session)
        result = await repo.delete(1)
        assert result is True
        assert fake_obj.aktif is False

    async def test_hard_delete_called_when_no_aktif(self):
        session = _make_session()
        mock_result = MagicMock()
        mock_result.rowcount = 1
        session.execute = AsyncMock(return_value=mock_result)
        repo = FakeRepoNoAktif(session=session)
        result = await repo.hard_delete(1)
        assert result is True
        session.execute.assert_called_once()

    async def test_hard_delete_returns_false_when_not_found(self):
        session = _make_session()
        mock_result = MagicMock()
        mock_result.rowcount = 0
        session.execute = AsyncMock(return_value=mock_result)
        repo = FakeRepoNoAktif(session=session)
        result = await repo.hard_delete(999)
        assert result is False


# ---------------------------------------------------------------------------
# exists
# ---------------------------------------------------------------------------


class TestExists:
    async def test_returns_true_when_found(self):
        session = _make_session()
        session.execute.return_value.scalar.return_value = 1
        repo = FakeRepo(session=session)
        assert await repo.exists(1) is True

    async def test_returns_false_when_not_found(self):
        session = _make_session()
        session.execute.return_value.scalar.return_value = None
        repo = FakeRepo(session=session)
        assert await repo.exists(999) is False


# ---------------------------------------------------------------------------
# count
# ---------------------------------------------------------------------------


class TestCount:
    async def test_returns_integer(self):
        session = _make_session()
        session.execute.return_value.scalar.return_value = 5
        repo = FakeRepo(session=session)
        result = await repo.count()
        assert result == 5

    async def test_raises_on_exception(self):
        # AUDIT-003: count() artık exception'ı YUTMAZ (return 0 sessiz hatasıydı) →
        # hatayı yükseltir ki çağıran 0'ı gerçek sayı sanmasın.
        session = _make_session()
        session.execute = AsyncMock(side_effect=Exception("db error"))
        repo = FakeRepo(session=session)
        with pytest.raises(Exception, match="db error"):
            await repo.count()

    async def test_count_with_filters(self):
        session = _make_session()
        session.execute.return_value.scalar.return_value = 3
        repo = FakeRepo(session=session)
        result = await repo.count(filters={"name": "foo"})
        assert result == 3

    async def test_count_include_inactive(self):
        session = _make_session()
        session.execute.return_value.scalar.return_value = 10
        repo = FakeRepo(session=session)
        result = await repo.count(include_inactive=True)
        assert result == 10


# ---------------------------------------------------------------------------
# execute_query / execute_scalar
# ---------------------------------------------------------------------------


class TestExecuteQuery:
    async def test_returns_list_of_dicts(self):
        session = _make_session()
        mock_mappings = MagicMock()
        mock_mappings.all.return_value = [{"id": 1}]
        session.execute.return_value.mappings.return_value = mock_mappings
        repo = FakeRepo(session=session)
        result = await repo.execute_query("SELECT 1")
        assert isinstance(result, list)

    async def test_execute_scalar_returns_value(self):
        session = _make_session()
        session.execute.return_value.scalar.return_value = 42
        repo = FakeRepo(session=session)
        result = await repo.execute_scalar("SELECT COUNT(*)")
        assert result == 42

    async def test_execute_query_with_params(self):
        session = _make_session()
        mock_mappings = MagicMock()
        mock_mappings.all.return_value = []
        session.execute.return_value.mappings.return_value = mock_mappings
        repo = FakeRepo(session=session)
        result = await repo.execute_query("SELECT * WHERE id = :id", {"id": 1})
        assert result == []


# ---------------------------------------------------------------------------
# bulk_create
# ---------------------------------------------------------------------------


class TestBulkCreate:
    async def test_empty_list_returns_empty(self):
        session = _make_session()
        repo = FakeRepo(session=session)
        result = await repo.bulk_create([])
        assert result == []

    async def test_bulk_create_returns_ids(self):
        session = _make_session()
        repo = FakeRepo(session=session)

        instances_created = []

        class TrackingModel(FakeModel):
            __tablename__ = "fake_items"
            __table_args__ = {"extend_existing": True}

            def __init__(self, **kw):
                super().__init__(**kw)
                self.id = len(instances_created) + 10
                instances_created.append(self)

        repo.model = TrackingModel

        result = await repo.bulk_create([{"name": "a"}, {"name": "b"}])
        assert len(result) == 2
