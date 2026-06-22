from datetime import datetime, timedelta, timezone

import pytest

from app.core.services.auth_service import AuthService
from app.database.models import Kullanici


@pytest.fixture
def mock_db_session(mocker):
    db_session = mocker.Mock()
    return db_session


@pytest.fixture
def auth_service(mocker):
    uow_mock = mocker.Mock()
    uow_mock.__aenter__ = mocker.AsyncMock(return_value=uow_mock)
    uow_mock.__aexit__ = mocker.AsyncMock(return_value=None)
    return AuthService(uow=uow_mock)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_successful_login_resets_counter(auth_service, mocker):
    user = Kullanici(id=1, email="test@test.com", aktif=True, basarisiz_giris_sayisi=3)
    user.sifre_hash = "dummyhash"
    user.rol = mocker.Mock()
    user.rol.ad = "superadmin"

    auth_service.uow.kullanici_repo.get_by_email = mocker.AsyncMock(return_value=user)
    mocker.patch(
        "app.infrastructure.security.jwt_handler.verify_password", return_value=True
    )
    mocker.patch(
        "app.infrastructure.security.jwt_handler.create_access_token",
        return_value="acc",
    )
    mocker.patch(
        "app.infrastructure.security.jwt_handler.create_refresh_token",
        return_value="ref",
    )
    mocker.patch(
        "app.infrastructure.security.jwt_handler.decode_token",
        return_value={"exp": 9999999999, "sub": "test@test.com", "typ": "access"},
    )
    mocker.patch(
        "app.infrastructure.security.jwt_handler.decode_refresh_token",
        return_value={"exp": 9999999999, "sub": "test@test.com", "typ": "refresh"},
    )
    mocker.patch(
        "app.infrastructure.security.jwt_handler.hash_token", return_value="hash"
    )
    mocker.patch(
        "app.infrastructure.security.jwt_handler.get_password_hash", return_value="hash"
    )

    mock_req = mocker.Mock()
    mock_req.client.host = "127.0.0.1"
    mock_req.headers.get.return_value = "TestAgent"

    auth_service.uow.session = mocker.Mock()
    auth_service.uow.commit = mocker.AsyncMock(return_value=None)

    await auth_service.authenticate("test@test.com", "password", mock_req)
    assert user.basarisiz_giris_sayisi == 0


@pytest.mark.unit
@pytest.mark.asyncio
async def test_failed_login_increments_counter(auth_service, mocker):
    user = Kullanici(id=1, email="test@test.com", aktif=True, basarisiz_giris_sayisi=0)
    auth_service.uow.kullanici_repo.get_by_email = mocker.AsyncMock(return_value=user)
    auth_service.uow.commit = mocker.AsyncMock(return_value=None)
    mocker.patch(
        "app.infrastructure.security.jwt_handler.verify_password", return_value=False
    )

    mock_req = mocker.Mock()

    with pytest.raises(Exception):
        await auth_service.authenticate("test@test.com", "wrongpass", mock_req)

    assert user.basarisiz_giris_sayisi == 1


@pytest.mark.unit
@pytest.mark.asyncio
async def test_user_locked_out_after_5_attempts(auth_service, mocker):
    user = Kullanici(id=1, email="test@test.com", aktif=True, basarisiz_giris_sayisi=5)
    user.kilitli_kadar = datetime.now(timezone.utc) + timedelta(minutes=20)
    auth_service.uow.kullanici_repo.get_by_email = mocker.AsyncMock(return_value=user)
    mocker.patch(
        "app.infrastructure.security.jwt_handler.verify_password", return_value=True
    )

    mock_req = mocker.Mock()

    with pytest.raises(Exception) as exc_info:
        await auth_service.authenticate("test@test.com", "password", mock_req)

    assert "kilitlen" in str(exc_info.value).lower()
