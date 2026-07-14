from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from v2.modules.auth_rbac.application import user_service


@pytest.mark.asyncio
async def test_user_service_list_users():
    with patch(
        "v2.modules.auth_rbac.application.user_service.UnitOfWork"
    ) as mock_uow_cls:
        mock_uow = MagicMock()
        mock_uow.__aenter__.return_value = mock_uow
        mock_uow_cls.return_value = mock_uow

        mock_uow.kullanici_repo.get_all = AsyncMock(
            return_value=[{"id": 1, "email": "test@test.com"}]
        )

        users = await user_service.list_users()
        assert len(users) == 1
        assert users[0]["email"] == "test@test.com"
        mock_uow.kullanici_repo.get_all.assert_awaited_once_with(
            offset=0, limit=100, load_relations=["rol"]
        )


@pytest.mark.asyncio
async def test_user_service_create_user_email_exists():
    with patch(
        "v2.modules.auth_rbac.application.user_service.UnitOfWork"
    ) as mock_uow_cls:
        mock_uow = MagicMock()
        mock_uow.__aenter__.return_value = mock_uow
        mock_uow_cls.return_value = mock_uow

        mock_uow.kullanici_repo.get_by_email = AsyncMock(return_value={"id": 1})

        with pytest.raises(Exception) as exc:
            await user_service.create_user(
                {
                    "email": "exists@test.com",
                    "ad_soyad": "X",
                    "rol_id": 1,
                    "sifre": "Abcdef!12",
                },
                created_by_id=1,
            )
        assert "zaten kullanımda" in str(exc.value)


@pytest.mark.asyncio
async def test_user_service_create_user_success():
    with patch(
        "v2.modules.auth_rbac.application.user_service.UnitOfWork"
    ) as mock_uow_cls:
        mock_uow = MagicMock()
        mock_uow.__aenter__.return_value = mock_uow
        mock_uow_cls.return_value = mock_uow

        mock_uow.kullanici_repo.get_by_email = AsyncMock(return_value=None)
        mock_uow.kullanici_repo.create = AsyncMock(return_value=42)
        mock_uow.kullanici_repo.get_by_id = AsyncMock(
            return_value={"id": 42, "email": "new@test.com", "ad_soyad": "Yeni"}
        )
        mock_uow.commit = AsyncMock()

        created = await user_service.create_user(
            {
                "email": "new@test.com",
                "ad_soyad": "Yeni",
                "rol_id": 2,
                "sifre": "Abcdef!12",
            },
            created_by_id=99,
        )
        assert created["id"] == 42
        mock_uow.commit.assert_awaited_once()
        # The hashed password must be passed under sifre_hash, not sifre
        call_kwargs = mock_uow.kullanici_repo.create.await_args.kwargs
        assert "sifre_hash" in call_kwargs
        assert "sifre" not in call_kwargs
        assert call_kwargs["olusturan_id"] == 99


@pytest.mark.asyncio
async def test_user_service_delete_user():
    with patch(
        "v2.modules.auth_rbac.application.user_service.UnitOfWork"
    ) as mock_uow_cls:
        mock_uow = MagicMock()
        mock_uow.__aenter__.return_value = mock_uow
        mock_uow_cls.return_value = mock_uow

        mock_uow.commit = AsyncMock()
        mock_uow.kullanici_repo.delete = AsyncMock(return_value=True)

        success = await user_service.delete_user(1)
        assert success is True
        mock_uow.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_user_service_get_user():
    """Verify retrieval of a single user."""
    with patch(
        "v2.modules.auth_rbac.application.user_service.UnitOfWork"
    ) as mock_uow_cls:
        mock_uow = MagicMock()
        mock_uow.__aenter__.return_value = mock_uow
        mock_uow_cls.return_value = mock_uow

        mock_uow.kullanici_repo.get_by_id = AsyncMock(
            return_value={"id": 1, "email": "get@test.com"}
        )

        user = await user_service.get_user(1)
        assert user["id"] == 1
        assert user["email"] == "get@test.com"


@pytest.mark.asyncio
async def test_user_service_update_user():
    """Verify partial updates for a user."""
    with patch(
        "v2.modules.auth_rbac.application.user_service.UnitOfWork"
    ) as mock_uow_cls:
        mock_uow = MagicMock()
        mock_uow.__aenter__.return_value = mock_uow
        mock_uow_cls.return_value = mock_uow

        mock_uow.kullanici_repo.get_by_id = AsyncMock(
            side_effect=[
                {"id": 1, "ad_soyad": "Old Name"},
                {"id": 1, "ad_soyad": "New Name"},
            ]
        )
        mock_uow.kullanici_repo.update = AsyncMock(return_value=True)
        mock_uow.commit = AsyncMock()

        updated_user = await user_service.update_user(1, {"ad_soyad": "New Name"})
        assert updated_user["ad_soyad"] == "New Name"
        mock_uow.kullanici_repo.update.assert_called_with(1, ad_soyad="New Name")
        mock_uow.commit.assert_awaited_once()
