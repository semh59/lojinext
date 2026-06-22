from unittest.mock import AsyncMock, patch

import pytest
from fastapi import HTTPException

pytestmark = pytest.mark.unit


def _make_uow(sefer=None, update_result=True):
    """Helper: build a mock UnitOfWork that behaves as an async context manager."""
    mock_uow = AsyncMock()
    mock_uow.__aenter__ = AsyncMock(return_value=mock_uow)
    mock_uow.__aexit__ = AsyncMock(return_value=None)
    mock_uow.sefer_repo = AsyncMock()
    mock_uow.sefer_repo.get_by_id = AsyncMock(return_value=sefer)
    mock_uow.sefer_repo.update = AsyncMock(return_value=update_result)
    mock_uow.commit = AsyncMock()
    return mock_uow


def _make_service(uow, event_bus=None):
    from app.core.services.attribution_service import AttributionService

    if event_bus is None:
        event_bus = AsyncMock()
        event_bus.publish_async = AsyncMock()

    with patch(
        "app.core.services.attribution_service.get_event_bus", return_value=event_bus
    ):
        svc = AttributionService(uow=uow)
    svc.event_bus = event_bus
    return svc


class TestAttributionService:
    def test_service_exists(self):
        from app.core.services.attribution_service import AttributionService

        assert AttributionService is not None

    async def test_basic_initialization(self):
        mock_uow = _make_uow()
        svc = _make_service(mock_uow)

        from app.core.services.attribution_service import AttributionService

        assert isinstance(svc, AttributionService)
        assert svc.uow is mock_uow

    async def test_happy_path_override_arac(self):
        sefer = {"id": 1, "arac_id": 10, "sofor_id": 20}
        mock_uow = _make_uow(sefer=sefer, update_result=True)
        svc = _make_service(mock_uow)

        result = await svc.override_attribution(sefer_id=1, arac_id=99, reason="Test")

        assert result is True
        mock_uow.sefer_repo.update.assert_awaited_once()
        mock_uow.commit.assert_awaited_once()

    async def test_happy_path_override_sofor(self):
        sefer = {"id": 1, "arac_id": 10, "sofor_id": 20}
        mock_uow = _make_uow(sefer=sefer, update_result=True)
        svc = _make_service(mock_uow)

        result = await svc.override_attribution(
            sefer_id=1, sofor_id=55, reason="Sürücü değişti"
        )

        assert result is True
        call_kwargs = mock_uow.sefer_repo.update.call_args
        assert call_kwargs.kwargs.get("sofor_id") == 55 or 55 in call_kwargs.args

    async def test_error_handling_sefer_not_found(self):
        mock_uow = _make_uow(sefer=None)
        svc = _make_service(mock_uow)

        with pytest.raises(HTTPException) as exc_info:
            await svc.override_attribution(sefer_id=999)

        assert exc_info.value.status_code == 404

    async def test_edge_case_update_returns_false(self):
        """When repo.update returns False the method should return False without commit."""
        sefer = {"id": 1, "arac_id": 10, "sofor_id": 20}
        mock_uow = _make_uow(sefer=sefer, update_result=False)
        svc = _make_service(mock_uow)

        result = await svc.override_attribution(sefer_id=1, arac_id=99)

        assert result is False
        mock_uow.commit.assert_not_awaited()

    async def test_event_published_on_success(self):
        sefer = {"id": 5, "arac_id": 10, "sofor_id": 20}
        mock_uow = _make_uow(sefer=sefer, update_result=True)
        event_bus = AsyncMock()
        event_bus.publish_async = AsyncMock()
        svc = _make_service(mock_uow, event_bus=event_bus)

        await svc.override_attribution(sefer_id=5, arac_id=77, reason="Nakil")

        event_bus.publish_async.assert_awaited_once()
        published_event = event_bus.publish_async.call_args[0][0]
        assert published_event.data["sefer_id"] == 5
        assert published_event.data["new_arac_id"] == 77

    async def test_bulk_override_returns_count(self):
        sefer = {"id": 1, "arac_id": 10, "sofor_id": 20}
        mock_uow = _make_uow(sefer=sefer, update_result=True)
        svc = _make_service(mock_uow)

        overrides = [
            {"sefer_id": 1, "arac_id": 11, "reason": "r1"},
            {"sefer_id": 1, "sofor_id": 22, "reason": "r2"},
        ]
        count = await svc.bulk_override(overrides)

        assert count == 2

    async def test_bulk_override_partial_failure(self):
        """Bulk override swallows individual errors and still counts successes."""
        mock_uow = _make_uow(sefer=None)  # sefer not found → raises HTTPException
        svc = _make_service(mock_uow)

        overrides = [
            {"sefer_id": 999, "arac_id": 11},
            {"sefer_id": 999, "sofor_id": 22},
        ]
        count = await svc.bulk_override(overrides)

        assert count == 0

    async def test_integration_with_mock(self):
        """Both arac_id and sofor_id can be overridden together."""
        sefer = {"id": 3, "arac_id": 1, "sofor_id": 2}
        mock_uow = _make_uow(sefer=sefer, update_result=True)
        svc = _make_service(mock_uow)

        result = await svc.override_attribution(
            sefer_id=3, arac_id=100, sofor_id=200, reason="Full override"
        )

        assert result is True
        call_kwargs = mock_uow.sefer_repo.update.call_args
        assert call_kwargs.kwargs.get("is_corrected") is True

    async def test_return_type_validation(self):
        sefer = {"id": 1, "arac_id": 10, "sofor_id": 20}
        mock_uow = _make_uow(sefer=sefer, update_result=True)
        svc = _make_service(mock_uow)

        result = await svc.override_attribution(sefer_id=1, arac_id=5)
        assert isinstance(result, bool)
        assert result is True
