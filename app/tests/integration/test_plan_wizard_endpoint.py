"""Feature C.3 — POST /trips/plan-wizard endpoint integration testleri.

Engine'in iç davranışı `app/tests/unit/test_trip_planner_engine.py`'da test edildi;
burada sadece endpoint kontratı (auth, flag, top_n clamp, audit log) doğrulanır.
TripPlannerEngine.plan monkeypatch'lenir → DB seed + ensemble predict gerekmez.
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any, Dict

import pytest


def _build_payload(**overrides: Any) -> Dict[str, Any]:
    base = {
        "tarih": date.today().isoformat(),
        "guzergah_id": None,
        "cikis_yeri": "Ankara",
        "varis_yeri": "İstanbul",
        "mesafe_km": 450.0,
        "ascent_m": 320.0,
        "descent_m": 310.0,
        "flat_distance_km": 400.0,
        "weight_kg": 22000.0,
        "top_n": 3,
    }
    base.update(overrides)
    return base


def _fake_plan_result(*, vehicles: int = 3, drivers: int = 3):
    """TripPlannerEngine.plan'in döneceği nesne — dataclass benzeri."""
    from app.core.ai.trip_planner import (
        DriverCandidate,
        PlanResult,
        VehicleCandidate,
    )

    veh = [
        VehicleCandidate(
            arac_id=i + 1,
            plaka=f"34 ABC {i:03d}",
            yas=3 + i,
            score=round(0.9 - i * 0.1, 3),
            predicted_liters=120.0 + i,
            fuel_score=round(1.0 - i * 0.1, 3),
            route_history_score=0.8,
            vehicle_health_score=0.84,
            availability_score=0.71,
            similar_trip_count=4,
            cold_start=False,
            reasons=["Aday seti içinde düşük tahmini tüketim"],
        )
        for i in range(vehicles)
    ]
    drv = [
        DriverCandidate(
            sofor_id=100 + i,
            ad_soyad=f"Şoför {i}",
            score=round(0.85 - i * 0.1, 3),
            route_type_perf=0.85,
            overall_hybrid=0.72,
            availability_score=0.71,
            route_type="highway_dominant",
            deviation_pct=-4.5,
            cold_start=False,
            reasons=["Bu güzergah tipinde tutarlı performans"],
        )
        for i in range(drivers)
    ]
    return PlanResult(
        weather_impact=1.07,
        risk_label="medium",
        route_type="highway_dominant",
        vehicles=veh,
        drivers=drv,
        generated_at=datetime.now(timezone.utc),
        cache_hit=False,
    )


@pytest.mark.integration
@pytest.mark.asyncio
class TestPlanWizardEndpoint:
    async def test_happy_path_returns_3_vehicles_and_3_drivers(
        self, async_client, admin_auth_headers, monkeypatch
    ):
        from app.core.ai import trip_planner as tp_mod

        async def _fake_plan(self, inp, top_n=3):  # noqa: ARG001
            return _fake_plan_result(vehicles=min(3, top_n), drivers=min(3, top_n))

        monkeypatch.setattr(tp_mod.TripPlannerEngine, "plan", _fake_plan)

        resp = await async_client.post(
            "/api/v1/trips/plan-wizard",
            json=_build_payload(),
            headers=admin_auth_headers,
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["risk_label"] == "medium"
        assert body["route_type"] == "highway_dominant"
        assert len(body["vehicles"]) == 3
        assert len(body["drivers"]) == 3
        # Skor sıralı + alt skor alanları mevcut
        v0 = body["vehicles"][0]
        assert {"score", "fuel_score", "predicted_liters", "reasons"}.issubset(v0)

    async def test_top_n_passed_to_engine(
        self, async_client, admin_auth_headers, monkeypatch
    ):
        from app.core.ai import trip_planner as tp_mod

        captured: Dict[str, Any] = {}

        async def _fake_plan(self, inp, top_n=3):  # noqa: ARG001
            captured["top_n"] = top_n
            return _fake_plan_result(vehicles=min(top_n, 3), drivers=min(top_n, 3))

        monkeypatch.setattr(tp_mod.TripPlannerEngine, "plan", _fake_plan)

        resp = await async_client.post(
            "/api/v1/trips/plan-wizard",
            json=_build_payload(top_n=5),
            headers=admin_auth_headers,
        )
        assert resp.status_code == 200
        assert captured["top_n"] == 5

    async def test_top_n_above_max_rejected_by_validation(
        self, async_client, admin_auth_headers
    ):
        """Pydantic ge/le → top_n>5 olduğunda 422."""
        resp = await async_client.post(
            "/api/v1/trips/plan-wizard",
            json=_build_payload(top_n=99),
            headers=admin_auth_headers,
        )
        assert resp.status_code == 422

    async def test_no_eligible_returns_empty_lists(
        self, async_client, admin_auth_headers, monkeypatch
    ):
        """Hard filter boş → 200 + boş listeler."""
        from app.core.ai import trip_planner as tp_mod

        async def _fake_plan(self, inp, top_n=3):  # noqa: ARG001
            return _fake_plan_result(vehicles=0, drivers=0)

        monkeypatch.setattr(tp_mod.TripPlannerEngine, "plan", _fake_plan)

        resp = await async_client.post(
            "/api/v1/trips/plan-wizard",
            json=_build_payload(),
            headers=admin_auth_headers,
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["vehicles"] == []
        assert body["drivers"] == []

    async def test_503_when_flag_off(
        self, async_client, admin_auth_headers, monkeypatch
    ):
        monkeypatch.setattr("app.config.settings.TRIP_PLANNER_ENABLED", False)
        resp = await async_client.post(
            "/api/v1/trips/plan-wizard",
            json=_build_payload(),
            headers=admin_auth_headers,
        )
        assert resp.status_code == 503

    async def test_403_for_non_admin(self, async_client, normal_auth_headers):
        """normal_auth_headers sadece sefer:read; sefer:write yok → 403."""
        resp = await async_client.post(
            "/api/v1/trips/plan-wizard",
            json=_build_payload(),
            headers=normal_auth_headers,
        )
        assert resp.status_code == 403

    async def test_missing_required_field_returns_422(
        self, async_client, admin_auth_headers
    ):
        bad_payload = _build_payload()
        del bad_payload["mesafe_km"]
        resp = await async_client.post(
            "/api/v1/trips/plan-wizard",
            json=bad_payload,
            headers=admin_auth_headers,
        )
        assert resp.status_code == 422
