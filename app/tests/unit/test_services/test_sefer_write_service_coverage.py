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

0-mock (Dilim 25): all monkeypatch(UnitOfWork/get_uow) removed → real DB via
db_session fixture. Kept targeted mocks:
- DummyUoW passed as ARGUMENT to _update_sefer_uow / _check_sla_delay (not patched)
- patch.object(SeferWriteService, "_predict_outbound") — ML boundary
- monkeypatch(get_outbox_service) — outbox boundary (separate service)
- patch.object(svc, "_repredikt_for_update") — internal call in weight-sync tests
- patch.object(svc, "_check_sla_delay") — in partial-failure test to avoid guzergah FK
"""

from datetime import date, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

import app.core.services.sefer_write_service as sefer_write_module
from app.core.exceptions import RouteProcessingError
from app.core.services.sefer_write_service import SeferWriteService
from app.schemas.sefer import SeferCreate, SeferUpdate, TripStatus
from app.tests._helpers.seed import seed_arac, seed_sefer, seed_sofor

pytestmark = pytest.mark.integration
# ---------------------------------------------------------------------------
# Helpers / DummyUoW
# ---------------------------------------------------------------------------


class DummyUoW:
    """Minimal async context-manager UnitOfWork replacement.

    Used ONLY in tests that call svc._update_sefer_uow(uow, ...) / _check_sla_delay
    directly — passing DummyUoW as an ARGUMENT, not patching module-level UnitOfWork.
    """

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
# 2. add_sefer — error paths (real DB)
# ============================================================


async def test_add_sefer_raises_on_duplicate_sefer_no(db_session):
    arac = await seed_arac(db_session, plaka="34SWCDUP01")
    sofor = await seed_sofor(db_session, ad_soyad="Sofor SWC Dup")
    await seed_sefer(
        db_session, arac_id=arac.id, sofor_id=sofor.id, sefer_no="SWC-TRIP-DUP"
    )
    await db_session.commit()

    svc, _ = _make_service()
    data = _sefer_create(arac_id=arac.id, sofor_id=sofor.id, sefer_no="SWC-TRIP-DUP")

    with pytest.raises(RouteProcessingError) as exc_info:
        await svc.add_sefer(data)
    assert exc_info.value.reason == "DUPLICATE_SEFER_NO"


async def test_add_sefer_raises_when_arac_not_found(db_session):
    svc, _ = _make_service()
    data = _sefer_create(arac_id=999999, sofor_id=999999)

    with pytest.raises(RouteProcessingError) as exc_info:
        await svc.add_sefer(data)
    assert exc_info.value.reason == "ARAC_NOT_FOUND"


async def test_add_sefer_raises_when_arac_inactive(db_session):
    arac = await seed_arac(db_session, plaka="34SWCINA01", aktif=False)
    await db_session.commit()

    svc, _ = _make_service()
    data = _sefer_create(arac_id=arac.id, sofor_id=999999)

    with pytest.raises(RouteProcessingError) as exc_info:
        await svc.add_sefer(data)
    assert exc_info.value.reason == "ARAC_NOT_FOUND"


async def test_add_sefer_raises_when_sofor_not_found(db_session):
    arac = await seed_arac(db_session, plaka="34SWCSOF01")
    await db_session.commit()

    svc, _ = _make_service()
    data = _sefer_create(arac_id=arac.id, sofor_id=999999)

    with pytest.raises(RouteProcessingError) as exc_info:
        await svc.add_sefer(data)
    assert exc_info.value.reason == "SOFOR_NOT_FOUND"


async def test_add_sefer_raises_on_same_origin_destination(db_session):
    """_validate_sefer_create fires before any DB read → no seeding needed."""
    svc, _ = _make_service()
    data = _sefer_create(cikis_yeri="Ankara", varis_yeri="Ankara")

    with pytest.raises(RouteProcessingError):
        await svc.add_sefer(data)


async def test_add_sefer_sets_default_status_planned(db_session, monkeypatch):
    """When durum is not provided the service defaults to Planned."""
    arac = await seed_arac(db_session, plaka="34SWCPL01")
    sofor = await seed_sofor(db_session, ad_soyad="Sofor SWC Pl")
    await db_session.commit()

    mock_outbox = MagicMock()
    mock_outbox.save_event = AsyncMock()
    monkeypatch.setattr(sefer_write_module, "get_outbox_service", lambda: mock_outbox)

    with patch.object(
        SeferWriteService,
        "_predict_outbound",
        new=AsyncMock(return_value=(None, None, None)),
    ):
        svc, _ = _make_service()
        data = _sefer_create(arac_id=arac.id, sofor_id=sofor.id)
        sefer_id = await svc.add_sefer(data)

    assert isinstance(sefer_id, int) and sefer_id > 0


# ============================================================
# 3. update_sefer (_update_sefer_uow) paths
# (pass DummyUoW as argument — no module-level UnitOfWork patch)
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
# 4. delete_sefer (real DB)
# ============================================================


async def test_delete_sefer_calls_repo_delete(db_session):
    arac = await seed_arac(db_session, plaka="34SWCDEL01")
    sofor = await seed_sofor(db_session, ad_soyad="Sofor SWC Del")
    sefer = await seed_sefer(db_session, arac_id=arac.id, sofor_id=sofor.id)
    await db_session.commit()

    svc, _ = _make_service()
    result = await svc.delete_sefer(sefer.id)
    assert result is True


async def test_delete_sefer_returns_false_when_not_found(db_session):
    svc, _ = _make_service()
    result = await svc.delete_sefer(999999)
    assert result is False


async def test_delete_sefer_uow_propagates_exception():
    uow = DummyUoW()
    uow.sefer_repo.delete = AsyncMock(side_effect=RuntimeError("DB error"))

    svc, _ = _make_service()
    with pytest.raises(RuntimeError, match="DB error"):
        await svc._delete_sefer_uow(uow, 99)


# ============================================================
# 5. bulk_update_status (real DB)
# ============================================================


async def test_bulk_update_status_rejects_iptal(db_session):
    svc, _ = _make_service()
    with pytest.raises(ValueError, match="bulk_cancel"):
        await svc.bulk_update_status([1, 2], "Cancelled")


async def test_bulk_update_status_success(db_session):
    arac = await seed_arac(db_session, plaka="34SWCBUS01")
    sofor = await seed_sofor(db_session, ad_soyad="Sofor SWC Bus")
    sefer = await seed_sefer(
        db_session, arac_id=arac.id, sofor_id=sofor.id, durum="Planned"
    )
    await db_session.commit()

    svc, _ = _make_service()
    result = await svc.bulk_update_status([sefer.id], "Completed")

    assert result["success_count"] == 1
    assert result["failed_count"] == 0


async def test_bulk_update_status_partial_failure(db_session):
    """Sefer not found → counted as failure."""
    arac = await seed_arac(db_session, plaka="34SWCBUS02")
    sofor = await seed_sofor(db_session, ad_soyad="Sofor SWC Bus2")
    sefer = await seed_sefer(
        db_session, arac_id=arac.id, sofor_id=sofor.id, durum="Planned"
    )
    await db_session.commit()

    svc, _ = _make_service()
    with patch.object(svc, "_check_sla_delay", new=AsyncMock()):
        result = await svc.bulk_update_status([sefer.id, 999999], "Completed")
    assert result["success_count"] == 1
    assert result["failed_count"] == 1


# ============================================================
# 6. bulk_cancel (real DB)
# ============================================================


async def test_bulk_cancel_success(db_session):
    arac = await seed_arac(db_session, plaka="34SWCCAN01")
    sofor = await seed_sofor(db_session, ad_soyad="Sofor SWC Can")
    sefer = await seed_sefer(
        db_session, arac_id=arac.id, sofor_id=sofor.id, durum="Planned"
    )
    await db_session.commit()

    svc, _ = _make_service()
    result = await svc.bulk_cancel([sefer.id], iptal_nedeni="Test iptal")
    assert result["success_count"] == 1
    assert result["failed_count"] == 0


async def test_bulk_cancel_handles_error_in_individual_item(db_session):
    svc, _ = _make_service()
    result = await svc.bulk_cancel([999999], iptal_nedeni="Test iptal")
    assert result["failed_count"] == 1


# ============================================================
# 7. bulk_delete (real DB)
# ============================================================


async def test_bulk_delete_success(db_session):
    arac = await seed_arac(db_session, plaka="34SWCBDL01")
    sofor = await seed_sofor(db_session, ad_soyad="Sofor SWC Bdl")
    s1 = await seed_sefer(db_session, arac_id=arac.id, sofor_id=sofor.id)
    s2 = await seed_sefer(db_session, arac_id=arac.id, sofor_id=sofor.id)
    s3 = await seed_sefer(db_session, arac_id=arac.id, sofor_id=sofor.id)
    await db_session.commit()

    svc, _ = _make_service()
    result = await svc.bulk_delete([s1.id, s2.id, s3.id])
    assert result["success_count"] == 3
    assert result["failed_count"] == 0


async def test_bulk_delete_partial_failure(db_session):
    arac = await seed_arac(db_session, plaka="34SWCBDL02")
    sofor = await seed_sofor(db_session, ad_soyad="Sofor SWC Bdl2")
    s1 = await seed_sefer(db_session, arac_id=arac.id, sofor_id=sofor.id)
    s2 = await seed_sefer(db_session, arac_id=arac.id, sofor_id=sofor.id)
    await db_session.commit()

    svc, _ = _make_service()
    result = await svc.bulk_delete([s1.id, 999999, s2.id])
    assert result["success_count"] == 2
    assert result["failed_count"] == 1


async def test_bulk_delete_empty_list(db_session):
    svc, _ = _make_service()
    result = await svc.bulk_delete([])
    assert result["success_count"] == 0


# ============================================================
# 8. create_return_trip (real DB)
# ============================================================


async def test_create_return_trip_success(db_session):
    arac = await seed_arac(db_session, plaka="34SWCRT01")
    sofor = await seed_sofor(db_session, ad_soyad="Sofor SWC Rt")
    sefer = await seed_sefer(
        db_session,
        arac_id=arac.id,
        sofor_id=sofor.id,
        sefer_no="SWC-TRIP-RT01",
        cikis_yeri="Istanbul",
        varis_yeri="Ankara",
    )
    await db_session.commit()

    svc, _ = _make_service()
    # user_id=None to avoid FK violation against kullanicilar (no user 1 in test DB)
    new_id = await svc.create_return_trip(sefer.id, user_id=None)
    assert isinstance(new_id, int) and new_id > 0 and new_id != sefer.id


async def test_create_return_trip_raises_when_not_found(db_session):
    svc, _ = _make_service()
    with pytest.raises((ValueError, Exception)):
        await svc.create_return_trip(999999)


async def test_update_sefer_round_trip_failure_is_not_silently_swallowed(db_session):
    """2026-07-01 prod-grade denetimi P0 bug: `_handle_round_trip_on_update`
    dönüş seferi oluşturma hatasını `except Exception: logger.error(...)` ile
    yutuyordu; `update_sefer` yine de True dönüyor, kullanıcı dönüş seferinin
    oluştuğunu sanıyordu. Fix sonrası hata artık yutulmuyor — update_sefer'ın
    kendi dış except/raise zincirine yükselip caller'a görünür oluyor.
    """
    arac = await seed_arac(db_session, plaka="34SWCRT03")
    sofor = await seed_sofor(db_session, ad_soyad="Sofor SWC Rt3")
    sefer = await seed_sefer(
        db_session,
        arac_id=arac.id,
        sofor_id=sofor.id,
        sefer_no="SWC-TRIP-RT03",
        cikis_yeri="Istanbul",
        varis_yeri="Ankara",
    )
    await db_session.commit()

    svc, _ = _make_service()
    with patch.object(
        svc, "_create_return_trip", new=AsyncMock(side_effect=RuntimeError("boom"))
    ):
        with pytest.raises(RuntimeError, match="boom"):
            # is_round_trip is a signal-only field (not a physical Sefer
            # column) — pair it with a real column change so
            # `uow.sefer_repo.update_sefer` actually returns True and the
            # ROUND-TRIP CHECK branch executes.
            await svc.update_sefer(
                sefer.id,
                SeferUpdate(is_round_trip=True, notlar="round-trip test"),
            )
    # RuntimeError("boom") propagated instead of being swallowed by
    # `_handle_round_trip_on_update`'s old bare `except Exception` — the
    # caller now sees the failure instead of a silent `True`.


async def test_create_return_trip_no_double_suffix(db_session):
    """Return trip sefer_no gets exactly one '-D' suffix, not '-D-D'.

    The '-D' strip logic on a sefer_no ending in '-D' would re-use the same
    sefer_no (uniqueness conflict). Here we test the happy path: a sefer with
    no sefer_no at all (NULL) → return trip succeeds with NULL sefer_no too.
    """
    arac = await seed_arac(db_session, plaka="34SWCRT02")
    sofor = await seed_sofor(db_session, ad_soyad="Sofor SWC Rt2")
    sefer = await seed_sefer(
        db_session,
        arac_id=arac.id,
        sofor_id=sofor.id,
        cikis_yeri="Ankara",
        varis_yeri="Istanbul",
    )
    await db_session.commit()

    svc, _ = _make_service()
    new_id = await svc.create_return_trip(sefer.id)
    assert isinstance(new_id, int) and new_id > 0


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
# 9b. _repredikt_for_update — soft-deleted guzergah (2026-07-01 audit)
# ============================================================


async def test_repredikt_for_update_ignores_soft_deleted_guzergah(monkeypatch):
    """2026-07-01 prod-grade denetimi bug (sefer_write_service.py:281):
    `guzergah_id` update_data'da set olsa bile, referans ettiği güzergah
    soft-deleted/pasifse (kök-fix sonrası lokasyon_repo.get_by_id None döner),
    eski/silinmiş rota verisi tahmine beslenmemeli — update_data'daki mesafe/
    eğim alanları current_sefer'daki mevcut değerlerle kalmalı.

    NOT: Bu test `_repredikt_for_update`'in `lokasyon_repo.get_by_id`
    `None` DÖNDÜĞÜNDE doğru davrandığını kilitler — `DummyUoW.lokasyon_repo
    .get_by_id` sabit `AsyncMock(return_value=None)` olduğu için kök-neden
    fix'ini (BaseRepository.get_by_id soft-delete filtresi) DOĞRUDAN kilitlemez;
    bu fix reverte edilse bile bu test yeşil kalır. Kök-neden guard'ı ayrı
    ve gerçek DB'ye karşı çalışan `test_get_by_id_excludes_soft_deleted_by_default`
    (test_base_repository.py) testidir.
    """
    uow = DummyUoW()
    # DummyUoW.lokasyon_repo.get_by_id zaten None döner — soft-deleted
    # güzergah_id'nin kök-fix sonrası gerçek davranışını modelliyor.

    captured = {}

    class _FakePredictionService:
        async def predict_consumption(self, **kwargs):
            captured.update(kwargs)
            return {"tahmini_tuketim": 42.0, "tahmini_litre": 42.0}

    monkeypatch.setattr(
        "v2.modules.prediction_ml.public.get_prediction_service",
        lambda: _FakePredictionService(),
    )

    svc, _ = _make_service()
    current_sefer = _current_sefer(mesafe_km=450.0, ascent_m=200.0, descent_m=150.0)
    update_data = {"guzergah_id": 999}  # references a soft-deleted/gone location

    await svc._repredikt_for_update(uow, current_sefer, update_data)

    # Soft-deleted route contributed nothing — the OLD (current_sefer) route
    # metrics were used for the prediction call, not stale/deleted data.
    assert captured["mesafe_km"] == 450.0
    assert captured["ascent_m"] == 200.0
    assert captured["descent_m"] == 150.0
    # And update_data itself was not silently filled with deleted-route data.
    assert "mesafe_km" not in update_data
    assert "ascent_m" not in update_data
    assert "descent_m" not in update_data


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


async def test_resolve_route_ignores_soft_deleted_guzergah(monkeypatch):
    """2026-07-01 prod-grade denetimi bug: BaseRepository.get_by_id soft-delete
    filtresizdi, bu yüzden pasif/silinmiş bir güzergahın eski mesafe/eğim verisi
    doğrudan canlı yakıt tahminine besleniyordu (sefer_write_service.py:402).
    Kök neden düzeltmesiyle `lokasyon_repo.get_by_id` artık soft-deleted bir
    güzergah için None döner — bu test o davranışı `_resolve_route` seviyesinde
    kilitler: guzergah_id set olsa bile route None dönerse hiçbir stale veri
    `data`'ya yazılmamalı.

    NOT: `DummyUoW.lokasyon_repo.get_by_id` sabit `None` döndürdüğü için bu
    test kök-neden fix'ini (BaseRepository.get_by_id filtresi) DOĞRUDAN
    kilitlemez — sadece `_resolve_route`'un `route_dict=None` girdisini doğru
    işlediğini kilitler. Kök-neden guard'ı `test_base_repository.py`'deki
    gerçek-DB testleridir.
    """
    uow = DummyUoW()
    # DummyUoW.lokasyon_repo.get_by_id zaten None döner (bkz. sınıf tanımı) —
    # bu, kök-fix sonrası soft-deleted bir güzergah_id'nin gerçek davranışını
    # birebir modelliyor.
    svc, _ = _make_service()
    # mesafe_km SeferCreate şemasında >0 zorunlu — burada kasıtlı olarak
    # route enrichment'tan BAĞIMSIZ, çağıranın zaten sağladığı geçerli bir
    # değer kullanılıyor; asıl iddia route_dict None dönünce fonksiyonun
    # hiçbir alanı (ascent_m/descent_m dahil) silinmiş rota verisiyle
    # doldurmadan erkenden None dönmesi.
    data = _sefer_create(guzergah_id=999, mesafe_km=450.0)

    result = await svc._resolve_route(uow, data)

    assert result is None
    assert data.mesafe_km == 450.0  # değişmedi — stale rota verisiyle ezilmedi
    assert data.ascent_m is None  # route None döndüğü için hiç dokunulmadı
    assert data.descent_m is None


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
# 12. bulk_add_sefer — edge cases (real DB)
# ============================================================


async def test_bulk_add_sefer_empty_list_returns_zero(db_session):
    svc, _ = _make_service()
    count = await svc.bulk_add_sefer([])
    assert count == 0


async def test_bulk_add_sefer_skips_same_origin_destination(db_session):
    arac = await seed_arac(db_session, plaka="34SWCBAS01")
    sofor = await seed_sofor(db_session, ad_soyad="Sofor SWC Bas")
    await db_session.commit()

    svc, _ = _make_service()
    data = _sefer_create(
        arac_id=arac.id,
        sofor_id=sofor.id,
        cikis_yeri="Ankara",
        varis_yeri="Ankara",
    )
    count = await svc.bulk_add_sefer([data])
    assert count == 0


async def test_bulk_add_sefer_skips_zero_distance(db_session):
    """mesafe_km <= 0 check fires before arac/sofor check — no seeding needed."""
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
