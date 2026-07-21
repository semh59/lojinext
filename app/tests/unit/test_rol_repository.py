"""Tests for RolRepository compliance with repository pattern."""

from unittest.mock import AsyncMock, MagicMock

import pytest

pytestmark = pytest.mark.asyncio


async def test_rol_repo_inherits_from_base_repository():
    """RolRepository must be a subclass of BaseRepository."""
    from app.database.base_repository import BaseRepository
    from v2.modules.auth_rbac.infrastructure.rol_repository import RolRepository

    assert issubclass(RolRepository, BaseRepository)


async def test_uow_has_rol_repo():
    """UoW must expose rol_repo as a lazy descriptor."""
    from app.database.unit_of_work import UnitOfWork

    # The lazy descriptor (_Lazy) is stored on the class itself; assert it is a
    # descriptor (has __get__) rather than asserting its concrete type.
    descriptor = UnitOfWork.__dict__.get("rol_repo")
    assert descriptor is not None and hasattr(descriptor, "__get__"), (
        "UnitOfWork must have a 'rol_repo' lazy descriptor"
    )


async def test_rol_repo_create_uses_flush_not_commit():
    """create() must call flush, not commit."""
    from v2.modules.auth_rbac.infrastructure.rol_repository import RolRepository

    mock_session = MagicMock()
    mock_session.execute = AsyncMock()
    mock_session.flush = AsyncMock()
    mock_session.commit = AsyncMock()
    mock_session.add = MagicMock()
    mock_session.refresh = AsyncMock()

    # No existing role
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_session.execute.return_value = mock_result

    repo = RolRepository(mock_session)
    await repo.create(ad="test_rol", yetkiler=["read"])

    mock_session.flush.assert_called_once()
    mock_session.commit.assert_not_called()


async def test_rol_repo_create_raises_on_duplicate():
    """create() raises ValueError when role name already exists."""
    from v2.modules.auth_rbac.infrastructure.rol_repository import RolRepository
    from v2.modules.auth_rbac.public import Rol

    mock_session = MagicMock()
    mock_session.execute = AsyncMock()

    existing_role = MagicMock(spec=Rol)
    existing_role.ad = "admin"
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = existing_role
    mock_session.execute.return_value = mock_result

    repo = RolRepository(mock_session)
    with pytest.raises(ValueError, match="zaten var"):
        await repo.create(ad="admin", yetkiler=["read"])


async def test_rol_repo_update_uses_flush_not_commit():
    """update() değişiklikleri uygular, flush eder, commit ETMEZ."""
    from v2.modules.auth_rbac.infrastructure.rol_repository import RolRepository
    from v2.modules.auth_rbac.public import Rol

    role = MagicMock(spec=Rol)
    role.id = 5
    role.ad = "eski_ad"
    role.yetkiler = {"sefer:read": True}

    mock_session = MagicMock()
    mock_session.get = AsyncMock(return_value=role)
    mock_session.flush = AsyncMock()
    mock_session.commit = AsyncMock()
    # get_by_name (ad değiştiği için) → çakışma yok
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_session.execute = AsyncMock(return_value=mock_result)

    repo = RolRepository(mock_session)
    updated = await repo.update(5, ad="yeni_ad", yetkiler={"sefer:write": True})

    assert updated is role
    assert role.ad == "yeni_ad"
    assert role.yetkiler == {"sefer:write": True}
    mock_session.flush.assert_called_once()
    mock_session.commit.assert_not_called()


async def test_rol_repo_update_returns_none_when_missing():
    """update() rol yoksa None döner."""
    from v2.modules.auth_rbac.infrastructure.rol_repository import RolRepository

    mock_session = MagicMock()
    mock_session.get = AsyncMock(return_value=None)
    repo = RolRepository(mock_session)
    assert await repo.update(999, ad="x", yetkiler={"a": True}) is None


async def test_rol_repo_update_raises_on_name_clash():
    """update() farklı bir role ait ada çekilirse ValueError fırlatır."""
    from v2.modules.auth_rbac.infrastructure.rol_repository import RolRepository
    from v2.modules.auth_rbac.public import Rol

    role = MagicMock(spec=Rol)
    role.id = 5
    role.ad = "eski_ad"
    role.yetkiler = {}

    clash = MagicMock(spec=Rol)
    clash.id = 9  # başka bir rol aynı adı kullanıyor

    mock_session = MagicMock()
    mock_session.get = AsyncMock(return_value=role)
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = clash
    mock_session.execute = AsyncMock(return_value=mock_result)
    mock_session.flush = AsyncMock()

    repo = RolRepository(mock_session)
    with pytest.raises(ValueError, match="zaten var"):
        await repo.update(5, ad="cakisan_ad", yetkiler={"a": True})


async def test_rol_repo_delete_calls_session_delete():
    """delete() session.delete + flush çağırır, commit ETMEZ."""
    from v2.modules.auth_rbac.infrastructure.rol_repository import RolRepository
    from v2.modules.auth_rbac.public import Rol

    role = MagicMock(spec=Rol)
    role.id = 7

    mock_session = MagicMock()
    mock_session.get = AsyncMock(return_value=role)
    mock_session.delete = AsyncMock()
    mock_session.flush = AsyncMock()
    mock_session.commit = AsyncMock()

    repo = RolRepository(mock_session)
    result = await repo.delete(7)

    assert result is True
    mock_session.delete.assert_called_once_with(role)
    mock_session.flush.assert_called_once()
    mock_session.commit.assert_not_called()


async def test_rol_repo_delete_returns_false_when_missing():
    """delete() rol yoksa False döner."""
    from v2.modules.auth_rbac.infrastructure.rol_repository import RolRepository

    mock_session = MagicMock()
    mock_session.get = AsyncMock(return_value=None)
    mock_session.delete = AsyncMock()
    repo = RolRepository(mock_session)

    assert await repo.delete(999) is False
    mock_session.delete.assert_not_called()


async def test_rol_repo_count_users_with_role():
    """count_users_with_role() scalar sayıyı int döndürür."""
    from v2.modules.auth_rbac.infrastructure.rol_repository import RolRepository

    mock_session = MagicMock()
    mock_result = MagicMock()
    mock_result.scalar.return_value = 3
    mock_session.execute = AsyncMock(return_value=mock_result)

    repo = RolRepository(mock_session)
    assert await repo.count_users_with_role(5) == 3
