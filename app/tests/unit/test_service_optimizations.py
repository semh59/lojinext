import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.services.weather_service import WeatherService
from v2.modules.analytics_executive.application.generate_insights import (
    Insight,
    InsightType,
)


@pytest.mark.asyncio
async def test_insight_engine_bulk_insert():
    """Verify generate_all_and_save uses bulk insert (dalga 11 — free function,
    eski InsightEngine sınıfı kaldırıldı)."""
    with (
        patch(
            "v2.modules.analytics_executive.application.generate_insights.generate_fleet_insights",
            AsyncMock(
                return_value=[Insight(InsightType.UYARI, "filo", None, "Test Fleet")]
            ),
        ),
        patch(
            "v2.modules.analytics_executive.application.generate_insights.generate_vehicle_insights_bulk",
            AsyncMock(
                return_value=[Insight(InsightType.UYARI, "arac", 1, "Test Vehicle")]
            ),
        ),
        patch(
            "v2.modules.analytics_executive.application.generate_insights.generate_driver_insights_bulk",
            AsyncMock(return_value=[]),
        ),
    ):
        # AUDIT-094: generate_all_and_save kaydetme yolu get_uow().analiz_repo kullanır.
        mock_uow = AsyncMock()
        mock_uow.__aenter__ = AsyncMock(return_value=mock_uow)
        mock_uow.__aexit__ = AsyncMock(return_value=None)
        mock_uow.analiz_repo = MagicMock()
        mock_uow.analiz_repo.bulk_create_alerts = AsyncMock(return_value=2)
        mock_uow.commit = AsyncMock()

        with patch(
            "v2.modules.analytics_executive.application.generate_insights.get_uow",
            return_value=mock_uow,
        ):
            from v2.modules.analytics_executive.application.generate_insights import (
                generate_all_and_save,
            )

            count = await generate_all_and_save()

            assert count == 2
            # Verify bulk_create_alerts was called instead of create_insight_alert
            mock_uow.analiz_repo.bulk_create_alerts.assert_called_once()
            args = mock_uow.analiz_repo.bulk_create_alerts.call_args[0][0]
            assert len(args) == 2
            assert args[0]["title"] == "Sistem Analizi: Uyari"


@pytest.mark.asyncio
async def test_weather_service_parallelism():
    """Verify WeatherService fetches start/end weather in parallel"""
    # Mock ExternalService
    mock_ext = AsyncMock()
    service = WeatherService(external_service=mock_ext)

    async def delayed_weather(*args):
        await asyncio.sleep(0.1)
        return {"daily": {}}

    mock_ext.get_weather_forecast.side_effect = delayed_weather

    import time

    start = time.time()
    await service.get_trip_impact_analysis(0, 0, 1, 1)
    end = time.time()

    assert (end - start) < 0.18, "Weather fetch should be parallel"
