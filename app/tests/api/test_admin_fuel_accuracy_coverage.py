"""Coverage tests for app/api/v1/endpoints/admin_fuel_accuracy.py

Targets ~51% → ≥75%
Covers: get_fuel_accuracy — no data (zero sample), paired data with metrics,
        arac_id filter, sofor_id filter, breakdown_by_arac, coverage_pct
        calculation, null metric fields.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_client():
    from httpx import AsyncClient
    from httpx._transports.asgi import ASGITransport

    from app.main import app

    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


def _make_admin_user():
    u = MagicMock()
    u.id = 1
    u.email = "admin@example.com"
    u.aktif = True
    u.rol = "admin"
    return u


def _make_row(
    sample_size=10,
    total_completed=20,
    mape_pct=5.5,
    rmse=2.3,
    mean_predicted=35.0,
    mean_actual=33.0,
    bias_pct=6.1,
):
    row = MagicMock()
    row.__getitem__ = lambda self, key: {
        "sample_size": sample_size,
        "total_completed": total_completed,
        "mape_pct": mape_pct,
        "rmse": rmse,
        "mean_predicted": mean_predicted,
        "mean_actual": mean_actual,
        "bias_pct": bias_pct,
    }[key]
    return row


def _make_arac_row(arac_id=1, samples=5, mape_pct=4.2, bias_pct=3.1):
    row = MagicMock()
    row.__getitem__ = lambda self, key: {
        "arac_id": arac_id,
        "samples": samples,
        "mape_pct": mape_pct,
        "bias_pct": bias_pct,
    }[key]
    return row


def _setup_db_mock(agg_row, arac_rows=None):
    """Create a mock DB session that returns the given aggregate row and arac rows."""
    if arac_rows is None:
        arac_rows = []

    mock_db = AsyncMock()
    call_count = [0]

    agg_mappings = MagicMock()
    agg_mappings.one_or_none.return_value = agg_row

    arac_mappings = MagicMock()
    arac_mappings.all.return_value = arac_rows

    async def mock_execute(stmt, params=None):
        call_count[0] += 1
        result = MagicMock()
        if call_count[0] == 1:
            result.mappings.return_value = agg_mappings
        else:
            result.mappings.return_value = arac_mappings
        return result

    mock_db.execute = mock_execute
    return mock_db


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestGetFuelAccuracy:
    async def test_no_data_returns_zero_sample_size(self):
        """get_fuel_accuracy returns zeros when no completed trips."""
        from app.api.deps import get_current_active_admin
        from app.main import app
        from v2.modules.platform_infra.database.connection import get_db

        admin = _make_admin_user()
        mock_db = _setup_db_mock(agg_row=None)

        async def _fake_admin():
            return admin

        async def _fake_db():
            yield mock_db

        app.dependency_overrides[get_current_active_admin] = _fake_admin
        app.dependency_overrides[get_db] = _fake_db
        try:
            async with _make_client() as client:
                resp = await client.get("/api/v1/admin/fuel-accuracy")
            assert resp.status_code == 200
            data = resp.json()
            assert data["sample_size"] == 0
            assert data["mape_pct"] is None
            assert data["rmse_l_100km"] is None
            assert data["coverage_pct"] == 0.0
        finally:
            app.dependency_overrides.clear()

    async def test_with_data_returns_metrics(self):
        """get_fuel_accuracy returns MAPE/RMSE when data exists."""
        from app.api.deps import get_current_active_admin
        from app.main import app
        from v2.modules.platform_infra.database.connection import get_db

        admin = _make_admin_user()
        agg_row = _make_row(
            sample_size=10,
            total_completed=20,
            mape_pct=5.5,
            rmse=2.3,
            mean_predicted=35.0,
            mean_actual=33.0,
            bias_pct=6.1,
        )
        arac_row = _make_arac_row(arac_id=7, samples=5, mape_pct=4.2, bias_pct=3.1)
        mock_db = _setup_db_mock(agg_row=agg_row, arac_rows=[arac_row])

        async def _fake_admin():
            return admin

        async def _fake_db():
            yield mock_db

        app.dependency_overrides[get_current_active_admin] = _fake_admin
        app.dependency_overrides[get_db] = _fake_db
        try:
            async with _make_client() as client:
                resp = await client.get("/api/v1/admin/fuel-accuracy?days=30")
            assert resp.status_code == 200
            data = resp.json()
            assert data["sample_size"] == 10
            assert data["mape_pct"] == 5.5
            assert data["rmse_l_100km"] == 2.3
            assert data["mean_predicted"] == 35.0
            assert data["mean_actual"] == 33.0
            assert data["bias_pct"] == 6.1
            assert data["coverage_pct"] == 50.0  # 10/20 * 100
            assert len(data["breakdown_by_arac"]) == 1
            assert data["breakdown_by_arac"][0]["arac_id"] == 7
        finally:
            app.dependency_overrides.clear()

    async def test_arac_id_filter_passed_to_query(self):
        """get_fuel_accuracy accepts arac_id query param."""
        from app.api.deps import get_current_active_admin
        from app.main import app
        from v2.modules.platform_infra.database.connection import get_db

        admin = _make_admin_user()
        mock_db = _setup_db_mock(agg_row=None)

        async def _fake_admin():
            return admin

        async def _fake_db():
            yield mock_db

        app.dependency_overrides[get_current_active_admin] = _fake_admin
        app.dependency_overrides[get_db] = _fake_db
        try:
            async with _make_client() as client:
                resp = await client.get("/api/v1/admin/fuel-accuracy?arac_id=3")
            assert resp.status_code == 200
        finally:
            app.dependency_overrides.clear()

    async def test_sofor_id_filter_accepted(self):
        """get_fuel_accuracy accepts sofor_id query param."""
        from app.api.deps import get_current_active_admin
        from app.main import app
        from v2.modules.platform_infra.database.connection import get_db

        admin = _make_admin_user()
        mock_db = _setup_db_mock(agg_row=None)

        async def _fake_admin():
            return admin

        async def _fake_db():
            yield mock_db

        app.dependency_overrides[get_current_active_admin] = _fake_admin
        app.dependency_overrides[get_db] = _fake_db
        try:
            async with _make_client() as client:
                resp = await client.get("/api/v1/admin/fuel-accuracy?sofor_id=5")
            assert resp.status_code == 200
        finally:
            app.dependency_overrides.clear()

    async def test_null_metrics_returned_as_none(self):
        """get_fuel_accuracy returns None for NULL metric fields."""
        from app.api.deps import get_current_active_admin
        from app.main import app
        from v2.modules.platform_infra.database.connection import get_db

        admin = _make_admin_user()
        agg_row = _make_row(
            sample_size=0,
            total_completed=5,
            mape_pct=None,
            rmse=None,
            mean_predicted=None,
            mean_actual=None,
            bias_pct=None,
        )
        mock_db = _setup_db_mock(agg_row=agg_row)

        async def _fake_admin():
            return admin

        async def _fake_db():
            yield mock_db

        app.dependency_overrides[get_current_active_admin] = _fake_admin
        app.dependency_overrides[get_db] = _fake_db
        try:
            async with _make_client() as client:
                resp = await client.get("/api/v1/admin/fuel-accuracy")
            assert resp.status_code == 200
            data = resp.json()
            assert data["mape_pct"] is None
            assert data["rmse_l_100km"] is None
            assert data["mean_predicted"] is None
            assert data["mean_actual"] is None
            assert data["bias_pct"] is None
        finally:
            app.dependency_overrides.clear()

    async def test_days_param_validation(self):
        """get_fuel_accuracy rejects days < 1."""
        from app.api.deps import get_current_active_admin
        from app.main import app
        from v2.modules.platform_infra.database.connection import get_db

        admin = _make_admin_user()

        async def _fake_admin():
            return admin

        async def _fake_db():
            yield AsyncMock()

        app.dependency_overrides[get_current_active_admin] = _fake_admin
        app.dependency_overrides[get_db] = _fake_db
        try:
            async with _make_client() as client:
                resp = await client.get("/api/v1/admin/fuel-accuracy?days=0")
            assert resp.status_code == 422
        finally:
            app.dependency_overrides.clear()

    async def test_days_param_max_validation(self):
        """get_fuel_accuracy rejects days > 365."""
        from app.api.deps import get_current_active_admin
        from app.main import app
        from v2.modules.platform_infra.database.connection import get_db

        admin = _make_admin_user()

        async def _fake_admin():
            return admin

        async def _fake_db():
            yield AsyncMock()

        app.dependency_overrides[get_current_active_admin] = _fake_admin
        app.dependency_overrides[get_db] = _fake_db
        try:
            async with _make_client() as client:
                resp = await client.get("/api/v1/admin/fuel-accuracy?days=999")
            assert resp.status_code == 422
        finally:
            app.dependency_overrides.clear()

    async def test_full_coverage_calculation(self):
        """coverage_pct is correctly computed as sample/total * 100."""
        from app.api.deps import get_current_active_admin
        from app.main import app
        from v2.modules.platform_infra.database.connection import get_db

        admin = _make_admin_user()
        agg_row = _make_row(sample_size=25, total_completed=100)
        mock_db = _setup_db_mock(agg_row=agg_row)

        async def _fake_admin():
            return admin

        async def _fake_db():
            yield mock_db

        app.dependency_overrides[get_current_active_admin] = _fake_admin
        app.dependency_overrides[get_db] = _fake_db
        try:
            async with _make_client() as client:
                resp = await client.get("/api/v1/admin/fuel-accuracy")
            assert resp.status_code == 200
            data = resp.json()
            assert data["coverage_pct"] == 25.0
        finally:
            app.dependency_overrides.clear()

    async def test_breakdown_null_mape_handled(self):
        """get_fuel_accuracy handles NULL mape_pct in breakdown rows."""
        from app.api.deps import get_current_active_admin
        from app.main import app
        from v2.modules.platform_infra.database.connection import get_db

        admin = _make_admin_user()
        agg_row = _make_row(sample_size=3, total_completed=3)
        arac_row = _make_arac_row(arac_id=2, samples=3, mape_pct=None, bias_pct=None)
        mock_db = _setup_db_mock(agg_row=agg_row, arac_rows=[arac_row])

        async def _fake_admin():
            return admin

        async def _fake_db():
            yield mock_db

        app.dependency_overrides[get_current_active_admin] = _fake_admin
        app.dependency_overrides[get_db] = _fake_db
        try:
            async with _make_client() as client:
                resp = await client.get("/api/v1/admin/fuel-accuracy")
            assert resp.status_code == 200
            breakdown = resp.json()["breakdown_by_arac"]
            assert breakdown[0]["mape_pct"] is None
            assert breakdown[0]["bias_pct"] is None
        finally:
            app.dependency_overrides.clear()
