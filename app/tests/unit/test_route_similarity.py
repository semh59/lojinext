"""Tests for route similarity engine."""

import numpy as np
import pytest

from app.tests._helpers.seed import seed_arac, seed_sefer, seed_sofor

pytestmark = pytest.mark.integration


def test_encode_route_returns_8d_vector():
    from app.core.ml.route_similarity import encode_route

    analysis = {
        "motorway": {"flat": 100.0, "up": 10.0, "down": 10.0},
        "trunk": {"flat": 50.0},
        "primary": {},
        "secondary": {},
        "residential": {"flat": 5.0},
        "other": {},
        "ascent_m": 800.0,
        "descent_m": 750.0,
    }
    vec = encode_route(analysis)
    assert vec.shape == (8,)
    assert vec.dtype == np.float32


def test_cosine_similarity_identical():
    from app.core.ml.route_similarity import cosine_similarity

    v = np.array([1.0, 0.5, 0.3, 0.0, 0.2, 0.0, 500.0, 300.0], dtype=np.float32)
    assert cosine_similarity(v, v) == pytest.approx(1.0)


def test_cosine_similarity_orthogonal():
    from app.core.ml.route_similarity import cosine_similarity

    a = np.array([1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0], dtype=np.float32)
    b = np.array([0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0], dtype=np.float32)
    assert cosine_similarity(a, b) == pytest.approx(0.0)


def test_cosine_similarity_zero_vectors():
    from app.core.ml.route_similarity import cosine_similarity

    z = np.zeros(8, dtype=np.float32)
    assert cosine_similarity(z, z) == 0.0


async def test_find_similar_trips_distance_filter(db_session):
    """Trips with >20% distance difference must be filtered out."""
    from app.core.ml.route_similarity import find_similar_trips

    arac = await seed_arac(db_session)
    sofor = await seed_sofor(db_session)
    await seed_sefer(
        db_session,
        arac_id=arac.id,
        sofor_id=sofor.id,
        mesafe_km=500.0,
        tuketim=80.0,
        rota_detay={"motorway": {"flat": 400.0}},
    )
    await db_session.commit()

    result = await find_similar_trips({}, mesafe_km=100.0)
    assert result == []


async def test_find_similar_trips_returns_sorted_by_similarity(db_session):
    """Results must be sorted by similarity descending."""
    from app.core.ml.route_similarity import find_similar_trips

    vec = {"motorway": {"flat": 100.0}, "ascent_m": 500.0, "descent_m": 400.0}
    arac = await seed_arac(db_session)
    sofor = await seed_sofor(db_session)
    await seed_sefer(
        db_session,
        arac_id=arac.id,
        sofor_id=sofor.id,
        mesafe_km=100.0,
        tuketim=50.0,
        rota_detay=vec,
    )
    await seed_sefer(
        db_session,
        arac_id=arac.id,
        sofor_id=sofor.id,
        mesafe_km=100.0,
        tuketim=55.0,
        rota_detay=vec,
    )
    await db_session.commit()

    result = await find_similar_trips(vec, mesafe_km=100.0)
    assert len(result) >= 1
    if len(result) > 1:
        assert result[0]["similarity"] >= result[1]["similarity"]
