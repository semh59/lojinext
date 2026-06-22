"""Tests for driver x route-type coefficient module."""

from app.tests._helpers.seed import seed_arac, seed_sefer, seed_sofor


def test_classify_route_highway_dominant():
    from app.core.ml.driver_route_profile import classify_route

    analysis = {"motorway": {"flat": 600.0, "up": 10.0, "down": 10.0}}
    assert classify_route(analysis) == "highway_dominant"


def test_classify_route_mountain():
    from app.core.ml.driver_route_profile import classify_route

    # ascent_m/total > 15 triggers mountain
    analysis = {
        "primary": {"flat": 0.0, "up": 5.0, "down": 5.0},
        "ascent_m": 300.0,  # 300 / 10 = 30 > 15
    }
    assert classify_route(analysis) == "mountain"


def test_classify_route_urban():
    from app.core.ml.driver_route_profile import classify_route

    analysis = {
        "residential": {"flat": 40.0, "up": 2.0, "down": 2.0},
        "primary": {"flat": 60.0, "up": 5.0, "down": 5.0},
    }
    assert classify_route(analysis) == "urban"


def test_classify_route_empty_returns_mixed():
    from app.core.ml.driver_route_profile import classify_route

    assert classify_route({}) == "mixed"


async def test_coefficient_returns_neutral_when_insufficient_data(db_session):
    """Must return 1.0 when fewer than min_trips exist."""
    from app.core.ml.driver_route_profile import get_driver_route_coefficient

    sofor = await seed_sofor(db_session)
    await db_session.commit()

    result = await get_driver_route_coefficient(
        sofor_id=sofor.id, route_type="highway_dominant"
    )
    assert result == 1.0


async def test_coefficient_returns_median_ratio(db_session):
    """With enough trips, must return median of gercek/tahmini ratios."""
    # Ratios: 1.05, 1.10, 1.075, 1.025, 1.00 → sorted: 1.00, 1.025, 1.05, 1.075, 1.10 → median = 1.05
    from app.core.ml.driver_route_profile import get_driver_route_coefficient

    pairs = [(42.0, 40.0), (44.0, 40.0), (43.0, 40.0), (41.0, 40.0), (40.0, 40.0)]
    arac = await seed_arac(db_session)
    sofor = await seed_sofor(db_session)
    for g, t in pairs:
        await seed_sefer(
            db_session,
            arac_id=arac.id,
            sofor_id=sofor.id,
            durum="Completed",
            tuketim=g,
            tahmini_tuketim=t,
            rota_detay={"motorway": {"flat": 600.0}},
        )
    await db_session.commit()

    result = await get_driver_route_coefficient(
        sofor_id=sofor.id, route_type="highway_dominant"
    )
    assert 1.0 <= result <= 1.15
