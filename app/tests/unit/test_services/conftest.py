"""Fixtures for service layer tests."""

from unittest.mock import AsyncMock, MagicMock

import pytest


@pytest.fixture
def mock_uow(monkeypatch):
    """Mock UnitOfWork that can be used by services without a real DB."""
    from app.database.unit_of_work import UnitOfWork

    # Create a mock UnitOfWork instance
    uow = MagicMock(spec=UnitOfWork)
    uow.__aenter__ = AsyncMock(return_value=uow)
    uow.__aexit__ = AsyncMock(return_value=False)
    uow.commit = AsyncMock()
    uow.rollback = AsyncMock()

    # Mock repositories with default return values
    uow.arac_repo = MagicMock()
    uow.arac_repo.get_all = AsyncMock(return_value=[])
    uow.arac_repo.get_by_id = AsyncMock(return_value=None)
    uow.arac_repo.get_stats = AsyncMock(return_value=None)
    uow.arac_repo.count_all = AsyncMock(return_value=0)
    uow.arac_repo.get_all_paged = AsyncMock(
        return_value={"items": [], "total": 0, "page": 1, "pages": 0}
    )

    uow.sofor_repo = MagicMock()
    uow.sofor_repo.get_all = AsyncMock(return_value=[])
    uow.sofor_repo.get_all_paged = AsyncMock(
        return_value={"items": [], "total": 0, "page": 1, "pages": 0}
    )
    uow.sofor_repo.get_by_id = AsyncMock(return_value=None)
    uow.sofor_repo.get_by_name = AsyncMock(return_value=None)
    uow.sofor_repo.count_all = AsyncMock(return_value=0)
    uow.sofor_repo.add = AsyncMock(return_value=None)
    uow.sofor_repo.update = AsyncMock(return_value=None)
    uow.sofor_repo.delete = AsyncMock(return_value=None)

    uow.yakit_repo = MagicMock()
    uow.yakit_repo.get_all = AsyncMock(return_value={"items": [], "total": 0})
    uow.yakit_repo.get_by_id = AsyncMock(return_value=None)
    uow.yakit_repo.get_by_vehicle = AsyncMock(return_value=[])
    uow.yakit_repo.count_all = AsyncMock(return_value=0)
    uow.yakit_repo.get_stats = AsyncMock(
        return_value={"toplam_yakit": 0, "aylik_ort": 0}
    )
    uow.yakit_repo.add = AsyncMock(return_value=None)
    uow.yakit_repo.update = AsyncMock(return_value=None)

    uow.sefer_repo = MagicMock()
    uow.sefer_repo.get_all = AsyncMock(return_value=[])
    uow.sefer_repo.get_by_id = AsyncMock(return_value=None)
    uow.sefer_repo.add = AsyncMock(return_value=None)
    uow.sefer_repo.update = AsyncMock(return_value=None)
    uow.sefer_repo.delete = AsyncMock(return_value=None)

    uow.analiz_repo = MagicMock()
    uow.analiz_repo.get_monthly_consumption_series = AsyncMock(return_value=[])
    uow.analiz_repo.get_daily_consumption_series = AsyncMock(return_value=[])
    uow.analiz_repo.get_dashboard_stats = AsyncMock(
        return_value={"toplam_yakit": 0, "filo_ortalama": 0}
    )

    return uow


@pytest.fixture
def mock_arac_service_uow(monkeypatch, mock_uow):
    """Patch UnitOfWork in arac_service module and reset container afterward."""
    from app.database.unit_of_work import UnitOfWork

    monkeypatch.setattr(UnitOfWork, "__aenter__", AsyncMock(return_value=mock_uow))
    monkeypatch.setattr(UnitOfWork, "__aexit__", AsyncMock(return_value=False))

    # Reset container so it uses the mocked UnitOfWork
    import app.core.container as container_mod

    container_mod.reset_container()

    yield mock_uow

    # Reset after test
    container_mod.reset_container()


@pytest.fixture
def arac_service(mock_arac_service_uow):
    """Override arac_service fixture to use mocked UnitOfWork."""
    from app.core.services.arac_service import get_arac_service

    return get_arac_service()


@pytest.fixture
def mock_sofor_service_uow(monkeypatch, mock_uow):
    """Patch UnitOfWork in sofor_service module and reset container afterward."""
    from app.database.unit_of_work import UnitOfWork

    monkeypatch.setattr(UnitOfWork, "__aenter__", AsyncMock(return_value=mock_uow))
    monkeypatch.setattr(UnitOfWork, "__aexit__", AsyncMock(return_value=False))

    # Reset container so it uses the mocked UnitOfWork
    import app.core.container as container_mod

    container_mod.reset_container()

    yield mock_uow

    # Reset after test
    container_mod.reset_container()


@pytest.fixture
def sofor_service(mock_sofor_service_uow):
    """Override sofor_service fixture to use mocked UnitOfWork."""
    from app.core.services.sofor_service import get_sofor_service

    return get_sofor_service()


@pytest.fixture
def sofor_service_with_mock_event_bus(mock_sofor_service_uow, mock_event_bus):
    """Create sofor_service with both mocked UnitOfWork and event bus."""
    from app.core.services.sofor_service import SoforService

    return SoforService(event_bus=mock_event_bus)


@pytest.fixture
def mock_yakit_service_uow(monkeypatch, mock_uow):
    """Patch UnitOfWork in yakit_service module and reset container afterward."""
    from app.database.unit_of_work import UnitOfWork

    monkeypatch.setattr(UnitOfWork, "__aenter__", AsyncMock(return_value=mock_uow))
    monkeypatch.setattr(UnitOfWork, "__aexit__", AsyncMock(return_value=False))

    # Reset container so it uses the mocked UnitOfWork
    import app.core.container as container_mod

    container_mod.reset_container()

    yield mock_uow

    # Reset after test
    container_mod.reset_container()


@pytest.fixture
def yakit_service(mock_yakit_service_uow):
    """Override yakit_service fixture to use mocked UnitOfWork."""
    from app.core.services.yakit_service import get_yakit_service

    return get_yakit_service()
