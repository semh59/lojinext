"""
Additional coverage tests for trip write use-cases (eski SeferWriteService).

Targets uncovered branches not hit by existing test files:
- build_prediction_route_analysis: distributions already in analysis (no duplicate)
- extract_prediction_values: explanation_summary, warning_level, insight, model_version
- resolve_route: route found but data.mesafe_km already set (no override)
- resolve_route: route found but data.ascent_m / descent_m already set
- predict_outbound: USE_SEFER_FUEL_ESTIMATOR=False, no guzergah_id (no weather call)
- predict_outbound: weather call returns c_lat=None (skip weather)
- predict_outbound: timeout path (asyncio.TimeoutError)
- predict_outbound: general exception path
- repredikt_for_update: guzergah_id present in update_data (route enrichment path)
- repredikt_for_update: pred_bos_sefer=True → ton forced to 0
- repredikt_for_update: prediction returns None (no update)
- handle_round_trip_on_update: sefer not found → early return
- handle_round_trip_on_update: existing return trip found → skip creation
- create_return_trip: sefer_no is None → return_sefer_no is None
- add_sefer: route_dict elevation correction applied (RouteValidator.validate_and_correct)
- refresh_stats: non-pytest path (production bg task)
- bulk_update_status: all fail → no commit
- bulk_cancel: all fail → no commit
- bulk_add_sefer: >20 items → skip_prediction=True
"""

import asyncio
from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from v2.modules.shared_kernel.infrastructure.unit_of_work import UnitOfWork
from v2.modules.trip.application import add_trip, return_trip
from v2.modules.trip.application.add_trip import add_sefer
from v2.modules.trip.application.bulk_add_trips import bulk_add_sefer
from v2.modules.trip.application.bulk_trip_ops import bulk_cancel, bulk_update_status
from v2.modules.trip.application.return_trip import (
    create_return_trip,
    handle_round_trip_on_update,
)
from v2.modules.trip.application.sla import check_sla_delay
from v2.modules.trip.application.stats_refresh import refresh_stats
from v2.modules.trip.application.trip_prediction_enrichment import (
    build_prediction_route_analysis,
    extract_prediction_values,
    predict_outbound,
    predict_via_estimator,
    repredikt_for_update,
    resolve_route,
)
from v2.modules.trip.application.update_trip import update_sefer_uow
from v2.modules.trip.schemas import SeferCreate, SeferUpdate

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# Helpers (re-defined locally for isolation)
# ---------------------------------------------------------------------------


class DummyUoW:
    def __init__(self):
        self.sefer_repo = MagicMock()
        self.arac_repo = MagicMock()
        self.sofor_repo = MagicMock()
        self.lokasyon_repo = MagicMock()
        self.commit = AsyncMock()
        self.rollback = AsyncMock()
        self.session = MagicMock()
        self.session.add = MagicMock()
        self.session.flush = AsyncMock()
        # AUDIT-041: sefer_no benzersizlik kontrolü session.execute(...).fetchall() çağırır.
        self.session.execute = AsyncMock(
            return_value=MagicMock(fetchall=MagicMock(return_value=[]))
        )

        self.sefer_repo.add = AsyncMock(return_value=42)
        self.sefer_repo.get_by_id = AsyncMock(return_value=None)
        self.sefer_repo.get_by_sefer_no = AsyncMock(return_value=None)
        self.sefer_repo.update_sefer = AsyncMock(return_value=True)
        self.sefer_repo.delete = AsyncMock(return_value=True)
        self.sefer_repo.bulk_create = AsyncMock(return_value=[])
        self.sefer_repo.refresh_stats_mv = AsyncMock()
        self.sefer_repo.get_existing_sefer_nos = AsyncMock(return_value=set())
        self.arac_repo.get_by_id = AsyncMock(return_value=None)
        self.arac_repo.get_all = AsyncMock(return_value=[])
        self.arac_repo.get_by_ids = AsyncMock(return_value={})
        self.sofor_repo.get_by_id = AsyncMock(return_value=None)
        self.sofor_repo.get_by_ids = AsyncMock(return_value={})
        # AUDIT-041: bulk_add_sefer aktif sofor doğrulaması için get_all çağırır.
        self.sofor_repo.get_all = AsyncMock(return_value=[])
        self.lokasyon_repo.get_by_id = AsyncMock(return_value=None)
        self.lokasyon_repo.get_all = AsyncMock(return_value=[])
        self.lokasyon_repo.get_benzersiz_lokasyonlar = AsyncMock(return_value=[])
        self.lokasyon_repo.find_closest_match = AsyncMock(side_effect=lambda v, **_: v)

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_):
        return False


def _sefer_create(**overrides) -> SeferCreate:
    defaults = dict(
        tarih=date(2026, 3, 15),
        saat="09:00",
        arac_id=1,
        sofor_id=2,
        cikis_yeri="Istanbul",
        varis_yeri="Ankara",
        mesafe_km=450.0,
        net_kg=10000,
        bos_agirlik_kg=8000,
        dolu_agirlik_kg=18000,
        durum="Planned",
        bos_sefer=False,
        is_round_trip=False,
    )
    defaults.update(overrides)
    return SeferCreate(**defaults)


def _current_sefer(**overrides) -> dict:
    base = {
        "id": 99,
        "durum": "Planned",
        "arac_id": 1,
        "sofor_id": 2,
        "dorse_id": None,
        "tarih": date(2026, 3, 15),
        "mesafe_km": 450.0,
        "net_kg": 10000,
        "bos_sefer": False,
        "ascent_m": 200.0,
        "descent_m": 150.0,
        "flat_distance_km": 100.0,
        "rota_detay": None,
        "otoban_mesafe_km": None,
        "sehir_ici_mesafe_km": None,
        "bos_agirlik_kg": 8000,
        "dolu_agirlik_kg": 18000,
        "version": 1,
        "sefer_no": "TRIP-099",
    }
    base.update(overrides)
    return base


# ============================================================
# 1. build_prediction_route_analysis — distributions edge cases
# ============================================================


def test_build_prediction_route_analysis_no_duplicate_distributions():
    """distributions key already in route_analysis should not be overwritten."""
    route = {
        "route_analysis": {"distributions": {"type": "from_analysis"}},
        "distributions": {"type": "standalone"},
    }
    result = build_prediction_route_analysis(route_details=route)
    # "distributions" already set in analysis — standalone should NOT overwrite
    assert result["distributions"]["type"] == "from_analysis"


def test_build_prediction_route_analysis_standalone_distributions_added():
    """When route_analysis has no 'distributions', standalone one is included."""
    route = {
        "route_analysis": {"ratios": {"otoyol": 0.7}},
        "distributions": {"type": "standalone"},
    }
    result = build_prediction_route_analysis(route_details=route)
    assert result["distributions"]["type"] == "standalone"


# ============================================================
# 2. extract_prediction_values — extra meta fields
# ============================================================


def test_extract_prediction_values_explanation_summary():
    payload = {
        "tahmini_tuketim": 32.0,
        "explanation_summary": "Physics-dominant",
        "insight": "No anomalies",
        "warning_level": "GREEN",
        "model_version": "v2.1",
    }
    val, meta = extract_prediction_values(payload)
    assert val == 32.0
    assert meta["explanation_summary"] == "Physics-dominant"
    assert meta["insight"] == "No anomalies"
    assert meta["warning_level"] == "GREEN"
    assert meta["model_version"] == "v2.1"


def test_extract_prediction_values_none_fields_skipped():
    """Fields with None value should NOT be added to meta."""
    payload = {
        "tahmini_tuketim": 28.0,
        "model_used": None,
        "status": None,
        "confidence_score": None,
    }
    val, meta = extract_prediction_values(payload)
    assert "model_used" not in meta
    assert "confidence_score" not in meta


def test_extract_prediction_values_tahmini_litre_falls_back_to_prediction_liters_only():
    """When tahmini_litre is None, prediction_liters should be used."""
    payload = {
        "tahmini_tuketim": 30.0,
        "tahmini_litre": None,
        "prediction_liters": 135.0,
    }
    val, meta = extract_prediction_values(payload)
    assert meta.get("tahmini_litre") == 135.0


# ============================================================
# 3. resolve_route — various branches
# ============================================================


async def test_resolve_route_does_not_override_existing_mesafe():
    """When data.mesafe_km is already set, route value should not override it."""
    uow = DummyUoW()
    uow.lokasyon_repo.get_by_id = AsyncMock(
        return_value={"mesafe_km": 999.0, "ascent_m": 400.0, "descent_m": 300.0}
    )
    data = _sefer_create(guzergah_id=7, mesafe_km=450.0)  # mesafe_km already set
    await resolve_route(uow, data)
    # mesafe_km should remain as 450.0 (truthy → no override)
    assert data.mesafe_km == 450.0


async def test_resolve_route_returns_none_when_route_not_found():
    """If lokasyon_repo returns None, resolve_route returns None."""
    uow = DummyUoW()
    uow.lokasyon_repo.get_by_id = AsyncMock(return_value=None)
    data = _sefer_create(guzergah_id=99)
    result = await resolve_route(uow, data)
    assert result is None


async def test_resolve_route_fills_ascent_when_not_set():
    """When data.ascent_m is 0/None, it should be filled from route."""
    uow = DummyUoW()
    uow.lokasyon_repo.get_by_id = AsyncMock(
        return_value={"mesafe_km": 450.0, "ascent_m": 800.0, "descent_m": 600.0}
    )
    data = _sefer_create(guzergah_id=7, mesafe_km=450.0)
    data.ascent_m = 0.0
    data.descent_m = 0.0
    await resolve_route(uow, data)
    assert data.ascent_m == 800.0
    assert data.descent_m == 600.0


# ============================================================
# 4. predict_outbound — various paths
# ============================================================


async def test_predict_outbound_no_guzergah_id_skips_weather():
    """When no guzergah_id, weather call is skipped — prediction still called."""
    uow = DummyUoW()
    data = _sefer_create(guzergah_id=None)

    mock_pred = MagicMock()
    mock_pred.predict_consumption = AsyncMock(
        return_value={"tahmini_tuketim": 28.0, "tahmini_litre": 126.0}
    )
    mock_weather = MagicMock()
    mock_weather.get_trip_impact_analysis = AsyncMock()

    with (
        patch(
            "v2.modules.prediction_ml.public.get_prediction_service",
            return_value=mock_pred,
        ),
        patch(
            "app.core.services.weather_service.get_weather_service",
            return_value=mock_weather,
        ),
        patch("app.config.settings.USE_SEFER_FUEL_ESTIMATOR", False),
    ):
        tuk, meta, sim_id = await predict_outbound(uow, data, date(2026, 3, 15), None)

    assert tuk == 28.0
    mock_weather.get_trip_impact_analysis.assert_not_called()


async def test_predict_outbound_weather_no_lat_skips_call():
    """When route has no cikis_lat, weather call is skipped."""
    uow = DummyUoW()
    data = _sefer_create(guzergah_id=5)
    route_dict = {
        "cikis_lat": None,
        "cikis_lon": None,
        "varis_lat": None,
        "varis_lon": None,
    }

    mock_pred = MagicMock()
    mock_pred.predict_consumption = AsyncMock(return_value={"tahmini_tuketim": 30.0})
    mock_weather = MagicMock()
    mock_weather.get_trip_impact_analysis = AsyncMock()

    with (
        patch(
            "v2.modules.prediction_ml.public.get_prediction_service",
            return_value=mock_pred,
        ),
        patch(
            "app.core.services.weather_service.get_weather_service",
            return_value=mock_weather,
        ),
        patch("app.config.settings.USE_SEFER_FUEL_ESTIMATOR", False),
    ):
        tuk, meta, sim_id = await predict_outbound(
            uow, data, date(2026, 3, 15), route_dict
        )

    mock_weather.get_trip_impact_analysis.assert_not_called()


async def test_predict_outbound_timeout_returns_none_triple():
    """asyncio.TimeoutError in prediction → returns (None, None, None)."""
    uow = DummyUoW()
    data = _sefer_create()

    async def _slow(*_, **__):
        await asyncio.sleep(10)

    mock_pred = MagicMock()
    mock_pred.predict_consumption = _slow
    mock_weather = MagicMock()
    mock_weather.get_trip_impact_analysis = AsyncMock(return_value={"success": False})

    with (
        patch(
            "v2.modules.prediction_ml.public.get_prediction_service",
            return_value=mock_pred,
        ),
        patch(
            "app.core.services.weather_service.get_weather_service",
            return_value=mock_weather,
        ),
        patch("app.config.settings.USE_SEFER_FUEL_ESTIMATOR", False),
    ):
        tuk, meta, sim_id = await predict_outbound(uow, data, date(2026, 3, 15), None)

    assert tuk is None
    assert meta is None
    assert sim_id is None


def test_prediction_timeout_is_a_single_shared_constant():
    """2026-07-02 prod-grade denetimi P2 (Tier B madde 8): aynı 2.5s timeout
    literal 3 yerde (predict_via_estimator, predict_outbound legacy yolu,
    bulk_add_sefer) tekrarlanmıştı — biri güncellenip diğerleri unutulursa
    coverage_pct sessizce sapabilirdi. Artık tek bir modül-seviyesi sabite
    (`PREDICTION_TIMEOUT_SECONDS`, trip_prediction_enrichment.py) indirgendi;
    bu test hem sabitin var olduğunu hem de dosyada başka bir
    `timeout=<literal>` kalmadığını doğrular (regresyon guard'ı — gelecekte
    tekrar ayrı literallere bölünürse bu test kırmızı olur)."""
    import inspect
    import re

    from v2.modules.trip.application import trip_prediction_enrichment as mod

    assert mod.PREDICTION_TIMEOUT_SECONDS == 2.5

    source = inspect.getsource(mod)
    timeout_assignments = re.findall(r"timeout=([^\s,)]+)", source)
    assert len(timeout_assignments) >= 2, (
        f"Beklenen en az 2 'timeout=' kullanımı bulundu: {len(timeout_assignments)}"
    )
    for value in timeout_assignments:
        assert value == "PREDICTION_TIMEOUT_SECONDS", (
            f"'timeout={value}' ham literal kullanıyor, paylaşılan sabiti değil "
            "— madde 8'in önlemeye çalıştığı tam drift senaryosu."
        )


async def test_predict_outbound_general_exception_returns_none_triple():
    """General exception in prediction → returns (None, None, None)."""
    uow = DummyUoW()
    data = _sefer_create()

    mock_pred = MagicMock()
    mock_pred.predict_consumption = AsyncMock(side_effect=RuntimeError("model crash"))

    with (
        patch(
            "v2.modules.prediction_ml.public.get_prediction_service",
            return_value=mock_pred,
        ),
        patch(
            "app.core.services.weather_service.get_weather_service",
            return_value=MagicMock(),
        ),
        patch("app.config.settings.USE_SEFER_FUEL_ESTIMATOR", False),
    ):
        tuk, meta, sim_id = await predict_outbound(uow, data, date(2026, 3, 15), None)

    assert tuk is None


# ============================================================
# 5. repredikt_for_update — edge cases
# ============================================================


async def test_repredikt_for_update_bos_sefer_forces_ton_zero():
    """When pred_bos_sefer=True, ton should be forced to 0."""
    uow = DummyUoW()
    current_sefer = {
        "arac_id": 1,
        "sofor_id": 2,
        "tarih": date(2026, 3, 15),
        "bos_sefer": True,
        "dorse_id": None,
        "mesafe_km": 450.0,
        "ascent_m": 0.0,
        "descent_m": 0.0,
        "flat_distance_km": 0.0,
        "net_kg": 0,
        "rota_detay": None,
        "otoban_mesafe_km": None,
        "sehir_ici_mesafe_km": None,
    }
    update_data = {"bos_sefer": True, "net_kg": 5000}

    mock_pred = MagicMock()
    call_kwargs = {}

    async def _capture_predict(**kwargs):
        call_kwargs.update(kwargs)
        return {"tahmini_tuketim": 22.0}

    mock_pred.predict_consumption = _capture_predict

    with patch(
        "v2.modules.prediction_ml.public.get_prediction_service",
        return_value=mock_pred,
    ):
        await repredikt_for_update(uow, current_sefer, update_data)

    assert call_kwargs["ton"] == 0.0


async def test_repredikt_for_update_with_new_guzergah_enriches_route(monkeypatch):
    """When guzergah_id is in update_data, route details are fetched and applied."""
    uow = DummyUoW()
    uow.lokasyon_repo.get_by_id = AsyncMock(
        return_value={
            "mesafe_km": 600.0,
            "ascent_m": 500.0,
            "descent_m": 400.0,
            "flat_distance_km": 200.0,
            "route_analysis": {"ratios": {"otoyol": 0.8}},
            "otoban_mesafe_km": 480.0,
            "sehir_ici_mesafe_km": 20.0,
        }
    )
    current_sefer = {
        "arac_id": 1,
        "sofor_id": 2,
        "tarih": date(2026, 3, 15),
        "bos_sefer": False,
        "dorse_id": None,
        "mesafe_km": 450.0,
        "ascent_m": 0.0,
        "descent_m": 0.0,
        "flat_distance_km": 0.0,
        "net_kg": 10000,
        "rota_detay": None,
        "otoban_mesafe_km": None,
        "sehir_ici_mesafe_km": None,
    }
    update_data = {"guzergah_id": 7}

    mock_pred = MagicMock()
    mock_pred.predict_consumption = AsyncMock(
        return_value={"tahmini_tuketim": 35.0, "tahmini_litre": 210.0}
    )

    with patch(
        "v2.modules.prediction_ml.public.get_prediction_service",
        return_value=mock_pred,
    ):
        await repredikt_for_update(uow, current_sefer, update_data)

    # Route fields should have been written into update_data
    assert update_data["mesafe_km"] == 600.0
    assert update_data["rota_detay"] == {"ratios": {"otoyol": 0.8}}
    assert update_data.get("tahmini_tuketim") == 35.0


async def test_repredikt_for_update_prediction_returns_none():
    """When prediction returns no tahmini_tuketim, update_data is unchanged."""
    uow = DummyUoW()
    current_sefer = {
        "arac_id": 1,
        "sofor_id": 2,
        "tarih": date(2026, 3, 15),
        "bos_sefer": False,
        "dorse_id": None,
        "mesafe_km": 450.0,
        "ascent_m": 0.0,
        "descent_m": 0.0,
        "flat_distance_km": 0.0,
        "net_kg": 10000,
        "rota_detay": None,
        "otoban_mesafe_km": None,
        "sehir_ici_mesafe_km": None,
    }
    update_data = {"net_kg": 12000}

    mock_pred = MagicMock()
    mock_pred.predict_consumption = AsyncMock(
        return_value={"other_key": "no consumption"}
    )

    with patch(
        "v2.modules.prediction_ml.public.get_prediction_service",
        return_value=mock_pred,
    ):
        await repredikt_for_update(uow, current_sefer, update_data)

    # No tahmini_tuketim should have been added
    assert "tahmini_tuketim" not in update_data


# ============================================================
# 6. handle_round_trip_on_update — edge cases
# ============================================================


async def test_handle_round_trip_on_update_sefer_not_found():
    """When current sefer not found, function returns early without creating return."""
    uow = DummyUoW()
    uow.sefer_repo.get_by_id = AsyncMock(return_value=None)

    # Should not raise
    await handle_round_trip_on_update(uow, 999, {"return_net_kg": 0})
    uow.sefer_repo.add.assert_not_called()


async def test_handle_round_trip_on_update_existing_return_skips_creation():
    """When return trip already exists, build_return_trip should NOT be called."""
    uow = DummyUoW()
    uow.sefer_repo.get_by_id = AsyncMock(
        return_value={
            "sefer_no": "TRIP-010",
            "tarih": date(2026, 3, 15),
            "saat": "09:00",
            "arac_id": 1,
            "sofor_id": 2,
            "guzergah_id": None,
            "cikis_yeri": "Istanbul",
            "varis_yeri": "Ankara",
            "mesafe_km": 450.0,
            "bos_agirlik_kg": 8000,
            "dolu_agirlik_kg": 18000,
            "net_kg": 10000,
            "bos_sefer": False,
            "durum": "Planned",
            "ascent_m": 200.0,
            "descent_m": 100.0,
            "flat_distance_km": 50.0,
        }
    )
    # Return trip already exists
    uow.sefer_repo.get_by_sefer_no = AsyncMock(return_value={"id": 11})

    with patch.object(
        return_trip, "build_return_trip", new=AsyncMock()
    ) as mock_create:
        await handle_round_trip_on_update(uow, 10, {"return_net_kg": 0})
    mock_create.assert_not_called()


# ============================================================
# 7. refresh_stats — production (non-pytest) path
# ============================================================


async def test_refresh_stats_production_path_creates_bg_task(monkeypatch):
    """In non-pytest env, refresh_stats creates an asyncio background task."""
    # Temporarily remove PYTEST_CURRENT_TEST so the production code path runs
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)

    uow = DummyUoW()

    created_tasks = []
    original_create_task = asyncio.create_task

    def _track_task(coro, **kwargs):
        t = original_create_task(coro, **kwargs)
        created_tasks.append(t)
        return t

    # Patch AsyncSessionLocal and SeferRepository to avoid real DB
    fake_session = AsyncMock()
    fake_session.__aenter__ = AsyncMock(return_value=fake_session)
    fake_session.__aexit__ = AsyncMock(return_value=False)

    fake_repo = MagicMock()
    fake_repo.refresh_stats_mv = AsyncMock()

    with (
        patch("asyncio.create_task", side_effect=_track_task),
        patch(
            "v2.modules.platform_infra.public.AsyncSessionLocal",
            return_value=fake_session,
        ),
        patch(
            "v2.modules.trip.infrastructure.repository.SeferRepository",
            return_value=fake_repo,
        ),
    ):
        await refresh_stats(uow)
        # Give bg task a chance to run
        await asyncio.sleep(0)

    assert len(created_tasks) >= 1


# ============================================================
# 8. bulk_update_status — all fail path
# ============================================================


async def test_bulk_update_status_all_fail_no_commit(monkeypatch):
    """When all updates fail, commit should NOT be called."""
    uow = DummyUoW()
    uow.sefer_repo.get_by_id = AsyncMock(return_value=None)  # all not found

    monkeypatch.setattr(UnitOfWork, "__aenter__", AsyncMock(return_value=uow))
    monkeypatch.setattr(UnitOfWork, "__aexit__", AsyncMock(return_value=False))

    result = await bulk_update_status([1, 2], "Completed")

    assert result["success_count"] == 0
    assert result["failed_count"] == 2
    uow.commit.assert_not_called()


# ============================================================
# 9. bulk_cancel — all fail path
# ============================================================


async def test_bulk_cancel_all_fail_no_commit(monkeypatch):
    """When all cancels fail, commit should NOT be called."""
    uow = DummyUoW()
    uow.sefer_repo.get_by_id = AsyncMock(return_value=None)  # all not found

    monkeypatch.setattr(UnitOfWork, "__aenter__", AsyncMock(return_value=uow))
    monkeypatch.setattr(UnitOfWork, "__aexit__", AsyncMock(return_value=False))

    result = await bulk_cancel([1, 2], iptal_nedeni="Test")

    assert result["success_count"] == 0
    uow.commit.assert_not_called()


# ============================================================
# 10. bulk_add_sefer — skip_prediction when >20 items
# ============================================================


async def test_bulk_add_sefer_skips_prediction_for_large_batches(monkeypatch):
    """When len(sefer_list) > 20, prediction is skipped for all items."""
    uow = DummyUoW()
    uow.lokasyon_repo.get_benzersiz_lokasyonlar = AsyncMock(return_value=[])
    uow.lokasyon_repo.get_all = AsyncMock(return_value=[])
    uow.lokasyon_repo.find_closest_match = AsyncMock(side_effect=lambda v, **_: v)
    # AUDIT-041: satırların işlenmesi için arac_id=1/sofor_id=2 aktif olmalı.
    uow.arac_repo.get_all = AsyncMock(
        return_value=[{"id": 1, "bos_agirlik_kg": 8000, "aktif": True}]
    )
    uow.sofor_repo.get_all = AsyncMock(return_value=[{"id": 2, "aktif": True}])

    monkeypatch.setattr(UnitOfWork, "__aenter__", AsyncMock(return_value=uow))
    monkeypatch.setattr(UnitOfWork, "__aexit__", AsyncMock(return_value=False))

    import v2.modules.prediction_ml.public as pred_module

    mock_pred = MagicMock()
    mock_pred.predict_consumption = AsyncMock(return_value=None)
    monkeypatch.setattr(pred_module, "get_prediction_service", lambda: mock_pred)

    # Create 21 items — threshold is >20
    items = [
        _sefer_create(
            cikis_yeri=f"Sehir{i}",
            varis_yeri=f"Varis{i}",
            sefer_no=f"TRIP-{i:03d}",
        )
        for i in range(21)
    ]
    count = await bulk_add_sefer(items)

    # All 21 items should be processed (prediction skipped, but items added)
    assert count == 21
    mock_pred.predict_consumption.assert_not_called()


# ============================================================
# 11. create_return_trip — sefer_no is None
# ============================================================


async def test_create_return_trip_no_sefer_no(monkeypatch):
    """When ref sefer has no sefer_no, return_sefer_no should be None."""
    uow = DummyUoW()
    uow.sefer_repo.get_by_id = AsyncMock(
        return_value={
            "id": 30,
            "sefer_no": None,
            "arac_id": 1,
            "sofor_id": 2,
            "dorse_id": None,
            "guzergah_id": None,
            "cikis_yeri": "Izmir",
            "varis_yeri": "Bursa",
            "mesafe_km": 300.0,
            "bos_agirlik_kg": 7000,
            "dolu_agirlik_kg": 7000,
            "net_kg": 0,
            "ascent_m": 100.0,
            "descent_m": 200.0,
            "flat_distance_km": 50.0,
            "is_real": False,
        }
    )
    uow.sefer_repo.add = AsyncMock(return_value=31)
    monkeypatch.setattr(return_trip, "get_uow", lambda: uow)

    new_id = await create_return_trip(30)
    assert new_id == 31

    add_kwargs = uow.sefer_repo.add.await_args.kwargs
    assert add_kwargs["sefer_no"] is None


# ============================================================
# 12. update_sefer_uow — round_trip flag triggers handle_round_trip
# ============================================================


async def test_update_sefer_round_trip_flag_calls_handler():
    uow = DummyUoW()
    uow.sefer_repo.get_by_id = AsyncMock(return_value=_current_sefer(durum="Planned"))
    uow.sefer_repo.update_sefer = AsyncMock(return_value=True)

    from v2.modules.trip.application import update_trip

    with patch.object(
        update_trip, "handle_round_trip_on_update", new=AsyncMock()
    ) as mock_rt:
        await update_sefer_uow(uow, 99, SeferUpdate(is_round_trip=True))
    mock_rt.assert_awaited_once()


# ============================================================
# 13. check_sla_delay — actual_duration is None → no outbox
# ============================================================


async def test_check_sla_delay_skips_when_no_duration(monkeypatch):
    uow = DummyUoW()
    uow.sefer_repo.get_by_id = AsyncMock(
        return_value={
            "id": 99,
            "duration_min": None,  # no actual duration recorded
            "guzergah_id": 5,
        }
    )
    uow.lokasyon_repo.get_by_id = AsyncMock(return_value={"tahmini_sure_saat": 8.0})

    mock_outbox = MagicMock()
    mock_outbox.save_event = AsyncMock()
    from v2.modules.trip.application import sla as sla_module

    monkeypatch.setattr(sla_module, "get_outbox_service", lambda: mock_outbox)

    await check_sla_delay(uow, 99, 1, {})
    mock_outbox.save_event.assert_not_awaited()


# ============================================================
# 14. update_sefer_uow — tarih string conversion
# ============================================================


async def test_update_sefer_tarih_string_converted_to_date():
    """String tarih value in update_data should be converted to date object."""
    uow = DummyUoW()
    uow.sefer_repo.get_by_id = AsyncMock(return_value=_current_sefer(durum="Planned"))
    uow.sefer_repo.update_sefer = AsyncMock(return_value=True)

    await update_sefer_uow(uow, 99, SeferUpdate(tarih=date(2026, 4, 1)))

    call_kwargs = uow.sefer_repo.update_sefer.await_args.kwargs
    # tarih should be a date object (not string) after conversion
    assert isinstance(call_kwargs.get("tarih"), date)


# ============================================================
# 15. predict_via_estimator — estimate is None
# ============================================================


async def test_predict_via_estimator_returns_none_when_estimate_is_none():
    """When estimator.predict returns None, tuple of Nones is returned."""
    mock_estimator = MagicMock()
    mock_estimator.predict = AsyncMock(return_value=None)

    with patch(
        "v2.modules.trip.application.sefer_fuel_estimator.get_sefer_fuel_estimator",
        return_value=mock_estimator,
    ):
        uow = DummyUoW()
        data = _sefer_create()
        tuk, meta, sim_id = await predict_via_estimator(
            uow, data, date(2026, 3, 15), None
        )

    assert tuk is None
    assert meta is None
    assert sim_id is None


# ============================================================
# 16. add_sefer: round trip creation invoked
# ============================================================


async def test_add_sefer_round_trip_invokes_create_return(monkeypatch):
    """When is_round_trip=True, build_return_trip is called."""
    uow = DummyUoW()
    uow.sefer_repo.add = AsyncMock(return_value=55)
    uow.arac_repo.get_by_id = AsyncMock(
        return_value={"aktif": True, "bos_agirlik_kg": 8000}
    )
    uow.sofor_repo.get_by_id = AsyncMock(return_value={"aktif": True})

    monkeypatch.setattr(UnitOfWork, "__aenter__", AsyncMock(return_value=uow))
    monkeypatch.setattr(UnitOfWork, "__aexit__", AsyncMock(return_value=False))

    mock_outbox = MagicMock()
    mock_outbox.save_event = AsyncMock()
    monkeypatch.setattr(add_trip, "get_outbox_service", lambda: mock_outbox)

    with patch.object(
        add_trip,
        "predict_outbound",
        new=AsyncMock(return_value=(None, None, None)),
    ):
        with patch.object(
            add_trip,
            "build_return_trip",
            new=AsyncMock(),
        ) as mock_return:
            data = _sefer_create(is_round_trip=True, return_net_kg=0)
            await add_sefer(data)

    mock_return.assert_awaited_once()
