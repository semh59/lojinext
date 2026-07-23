"""v2/modules/driver/infrastructure/driver_metrics_queries.py unit tests.

dalga 11: get_bulk_driver_metrics eskiden
AnalizRepository'nin (app/database/repositories/analiz_repo.py) parçasıydı
— driver modülüne taşındı (driver dalgasının [5] atladığı bir taşıma, bu
dalgada tamamlandı). Testler repo-method çağrısından free-function
çağrısına (fake uow.session ile) çevrildi.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_uow(session=None):
    uow = MagicMock()
    uow.session = session if session is not None else AsyncMock()
    return uow


def _mapping_row(**kwargs):
    """Build a mock row that has a ._mapping attribute."""
    m = MagicMock()
    m._mapping = kwargs
    return m


def _fetchall_result(rows):
    """Build a mock execute result whose .fetchall() returns rows."""
    result = MagicMock()
    result.fetchall = MagicMock(return_value=rows)
    return result


# ---------------------------------------------------------------------------
# get_bulk_driver_metrics
# ---------------------------------------------------------------------------


class TestGetBulkDriverMetrics:
    async def test_returns_list_of_dicts(self):
        from v2.modules.driver.infrastructure.driver_metrics_queries import (
            get_bulk_driver_metrics,
        )

        uow = _make_uow()
        row = _mapping_row(sofor_id=1, ad_soyad="Ali Veli", toplam_sefer=10)
        uow.session.execute = AsyncMock(return_value=_fetchall_result([row]))

        result = await get_bulk_driver_metrics(uow)
        assert isinstance(result, list)
        assert len(result) == 1
        assert result[0]["sofor_id"] == 1

    async def test_empty_returns_empty_list(self):
        from v2.modules.driver.infrastructure.driver_metrics_queries import (
            get_bulk_driver_metrics,
        )

        uow = _make_uow()
        uow.session.execute = AsyncMock(return_value=_fetchall_result([]))

        result = await get_bulk_driver_metrics(uow)
        assert result == []
