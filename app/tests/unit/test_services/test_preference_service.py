from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.services.preference_service import PreferenceService
from app.database.models import KullaniciAyari

pytestmark = pytest.mark.unit


@pytest.fixture
def mock_uow():
    uow = MagicMock()
    uow.__aenter__ = AsyncMock(return_value=uow)
    uow.__aexit__ = AsyncMock(return_value=None)
    uow.setting_repo = MagicMock()
    # The service now creates/fetches the ORM row via the session directly
    # (session.add is sync; session.get is awaited).
    uow.session = MagicMock()
    uow.session.add = MagicMock()
    uow.commit = AsyncMock()
    return uow


class TestPreferenceService:
    async def test_get_preferences_happy_path(self, mock_uow):
        mock_setting = MagicMock(spec=KullaniciAyari)
        mock_setting.deger = "dark"
        mock_uow.setting_repo.get_user_settings = AsyncMock(return_value=[mock_setting])

        with patch("app.core.services.preference_service.UnitOfWork") as MockUoW:
            MockUoW.return_value.__aenter__.return_value = mock_uow
            service = PreferenceService()
            result = await service.get_preferences(user_id=1, modul="dashboard")
            assert len(result) == 1
            assert result[0].deger == "dark"

    async def test_get_preferences_not_found(self, mock_uow):
        mock_uow.setting_repo.get_user_settings = AsyncMock(return_value=[])

        with patch("app.core.services.preference_service.UnitOfWork") as MockUoW:
            MockUoW.return_value.__aenter__.return_value = mock_uow
            service = PreferenceService()
            result = await service.get_preferences(user_id=1, modul="trips")
            assert result == []

    async def test_save_preference_happy_path(self, mock_uow):
        mock_uow.setting_repo.get_user_settings = AsyncMock(return_value=[])
        mock_pref = MagicMock(spec=KullaniciAyari)
        mock_pref.id = 1
        mock_uow.session.get = AsyncMock(return_value=mock_pref)
        mock_uow.commit = AsyncMock()

        with patch("app.core.services.preference_service.UnitOfWork") as MockUoW:
            MockUoW.return_value.__aenter__.return_value = mock_uow
            service = PreferenceService()
            result = await service.save_preference(
                user_id=1,
                modul="dashboard",
                ayar_tipi="filter",
                deger={"theme": "dark"},
            )
            assert result is not None
            mock_uow.session.add.assert_called()

    async def test_save_preference_with_existing(self, mock_uow):
        existing = MagicMock(spec=KullaniciAyari)
        existing.id = 1
        mock_uow.setting_repo.get_user_settings = AsyncMock(return_value=[existing])
        mock_uow.setting_repo.update = AsyncMock(return_value=True)
        mock_uow.session.get = AsyncMock(return_value=existing)
        mock_uow.commit = AsyncMock()

        with patch("app.core.services.preference_service.UnitOfWork") as MockUoW:
            MockUoW.return_value.__aenter__.return_value = mock_uow
            service = PreferenceService()
            result = await service.save_preference(
                user_id=1, modul="dashboard", ayar_tipi="sutun", deger=["col1", "col2"]
            )
            assert result is not None
            mock_uow.setting_repo.update.assert_called()

    async def test_delete_preference(self, mock_uow):
        pref = MagicMock(spec=KullaniciAyari)
        pref.kullanici_id = 1
        mock_uow.session.get = AsyncMock(return_value=pref)
        mock_uow.setting_repo.delete = AsyncMock(return_value=True)
        mock_uow.commit = AsyncMock()

        with patch("app.core.services.preference_service.UnitOfWork") as MockUoW:
            MockUoW.return_value.__aenter__.return_value = mock_uow
            service = PreferenceService()
            result = await service.delete_preference(user_id=1, pref_id=1)
            assert result is True
            mock_uow.setting_repo.delete.assert_called()

    async def test_delete_preference_not_found(self, mock_uow):
        mock_uow.session.get = AsyncMock(return_value=None)

        with patch("app.core.services.preference_service.UnitOfWork") as MockUoW:
            MockUoW.return_value.__aenter__.return_value = mock_uow
            service = PreferenceService()
            result = await service.delete_preference(user_id=1, pref_id=999)
            assert result is False

    async def test_set_default(self, mock_uow):
        pref = MagicMock(spec=KullaniciAyari)
        pref.kullanici_id = 1
        pref.modul = "dashboard"
        pref.ayar_tipi = "filter"
        mock_uow.session.get = AsyncMock(return_value=pref)
        mock_uow.setting_repo.clear_default = AsyncMock()
        mock_uow.setting_repo.update = AsyncMock(return_value=True)
        mock_uow.commit = AsyncMock()

        with patch("app.core.services.preference_service.UnitOfWork") as MockUoW:
            MockUoW.return_value.__aenter__.return_value = mock_uow
            service = PreferenceService()
            result = await service.set_default(user_id=1, pref_id=1)
            assert result is True

    def test_service_instantiation(self):
        service = PreferenceService()
        assert service is not None
        assert hasattr(service, "get_preferences")
        assert hasattr(service, "save_preference")
