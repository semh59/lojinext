import pytest

from app.database.repositories.route_repo import RouteRepository

pytestmark = pytest.mark.integration


@pytest.mark.asyncio
async def test_route_repo_save_route_persists_extended_cache_fields(db_session):
    repo = RouteRepository(session=db_session)
    payload = {
        "origin_lat": 40.0,
        "origin_lon": 29.0,
        "dest_lat": 39.0,
        "dest_lon": 32.0,
        "distance_km": 120.5,
        "duration_min": 95.0,
        "ascent_m": 320.0,
        "descent_m": 180.0,
        "flat_distance_km": 90.0,
        "otoban_mesafe_km": 108.0,
        "sehir_ici_mesafe_km": 12.5,
        "difficulty": "Normal",
        "geometry": {"type": "LineString", "coordinates": [[29.0, 40.0], [32.0, 39.0]]},
        "route_analysis": {
            "ratios": {"otoyol": 0.55, "devlet_yolu": 0.35, "sehir_ici": 0.1}
        },
        "fuel_estimate_cache": {"tahmini_tuketim": 31.2},
    }

    route_id = await repo.save_route(payload)
    cached = await repo.get_by_coords(40.0, 29.0, 39.0, 32.0)

    assert route_id > 0
    assert cached is not None
    assert cached["otoban_mesafe_km"] == 108.0
    assert cached["sehir_ici_mesafe_km"] == 12.5
    assert cached["difficulty"] == "Normal"
    assert cached["route_analysis"]["ratios"]["otoyol"] == 0.55


@pytest.mark.asyncio
async def test_route_repo_save_route_updates_existing_record(db_session):
    repo = RouteRepository(session=db_session)
    base_payload = {
        "origin_lat": 41.0,
        "origin_lon": 29.0,
        "dest_lat": 38.0,
        "dest_lon": 27.0,
        "distance_km": 100.0,
        "duration_min": 80.0,
        "ascent_m": 200.0,
        "descent_m": 150.0,
        "flat_distance_km": 75.0,
        "otoban_mesafe_km": 88.0,
        "sehir_ici_mesafe_km": 12.0,
        "difficulty": "Kolay",
        "geometry": {"type": "LineString", "coordinates": [[29.0, 41.0], [27.0, 38.0]]},
        "route_analysis": {
            "ratios": {"otoyol": 0.5, "devlet_yolu": 0.38, "sehir_ici": 0.12}
        },
        "fuel_estimate_cache": {"tahmini_tuketim": 28.0},
    }

    route_id = await repo.save_route(base_payload)
    updated_id = await repo.save_route(
        {
            **base_payload,
            "distance_km": 101.0,
            "otoban_mesafe_km": 90.0,
            "route_analysis": {
                "ratios": {"otoyol": 0.52, "devlet_yolu": 0.33, "sehir_ici": 0.15}
            },
        }
    )
    cached = await repo.get_by_coords(41.0, 29.0, 38.0, 27.0)

    assert updated_id == route_id
    assert cached["distance_km"] == 101.0
    assert cached["otoban_mesafe_km"] == 90.0
    assert cached["route_analysis"]["ratios"]["sehir_ici"] == 0.15
