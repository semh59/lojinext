"""
Additional coverage for app/core/services/lokasyon_service.py.

Targets missing lines:
  206-207 — add_lokasyon: analyze_route raises → warning logged, lokasyon_id still returned
  255-257 — delete_lokasyon: outer except catches non-ValueError (not FK) → re-raises as ValueError
  324-372 — analyze_route: happy path (success with route service + fuel predictor)
  376-378 — get_lokasyon_service (container access)
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

pytestmark = pytest.mark.unit


def _make_service(repo=None, event_bus=None):
    from app.core.services.lokasyon_service import LokasyonService

    mock_repo = repo or AsyncMock()
    mock_bus = event_bus or MagicMock()
    mock_bus.publish = MagicMock()
    return LokasyonService(repo=mock_repo, event_bus=mock_bus), mock_repo


def _make_create_with_coords():
    from app.schemas.lokasyon import LokasyonCreate

    return LokasyonCreate(
        cikis_yeri="İstanbul",
        varis_yeri="Ankara",
        mesafe_km=450.0,
        cikis_lat=41.0,
        cikis_lon=29.0,
        varis_lat=39.9,
        varis_lon=32.8,
    )


# ---------------------------------------------------------------------------
# add_lokasyon — analyze_route raises → warning, id still returned (lines 206-207)
# ---------------------------------------------------------------------------


async def test_add_lokasyon_analyze_route_exception_still_returns_id():
    """When analyze_route raises an exception, the warning is logged
    but add_lokasyon still returns the new lokasyon id."""
    svc, mock_repo = _make_service()
    mock_repo.get_by_route.return_value = None
    mock_repo.add.return_value = 42

    with patch.object(svc, "analyze_route", side_effect=Exception("route api error")):
        result = await svc.add_lokasyon(_make_create_with_coords())

    assert result == 42
    mock_repo.add.assert_called_once()


async def test_add_lokasyon_analyze_route_called_with_returned_id():
    """analyze_route is called with the id returned by repo.add."""
    svc, mock_repo = _make_service()
    mock_repo.get_by_route.return_value = None
    mock_repo.add.return_value = 77

    analyze_calls = []

    async def _fake_analyze(lok_id):
        analyze_calls.append(lok_id)
        return {"distance_km": 450.0}

    with patch.object(svc, "analyze_route", side_effect=_fake_analyze):
        result = await svc.add_lokasyon(_make_create_with_coords())

    assert result == 77
    assert analyze_calls == [77]


# ---------------------------------------------------------------------------
# delete_lokasyon — outer except catches unexpected exception (lines 255-257)
# ---------------------------------------------------------------------------


async def test_delete_lokasyon_unexpected_exception_raises_value_error():
    """An unexpected exception (not ValueError) during delete_lokasyon should
    be caught and re-raised as ValueError with a generic message."""
    svc, mock_repo = _make_service()
    # get_by_id raises an unexpected error (not ValueError)
    mock_repo.get_by_id.side_effect = RuntimeError("unexpected db failure")

    with pytest.raises(ValueError, match="Silme işlemi"):
        await svc.delete_lokasyon(99)


# ---------------------------------------------------------------------------
# analyze_route — happy path (lines 324-372)
# ---------------------------------------------------------------------------


async def test_analyze_route_success():
    """analyze_route: location found with coords, route service succeeds,
    fuel predictor succeeds — all fields updated in repo."""
    svc, mock_repo = _make_service()

    mock_repo.get_by_id.return_value = {
        "id": 1,
        "cikis_lat": 41.0,
        "cikis_lon": 29.0,
        "varis_lat": 39.9,
        "varis_lon": 32.8,
        "zorluk": "Normal",
    }

    route_result = {
        "distance_km": 450.0,
        "duration_min": 330.0,
        "ascent_m": 800,
        "descent_m": 700,
        "flat_distance_km": 200.0,
        "otoban_mesafe_km": 350.0,
        "sehir_ici_mesafe_km": 50.0,
        "difficulty": "Orta",
        "source": "ors",
        "is_corrected": False,
        "correction_reason": None,
        "route_analysis": {"highway_pct": 0.78},
        "distributions": {},
    }

    mock_rs = AsyncMock()
    mock_rs.get_route_details = AsyncMock(return_value=route_result)
    mock_route_service_module = MagicMock()
    mock_route_service_module.get_route_service = MagicMock(return_value=mock_rs)

    # Fuel predictor
    fuel_pred = MagicMock()
    fuel_pred.total_liters = 135.0
    mock_physics_predictor = MagicMock()
    mock_physics_predictor.predict.return_value = fuel_pred

    mock_physics_module = MagicMock()
    mock_physics_module.PhysicsBasedFuelPredictor.return_value = mock_physics_predictor
    mock_physics_module.RouteConditions = MagicMock(return_value=MagicMock())

    with patch.dict(
        "sys.modules",
        {
            "app.services.route_service": mock_route_service_module,
            "app.core.ml.physics_fuel_predictor": mock_physics_module,
        },
    ):
        with patch("asyncio.to_thread", new_callable=AsyncMock, return_value=fuel_pred):
            result = await svc.analyze_route(1)

    assert result["distance_km"] == 450.0
    mock_repo.update.assert_called()


async def test_analyze_route_success_no_fuel_predictor():
    """analyze_route works even if fuel predictor raises — warning logged."""
    svc, mock_repo = _make_service()

    mock_repo.get_by_id.return_value = {
        "id": 2,
        "cikis_lat": 41.0,
        "cikis_lon": 29.0,
        "varis_lat": 39.9,
        "varis_lon": 32.8,
        "zorluk": "Zor",
    }

    route_result = {
        "distance_km": 600.0,
        "duration_min": 420.0,
        "ascent_m": 1000,
        "descent_m": 900,
        "flat_distance_km": 250.0,
        "otoban_mesafe_km": None,
        "sehir_ici_mesafe_km": None,
        "source": "mapbox",
        "is_corrected": True,
        "correction_reason": "ORS failed",
        "route_analysis": None,
        "distributions": None,
    }

    mock_rs = AsyncMock()
    mock_rs.get_route_details = AsyncMock(return_value=route_result)
    mock_route_service_module = MagicMock()
    mock_route_service_module.get_route_service = MagicMock(return_value=mock_rs)

    # Physics predictor raises
    mock_physics_module = MagicMock()
    mock_physics_module.PhysicsBasedFuelPredictor.side_effect = Exception(
        "physics error"
    )
    mock_physics_module.RouteConditions = MagicMock()

    with patch.dict(
        "sys.modules",
        {
            "app.services.route_service": mock_route_service_module,
            "app.core.ml.physics_fuel_predictor": mock_physics_module,
        },
    ):
        result = await svc.analyze_route(2)

    assert result["distance_km"] == 600.0
    # Should still have called repo.update once for route data
    mock_repo.update.assert_called()


async def test_analyze_route_error_response_raises_value_error():
    """If route service returns error key, raises ValueError."""
    svc, mock_repo = _make_service()

    mock_repo.get_by_id.return_value = {
        "id": 3,
        "cikis_lat": 41.0,
        "cikis_lon": 29.0,
        "varis_lat": 39.9,
        "varis_lon": 32.8,
    }

    mock_rs = AsyncMock()
    mock_rs.get_route_details = AsyncMock(return_value={"error": "no route found"})
    mock_route_service_module = MagicMock()
    mock_route_service_module.get_route_service = MagicMock(return_value=mock_rs)

    with patch.dict(
        "sys.modules", {"app.services.route_service": mock_route_service_module}
    ):
        with pytest.raises(ValueError, match="Analiz hatası"):
            await svc.analyze_route(3)


# ---------------------------------------------------------------------------
# get_lokasyon_service — container access (lines 376-378)
# ---------------------------------------------------------------------------


def test_get_lokasyon_service_from_container():
    """get_lokasyon_service retrieves from the container singleton."""
    from app.core.services.lokasyon_service import LokasyonService

    fake_svc = MagicMock(spec=LokasyonService)
    fake_container = MagicMock()
    fake_container.lokasyon_service = fake_svc

    with patch("app.core.container.get_container", return_value=fake_container):
        from app.core.services.lokasyon_service import get_lokasyon_service

        result = get_lokasyon_service()

    assert result is fake_svc
