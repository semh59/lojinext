"""POST/GET /api/v1/routes/simulate — Phase 1.5 + 2.2 endpoint testleri.

RouteSimulator'ı FastAPI dependency override ile mock'luyoruz — bu
DOKÜMANTE bir istisna (0-mock epiği Faz1 dilim4/5): RouteSimulator'ın
kendisi (fizik+ML pipeline: Mapbox/Open-Meteo/segment simülasyonu) ayrı
bir domain, Faz1 dilim4'te route_service/route_api/route_service_hybrid
için de aynı gerekçeyle mock'lu bırakıldı. Bu dosyada gerçek olan:
DB persist/reload (`get_db` hiç mock'lanmıyor — gerçek db_session'a
karşı `async_client` çalışıyor), auth, validation, serialization ve
502 fallback path'i.
"""

from __future__ import annotations

import pytest

from app.core.ml.segment_simulator import (
    SegmentOutput,
    SegmentSummary,
)
from app.core.services.route_simulator import (
    SimulationResult,
    get_route_simulator,
)

pytestmark = pytest.mark.integration


def _build_result() -> SimulationResult:
    """Minimal SimulationResult — 2 bucket."""
    segments = [
        SegmentOutput(
            length_km=0.5,
            sim_speed_kmh=85.0,
            sim_l_per_100km=28.0,
            sim_l_total=0.14,
            eta_sec=21.2,
            grade_pct=2.0,
            road_class="motorway",
        ),
        SegmentOutput(
            length_km=0.5,
            sim_speed_kmh=80.0,
            sim_l_per_100km=30.0,
            sim_l_total=0.15,
            eta_sec=22.5,
            grade_pct=-1.0,
            road_class="trunk",
        ),
    ]
    summary = SegmentSummary(
        total_km=1.0,
        total_l=0.29,
        avg_l_per_100km=29.0,
        total_eta_sec=43.7,
        total_ascent_m=10.0,
        total_descent_m=5.0,
        segments=segments,
    )
    return SimulationResult(
        summary=summary,
        boundary_coords=[(28.0, 41.0), (28.005, 41.0), (28.01, 41.0)],
        elevations=[0.0, 10.0, 5.0],
        raw_segment_count=12,
        resampled_segment_count=2,
        elevation_coverage_pct=100.0,
        meta={"ton": 15.0, "arac_yasi": 5, "target_length_km": 0.5},
    )


class FakeSimulator:
    def __init__(self, result):
        self._result = result
        self.calls = []

    async def simulate(self, **kw):
        self.calls.append(kw)
        return self._result


@pytest.mark.asyncio
async def test_simulate_endpoint_returns_summary_and_segments(
    async_client, async_superuser_token_headers
):
    from app.main import app

    fake = FakeSimulator(_build_result())
    app.dependency_overrides[get_route_simulator] = lambda: fake

    try:
        resp = await async_client.post(
            "/api/v1/routes/simulate",
            json={
                "cikis_lat": 41.0082,
                "cikis_lon": 28.9784,
                "varis_lat": 39.9334,
                "varis_lon": 32.8597,
                "ton": 15.0,
                "arac_yasi": 5,
                "segment_length_m": 500,
            },
            headers=async_superuser_token_headers,
        )
    finally:
        app.dependency_overrides.pop(get_route_simulator, None)

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["summary"]["distance_km"] == 1.0
    assert body["summary"]["avg_l_per_100km"] == 29.0
    assert len(body["segments"]) == 2
    assert body["segments"][0]["road_class"] == "motorway"
    assert body["segments"][0]["seq"] == 0
    assert body["segments"][1]["seq"] == 1
    assert body["raw_segment_count"] == 12
    assert body["resampled_segment_count"] == 2
    assert body["elevation_coverage_pct"] == 100.0
    assert body["meta"]["ton"] == 15.0
    # Phase 2.2: persist sonrası simulation_id döner
    assert isinstance(body["simulation_id"], int) and body["simulation_id"] > 0
    assert "created_at" in body


@pytest.mark.asyncio
async def test_get_simulation_returns_persisted_record(
    async_client, async_superuser_token_headers
):
    """POST sonrası GET /simulate/{id} aynı veriyi döndürmeli."""
    from app.main import app

    fake = FakeSimulator(_build_result())
    app.dependency_overrides[get_route_simulator] = lambda: fake

    try:
        post_resp = await async_client.post(
            "/api/v1/routes/simulate",
            json={
                "cikis_lat": 41.0082,
                "cikis_lon": 28.9784,
                "varis_lat": 39.9334,
                "varis_lon": 32.8597,
            },
            headers=async_superuser_token_headers,
        )
        assert post_resp.status_code == 200
        sim_id = post_resp.json()["simulation_id"]
    finally:
        app.dependency_overrides.pop(get_route_simulator, None)

    # GET — simulator dependency'ye DOKUNULMAMALI (cache hit)
    get_resp = await async_client.get(
        f"/api/v1/routes/simulate/{sim_id}",
        headers=async_superuser_token_headers,
    )
    assert get_resp.status_code == 200
    body = get_resp.json()
    assert body["simulation_id"] == sim_id
    assert body["summary"]["distance_km"] == 1.0
    assert len(body["segments"]) == 2
    assert body["segments"][0]["road_class"] == "motorway"


@pytest.mark.asyncio
async def test_get_simulation_404_for_unknown_id(
    async_client, async_superuser_token_headers
):
    resp = await async_client.get(
        "/api/v1/routes/simulate/999999",
        headers=async_superuser_token_headers,
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_get_simulation_requires_auth(async_client):
    resp = await async_client.get("/api/v1/routes/simulate/1")
    assert resp.status_code in (401, 403)


@pytest.mark.asyncio
async def test_simulate_endpoint_502_when_provider_fails(
    async_client, async_superuser_token_headers
):
    from app.main import app

    fake = FakeSimulator(None)  # Mapbox failure
    app.dependency_overrides[get_route_simulator] = lambda: fake

    try:
        resp = await async_client.post(
            "/api/v1/routes/simulate",
            json={
                "cikis_lat": 41.0,
                "cikis_lon": 28.9,
                "varis_lat": 39.9,
                "varis_lon": 32.8,
            },
            headers=async_superuser_token_headers,
        )
    finally:
        app.dependency_overrides.pop(get_route_simulator, None)

    assert resp.status_code == 502
    # Error responses use the project envelope {"error": {"code", "message", ...}},
    # not FastAPI's default {"detail": ...} (HTTPException handler in main.py).
    message = resp.json()["error"]["message"]
    assert "Mapbox" in message or "provider" in message.lower()


@pytest.mark.asyncio
async def test_simulate_endpoint_validates_lat_bounds(
    async_client, async_superuser_token_headers
):
    resp = await async_client.post(
        "/api/v1/routes/simulate",
        json={
            "cikis_lat": 91.0,
            "cikis_lon": 28.9,  # invalid lat
            "varis_lat": 39.9,
            "varis_lon": 32.8,
        },
        headers=async_superuser_token_headers,
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_simulate_endpoint_validates_ton_bounds(
    async_client, async_superuser_token_headers
):
    resp = await async_client.post(
        "/api/v1/routes/simulate",
        json={
            "cikis_lat": 41.0,
            "cikis_lon": 28.9,
            "varis_lat": 39.9,
            "varis_lon": 32.8,
            "ton": -5,  # invalid
        },
        headers=async_superuser_token_headers,
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_simulate_endpoint_requires_auth(async_client):
    resp = await async_client.post(
        "/api/v1/routes/simulate",
        json={
            "cikis_lat": 41.0,
            "cikis_lon": 28.9,
            "varis_lat": 39.9,
            "varis_lon": 32.8,
        },
    )
    assert resp.status_code in (401, 403)


@pytest.mark.asyncio
async def test_simulate_endpoint_default_parameters(
    async_client, async_superuser_token_headers
):
    """ton/arac_yasi/segment_length_m default değerleri kullanılabilir."""
    from app.main import app

    fake = FakeSimulator(_build_result())
    app.dependency_overrides[get_route_simulator] = lambda: fake

    try:
        resp = await async_client.post(
            "/api/v1/routes/simulate",
            json={
                "cikis_lat": 41.0,
                "cikis_lon": 28.9,
                "varis_lat": 39.9,
                "varis_lon": 32.8,
            },
            headers=async_superuser_token_headers,
        )
    finally:
        app.dependency_overrides.pop(get_route_simulator, None)

    assert resp.status_code == 200
    # Simulator default args ile çağrılmış olmalı
    assert len(fake.calls) == 1
    call = fake.calls[0]
    assert call["ton"] == 15.0
    assert call["arac_yasi"] == 5
    assert call["target_length_km"] == 0.5
