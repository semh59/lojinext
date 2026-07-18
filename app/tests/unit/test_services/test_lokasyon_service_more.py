"""
Additional coverage for v2/modules/location/application/{create_location,
delete_location,analyze_location_route}.py.

Targets:
  create_location: analyze_location_route raises → warning logged, id still returned
  delete_location: outer except catches non-ValueError (not FK) → re-raises as ValueError
  analyze_location_route: happy path (success with route service + fuel predictor)
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from v2.modules.location.application.analyze_location_route import (
    analyze_location_route,
)
from v2.modules.location.application.create_location import create_location
from v2.modules.location.application.delete_location import delete_location
from v2.modules.location.infrastructure.repository import LokasyonRepository
from v2.modules.location.schemas import LokasyonCreate

pytestmark = pytest.mark.integration
# 0-mock epiği: create_location/delete_location testleri gerçek
# LokasyonRepository + gerçek DB'ye (db_session) çevrildi.
# analyze_location_route testleri route_service/physics_fuel_predictor'ı
# (ayrı domainler — ilki route_simulation modülünün kendi dilimi, ikincisi
# ML domain'i, bu turun kapsamı dışı) mock'lu bırakıyor — DOKÜMANTE.


def _make_create_with_coords():
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
# create_location — analyze_location_route raises → warning, id still returned
# ---------------------------------------------------------------------------


async def test_create_location_analyze_route_exception_still_returns_id(db_session):
    """When analyze_location_route raises an exception, the warning is logged
    but create_location still returns the new lokasyon id (gerçek DB'ye
    karşı — route analysis ayrı domain, dokümante mock'lu kalıyor)."""
    repo = LokasyonRepository(session=db_session)

    with patch(
        "v2.modules.location.application.create_location.analyze_location_route",
        side_effect=Exception("route api error"),
    ):
        result = await create_location(repo, _make_create_with_coords())

    assert result is not None


async def test_create_location_analyze_route_called_with_returned_id(db_session):
    """analyze_location_route is called with the id returned by repo.add."""
    repo = LokasyonRepository(session=db_session)

    analyze_calls = []

    async def _fake_analyze(_repo, lok_id):
        analyze_calls.append(lok_id)
        return {"distance_km": 450.0}

    with patch(
        "v2.modules.location.application.create_location.analyze_location_route",
        side_effect=_fake_analyze,
    ):
        result = await create_location(repo, _make_create_with_coords())

    assert analyze_calls == [result]


# ---------------------------------------------------------------------------
# delete_location — outer except catches unexpected exception
# ---------------------------------------------------------------------------


async def test_delete_location_unexpected_exception_raises_value_error(db_session):
    """An unexpected exception (not ValueError) during delete_location should
    be caught and re-raised as ValueError with a generic message.

    DOKÜMANTE: get_by_id'nin gerçek DB'de RuntimeError fırlatmasını güvenle
    üretmek pratik değil (bkz. openroute_client_coverage'daki aynı gerekçe)
    — hedefli mock ile test ediliyor, repo'nun gerçek kurulumu (db_session)
    yine de kullanılıyor."""
    repo = LokasyonRepository(session=db_session)
    repo.get_by_id = AsyncMock(side_effect=RuntimeError("unexpected db failure"))

    with pytest.raises(ValueError, match="Silme işlemi"):
        await delete_location(repo, 99)


# ---------------------------------------------------------------------------
# analyze_location_route — happy path
# ---------------------------------------------------------------------------


async def test_analyze_location_route_success(db_session):
    """analyze_location_route: location found with coords, route service
    succeeds, fuel predictor succeeds — all fields updated in repo."""
    from app.tests._helpers.seed import seed_lokasyon

    lokasyon = await seed_lokasyon(
        db_session,
        cikis_yeri="A",
        varis_yeri="B",
        cikis_lat=41.0,
        cikis_lon=29.0,
        varis_lat=39.9,
        varis_lon=32.8,
        zorluk="Normal",
    )
    await db_session.commit()
    repo = LokasyonRepository(session=db_session)

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

    mock_route_service_module = MagicMock()
    mock_route_service_module.get_route_details = AsyncMock(return_value=route_result)

    # Fuel predictor
    fuel_pred = MagicMock()
    fuel_pred.total_liters = 135.0
    mock_physics_predictor = MagicMock()
    mock_physics_predictor.predict.return_value = fuel_pred

    mock_physics_module = MagicMock()
    mock_physics_module.PhysicsBasedFuelPredictor.return_value = mock_physics_predictor
    mock_physics_module.RouteConditions = MagicMock(return_value=MagicMock())

    with patch.dict("sys.modules", {"app.core.ml.physics_fuel_predictor": mock_physics_module}):
        with patch(
            "v2.modules.route_simulation.public.get_route_details",
            mock_route_service_module.get_route_details,
        ):
            with patch(
                "asyncio.to_thread", new_callable=AsyncMock, return_value=fuel_pred
            ):
                result = await analyze_location_route(repo, lokasyon.id)

    assert result["distance_km"] == 450.0


async def test_analyze_location_route_success_no_fuel_predictor(db_session):
    """analyze_location_route works even if fuel predictor raises — warning logged."""
    from app.tests._helpers.seed import seed_lokasyon

    lokasyon = await seed_lokasyon(
        db_session,
        cikis_yeri="A",
        varis_yeri="B",
        cikis_lat=41.0,
        cikis_lon=29.0,
        varis_lat=39.9,
        varis_lon=32.8,
        zorluk="Zor",
    )
    await db_session.commit()
    repo = LokasyonRepository(session=db_session)

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

    mock_route_service_module = MagicMock()
    mock_route_service_module.get_route_details = AsyncMock(return_value=route_result)

    # Physics predictor raises
    mock_physics_module = MagicMock()
    mock_physics_module.PhysicsBasedFuelPredictor.side_effect = Exception(
        "physics error"
    )
    mock_physics_module.RouteConditions = MagicMock()

    with patch.dict("sys.modules", {"app.core.ml.physics_fuel_predictor": mock_physics_module}):
        with patch(
            "v2.modules.route_simulation.public.get_route_details",
            mock_route_service_module.get_route_details,
        ):
            result = await analyze_location_route(repo, lokasyon.id)

    assert result["distance_km"] == 600.0


async def test_analyze_location_route_error_response_raises_value_error(db_session):
    """If route service returns error key, raises ValueError."""
    from app.tests._helpers.seed import seed_lokasyon

    lokasyon = await seed_lokasyon(
        db_session,
        cikis_yeri="A",
        varis_yeri="B",
        cikis_lat=41.0,
        cikis_lon=29.0,
        varis_lat=39.9,
        varis_lon=32.8,
    )
    await db_session.commit()
    repo = LokasyonRepository(session=db_session)

    mock_route_service_module = MagicMock()
    mock_route_service_module.get_route_details = AsyncMock(
        return_value={"error": "no route found"}
    )

    with patch(
        "v2.modules.route_simulation.public.get_route_details",
        mock_route_service_module.get_route_details,
    ):
        with pytest.raises(ValueError, match="Analiz hatası"):
            await analyze_location_route(repo, lokasyon.id)
