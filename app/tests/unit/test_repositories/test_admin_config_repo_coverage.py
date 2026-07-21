"""
Coverage tests for app/database/repositories/admin_config_repo.py
Tests get_config, get_value, update_value, get_by_group, get_history,
and get_admin_config_repo singleton/session factory.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_repo(session=None):
    """Return an AdminConfigRepository with a mock session."""
    from v2.modules.admin_platform.infrastructure.repository import (
        AdminConfigRepository,
    )

    repo = AdminConfigRepository.__new__(AdminConfigRepository)
    repo.session = session or AsyncMock()
    return repo


def _fake_konfig(key="fuel_price", value="50", group="prices"):
    """Return a MagicMock mimicking SistemKonfig."""
    obj = MagicMock()
    obj.anahtar = key
    obj.deger = value
    obj.grup = group
    obj.guncelleyen_id = None
    return obj


def _execute_result_for(config_obj):
    """update_value now does SELECT ... FOR UPDATE via session.execute();
    build a mock `Result`-like object whose scalar_one_or_none() returns
    the given config (or None)."""
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = config_obj
    return mock_result


# ---------------------------------------------------------------------------
# get_config
# ---------------------------------------------------------------------------


async def test_get_config_found():
    """Session.get returns a config object → _to_dict-style dict."""
    session = AsyncMock()
    konfig = _fake_konfig("fuel_price", "55")
    session.get = AsyncMock(return_value=konfig)

    repo = _make_repo(session)
    # Patch _to_dict to return deterministic dict
    repo._to_dict = MagicMock(return_value={"anahtar": "fuel_price", "deger": "55"})

    result = await repo.get_config("fuel_price")
    assert result == {"anahtar": "fuel_price", "deger": "55"}
    session.get.assert_called_once()


async def test_get_config_not_found_returns_none():
    session = AsyncMock()
    session.get = AsyncMock(return_value=None)

    repo = _make_repo(session)
    result = await repo.get_config("nonexistent_key")
    assert result is None


# ---------------------------------------------------------------------------
# get_value
# ---------------------------------------------------------------------------


async def test_get_value_returns_deger():
    repo = _make_repo()
    repo.get_config = AsyncMock(return_value={"anahtar": "threshold", "deger": "0.05"})

    result = await repo.get_value("threshold")
    assert result == "0.05"


async def test_get_value_returns_default_when_not_found():
    repo = _make_repo()
    repo.get_config = AsyncMock(return_value=None)

    result = await repo.get_value("missing_key", default="fallback")
    assert result == "fallback"


async def test_get_value_default_is_none_by_default():
    repo = _make_repo()
    repo.get_config = AsyncMock(return_value=None)

    result = await repo.get_value("missing")
    assert result is None


# ---------------------------------------------------------------------------
# update_value
# ---------------------------------------------------------------------------


async def test_update_value_success():
    """Happy path: config found, value updated, history entry added."""
    session = AsyncMock()
    konfig = _fake_konfig("fuel_price", "50")
    session.execute = AsyncMock(return_value=_execute_result_for(konfig))
    session.add = MagicMock()
    session.refresh = AsyncMock()

    repo = _make_repo(session)
    repo._to_dict = MagicMock(return_value={"anahtar": "fuel_price", "deger": "60"})

    result = await repo.update_value(
        "fuel_price", "60", updated_by_id=1, reason="market change"
    )

    assert result == {"anahtar": "fuel_price", "deger": "60"}
    assert konfig.deger == "60"
    assert konfig.guncelleyen_id == 1
    session.add.assert_called_once()
    session.refresh.assert_called_once_with(konfig)


async def test_update_value_key_not_found_raises():
    session = AsyncMock()
    session.execute = AsyncMock(return_value=_execute_result_for(None))

    repo = _make_repo(session)

    with pytest.raises(ValueError, match="not found"):
        await repo.update_value("nonexistent", "value")


async def test_update_value_zero_updated_by_sets_none():
    """updated_by_id <= 0 → guncelleyen_id set to None (FK guard)."""
    session = AsyncMock()
    konfig = _fake_konfig("key", "old")
    session.execute = AsyncMock(return_value=_execute_result_for(konfig))
    session.add = MagicMock()
    session.refresh = AsyncMock()

    repo = _make_repo(session)
    repo._to_dict = MagicMock(return_value={"anahtar": "key", "deger": "new"})

    await repo.update_value("key", "new", updated_by_id=0)

    # When updated_by_id <= 0, history.guncelleyen_id should be None
    added_history = session.add.call_args[0][0]
    assert added_history.guncelleyen_id is None


async def test_update_value_no_reason():
    """reason=None is passed through."""
    session = AsyncMock()
    konfig = _fake_konfig("k", "v1")
    session.execute = AsyncMock(return_value=_execute_result_for(konfig))
    session.add = MagicMock()
    session.refresh = AsyncMock()

    repo = _make_repo(session)
    repo._to_dict = MagicMock(return_value={"anahtar": "k", "deger": "v2"})

    await repo.update_value("k", "v2")
    added = session.add.call_args[0][0]
    assert added.degisiklik_sebebi is None


# ---------------------------------------------------------------------------
# get_by_group
# ---------------------------------------------------------------------------


async def test_get_by_group_returns_list():
    session = AsyncMock()

    obj1 = _fake_konfig("k1", "v1", "prices")
    obj2 = _fake_konfig("k2", "v2", "prices")

    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = [obj1, obj2]
    session.execute = AsyncMock(return_value=mock_result)

    repo = _make_repo(session)
    repo._to_dict = MagicMock(
        side_effect=lambda o: {"anahtar": o.anahtar, "deger": o.deger}
    )

    results = await repo.get_by_group("prices")
    assert len(results) == 2
    assert results[0]["anahtar"] == "k1"


async def test_get_by_group_empty():
    session = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = []
    session.execute = AsyncMock(return_value=mock_result)

    repo = _make_repo(session)
    repo._to_dict = MagicMock(return_value={})

    results = await repo.get_by_group("unknown_group")
    assert results == []


# ---------------------------------------------------------------------------
# get_history
# ---------------------------------------------------------------------------


async def test_get_history_returns_dicts():
    """get_history uses inspect(KonfigGecmis).mapper column_attrs."""
    session = AsyncMock()

    fake_hist = MagicMock()
    fake_hist.id = 1
    fake_hist.anahtar = "fuel_price"
    fake_hist.eski_deger = "50"
    fake_hist.yeni_deger = "55"
    fake_hist.zaman = "2025-01-01"

    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = [fake_hist]
    session.execute = AsyncMock(return_value=mock_result)

    repo = _make_repo(session)

    # Mock inspect so we control column attrs
    mock_col = MagicMock()
    mock_col.key = "anahtar"

    with patch("v2.modules.admin_platform.infrastructure.repository.inspect") as mock_inspect:
        mock_mapper = MagicMock()
        mock_mapper.column_attrs = [mock_col]
        mock_inspect.return_value.mapper = mock_mapper

        results = await repo.get_history("fuel_price", limit=5)

    assert len(results) == 1
    assert "anahtar" in results[0]


async def test_get_history_empty():
    session = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = []
    session.execute = AsyncMock(return_value=mock_result)

    repo = _make_repo(session)

    with patch("v2.modules.admin_platform.infrastructure.repository.inspect") as mock_inspect:
        mock_inspect.return_value.mapper.column_attrs = []
        results = await repo.get_history("nonexistent_key")

    assert results == []


# ---------------------------------------------------------------------------
# get_admin_config_repo factory
# ---------------------------------------------------------------------------


def test_get_admin_config_repo_with_session_returns_new_instance():
    """Passing a session always creates a fresh repo, never reuses singleton."""
    import v2.modules.admin_platform.infrastructure.repository as mod

    mod._admin_config_repo = None  # reset singleton

    mock_session = AsyncMock()
    repo1 = mod.get_admin_config_repo(session=mock_session)
    repo2 = mod.get_admin_config_repo(session=mock_session)

    assert repo1 is not repo2
    assert repo1.session is mock_session


def test_get_admin_config_repo_singleton_without_session():
    """Without session, the same singleton is returned."""
    import v2.modules.admin_platform.infrastructure.repository as mod

    mod._admin_config_repo = None  # reset singleton

    repo1 = mod.get_admin_config_repo()
    repo2 = mod.get_admin_config_repo()

    assert repo1 is repo2

    mod._admin_config_repo = None  # cleanup
