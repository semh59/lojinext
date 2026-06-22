from unittest.mock import AsyncMock, patch

import fastapi
import pytest


async def test_dashboard_silent_failure_is_gone():
    """
    Exception olunca boş DashboardStatsResponse() değil HTTPException(503) dönmeli.
    """
    from app.api.v1.endpoints import reports as reports_mod

    mock_service = AsyncMock()
    mock_service.generate_fleet_summary.side_effect = RuntimeError("test hatası")

    # ReportService is imported locally inside the function, so patch it at its source module
    with patch(
        "app.core.services.report_service.ReportService", return_value=mock_service
    ):
        with pytest.raises(fastapi.HTTPException) as exc_info:
            await reports_mod.get_dashboard_stats(db=AsyncMock(), current_user=None)
        assert exc_info.value.status_code == 503
