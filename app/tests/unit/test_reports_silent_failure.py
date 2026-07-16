from unittest.mock import AsyncMock, patch

import fastapi
import pytest


async def test_dashboard_silent_failure_is_gone():
    """
    Exception olunca boş DashboardStatsResponse() değil HTTPException(503) dönmeli.
    """
    from v2.modules.reports.api import dashboard_routes as reports_mod

    with patch(
        "v2.modules.reports.api.dashboard_routes.generate_fleet_summary",
        new=AsyncMock(side_effect=RuntimeError("test hatası")),
    ):
        with pytest.raises(fastapi.HTTPException) as exc_info:
            await reports_mod.get_dashboard_stats(db=AsyncMock(), current_user=None)
        assert exc_info.value.status_code == 503
