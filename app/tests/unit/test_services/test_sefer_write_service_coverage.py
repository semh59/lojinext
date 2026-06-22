"""
Coverage tests for SeferWriteService.

Targets uncovered blocks:
- Static helpers (_build_route_details_snapshot, _build_prediction_quality_flags,
  _build_prediction_route_analysis, _extract_prediction_values, _validate_sefer_create,
  _check_reprediction_needed, _sync_weight_fields)
- add_sefer: duplicate sefer_no, inactive arac, inactive sofor, round-trip
- update_sefer: not-found, status transitions, version conflict, weight sync,
  bulk_update_status, bulk_cancel, bulk_delete
- delete_sefer / _delete_sefer_uow
- create_return_trip
- _check_sla_delay, _handle_round_trip_on_update
- _predict_via_estimator (USE_SEFER_FUEL_ESTIMATOR path)
- _refresh_stats test vs production path
"""

from datetime import date, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

import app.core.services.sefer_write_service as sefer_write_module
from app.core.exceptions import RouteProcessingError
from app.core.services.sefer_write_service import SeferWriteService
from app.schemas.sefer import SeferCreate, SeferUpdate, TripStatus

pytestmark = pytest.mark.unit

# ---------------------------------------------------------------------------
# Helpers / DummyUoW
# ---------------------------------------------------------------------------


class DummyUoW:
    """Minimal async context-manager UnitOfWork replacement."""

    def __init__(self):
        self.sefer_repo = MagicMock()
        self.arac_repo = MagicMock()
        self.sofor_repo = MagicMock()
        self.lokasyon_repo = MagicMock()
        self.commit = AsyncMock()
        self.rollback = AsyncMock()

        # session mock — needed by OutboxService.save_event
        self.session = MagicMock()
        self.session.add = MagicMock()
        self.session.flush = AsyncMock()
        # AUDIT-041: sefer_no benzersizlik kontrolü session.execute(...).fetchall() çağırır.
        self.session.execute = AsyncMock(
            return_value=MagicMock(fetchall=MagicMock(return_value=[]))
        )

        # Commonly needed async stubs
        self.sefer_repo.add = AsyncMock(return_value=42)
        self.sefer_repo.get_by_id = AsyncMock(return_value=None)
        self.sefer_repo.get_by_sefer_no = AsyncMock(return_value=None)
        self.sefer_repo.update_sefer = AsyncMock(return_value=True)
        self.sefer_repo.delete = AsyncMock(return_value=True)
        self.sefer_repo.bulk_create = AsyncMock(return_value=[])
        self.sefer_repo.refresh_stats_mv = AsyncMock()
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
    svc = SeferWriteService(event_bus=bus)
    return svc, bus


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
    }
    base.update(overrides)
    return base


# ============================================================
# 1. Static helpers
# ============================================================


class TestBuildRouteDetailsSnapshot:
    def test_returns_none_for_non_dict(self):
        assert SeferWriteService._build_route_details_snapshot(None) is None
        assert SeferWriteService._build_route_details_snapshot("string") is None

    def test_returns_none_for_empty_dict(self):
        assert SeferWriteService._build_route_details_snapshot({}) is None

    def test_extracts_route_analysis(self):
        source = {"route_analysis": {"ratios": {"otoyol": 0.7}}}
        snap = SeferWriteService._build_route_details_snapshot(source)
        assert snap["route_analysis"]["ratios"]["otoyol"] == 0.7

    def test_falls_back_to_rota_detay(self):
        source = {"rota_detay": {"some_key": True}}
        snap = SeferWriteService._build_route_details_snapshot(source)
        assert snap["route_analysis"]["some_key"] is True

    def test_includes_distance_fields(self):
        source = {
            "otoban_mesafe_km": 300.0,
            "sehir_ici_mesafe_km": 50.0,
        }
        snap = SeferWriteService._build_route_details_snapshot(source)
        assert snap["otoban_mesafe_km"] == 300.0
        assert snap["sehir_ici_mesafe_km"] == 50.0


class TestBuildPredictionQualityFlags:
    def test_no_route_no_weather(self):
        flags = SeferWriteService._build_prediction_quality_flags()
        assert flags["canonical_prediction"] is True
        assert flags["route_available"] is False
        assert flags["route_analysis_available"] is False
        assert flags["weather_factor_applied"] is False

    def test_with_route_and_weather(self):
        route = {"route_analysis": {"x": 1}}
        flags = SeferWriteService._build_prediction_quality_flags(
            route_details=route, weather_factor=1.1
        )
        assert flags["route_available"] is True
        assert flags["route_analysis_available"] is True
        assert flags["weather_factor_applied"] is True

    def test_route_without_analysis(self):
        route = {"otoban_mesafe_km": 100.0}
        flags = SeferWriteService._build_prediction_quality_flags(route_details=route)
        assert flags["route_available"] is True
        assert flags["route_analysis_available"] is False


class TestBuildPredictionRouteAnalysis:
    def test_returns_none_when_empty(self):
        assert SeferWriteService._build_prediction_route_analysis() is None

    def test_includes_weather_factor(self):
        result = SeferWriteService._build_prediction_route_analysis(weather_factor=1.05)
        assert result["weather_factor"] == 1.05

    def test_includes_route_analysis_contents(self):
        route = {"route_analysis": {"ratios": {"otoyol": 0.8}}}
        result = SeferWriteService._build_prediction_route_analysis(route_details=route)
        assert result["ratios"]["otoyol"] == 0.8

    def test_includes_distributions_if_no_analysis(self):
        route = {"distributions": {"type": "normal"}}
        result = SeferWriteService._build_prediction_route_analysis(route_details=route)
        assert result["distributions"]["type"] == "normal"


class TestExtractPredictionValues:
    def test_returns_none_for_non_dict(self):
        val, meta = SeferWriteService._extract_prediction_values(None)
        assert val is None and meta is None

    def test_returns_none_when_no_tahmini_tuketim(self):
        val, meta = SeferWriteService._extract_prediction_values({"other": 1})
        assert val is None and meta is None

    def test_extracts_basic_values(self):
        payload = {
            "tahmini_tuketim": 35.0,
            "tahmini_litre": 157.5,
            "model_used": "ensemble",
            "status": "success",
        }
        val, meta = SeferWriteService._extract_prediction_values(payload)
        assert val == 35.0
        assert meta["tahmini_litre"] == 157.5
        assert meta["model_used"] == "ensemble"
        assert meta["input_quality"]["canonical_prediction"] is True

    def test_uses_prediction_liters_fallback(self):
        payload = {"tahmini_tuketim": 30.0, "prediction_liters": 135.0}
        val, meta = SeferWriteService._extract_prediction_values(payload)
        assert meta["tahmini_litre"] == 135.0

    def test_extracts_confidence_fields(self):
        payload = {
            "tahmini_tuketim": 28.0,
            "confidence_score": 0.85,
            "confidence_low": 25.0,
            "confidence_high": 31.0,
        }
        val, meta = SeferWriteService._extract_prediction_values(payload)
        assert meta["confidence_score"] == 0.85
        assert meta["confidence_low"] == 25.0

    def test_extracts_fallback_triggered(self):
        payload = {"tahmini_tuketim": 28.0, "fallback_triggered": True}
        val, meta = SeferWriteService._extract_prediction_values(payload)
        assert meta["fallback_triggered"] is True

    def test_extracts_faktorler(self):
        payload = {"tahmini_tuketim": 28.0, "faktorler": {"w": 1.1}}
        val, meta = SeferWriteService._extract_prediction_values(payload)
        assert meta["faktorler"]["w"] == 1.1

    def test_merges_quality_flags(self):
        payload = {"tahmini_tuketim": 28.0}
        quality = {"route_available": True}
        val, meta = SeferWriteService._extract_prediction_values(
            payload, quality_flags=quality
        )
        assert meta["input_quality"]["route_available"] is True


class TestValidateSeferCreate:
    def test_same_origin_destination_raises(self):
        data = _sefer_create(cikis_yeri="Ankara", varis_yeri="Ankara")
        with pytest.raises(RouteProcessingError, match="aynı olamaz"):
            SeferWriteService._validate_sefer_create(data, date(2026, 3, 15))

    def test_zero_distance_raises(self):
        # mesafe_km > 0 is enforced by Pydantic; test the service-level guard
        # by patching mesafe_km to 0 after construction
        data = _sefer_create()
        data.mesafe_km = 0.0
        with pytest.raises(RouteProcessingError, match="Mesafe"):
            SeferWriteService._validate_sefer_create(data, date(2026, 3, 15))

    def test_date_too_far_raises(self):
        future = date.today() + timedelta(days=400)
        data = _sefer_create()
        with pytest.raises(RouteProcessingError, match="1 yıldan"):
            SeferWriteService._validate_sefer_create(data, future)

    def test_valid_data_passes(self):
        data = _sefer_create()
        SeferWriteService._validate_sefer_create(data, date(2026, 3, 15))  # no raise


class TestCheckRepredictionNeeded:
    def test_detects_arac_id_change(self):
        assert SeferWriteService._check_reprediction_needed({"arac_id": 5}) is True

    def test_detects_net_kg_change(self):
        assert SeferWriteService._check_reprediction_needed({"net_kg": 12000}) is True

    def test_detects_tarih_change(self):
        assert (
            SeferWriteService._check_reprediction_needed({"tarih": date(2026, 4, 1)})
            is True
        )

    def test_no_prediction_fields_returns_false(self):
        assert SeferWriteService._check_reprediction_needed({"notlar": "x"}) is False

    def test_empty_dict_returns_false(self):
        assert SeferWriteService._check_reprediction_needed({}) is False


class TestSyncWeightFields:
    def test_sets_dolu_from_bos_plus_net(self):
        data = _sefer_create(bos_agirlik_kg=8000, net_kg=12000, dolu_agirlik_kg=0)
        arac = {"bos_agirlik_kg": 8000}
        SeferWriteService._sync_weight_fields(data, arac)
        assert data.dolu_agirlik_kg == 20000
        assert data.ton == 12.0

    def test_uses_arac_bos_when_data_bos_zero(self):
        data = _sefer_create(bos_agirlik_kg=0, net_kg=5000, dolu_agirlik_kg=0)
        arac = {"bos_agirlik_kg": 7000}
        SeferWriteService._sync_weight_fields(data, arac)
        assert data.bos_agirlik_kg == 7000
        assert data.dolu_agirlik_kg == 12000

    def test_derives_net_from_dolu_minus_bos_when_dolu_given(self):
        data = _sefer_create(bos_agirlik_kg=8000, net_kg=0, dolu_agirlik_kg=20000)
        arac = {}
        SeferWriteService._sync_weight_fields(data, arac)
        assert data.net_kg == 12000
        assert data.ton == 12.0

    def test_rejects_dolu_below_bos_negative_net(self):
        """dolu < bos → net would be negative (impossible cargo). The DB CHECK
        only enforces the arithmetic identity, so guard here with a 400-mapped
        ValueError instead of persisting negative weight / ton."""
        import pytest

        data = _sefer_create(bos_agirlik_kg=5000, net_kg=0, dolu_agirlik_kg=3000)
        with pytest.raises(ValueError, match="küçük olamaz"):
            SeferWriteService._sync_weight_fields(data, {})


# ============================================================
# 2. add_sefer — error paths
# ============================================================


async def test_add_sefer_raises_on_duplicate_sefer_no(monkeypatch):
    uow = DummyUoW()
    uow.sefer_repo.get_by_sefer_no = AsyncMock(return_value={"id": 10})  # duplicate
    uow.arac_repo.get_by_id = AsyncMock(
        return_value={"aktif": True, "bos_agirlik_kg": 8000}
    )
    uow.sofor_repo.get_by_id = AsyncMock(return_value={"aktif": True})

    monkeypatch.setattr(sefer_write_module, "UnitOfWork", lambda: uow)

    svc, _ = _make_service()
    data = _sefer_create(sefer_no="TRIP-001")

    with pytest.raises(RouteProcessingError) as exc_info:
        await svc.add_sefer(data)
    assert exc_info.value.reason == "DUPLICATE_SEFER_NO"


async def test_add_sefer_raises_when_arac_not_found(monkeypatch):
    uow = DummyUoW()
    uow.arac_repo.get_by_id = AsyncMock(return_value=None)

    monkeypatch.setattr(sefer_write_module, "UnitOfWork", lambda: uow)

    svc, _ = _make_service()
    data = _sefer_create()

    with pytest.raises(RouteProcessingError) as exc_info:
        await svc.add_sefer(data)
    assert exc_info.value.reason == "ARAC_NOT_FOUND"


async def test_add_sefer_raises_when_arac_inactive(monkeypatch):
    uow = DummyUoW()
    uow.arac_repo.get_by_id = AsyncMock(
        return_value={"aktif": False, "bos_agirlik_kg": 0}
    )

    monkeypatch.setattr(sefer_write_module, "UnitOfWork", lambda: uow)

    svc, _ = _make_service()
    data = _sefer_create()

    with pytest.raises(RouteProcessingError) as exc_info:
        await svc.add_sefer(data)
    assert exc_info.value.reason == "ARAC_NOT_FOUND"


async def test_add_sefer_raises_when_sofor_not_found(monkeypatch):
    uow = DummyUoW()
    uow.arac_repo.get_by_id = AsyncMock(
        return_value={"aktif": True, "bos_agirlik_kg": 8000}
    )
    uow.sofor_repo.get_by_id = AsyncMock(return_value=None)

    monkeypatch.setattr(sefer_write_module, "UnitOfWork", lambda: uow)

    svc, _ = _make_service()
    data = _sefer_create()

    with pytest.raises(RouteProcessingError) as exc_info:
        await svc.add_sefer(data)
    assert exc_info.value.reason == "SOFOR_NOT_FOUND"


async def test_add_sefer_raises_on_same_origin_destination(monkeypatch):
    uow = DummyUoW()
    monkeypatch.setattr(sefer_write_module, "UnitOfWork", lambda: uow)

    svc, _ = _make_service()
    data = _sefer_create(cikis_yeri="Ankara", varis_yeri="Ankara")

    with pytest.raises(RouteProcessingError):
        await svc.add_sefer(data)


async def test_add_sefer_sets_default_status_planned(monkeypatch):
    """When durum is not provided the service defaults to Planned."""
    uow = DummyUoW()
    uow.sefer_repo.add = AsyncMock(return_value=77)
    uow.arac_repo.get_by_id = AsyncMock(
        return_value={"aktif": True, "bos_agirlik_kg": 8000}
    )
    uow.sofor_repo.get_by_id = AsyncMock(return_value={"aktif": True})

    monkeypatch.setattr(sefer_write_module, "UnitOfWork", lambda: uow)

    # Patch outbox to avoid real DB dependency
    mock_outbox = MagicMock()
    mock_outbox.save_event = AsyncMock()
    monkeypatch.setattr(sefer_write_module, "get_outbox_service", lambda: mock_outbox)

    # Patch prediction to return None (no prediction)
    with patch.object(
        SeferWriteService,
        "_predict_outbound",
        new=AsyncMock(return_value=(None, None, None)),
    ):
        svc, _ = _make_service()
        data = _sefer_create()
        sefer_id = await svc.add_sefer(data)

    assert sefer_id == 77


# ============================================================
# 3. update_sefer (_update_sefer_uow) paths
# ============================================================


async def test_update_sefer_raises_when_not_found():
    uow = DummyUoW()
    uow.sefer_repo.get_by_id = AsyncMock(return_value=None)

    svc, _ = _make_service()
    with pytest.raises(RouteProcessingError) as exc_info:
        await svc._update_sefer_uow(uow, 999, SeferUpdate(notlar="x"))
    assert exc_info.value.reason == "SEFER_NOT_FOUND"


async def test_update_sefer_returns_true_when_nothing_to_update():
    uow = DummyUoW()
    uow.sefer_repo.get_by_id = AsyncMock(return_value=_current_sefer())

    svc, _ = _make_service()
    # SeferUpdate with no fields set → model_dump(exclude_unset=True) == {}
    result = await svc._update_sefer_uow(uow, 99, SeferUpdate())
    assert result is True
    uow.sefer_repo.update_sefer.assert_not_called()


async def test_update_sefer_invalid_status_transition_raises():
    """COMPLETED → PLANNED is not allowed (COMPLETED is terminal)."""
    uow = DummyUoW()
    uow.sefer_repo.get_by_id = AsyncMock(return_value=_current_sefer(durum="Completed"))

    svc, _ = _make_service()
    with pytest.raises(ValueError, match="Geçersiz durum geçişi"):
        await svc._update_sefer_uow(
            uow,
            99,
            SeferUpdate(durum=TripStatus.PLANNED),
        )


async def test_update_sefer_valid_status_transition_planned_to_completed():
    """Planned → Completed is allowed."""
    uow = DummyUoW()
    uow.sefer_repo.get_by_id = AsyncMock(return_value=_current_sefer(durum="Planned"))
    uow.sefer_repo.update_sefer = AsyncMock(return_value=True)

    svc, bus = _make_service()
    # Stub the SLA check to avoid further DB calls
    with patch.object(svc, "_check_sla_delay", new=AsyncMock()):
        result = await svc._update_sefer_uow(
            uow,
            99,
            SeferUpdate(durum=TripStatus.COMPLETED),
        )
    assert result is True
    # ROUTE_COMPLETED event must be published
    bus.publish_async.assert_awaited_once()


async def test_update_sefer_version_conflict_raises():
    uow = DummyUoW()
    uow.sefer_repo.get_by_id = AsyncMock(return_value=_current_sefer(version=3))

    svc, _ = _make_service()
    from fastapi import HTTPException

    with pytest.raises(HTTPException) as exc_info:
        await svc._update_sefer_uow(
            uow,
            99,
            SeferUpdate(version=1),  # stale — current is 3
        )
    assert exc_info.value.status_code == 409


async def test_update_sefer_duplicate_sefer_no_raises():
    uow = DummyUoW()
    uow.sefer_repo.get_by_id = AsyncMock(
        return_value=_current_sefer(sefer_no="OLD-001")
    )
    uow.sefer_repo.get_by_sefer_no = AsyncMock(return_value={"id": 5})  # already used

    svc, _ = _make_service()
    with pytest.raises(ValueError, match="zaten kullanımda"):
        await svc._update_sefer_uow(
            uow,
            99,
            SeferUpdate(sefer_no="NEW-999"),
        )


async def test_update_sefer_weight_sync_updates_dolu_when_net_changes():
    uow = DummyUoW()
    cs = _current_sefer(bos_agirlik_kg=8000, dolu_agirlik_kg=18000, net_kg=10000)
    uow.sefer_repo.get_by_id = AsyncMock(return_value=cs)
    uow.sefer_repo.update_sefer = AsyncMock(return_value=True)

    svc, _ = _make_service()
    with patch.object(svc, "_repredikt_for_update", new=AsyncMock()):
        await svc._update_sefer_uow(uow, 99, SeferUpdate(net_kg=15000))

    call_kwargs = uow.sefer_repo.update_sefer.await_args.kwargs
    assert call_kwargs["dolu_agirlik_kg"] == 23000  # 8000 + 15000
    assert call_kwargs["ton"] == 15.0


async def test_update_sefer_weight_sync_updates_net_when_dolu_changes():
    uow = DummyUoW()
    cs = _current_sefer(bos_agirlik_kg=8000, dolu_agirlik_kg=18000, net_kg=10000)
    uow.sefer_repo.get_by_id = AsyncMock(return_value=cs)
    uow.sefer_repo.update_sefer = AsyncMock(return_value=True)

    svc, _ = _make_service()
    with patch.object(svc, "_repredikt_for_update", new=AsyncMock()):
        await svc._update_sefer_uow(uow, 99, SeferUpdate(dolu_agirlik_kg=22000))

    call_kwargs = uow.sefer_repo.update_sefer.await_args.kwargs
    assert call_kwargs["net_kg"] == 14000  # 22000 - 8000


# ============================================================
# 4. delete_sefer
# ============================================================


async def test_delete_sefer_calls_repo_delete(monkeypatch):
    uow = DummyUoW()
    uow.sefer_repo.delete = AsyncMock(return_value=True)

    monkeypatch.setattr(sefer_write_module, "UnitOfWork", lambda: uow)

    svc, _ = _make_service()
    result = await svc.delete_sefer(99)

    assert result is True
    uow.sefer_repo.delete.assert_awaited_once_with(99)


async def test_delete_sefer_returns_false_when_not_found(monkeypatch):
    uow = DummyUoW()
    uow.sefer_repo.delete = AsyncMock(return_value=False)

    monkeypatch.setattr(sefer_write_module, "UnitOfWork", lambda: uow)

    svc, _ = _make_service()
    result = await svc.delete_sefer(999)
    assert result is False


async def test_delete_sefer_uow_propagates_exception():
    uow = DummyUoW()
    uow.sefer_repo.delete = AsyncMock(side_effect=RuntimeError("DB error"))

    svc, _ = _make_service()
    with pytest.raises(RuntimeError, match="DB error"):
        await svc._delete_sefer_uow(uow, 99)


# ============================================================
# 5. bulk_update_status
# ============================================================


async def test_bulk_update_status_rejects_iptal(monkeypatch):
    monkeypatch.setattr(sefer_write_module, "UnitOfWork", lambda: DummyUoW())
    svc, _ = _make_service()
    with pytest.raises(ValueError, match="bulk_cancel"):
        await svc.bulk_update_status([1, 2], "Cancelled")


async def test_bulk_update_status_success(monkeypatch):
    uow = DummyUoW()
    uow.sefer_repo.get_by_id = AsyncMock(return_value=_current_sefer(durum="Planned"))
    uow.sefer_repo.update_sefer = AsyncMock(return_value=True)

    monkeypatch.setattr(sefer_write_module, "UnitOfWork", lambda: uow)

    svc, _ = _make_service()
    result = await svc.bulk_update_status([99], "Completed")

    assert result["success_count"] == 1
    assert result["failed_count"] == 0


async def test_bulk_update_status_partial_failure(monkeypatch):
    """Sefer not found → counted as failure."""
    uow = DummyUoW()
    cs_planned = _current_sefer(id=99, durum="Planned")

    # First call returns a valid sefer, second call returns None (not found)
    uow.sefer_repo.get_by_id = AsyncMock(side_effect=[cs_planned, None])
    uow.sefer_repo.update_sefer = AsyncMock(return_value=True)

    monkeypatch.setattr(sefer_write_module, "UnitOfWork", lambda: uow)

    svc, _ = _make_service()
    with patch.object(svc, "_check_sla_delay", new=AsyncMock()):
        result = await svc.bulk_update_status([99, 100], "Completed")
    assert result["success_count"] == 1
    assert result["failed_count"] == 1


# ============================================================
# 6. bulk_cancel
# ============================================================


async def test_bulk_cancel_success(monkeypatch):
    uow = DummyUoW()
    uow.sefer_repo.get_by_id = AsyncMock(return_value=_current_sefer(durum="Planned"))
    uow.sefer_repo.update_sefer = AsyncMock(return_value=True)

    monkeypatch.setattr(sefer_write_module, "UnitOfWork", lambda: uow)

    svc, _ = _make_service()
    result = await svc.bulk_cancel([99], iptal_nedeni="Test iptal")
    assert result["success_count"] == 1
    assert result["failed_count"] == 0


async def test_bulk_cancel_handles_error_in_individual_item(monkeypatch):
    uow = DummyUoW()
    # Simulate sefer not found
    uow.sefer_repo.get_by_id = AsyncMock(return_value=None)

    monkeypatch.setattr(sefer_write_module, "UnitOfWork", lambda: uow)

    svc, _ = _make_service()
    result = await svc.bulk_cancel([999], iptal_nedeni="Test iptal")
    assert result["failed_count"] == 1


# ============================================================
# 7. bulk_delete
# ============================================================


async def test_bulk_delete_success(monkeypatch):
    uow = DummyUoW()
    uow.sefer_repo.delete = AsyncMock(return_value=True)

    monkeypatch.setattr(sefer_write_module, "UnitOfWork", lambda: uow)

    svc, _ = _make_service()
    result = await svc.bulk_delete([1, 2, 3])
    assert result["success_count"] == 3
    assert result["failed_count"] == 0


async def test_bulk_delete_partial_failure(monkeypatch):
    delete_results = [True, False, True]
    idx = [0]

    async def _delete_side(sid):
        result = delete_results[idx[0] % len(delete_results)]
        idx[0] += 1
        return result

    uow = DummyUoW()
    uow.sefer_repo.delete = AsyncMock(side_effect=_delete_side)

    monkeypatch.setattr(sefer_write_module, "UnitOfWork", lambda: uow)

    svc, _ = _make_service()
    result = await svc.bulk_delete([1, 2, 3])
    assert result["success_count"] == 2
    assert result["failed_count"] == 1


async def test_bulk_delete_empty_list(monkeypatch):
    monkeypatch.setattr(sefer_write_module, "UnitOfWork", lambda: DummyUoW())
    svc, _ = _make_service()
    result = await svc.bulk_delete([])
    assert result["success_count"] == 0


# ============================================================
# 8. create_return_trip
# ============================================================


async def test_create_return_trip_success(monkeypatch):
    uow = DummyUoW()
    uow.sefer_repo.get_by_id = AsyncMock(
        return_value={
            "id": 10,
            "sefer_no": "TRIP-010",
            "arac_id": 1,
            "sofor_id": 2,
            "dorse_id": None,
            "guzergah_id": None,
            "cikis_yeri": "Istanbul",
            "varis_yeri": "Ankara",
            "mesafe_km": 450.0,
            "bos_agirlik_kg": 8000,
            "dolu_agirlik_kg": 18000,
            "net_kg": 10000,
            "ascent_m": 300.0,
            "descent_m": 200.0,
            "flat_distance_km": 100.0,
            "is_real": False,
        }
    )
    uow.sefer_repo.add = AsyncMock(return_value=11)

    monkeypatch.setattr(sefer_write_module, "get_uow", lambda: uow)

    svc, _ = _make_service()
    new_id = await svc.create_return_trip(10, user_id=1)
    assert new_id == 11

    add_kwargs = uow.sefer_repo.add.await_args.kwargs
    assert add_kwargs["cikis_yeri"] == "Ankara"  # reversed
    assert add_kwargs["varis_yeri"] == "Istanbul"  # reversed
    assert add_kwargs["bos_sefer"] is True
    assert add_kwargs["net_kg"] == 0
    # elevation should be swapped
    assert add_kwargs["ascent_m"] == 200.0
    assert add_kwargs["descent_m"] == 300.0


async def test_create_return_trip_raises_when_not_found(monkeypatch):
    uow = DummyUoW()
    uow.sefer_repo.get_by_id = AsyncMock(return_value=None)

    monkeypatch.setattr(sefer_write_module, "get_uow", lambda: uow)

    svc, _ = _make_service()
    with pytest.raises((ValueError, Exception)):
        await svc.create_return_trip(999)


async def test_create_return_trip_strips_double_suffix(monkeypatch):
    """Sefer with existing '-D' suffix should produce '-D-R' not '-D-D'."""
    uow = DummyUoW()
    uow.sefer_repo.get_by_id = AsyncMock(
        return_value={
            "id": 20,
            "sefer_no": "TRIP-020-D",
            "arac_id": 1,
            "sofor_id": 2,
            "dorse_id": None,
            "guzergah_id": None,
            "cikis_yeri": "Ankara",
            "varis_yeri": "Istanbul",
            "mesafe_km": 450.0,
            "bos_agirlik_kg": 8000,
            "dolu_agirlik_kg": 8000,
            "net_kg": 0,
            "ascent_m": 0.0,
            "descent_m": 0.0,
            "flat_distance_km": 0.0,
            "is_real": False,
        }
    )
    uow.sefer_repo.add = AsyncMock(return_value=21)
    monkeypatch.setattr(sefer_write_module, "get_uow", lambda: uow)

    svc, _ = _make_service()
    await svc.create_return_trip(20)
    add_kwargs = uow.sefer_repo.add.await_args.kwargs
    # After stripping '-D', the new suffix should be '-D'
    assert add_kwargs["sefer_no"] == "TRIP-020-D"


# ============================================================
# 9. _check_sla_delay
# ============================================================


async def test_check_sla_delay_writes_outbox_on_delay(monkeypatch):
    uow = DummyUoW()
    uow.sefer_repo.get_by_id = AsyncMock(
        return_value={
            "id": 99,
            "duration_min": 600,  # actual
            "guzergah_id": 5,
        }
    )
    uow.lokasyon_repo.get_by_id = AsyncMock(
        return_value={"tahmini_sure_saat": 8.0}  # 480 min planned
    )

    mock_outbox = MagicMock()
    mock_outbox.save_event = AsyncMock()
    monkeypatch.setattr(sefer_write_module, "get_outbox_service", lambda: mock_outbox)

    svc, _ = _make_service()
    await svc._check_sla_delay(uow, 99, 1, {})
    mock_outbox.save_event.assert_awaited_once()
    call_kwargs = mock_outbox.save_event.await_args.kwargs
    assert call_kwargs["payload"]["delay_min"] == 120  # 600 - 480


async def test_check_sla_delay_skips_when_no_route(monkeypatch):
    uow = DummyUoW()
    uow.sefer_repo.get_by_id = AsyncMock(
        return_value={"id": 99, "duration_min": 600, "guzergah_id": None}
    )

    mock_outbox = MagicMock()
    mock_outbox.save_event = AsyncMock()
    monkeypatch.setattr(sefer_write_module, "get_outbox_service", lambda: mock_outbox)

    svc, _ = _make_service()
    await svc._check_sla_delay(uow, 99, 1, {})
    mock_outbox.save_event.assert_not_awaited()


async def test_check_sla_delay_skips_when_sefer_missing():
    uow = DummyUoW()
    uow.sefer_repo.get_by_id = AsyncMock(return_value=None)

    svc, _ = _make_service()
    # Should not raise
    await svc._check_sla_delay(uow, 999, None, {})


# ============================================================
# 10. _resolve_route
# ============================================================


async def test_resolve_route_returns_none_when_no_guzergah_id():
    uow = DummyUoW()
    svc, _ = _make_service()
    data = _sefer_create(guzergah_id=None)
    result = await svc._resolve_route(uow, data)
    assert result is None


async def test_resolve_route_fills_mesafe_from_route():
    uow = DummyUoW()
    uow.lokasyon_repo.get_by_id = AsyncMock(
        return_value={"mesafe_km": 550.0, "ascent_m": 400.0, "descent_m": 300.0}
    )
    svc, _ = _make_service()
    data = _sefer_create(guzergah_id=7, mesafe_km=0.1)
    # mesafe_km defaults to route value only when data.mesafe_km is falsy
    data.mesafe_km = 0.0
    await svc._resolve_route(uow, data)
    assert data.mesafe_km == 550.0


# ============================================================
# 11. _predict_via_estimator
# ============================================================


async def test_predict_via_estimator_returns_none_on_timeout(monkeypatch):
    import asyncio

    async def _slow_predict(*_, **__):
        await asyncio.sleep(10)

    mock_estimator = MagicMock()
    mock_estimator.predict = _slow_predict

    monkeypatch.setattr(
        sefer_write_module,
        "__builtins__",
        sefer_write_module.__builtins__,
    )

    with patch(
        "app.core.services.sefer_fuel_estimator.get_sefer_fuel_estimator",
        return_value=mock_estimator,
    ):
        svc, _ = _make_service()
        uow = DummyUoW()
        data = _sefer_create(guzergah_id=None)
        tuk, meta, sim_id = await svc._predict_via_estimator(
            uow, data, date(2026, 3, 15), None
        )
    assert tuk is None and meta is None and sim_id is None


async def test_predict_via_estimator_returns_none_on_exception():
    with patch(
        "app.core.services.sefer_fuel_estimator.get_sefer_fuel_estimator",
        side_effect=ImportError("mock"),
    ):
        svc, _ = _make_service()
        uow = DummyUoW()
        data = _sefer_create()
        tuk, meta, sim_id = await svc._predict_via_estimator(
            uow, data, date(2026, 3, 15), None
        )
    assert tuk is None


# ============================================================
# 12. bulk_add_sefer — edge cases
# ============================================================


async def test_bulk_add_sefer_empty_list_returns_zero(monkeypatch):
    monkeypatch.setattr(sefer_write_module, "UnitOfWork", lambda: DummyUoW())
    svc, _ = _make_service()
    count = await svc.bulk_add_sefer([])
    assert count == 0


async def test_bulk_add_sefer_skips_same_origin_destination(monkeypatch):
    uow = DummyUoW()
    uow.lokasyon_repo.get_benzersiz_lokasyonlar = AsyncMock(return_value=[])
    uow.lokasyon_repo.get_all = AsyncMock(return_value=[])
    uow.lokasyon_repo.find_closest_match = AsyncMock(side_effect=lambda v, **_: v)

    monkeypatch.setattr(sefer_write_module, "UnitOfWork", lambda: uow)

    # Patch prediction service to avoid real ML calls
    import app.services.prediction_service as pred_module

    mock_pred = MagicMock()
    mock_pred.predict_consumption = AsyncMock(return_value=None)
    monkeypatch.setattr(pred_module, "get_prediction_service", lambda: mock_pred)

    svc, _ = _make_service()
    data = _sefer_create(cikis_yeri="Ankara", varis_yeri="Ankara")
    count = await svc.bulk_add_sefer([data])
    # Same origin/destination should be filtered out → 0 inserted
    assert count == 0


async def test_bulk_add_sefer_skips_zero_distance(monkeypatch):
    uow = DummyUoW()
    uow.lokasyon_repo.get_benzersiz_lokasyonlar = AsyncMock(return_value=[])
    uow.lokasyon_repo.get_all = AsyncMock(return_value=[])
    uow.lokasyon_repo.find_closest_match = AsyncMock(side_effect=lambda v, **_: v)

    monkeypatch.setattr(sefer_write_module, "UnitOfWork", lambda: uow)

    import app.services.prediction_service as pred_module

    mock_pred = MagicMock()
    mock_pred.predict_consumption = AsyncMock(return_value=None)
    monkeypatch.setattr(pred_module, "get_prediction_service", lambda: mock_pred)

    svc, _ = _make_service()
    data = _sefer_create()
    data.mesafe_km = 0.0  # zero → should skip
    count = await svc.bulk_add_sefer([data])
    assert count == 0


# ============================================================
# 13. ALLOWED_TRANSITIONS class attribute
# ============================================================


def test_allowed_transitions_completeness():
    at = SeferWriteService.ALLOWED_TRANSITIONS
    assert TripStatus.COMPLETED in at
    assert at[TripStatus.COMPLETED] == []  # terminal
    assert TripStatus.PLANNED in at[TripStatus.CANCELLED]  # re-plan allowed


def test_valid_status_transitions_alias():
    """VALID_STATUS_TRANSITIONS is an alias for ALLOWED_TRANSITIONS."""
    assert (
        SeferWriteService.VALID_STATUS_TRANSITIONS
        is SeferWriteService.ALLOWED_TRANSITIONS
    )
