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
    uow.sefer_repo.get_existing_sefer_nos = AsyncMock(return_value=set())

    uow.analiz_repo = MagicMock()
    uow.analiz_repo.get_monthly_consumption_series = AsyncMock(return_value=[])
    uow.analiz_repo.get_daily_consumption_series = AsyncMock(return_value=[])
    uow.analiz_repo.get_dashboard_stats = AsyncMock(
        return_value={"toplam_yakit": 0, "filo_ortalama": 0}
    )
    uow.analiz_repo.get_anomalies_filtered = AsyncMock(return_value=[])
    uow.analiz_repo.bulk_create_anomalies = AsyncMock(return_value=0)
    uow.analiz_repo.get_anomaly_by_id = AsyncMock(return_value=None)
    uow.analiz_repo.update_anomaly = AsyncMock(return_value=None)

    uow.dorse_repo = MagicMock()
    uow.dorse_repo.get_by_id = AsyncMock(return_value=None)

    uow.yakit_repo.get_last_n_by_arac = AsyncMock(return_value=[])

    return uow


# mock_arac_service_uow / arac_service fixtures removed — AracService class
# deleted in dalga 3 (B.1 free-function refactor, v2.modules.fleet); nothing
# in this directory referenced them as a fixture param.


# mock_sofor_service_uow / sofor_service / sofor_service_with_mock_event_bus
# fixtures removed — SoforService class deleted in dalga 5 (B.1 free-function
# refactor, v2.modules.driver); use-cases now import UnitOfWork directly
# (patch v2.modules.driver.application.<file>.UnitOfWork where needed) or
# accept an explicit uow= kwarg (see test_sofor_service_coverage.py's
# _fake_sofor_repo pattern for get_score_breakdown_sofor/get_route_profile_sofor).


# mock_yakit_service_uow / yakit_service fixtures removed — YakitService
# class deleted in dalga 4 (B.1 free-function refactor, v2.modules.fuel);
# nothing in this directory references them as a fixture param anymore
# (tests import the free functions directly and rely on the real db_session,
# or patch v2.modules.fuel.application.<file>.UnitOfWork where needed).
