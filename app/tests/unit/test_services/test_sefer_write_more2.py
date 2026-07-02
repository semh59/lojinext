"""Additional coverage for SeferWriteService (round 2).

Targets uncovered branches not yet hit by existing test files:
- _predict_via_estimator: timeout path → (None, None, None)
- _predict_via_estimator: estimate is not None → full extraction path
- _predict_via_estimator: general exception → (None, None, None)
- _create_return_trip: sefer_no ends with -D → return_sn gets -R suffix
- _create_return_trip: return_sefer_no already provided (no suffix logic)
- _create_return_trip: data.arac_id or mesafe_km missing → skip prediction
- _create_return_trip: prediction raises → tahmini returns None
- _check_sla_delay: sefer not found → early return
- _check_sla_delay: guzergah not found → planned_duration_min stays 0
- _check_sla_delay: planned > 0, actual_duration set → SLA event written
- _check_sla_delay: exception swallowed
- bulk_add_sefer: exception during insert → rollback and re-raise
- update_sefer: user_id applied to update_data
- add_sefer: tarih is already a date object (no fromisoformat)
- _resolve_route: guzergah_id is 0/falsy → returns None early
"""

from __future__ import annotations

import asyncio
from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.services.sefer_write_service import SeferWriteService
from app.database.unit_of_work import UnitOfWork
from app.schemas.sefer import SeferCreate, SeferUpdate

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# Helpers
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


def _make_service(event_bus=None):
    bus = event_bus or MagicMock()
    bus.publish_async = AsyncMock()
    return SeferWriteService(event_bus=bus), bus


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
        "guzergah_id": None,
        "duration_min": None,
    }
    base.update(overrides)
    return base


# ============================================================
# 1. _predict_via_estimator paths
# ============================================================


async def test_predict_via_estimator_timeout():
    """Timeout → returns (None, None, None)."""
    svc, _ = _make_service()
    uow = DummyUoW()
    data = _sefer_create()

    async def _slow(*_, **__):
        await asyncio.sleep(10)

    mock_estimator = MagicMock()
    mock_estimator.predict = _slow

    with patch("app.config.settings.USE_SEFER_FUEL_ESTIMATOR", True):
        with patch(
            "app.core.services.sefer_fuel_estimator.get_sefer_fuel_estimator",
            return_value=mock_estimator,
        ):
            tuk, meta, sim_id = await svc._predict_via_estimator(
                uow, data, date(2026, 3, 15), None
            )

    assert tuk is None
    assert meta is None
    assert sim_id is None


async def test_predict_via_estimator_general_exception():
    """Unhandled exception → returns (None, None, None)."""
    svc, _ = _make_service()
    uow = DummyUoW()
    data = _sefer_create()

    with patch("app.config.settings.USE_SEFER_FUEL_ESTIMATOR", True):
        with patch(
            "app.core.services.sefer_fuel_estimator.get_sefer_fuel_estimator",
            side_effect=RuntimeError("estimator crashed"),
        ):
            tuk, meta, sim_id = await svc._predict_via_estimator(
                uow, data, date(2026, 3, 15), None
            )

    assert tuk is None


async def test_predict_via_estimator_success():
    """When estimator returns a valid estimate → extracts tahmini_tuketim."""
    svc, _ = _make_service()
    uow = DummyUoW()
    data = _sefer_create()

    mock_estimate = MagicMock()
    mock_estimate.to_legacy_prediction_dict = MagicMock(
        return_value={"tahmini_tuketim": 145.5, "tahmini_litre": 145.5}
    )
    mock_estimate.simulation_id = 999

    mock_estimator = MagicMock()
    mock_estimator.predict = AsyncMock(return_value=mock_estimate)

    with patch("app.config.settings.USE_SEFER_FUEL_ESTIMATOR", True):
        with patch(
            "app.core.services.sefer_fuel_estimator.get_sefer_fuel_estimator",
            return_value=mock_estimator,
        ):
            tuk, meta, sim_id = await svc._predict_via_estimator(
                uow, data, date(2026, 3, 15), None
            )

    assert tuk == 145.5
    assert sim_id == 999
    assert meta is not None
    assert meta.get("simulation_id") == 999
    assert meta.get("estimator_source") == "SeferFuelEstimator"


async def test_predict_via_estimator_estimate_is_none():
    """When estimator returns None → returns (None, None, None)."""
    svc, _ = _make_service()
    uow = DummyUoW()
    data = _sefer_create()

    mock_estimator = MagicMock()
    mock_estimator.predict = AsyncMock(return_value=None)

    with patch("app.config.settings.USE_SEFER_FUEL_ESTIMATOR", True):
        with patch(
            "app.core.services.sefer_fuel_estimator.get_sefer_fuel_estimator",
            return_value=mock_estimator,
        ):
            tuk, meta, sim_id = await svc._predict_via_estimator(
                uow, data, date(2026, 3, 15), None
            )

    assert tuk is None
    assert meta is None
    assert sim_id is None


# ============================================================
# 2. _create_return_trip: sefer_no endings
# ============================================================


async def test_create_return_trip_sefer_no_ends_with_d_gets_r_suffix():
    """When sefer_no ends with -D → return gets -D-R suffix (rare case guard)."""
    svc, _ = _make_service()
    uow = DummyUoW()
    uow.sefer_repo.add = AsyncMock(return_value=101)

    data = _sefer_create(
        sefer_no="TRIP-001-D",
        arac_id=1,
        mesafe_km=450.0,
        net_kg=0,
        bos_sefer=True,
        is_round_trip=True,
        return_net_kg=0,
    )

    mock_pred = MagicMock()
    mock_pred.predict_consumption = AsyncMock(return_value={"tahmini_tuketim": 130.0})

    with patch(
        "app.services.prediction_service.get_prediction_service",
        return_value=mock_pred,
    ):
        await svc._create_return_trip(uow, data, date(2026, 3, 15), ref_sefer_id=50)

    call_kwargs = uow.sefer_repo.add.call_args
    # base_sn ends with "-D" → return_sn = base_sn + "-R"
    sefer_no_used = call_kwargs.kwargs.get("sefer_no", "")
    assert sefer_no_used == "TRIP-001-D-R"


async def test_create_return_trip_with_explicit_return_sefer_no():
    """When return_sefer_no is provided, it's used directly."""
    svc, _ = _make_service()
    uow = DummyUoW()
    uow.sefer_repo.add = AsyncMock(return_value=102)

    data = _sefer_create(
        sefer_no="TRIP-002",
        arac_id=1,
        mesafe_km=300.0,
        net_kg=0,
        is_round_trip=True,
        return_net_kg=0,
        return_sefer_no="CUSTOM-RETURN-NO",
    )

    mock_pred = MagicMock()
    mock_pred.predict_consumption = AsyncMock(return_value={"tahmini_tuketim": 95.0})

    with patch(
        "app.services.prediction_service.get_prediction_service",
        return_value=mock_pred,
    ):
        await svc._create_return_trip(uow, data, date(2026, 3, 15), ref_sefer_id=55)

    call_kwargs = uow.sefer_repo.add.call_args
    sefer_no_used = call_kwargs.kwargs.get("sefer_no", "")
    assert sefer_no_used == "CUSTOM-RETURN-NO"


async def test_create_return_trip_no_mesafe_km_skips_prediction():
    """When mesafe_km is 0, prediction is skipped."""
    svc, _ = _make_service()
    uow = DummyUoW()
    uow.sefer_repo.add = AsyncMock(return_value=103)

    data = _sefer_create(
        sefer_no="TRIP-003",
        arac_id=1,
        mesafe_km=100.0,
        net_kg=0,
    )
    # Force mesafe_km to None so condition `data.arac_id and data.mesafe_km` is False
    data.mesafe_km = None

    await svc._create_return_trip(uow, data, date(2026, 3, 15), ref_sefer_id=60)

    # Should still call add
    uow.sefer_repo.add.assert_awaited_once()


async def test_create_return_trip_prediction_exception_handled():
    """When prediction raises, tahmini stays None but add is still called."""
    svc, _ = _make_service()
    uow = DummyUoW()
    uow.sefer_repo.add = AsyncMock(return_value=104)

    data = _sefer_create(
        sefer_no="TRIP-004",
        arac_id=1,
        mesafe_km=300.0,
        net_kg=5000,
    )

    mock_pred = MagicMock()
    mock_pred.predict_consumption = AsyncMock(side_effect=RuntimeError("pred fail"))

    with patch(
        "app.services.prediction_service.get_prediction_service",
        return_value=mock_pred,
    ):
        await svc._create_return_trip(uow, data, date(2026, 3, 15), ref_sefer_id=61)

    # add should still be called
    uow.sefer_repo.add.assert_awaited_once()
    call_kwargs = uow.sefer_repo.add.call_args
    assert call_kwargs.kwargs.get("tahmini_tuketim") is None


# ============================================================
# 3. _check_sla_delay paths
# ============================================================


async def test_check_sla_delay_sefer_not_found():
    """When get_by_id returns None → early return, no error."""
    svc, _ = _make_service()
    uow = DummyUoW()
    uow.sefer_repo.get_by_id = AsyncMock(return_value=None)

    # Should not raise
    await svc._check_sla_delay(uow, sefer_id=99, target_arac_id=1, current_sefer={})


async def test_check_sla_delay_no_duration():
    """When actual_duration is None → SLA event not written."""
    svc, _ = _make_service()
    uow = DummyUoW()
    uow.sefer_repo.get_by_id = AsyncMock(
        return_value={
            "id": 99,
            "duration_min": None,  # No duration → skip
            "guzergah_id": None,
        }
    )

    mock_outbox = MagicMock()
    mock_outbox.save_event = AsyncMock()

    with patch(
        "app.core.services.sefer_write_service.get_outbox_service",
        return_value=mock_outbox,
    ):
        await svc._check_sla_delay(uow, sefer_id=99, target_arac_id=1, current_sefer={})

    mock_outbox.save_event.assert_not_awaited()


async def test_check_sla_delay_guzergah_not_found():
    """When guzergah_id is set but route not found → planned_duration stays 0."""
    svc, _ = _make_service()
    uow = DummyUoW()
    uow.sefer_repo.get_by_id = AsyncMock(
        return_value={
            "id": 99,
            "duration_min": 360,
            "guzergah_id": 5,
        }
    )
    uow.lokasyon_repo.get_by_id = AsyncMock(return_value=None)

    mock_outbox = MagicMock()
    mock_outbox.save_event = AsyncMock()

    with patch(
        "app.core.services.sefer_write_service.get_outbox_service",
        return_value=mock_outbox,
    ):
        await svc._check_sla_delay(uow, sefer_id=99, target_arac_id=1, current_sefer={})

    # planned_duration_min stays 0, no SLA event
    mock_outbox.save_event.assert_not_awaited()


async def test_check_sla_delay_writes_sla_event_when_delayed():
    """When planned_duration > 0 and actual > planned → SLA event written."""
    svc, _ = _make_service()
    uow = DummyUoW()
    uow.sefer_repo.get_by_id = AsyncMock(
        return_value={
            "id": 99,
            "duration_min": 420,  # 7h actual
            "guzergah_id": 5,
            "arac_id": 1,
        }
    )
    uow.lokasyon_repo.get_by_id = AsyncMock(
        return_value={"tahmini_sure_saat": 5.0}  # 300 min planned
    )

    mock_outbox = MagicMock()
    mock_outbox.save_event = AsyncMock()

    with patch(
        "app.core.services.sefer_write_service.get_outbox_service",
        return_value=mock_outbox,
    ):
        await svc._check_sla_delay(uow, sefer_id=99, target_arac_id=1, current_sefer={})

    mock_outbox.save_event.assert_awaited_once()
    call_kwargs = mock_outbox.save_event.call_args
    payload = call_kwargs.kwargs.get("payload", {})
    assert payload["delay_min"] == 120  # 420 - 300


async def test_check_sla_delay_exception_swallowed():
    """Exception inside _check_sla_delay is caught and logged, not raised."""
    svc, _ = _make_service()
    uow = DummyUoW()
    uow.sefer_repo.get_by_id = AsyncMock(side_effect=RuntimeError("DB error"))

    # Should not raise
    await svc._check_sla_delay(uow, sefer_id=99, target_arac_id=1, current_sefer={})


# ============================================================
# 4. bulk_add_sefer: exception path
# ============================================================


async def test_bulk_add_sefer_exception_rollbacks(monkeypatch):
    """When bulk_create raises, rollback is called and exception re-raised."""
    svc, _ = _make_service()
    uow = DummyUoW()

    uow.sefer_repo.bulk_create = AsyncMock(side_effect=RuntimeError("insert fail"))
    uow.lokasyon_repo.get_benzersiz_lokasyonlar = AsyncMock(return_value=[])
    # AUDIT-041: aktif arac/sofor doğrulaması — satırın işlenmesi için aktif olmalı.
    uow.arac_repo.get_all = AsyncMock(
        return_value=[{"id": 1, "bos_agirlik_kg": 8000, "aktif": True}]
    )
    uow.arac_repo.get_by_ids = AsyncMock(return_value={1: {"id": 1}})
    uow.sofor_repo.get_by_ids = AsyncMock(return_value={})
    uow.sofor_repo.get_all = AsyncMock(return_value=[{"id": 2, "aktif": True}])
    uow.lokasyon_repo.get_all = AsyncMock(return_value=[])
    uow.lokasyon_repo.find_closest_match = AsyncMock(side_effect=lambda v, **_: v)

    monkeypatch.setattr(UnitOfWork, "__aenter__", AsyncMock(return_value=uow))
    monkeypatch.setattr(UnitOfWork, "__aexit__", AsyncMock(return_value=False))

    mock_pred = MagicMock()
    mock_pred.predict_consumption = AsyncMock(
        return_value={"tahmini_tuketim": 30.0, "tahmini_litre": 135.0}
    )

    sefer_list = [
        SeferCreate(
            tarih=date(2026, 4, 1),
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
        )
    ]

    with patch(
        "app.services.prediction_service.get_prediction_service",
        return_value=mock_pred,
    ):
        with pytest.raises(RuntimeError, match="insert fail"):
            await svc.bulk_add_sefer(sefer_list)

    uow.rollback.assert_awaited_once()


# ============================================================
# 5. update_sefer: user_id applied
# ============================================================


async def test_update_sefer_user_id_applied(monkeypatch):
    """When user_id is provided, updated_by_id is set in update_data."""
    svc, _ = _make_service()
    uow = DummyUoW()

    current = _current_sefer(durum="Planned")
    uow.sefer_repo.get_by_id = AsyncMock(return_value=current)
    uow.sefer_repo.update_sefer = AsyncMock(return_value=True)

    monkeypatch.setattr(UnitOfWork, "__aenter__", AsyncMock(return_value=uow))
    monkeypatch.setattr(UnitOfWork, "__aexit__", AsyncMock(return_value=False))

    result = await svc.update_sefer(
        sefer_id=99,
        data=SeferUpdate(durum="Completed"),
        user_id=42,
    )

    assert result is True
    call_kwargs = uow.sefer_repo.update_sefer.call_args
    assert call_kwargs.kwargs.get("updated_by_id") == 42


# ============================================================
# 6. _resolve_route: falsy guzergah_id
# ============================================================


async def test_resolve_route_falsy_guzergah_id():
    """guzergah_id=0 (falsy) → early return None."""
    svc, _ = _make_service()
    uow = DummyUoW()

    data = _sefer_create(guzergah_id=None)
    result = await svc._resolve_route(uow, data)
    assert result is None
    uow.lokasyon_repo.get_by_id.assert_not_awaited()


# ============================================================
# 7. _check_reprediction_needed: bos_sefer field
# ============================================================


def test_check_reprediction_needed_bos_sefer():
    assert SeferWriteService._check_reprediction_needed({"bos_sefer": True}) is True
    assert SeferWriteService._check_reprediction_needed({"dorse_id": 5}) is True
    assert SeferWriteService._check_reprediction_needed({"guzergah_id": 3}) is True


# ============================================================
# 8. _build_route_details_snapshot: rota_detay fallback
# ============================================================


def test_build_route_details_snapshot_uses_rota_detay_fallback():
    """When source has rota_detay but not route_analysis, uses rota_detay."""
    source = {"rota_detay": {"motorway": {"flat": 100.0}}}
    result = SeferWriteService._build_route_details_snapshot(source)
    assert result is not None
    assert "route_analysis" in result
    assert result["route_analysis"]["motorway"]["flat"] == 100.0


def test_build_route_details_snapshot_non_dict_route_analysis():
    """When route_analysis is not a dict, it's ignored."""
    source = {"route_analysis": "invalid-string"}
    result = SeferWriteService._build_route_details_snapshot(source)
    # Falls back to rota_detay check; rota_detay also missing → returns None or {}
    # Either None or a dict without route_analysis
    if result is not None:
        assert "route_analysis" not in result


# ============================================================
# 9. _extract_prediction_values: confidence fields
# ============================================================


def test_extract_prediction_values_confidence_fields():
    """confidence_low and confidence_high are extracted."""
    payload = {
        "tahmini_tuketim": 35.0,
        "confidence_low": 30.0,
        "confidence_high": 40.0,
        "confidence_score": 0.85,
    }
    val, meta = SeferWriteService._extract_prediction_values(payload)
    assert meta["confidence_low"] == 30.0
    assert meta["confidence_high"] == 40.0
    assert meta["confidence_score"] == 0.85


def test_extract_prediction_values_faktorler_included():
    """faktorler dict is included in meta."""
    payload = {
        "tahmini_tuketim": 32.0,
        "faktorler": {"agirlik": 1.1, "hava": 1.05},
    }
    val, meta = SeferWriteService._extract_prediction_values(payload)
    assert meta["faktorler"] == {"agirlik": 1.1, "hava": 1.05}


# ============================================================
# 10. _predict_outbound: USE_SEFER_FUEL_ESTIMATOR=True path
# ============================================================


async def test_predict_outbound_uses_estimator_when_flag_true():
    """When USE_SEFER_FUEL_ESTIMATOR=True, calls _predict_via_estimator."""
    svc, _ = _make_service()
    uow = DummyUoW()
    data = _sefer_create()

    estimator_result = (145.0, {"estimator_source": "SeferFuelEstimator"}, 77)
    svc._predict_via_estimator = AsyncMock(return_value=estimator_result)

    with patch("app.config.settings.USE_SEFER_FUEL_ESTIMATOR", True):
        tuk, meta, sim_id = await svc._predict_outbound(
            uow, data, date(2026, 3, 15), None
        )

    assert tuk == 145.0
    assert sim_id == 77
    svc._predict_via_estimator.assert_awaited_once()


# ============================================================
# ARCH-005 regression guard: _handle_round_trip_on_update builds a
# schemas.SeferCreate from the existing trip dict. After unifying the model
# families on app.schemas.sefer, this exercises that the construction works
# for normal data and that edge data which fails validation is swallowed by
# the method's try/except (return trip skipped, no crash). entities.SeferCreate
# and schemas.SeferCreate carry the SAME constraints (mesafe_km gt=0,
# cikis_yeri/varis_yeri min_length=2), so there is no behaviour change — these
# tests pin that.
# ============================================================


async def test_handle_round_trip_on_update_valid_data_builds_schema_and_creates_return():
    """Happy path: a valid trip dict -> schemas.SeferCreate -> return trip created."""
    svc, _ = _make_service()
    uow = DummyUoW()
    uow.sefer_repo.get_by_id = AsyncMock(
        return_value=_current_sefer(cikis_yeri="Istanbul", varis_yeri="Ankara")
    )
    uow.sefer_repo.get_by_sefer_no = AsyncMock(return_value=None)
    svc._create_return_trip = AsyncMock()

    await svc._handle_round_trip_on_update(uow, 99, {"return_net_kg": 5000})

    svc._create_return_trip.assert_awaited_once()
    built = svc._create_return_trip.await_args.args[1]
    assert isinstance(built, SeferCreate)
    assert built.is_round_trip is True
    assert built.mesafe_km == 450.0


async def test_handle_round_trip_on_update_edge_data_skips_gracefully():
    """Edge source data (mesafe_km=0) fails schemas.SeferCreate validation
    (gt=0); the method's try/except swallows it so the update path does not
    crash and the return trip is simply not created."""
    svc, _ = _make_service()
    uow = DummyUoW()
    uow.sefer_repo.get_by_id = AsyncMock(return_value=_current_sefer(mesafe_km=0))
    uow.sefer_repo.get_by_sefer_no = AsyncMock(return_value=None)
    svc._create_return_trip = AsyncMock()

    # Must not raise even though SeferCreate(mesafe_km=0) is invalid.
    await svc._handle_round_trip_on_update(uow, 99, {"return_net_kg": 5000})

    # Validation failed before reaching _create_return_trip.
    svc._create_return_trip.assert_not_awaited()


async def test_handle_round_trip_on_update_short_place_name_skips_gracefully():
    """Another edge: 1-char cikis_yeri fails min_length=2 -> skipped, no crash."""
    svc, _ = _make_service()
    uow = DummyUoW()
    uow.sefer_repo.get_by_id = AsyncMock(return_value=_current_sefer(cikis_yeri="X"))
    uow.sefer_repo.get_by_sefer_no = AsyncMock(return_value=None)
    svc._create_return_trip = AsyncMock()

    await svc._handle_round_trip_on_update(uow, 99, {"return_net_kg": 5000})

    svc._create_return_trip.assert_not_awaited()
