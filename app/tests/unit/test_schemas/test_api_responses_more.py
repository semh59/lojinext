"""
Extended coverage tests for app/schemas/api_responses.py

Targets missed branches not covered by test_schemas_coverage.py:
- NotificationRuleResponse
- NotificationItemResponse.heal_datetime_string (None case)
- MaintenanceRecordResponse.heal_update_time (iso + bad value)
- MaintenanceRecordResponse.heal_maliyet (valid positive)
- MaintenanceAlertItem validators
- FuelStatsResponse.heal_count (bad value)
- WeatherTripDetail / WeatherDashboardResponse
- MarkAllReadResponse / MarkSingleReadResponse
- BackupTriggerResponse / CircuitBreakerResetResponse
- RouteInfoResponse.heal_floats (bad string)
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# CircuitBreakerResetResponse / BackupTriggerResponse
# ---------------------------------------------------------------------------


class TestSimpleResponses:
    def test_circuit_breaker_reset(self):
        from v2.modules.admin_platform.schemas import CircuitBreakerResetResponse

        r = CircuitBreakerResetResponse(success=True, message="Reset OK")
        assert r.success is True
        assert r.message == "Reset OK"

    def test_backup_trigger(self):
        from v2.modules.admin_platform.schemas import BackupTriggerResponse

        r = BackupTriggerResponse(message="Backup started", task_id="abc-123")
        assert r.task_id == "abc-123"

    def test_mark_all_read(self):
        from v2.modules.notification.schemas import MarkAllReadResponse

        r = MarkAllReadResponse(success=True, count=5)
        assert r.count == 5

    def test_mark_single_read(self):
        from v2.modules.notification.schemas import MarkSingleReadResponse

        r = MarkSingleReadResponse(success=False)
        assert r.success is False


# ---------------------------------------------------------------------------
# NotificationRuleResponse
# ---------------------------------------------------------------------------


class TestNotificationRuleResponse:
    def test_valid(self):
        from v2.modules.notification.schemas import NotificationRuleResponse

        r = NotificationRuleResponse(
            id=1,
            olay_tipi="FUEL_ALERT",
            kanallar=["email", "sms"],
            alici_rol_id=2,
            aktif=True,
        )
        assert r.olay_tipi == "FUEL_ALERT"
        assert r.kanallar == ["email", "sms"]
        assert r.aktif is True

    def test_extra_fields_allowed(self):
        from v2.modules.notification.schemas import NotificationRuleResponse

        r = NotificationRuleResponse(
            id=2,
            olay_tipi="X",
            kanallar=[],
            alici_rol_id=1,
            aktif=False,
            extra_key="extra_val",
        )
        assert r.extra_key == "extra_val"


# ---------------------------------------------------------------------------
# NotificationItemResponse — additional branches
# ---------------------------------------------------------------------------


class TestNotificationItemResponseMore:
    def test_heal_datetime_string_none_returns_now(self):
        from v2.modules.notification.schemas import NotificationItemResponse

        item = NotificationItemResponse(
            id=10,
            baslik="X",
            icerik="Y",
            kanal="email",
            durum="sent",
            okundu=False,
            olusturma_tarihi=None,
        )
        # None → falls back to datetime.now().isoformat()
        assert isinstance(item.olusturma_tarihi, str)
        assert len(item.olusturma_tarihi) > 0

    def test_olay_tipi_none_stays_none(self):
        from v2.modules.notification.schemas import NotificationItemResponse

        item = NotificationItemResponse(
            id=11,
            baslik="B",
            icerik="C",
            olay_tipi=None,
            kanal="sms",
            durum="ok",
            okundu=True,
            olusturma_tarihi="2026-01-01",
        )
        assert item.olay_tipi is None

    def test_kanal_empty_becomes_bilinmiyor(self):
        from v2.modules.notification.schemas import NotificationItemResponse

        item = NotificationItemResponse(
            id=12,
            baslik="B",
            icerik="C",
            kanal="",
            durum="ok",
            okundu=False,
            olusturma_tarihi="2026-01-01",
        )
        assert item.kanal == "BİLİNMİYOR"

    def test_icerik_none_becomes_bilinmiyor(self):
        from v2.modules.notification.schemas import NotificationItemResponse

        item = NotificationItemResponse(
            id=13,
            baslik="Title",
            icerik=None,
            kanal="push",
            durum="sent",
            okundu=False,
            olusturma_tarihi="2026-01-01",
        )
        assert item.icerik == "BİLİNMİYOR"


# ---------------------------------------------------------------------------
# MaintenanceRecordResponse — more branches
# ---------------------------------------------------------------------------


class TestMaintenanceRecordResponseMore:
    def test_valid_maliyet_positive(self):
        from decimal import Decimal

        from v2.modules.fleet.schemas import MaintenanceRecordResponse

        rec = MaintenanceRecordResponse(
            id=20,
            bakim_tipi="Yağ Değişimi",
            km_bilgisi=75000,
            bakim_tarihi=datetime.now(timezone.utc),
            maliyet="1500.50",
        )
        assert rec.maliyet == Decimal("1500.50")

    def test_heal_update_time_isostring(self):
        from v2.modules.fleet.schemas import MaintenanceRecordResponse

        rec = MaintenanceRecordResponse(
            id=21,
            bakim_tipi="Filtre",
            km_bilgisi=0,
            bakim_tarihi=datetime.now(timezone.utc),
            guncelleme_tarihi="2026-05-01T12:00:00Z",
        )
        assert isinstance(rec.guncelleme_tarihi, datetime)
        assert rec.guncelleme_tarihi.year == 2026

    def test_heal_update_time_bad_value_becomes_none(self):
        from v2.modules.fleet.schemas import MaintenanceRecordResponse

        rec = MaintenanceRecordResponse(
            id=22,
            bakim_tipi="Brakes",
            km_bilgisi=0,
            bakim_tarihi=datetime.now(timezone.utc),
            guncelleme_tarihi="not-a-date",
        )
        assert rec.guncelleme_tarihi is None

    def test_heal_update_time_datetime_passthrough(self):
        from v2.modules.fleet.schemas import MaintenanceRecordResponse

        dt = datetime(2025, 6, 1, 0, 0, 0, tzinfo=timezone.utc)
        rec = MaintenanceRecordResponse(
            id=23,
            bakim_tipi="Tyres",
            km_bilgisi=0,
            bakim_tarihi=datetime.now(timezone.utc),
            guncelleme_tarihi=dt,
        )
        assert rec.guncelleme_tarihi == dt

    def test_km_bilgisi_string_parsed(self):
        from v2.modules.fleet.schemas import MaintenanceRecordResponse

        rec = MaintenanceRecordResponse(
            id=24,
            bakim_tipi="Test",
            km_bilgisi="50000",
            bakim_tarihi=datetime.now(timezone.utc),
        )
        assert rec.km_bilgisi == 50000

    def test_km_bilgisi_bad_string_becomes_zero(self):
        from v2.modules.fleet.schemas import MaintenanceRecordResponse

        rec = MaintenanceRecordResponse(
            id=25,
            bakim_tipi="Test",
            km_bilgisi="bad",
            bakim_tarihi=datetime.now(timezone.utc),
        )
        assert rec.km_bilgisi == 0

    def test_tamamlandi_defaults_false(self):
        from v2.modules.fleet.schemas import MaintenanceRecordResponse

        rec = MaintenanceRecordResponse(
            id=26,
            bakim_tipi="Test",
            km_bilgisi=0,
            bakim_tarihi=datetime.now(timezone.utc),
        )
        assert rec.tamamlandi is False


# ---------------------------------------------------------------------------
# MaintenanceAlertItem
# ---------------------------------------------------------------------------


class TestMaintenanceAlertItem:
    def test_valid(self):
        from v2.modules.fleet.schemas import MaintenanceAlertItem

        item = MaintenanceAlertItem(
            id=1,
            arac_id=10,
            plaka="34ABC123",
            bakim_tipi="Yağ",
            tarih=datetime.now(timezone.utc),
            vade_durumu="UPCOMING",
        )
        assert item.plaka == "34ABC123"
        assert item.vade_durumu == "UPCOMING"

    def test_empty_plaka_becomes_bilinmiyor(self):
        from v2.modules.fleet.schemas import MaintenanceAlertItem

        item = MaintenanceAlertItem(
            id=2,
            plaka=None,
            bakim_tipi="Fren",
            tarih=datetime.now(timezone.utc),
            vade_durumu="OVERDUE",
        )
        assert item.plaka == "BİLİNMİYOR"

    def test_empty_bakim_tipi_becomes_bilinmiyor(self):
        from v2.modules.fleet.schemas import MaintenanceAlertItem

        item = MaintenanceAlertItem(
            id=3,
            plaka="06XY99",
            bakim_tipi="",
            tarih=datetime.now(timezone.utc),
            vade_durumu="UPCOMING",
        )
        assert item.bakim_tipi == "BİLİNMİYOR"

    def test_tarih_from_isostring(self):
        from v2.modules.fleet.schemas import MaintenanceAlertItem

        item = MaintenanceAlertItem(
            id=4,
            plaka="06XY99",
            bakim_tipi="Yağ",
            tarih="2026-07-01T00:00:00Z",
            vade_durumu="UPCOMING",
        )
        assert isinstance(item.tarih, datetime)

    def test_tarih_bad_value_becomes_now(self):
        from v2.modules.fleet.schemas import MaintenanceAlertItem

        item = MaintenanceAlertItem(
            id=5,
            plaka="06XY99",
            bakim_tipi="Yağ",
            tarih="not-a-date",
            vade_durumu="OVERDUE",
        )
        assert isinstance(item.tarih, datetime)

    def test_tarih_none_becomes_now(self):
        from v2.modules.fleet.schemas import MaintenanceAlertItem

        item = MaintenanceAlertItem(
            id=6,
            plaka="06XY99",
            bakim_tipi="Yağ",
            tarih=None,
            vade_durumu="OVERDUE",
        )
        assert isinstance(item.tarih, datetime)


# ---------------------------------------------------------------------------
# FuelStatsResponse — heal_count bad value
# ---------------------------------------------------------------------------


class TestFuelStatsResponseMore:
    def test_bad_count_string_becomes_none(self):
        from v2.modules.fuel.schemas import FuelStatsResponse

        r = FuelStatsResponse(kayit_sayisi="not-an-int")
        assert r.kayit_sayisi is None

    def test_zero_count_accepted(self):
        from v2.modules.fuel.schemas import FuelStatsResponse

        r = FuelStatsResponse(kayit_sayisi=0)
        assert r.kayit_sayisi == 0

    def test_extra_fields_tolerated(self):
        from v2.modules.fuel.schemas import FuelStatsResponse

        r = FuelStatsResponse(toplam_litre=500.0, per_vehicle={"1": 250.0})
        assert r.per_vehicle == {"1": 250.0}

    def test_bad_float_toplam_maliyet_becomes_none(self):
        from v2.modules.fuel.schemas import FuelStatsResponse

        r = FuelStatsResponse(toplam_maliyet="abc")
        assert r.toplam_maliyet is None

    def test_bad_float_ortalama_birim_fiyat_becomes_none(self):
        from v2.modules.fuel.schemas import FuelStatsResponse

        r = FuelStatsResponse(ortalama_birim_fiyat="xyz")
        assert r.ortalama_birim_fiyat is None


# ---------------------------------------------------------------------------
# WeatherTripDetail / WeatherDashboardResponse
# ---------------------------------------------------------------------------


class TestWeatherSchemas:
    def test_weather_trip_detail_valid(self):
        from v2.modules.route_simulation.schemas import WeatherTripDetail

        d = WeatherTripDetail(
            trip_id=1, plaka="34ABC", risk="High", impact=0.85, error_code=None
        )
        assert d.risk == "High"
        assert d.impact == 0.85

    def test_weather_trip_detail_unavailable(self):
        from v2.modules.route_simulation.schemas import WeatherTripDetail

        d = WeatherTripDetail(
            trip_id=2, plaka="06XY", risk="Unavailable", error_code="TIMEOUT"
        )
        assert d.error_code == "TIMEOUT"
        assert d.impact is None

    def test_weather_dashboard_response(self):
        from v2.modules.route_simulation.schemas import (
            WeatherDashboardResponse,
            WeatherTripDetail,
        )

        r = WeatherDashboardResponse(
            total_active=10,
            high_risk=2,
            medium_risk=3,
            normal=4,
            unavailable=1,
            details=[
                WeatherTripDetail(trip_id=1, plaka="34A", risk="High"),
            ],
        )
        assert r.total_active == 10
        assert len(r.details) == 1

    def test_weather_dashboard_empty_details(self):
        from v2.modules.route_simulation.schemas import WeatherDashboardResponse

        r = WeatherDashboardResponse(
            total_active=0,
            high_risk=0,
            medium_risk=0,
            normal=0,
            unavailable=0,
            details=[],
        )
        assert r.details == []


# ---------------------------------------------------------------------------
# RouteInfoResponse — more branches
# ---------------------------------------------------------------------------


class TestRouteInfoResponseMore:
    def test_bad_float_becomes_none(self):
        from v2.modules.location.schemas import RouteInfoResponse

        r = RouteInfoResponse(distance_km="bad_val")
        assert r.distance_km is None

    def test_zero_float_accepted(self):
        from v2.modules.location.schemas import RouteInfoResponse

        r = RouteInfoResponse(distance_km=0.0)
        assert r.distance_km == 0.0

    def test_all_optional_fields_none(self):
        from v2.modules.location.schemas import RouteInfoResponse

        r = RouteInfoResponse()
        assert r.distance_km is None
        assert r.source is None

    def test_otoban_and_sehir_fields(self):
        from v2.modules.location.schemas import RouteInfoResponse

        r = RouteInfoResponse(otoban_mesafe_km=200.0, sehir_ici_mesafe_km=50.0)
        assert r.otoban_mesafe_km == 200.0
        assert r.sehir_ici_mesafe_km == 50.0

    def test_negative_otoban_becomes_none(self):
        from v2.modules.location.schemas import RouteInfoResponse

        r = RouteInfoResponse(otoban_mesafe_km=-1.0)
        assert r.otoban_mesafe_km is None


# ---------------------------------------------------------------------------
# RouteAnalysisResponse
# ---------------------------------------------------------------------------


class TestRouteAnalysisResponseMore:
    def test_none_difficulty_is_none(self):
        from v2.modules.route_simulation.schemas import RouteAnalysisResponse

        r = RouteAnalysisResponse()
        assert r.difficulty is None

    def test_whitespace_difficulty_becomes_none(self):
        from v2.modules.route_simulation.schemas import RouteAnalysisResponse

        r = RouteAnalysisResponse(difficulty="   ")
        assert r.difficulty is None

    def test_valid_difficulty(self):
        from v2.modules.route_simulation.schemas import RouteAnalysisResponse

        r = RouteAnalysisResponse(difficulty="Düz")
        assert r.difficulty == "Düz"
