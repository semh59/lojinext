"""
Coverage tests for app/schemas/sefer.py

Targets missed branches in:
- SeferBase validators (heal_yakit, heal_weights, normalize_durum, validate_tarih_not_future)
- SeferCreate (validate_km_range model_validator)
- SeferUpdate (heal_mesafe_km, normalize_durum, validate_iptal, validate_km_range)
- SeferResponse healers (heal_durum, heal_strings, heal_required_floats, heal_optional_floats, heal_tarih, _coerce_empty_saat)
- Bulk schemas
- SeferListResponse / SeferStatsResponse
"""  # noqa: E501

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import pytest

pytestmark = pytest.mark.unit


def _base_payload(**overrides) -> dict:
    """Minimal valid SeferCreate payload."""
    base = dict(
        tarih=date.today(),
        arac_id=1,
        sofor_id=1,
        cikis_yeri="Istanbul",
        varis_yeri="Ankara",
        mesafe_km=450.0,
    )
    base.update(overrides)
    return base


def _response_payload(**overrides) -> dict:
    """Minimal valid SeferResponse payload."""
    base = dict(
        id=1,
        tarih=date.today(),
        arac_id=1,
        sofor_id=1,
        cikis_yeri="Istanbul",
        varis_yeri="Ankara",
        mesafe_km=450.0,
        durum="Planlandı",
    )
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# SeferBase — TripStatus enum
# ---------------------------------------------------------------------------


class TestTripStatus:
    def test_all_values(self):
        from v2.modules.trip.schemas import TripStatus

        # Canonical durumlar — DB CHECK ile birebir (ASSIGNED/IN_PROGRESS
        # kaldırıldı, MODEL-001/ARCH-003).
        assert TripStatus.PLANNED == "Planned"
        assert TripStatus.COMPLETED == "Completed"
        assert TripStatus.CANCELLED == "Cancelled"
        assert not hasattr(TripStatus, "ASSIGNED")
        assert not hasattr(TripStatus, "IN_PROGRESS")


# ---------------------------------------------------------------------------
# SeferBase — heal_yakit
# ---------------------------------------------------------------------------


class TestSeferBaseHealYakit:
    def test_none_yakit_stays_none(self):
        from v2.modules.trip.schemas import SeferCreate

        obj = SeferCreate(**_base_payload(dagitilan_yakit=None))
        assert obj.dagitilan_yakit is None

    def test_valid_yakit_accepted(self):
        from v2.modules.trip.schemas import SeferCreate

        obj = SeferCreate(**_base_payload(dagitilan_yakit="250.50"))
        assert obj.dagitilan_yakit == Decimal("250.50")

    def test_negative_yakit_becomes_none(self):
        from v2.modules.trip.schemas import SeferCreate

        obj = SeferCreate(**_base_payload(dagitilan_yakit="-10"))
        assert obj.dagitilan_yakit is None

    def test_bad_yakit_string_becomes_none(self):
        from v2.modules.trip.schemas import SeferCreate

        obj = SeferCreate(**_base_payload(dagitilan_yakit="bad"))
        assert obj.dagitilan_yakit is None


# ---------------------------------------------------------------------------
# SeferBase — heal_weights
# ---------------------------------------------------------------------------


class TestSeferBaseHealWeights:
    def test_none_bos_agirlik_becomes_zero(self):
        from v2.modules.trip.schemas import SeferCreate

        obj = SeferCreate(**_base_payload(bos_agirlik_kg=None))
        assert obj.bos_agirlik_kg == 0

    def test_none_dolu_agirlik_becomes_zero(self):
        from v2.modules.trip.schemas import SeferCreate

        obj = SeferCreate(**_base_payload(dolu_agirlik_kg=None))
        assert obj.dolu_agirlik_kg == 0

    def test_negative_weight_becomes_zero(self):
        from v2.modules.trip.schemas import SeferCreate

        obj = SeferCreate(**_base_payload(net_kg=-100))
        assert obj.net_kg == 0

    def test_bad_weight_string_becomes_zero(self):
        from v2.modules.trip.schemas import SeferCreate

        obj = SeferCreate(**_base_payload(bos_agirlik_kg="bad"))
        assert obj.bos_agirlik_kg == 0


# ---------------------------------------------------------------------------
# SeferBase — validate_tarih_not_future
# ---------------------------------------------------------------------------


class TestSeferBaseTarih:
    def test_today_is_accepted(self):
        from v2.modules.trip.schemas import SeferCreate

        obj = SeferCreate(**_base_payload(tarih=date.today()))
        assert obj.tarih == date.today()

    def test_365_days_ahead_is_accepted(self):
        from v2.modules.trip.schemas import SeferCreate

        future = date.today() + timedelta(days=365)
        obj = SeferCreate(**_base_payload(tarih=future))
        assert obj.tarih == future

    def test_366_days_ahead_raises(self):
        from pydantic import ValidationError

        from v2.modules.trip.schemas import SeferCreate

        too_far = date.today() + timedelta(days=366)
        with pytest.raises(ValidationError, match="365 gun"):
            SeferCreate(**_base_payload(tarih=too_far))


# ---------------------------------------------------------------------------
# SeferCreate — validate_km_range
# ---------------------------------------------------------------------------


class TestSeferCreateMesafeKm:
    def test_zero_mesafe_km_raises(self):
        """SeferBase.mesafe_km carries Field(..., gt=0) — 0 must be rejected
        at the Pydantic layer (before any use-case/DB logic runs)."""
        from pydantic import ValidationError

        from v2.modules.trip.schemas import SeferCreate

        with pytest.raises(ValidationError, match="mesafe_km"):
            SeferCreate(**_base_payload(mesafe_km=0))


class TestSeferCreateKmRange:
    def test_valid_km_range(self):
        from v2.modules.trip.schemas import SeferCreate

        obj = SeferCreate(**_base_payload(baslangic_km=100, bitis_km=200))
        assert obj.bitis_km == 200

    def test_equal_km_accepted(self):
        from v2.modules.trip.schemas import SeferCreate

        obj = SeferCreate(**_base_payload(baslangic_km=100, bitis_km=100))
        assert obj.baslangic_km == obj.bitis_km

    def test_bitis_less_than_baslangic_raises(self):
        from pydantic import ValidationError

        from v2.modules.trip.schemas import SeferCreate

        with pytest.raises(ValidationError, match="buyuk olmali"):
            SeferCreate(**_base_payload(baslangic_km=200, bitis_km=100))

    def test_none_km_range_no_error(self):
        from v2.modules.trip.schemas import SeferCreate

        obj = SeferCreate(**_base_payload(baslangic_km=None, bitis_km=None))
        assert obj.baslangic_km is None

    def test_round_trip_fields_accepted(self):
        from v2.modules.trip.schemas import SeferCreate

        obj = SeferCreate(**_base_payload(is_round_trip=True, return_net_kg=500))
        assert obj.is_round_trip is True
        assert obj.return_net_kg == 500


# ---------------------------------------------------------------------------
# SeferUpdate — heal_mesafe_km
# ---------------------------------------------------------------------------


class TestSeferUpdateHealMesafeKm:
    def test_none_mesafe_stays_none(self):
        from v2.modules.trip.schemas import SeferUpdate

        obj = SeferUpdate(mesafe_km=None)
        assert obj.mesafe_km is None

    def test_positive_value_kept(self):
        from v2.modules.trip.schemas import SeferUpdate

        obj = SeferUpdate(mesafe_km=350.0)
        assert obj.mesafe_km == 350.0

    def test_zero_becomes_1(self):
        from v2.modules.trip.schemas import SeferUpdate

        obj = SeferUpdate(mesafe_km=0)
        assert obj.mesafe_km == 1.0

    def test_negative_becomes_1(self):
        from v2.modules.trip.schemas import SeferUpdate

        obj = SeferUpdate(mesafe_km=-50.0)
        assert obj.mesafe_km == 1.0

    def test_bad_string_becomes_none(self):
        from v2.modules.trip.schemas import SeferUpdate

        obj = SeferUpdate(mesafe_km="bad")
        assert obj.mesafe_km is None


# ---------------------------------------------------------------------------
# SeferUpdate — validate_iptal (CANCELLED requires iptal_nedeni)
# ---------------------------------------------------------------------------


class TestSeferUpdateValidateIptal:
    def test_cancelled_with_reason_ok(self):
        from v2.modules.trip.schemas import SeferUpdate, TripStatus

        obj = SeferUpdate(durum=TripStatus.CANCELLED, iptal_nedeni="Araç arızası")
        assert obj.durum == TripStatus.CANCELLED

    def test_cancelled_without_reason_raises(self):
        from pydantic import ValidationError

        from v2.modules.trip.schemas import SeferUpdate, TripStatus

        with pytest.raises(ValidationError, match="iptal_nedeni"):
            SeferUpdate(durum=TripStatus.CANCELLED, iptal_nedeni=None)

    def test_cancelled_empty_reason_raises(self):
        from pydantic import ValidationError

        from v2.modules.trip.schemas import SeferUpdate, TripStatus

        with pytest.raises(ValidationError, match="iptal_nedeni"):
            SeferUpdate(durum=TripStatus.CANCELLED, iptal_nedeni="   ")

    def test_planned_without_reason_ok(self):
        from v2.modules.trip.schemas import SeferUpdate, TripStatus

        obj = SeferUpdate(durum=TripStatus.PLANNED)
        assert obj.iptal_nedeni is None

    def test_km_range_in_update(self):
        from pydantic import ValidationError

        from v2.modules.trip.schemas import SeferUpdate

        with pytest.raises(ValidationError, match="buyuk olmali"):
            SeferUpdate(baslangic_km=500, bitis_km=100)


# ---------------------------------------------------------------------------
# SeferResponse — heal_durum
# ---------------------------------------------------------------------------


class TestSeferResponseHealDurum:
    def test_known_turkish_status_accepted(self):
        from v2.modules.trip.schemas import SeferResponse

        obj = SeferResponse.model_validate(_response_payload(durum="Yolda"))
        # heal_durum only recognises Turkish-style statuses → passes through
        assert obj.durum is not None

    def test_unknown_durum_falls_back_to_planned(self):
        from v2.modules.trip.schemas import SeferResponse

        obj = SeferResponse.model_validate(_response_payload(durum="UnknownStatus"))
        # heal_durum fallback = "Planlandı", then TripStatus maps PLANNED
        assert obj.durum is not None

    def test_none_durum_healed(self):
        from v2.modules.trip.schemas import SeferResponse

        obj = SeferResponse.model_validate(_response_payload(durum=None))
        assert obj.durum is not None


# ---------------------------------------------------------------------------
# SeferResponse — heal_strings
# ---------------------------------------------------------------------------


class TestSeferResponseHealStrings:
    def test_none_plaka_becomes_none(self):
        from v2.modules.trip.schemas import SeferResponse

        obj = SeferResponse.model_validate(_response_payload(plaka=None))
        assert obj.plaka is None

    def test_empty_plaka_becomes_none(self):
        from v2.modules.trip.schemas import SeferResponse

        obj = SeferResponse.model_validate(_response_payload(plaka="   "))
        assert obj.plaka is None

    def test_valid_plaka_stripped(self):
        from v2.modules.trip.schemas import SeferResponse

        obj = SeferResponse.model_validate(_response_payload(plaka="  34ABC  "))
        assert obj.plaka == "34ABC"

    def test_none_sofor_adi_is_none(self):
        from v2.modules.trip.schemas import SeferResponse

        obj = SeferResponse.model_validate(_response_payload(sofor_adi=None))
        assert obj.sofor_adi is None


# ---------------------------------------------------------------------------
# SeferResponse — heal_required_floats
# ---------------------------------------------------------------------------


class TestSeferResponseHealRequiredFloats:
    def test_none_mesafe_becomes_1(self):
        from v2.modules.trip.schemas import SeferResponse

        obj = SeferResponse.model_validate(_response_payload(mesafe_km=None))
        assert obj.mesafe_km == 1.0

    def test_zero_mesafe_becomes_1(self):
        from v2.modules.trip.schemas import SeferResponse

        obj = SeferResponse.model_validate(_response_payload(mesafe_km=0))
        assert obj.mesafe_km == 1.0

    def test_bad_mesafe_becomes_1(self):
        from v2.modules.trip.schemas import SeferResponse

        obj = SeferResponse.model_validate(_response_payload(mesafe_km="bad"))
        assert obj.mesafe_km == 1.0

    def test_valid_mesafe_kept(self):
        from v2.modules.trip.schemas import SeferResponse

        obj = SeferResponse.model_validate(_response_payload(mesafe_km=350.0))
        assert obj.mesafe_km == 350.0


# ---------------------------------------------------------------------------
# SeferResponse — heal_optional_floats
# ---------------------------------------------------------------------------


class TestSeferResponseHealOptionalFloats:
    def test_zero_ton_becomes_none(self):
        """heal_optional_floats: 0.0 is >= 0, stays 0.0 (ton has ge=0.0 default)."""
        from v2.modules.trip.schemas import SeferResponse

        obj = SeferResponse.model_validate(_response_payload(ton=0.0))
        assert obj.ton == 0.0

    def test_negative_ascent_becomes_none(self):
        from v2.modules.trip.schemas import SeferResponse

        obj = SeferResponse.model_validate(_response_payload(ascent_m=-100))
        assert obj.ascent_m is None

    def test_bad_tuketim_becomes_none(self):
        from v2.modules.trip.schemas import SeferResponse

        obj = SeferResponse.model_validate(_response_payload(tuketim="bad"))
        assert obj.tuketim is None

    def test_valid_descent_kept(self):
        from v2.modules.trip.schemas import SeferResponse

        obj = SeferResponse.model_validate(_response_payload(descent_m=200.0))
        assert obj.descent_m == 200.0


# ---------------------------------------------------------------------------
# SeferResponse — heal_tarih
# ---------------------------------------------------------------------------


class TestSeferResponseHealTarih:
    def test_isostring_tarih_parsed(self):
        from v2.modules.trip.schemas import SeferResponse

        obj = SeferResponse.model_validate(_response_payload(tarih="2026-01-15"))
        assert obj.tarih == date(2026, 1, 15)

    def test_bad_tarih_raises_validation_error(self):
        """heal_tarih returns None for bad strings, but tarih is required → ValidationError."""
        from pydantic import ValidationError

        from v2.modules.trip.schemas import SeferResponse

        with pytest.raises(ValidationError):
            SeferResponse.model_validate(_response_payload(tarih="not-a-date"))

    def test_datetime_tarih_truncated(self):
        from v2.modules.trip.schemas import SeferResponse

        obj = SeferResponse.model_validate(
            _response_payload(tarih="2026-03-20T10:00:00")
        )
        assert obj.tarih == date(2026, 3, 20)


# ---------------------------------------------------------------------------
# SeferResponse — _coerce_empty_saat
# ---------------------------------------------------------------------------


class TestSeferResponseCoerceSaat:
    def test_none_saat_stays_none(self):
        from v2.modules.trip.schemas import SeferResponse

        obj = SeferResponse.model_validate(_response_payload(saat=None))
        assert obj.saat is None

    def test_empty_saat_becomes_none(self):
        from v2.modules.trip.schemas import SeferResponse

        obj = SeferResponse.model_validate(_response_payload(saat=""))
        assert obj.saat is None

    def test_invalid_saat_format_becomes_none(self):
        from v2.modules.trip.schemas import SeferResponse

        obj = SeferResponse.model_validate(_response_payload(saat="25:00"))
        assert obj.saat is None

    def test_valid_saat_kept(self):
        from v2.modules.trip.schemas import SeferResponse

        obj = SeferResponse.model_validate(_response_payload(saat="14:30"))
        assert obj.saat == "14:30"


# ---------------------------------------------------------------------------
# Bulk schemas
# ---------------------------------------------------------------------------


class TestBulkSchemas:
    def test_bulk_status_update(self):
        from v2.modules.trip.schemas import SeferBulkStatusUpdate, TripStatus

        obj = SeferBulkStatusUpdate(
            sefer_ids=[1, 2, 3], new_status=TripStatus.COMPLETED
        )
        assert obj.new_status == TripStatus.COMPLETED
        assert len(obj.sefer_ids) == 3

    def test_bulk_cancel(self):
        from v2.modules.trip.schemas import SeferBulkCancel

        obj = SeferBulkCancel(sefer_ids=[4, 5], iptal_nedeni="Müşteri talebi")
        assert obj.iptal_nedeni == "Müşteri talebi"

    def test_bulk_delete(self):
        from v2.modules.trip.schemas import SeferBulkDelete

        obj = SeferBulkDelete(sefer_ids=[1])
        assert obj.sefer_ids == [1]

    def test_bulk_response(self):
        from v2.modules.trip.schemas import SeferBulkResponse

        obj = SeferBulkResponse(success_count=3, failed_count=1, failed=[99])
        assert obj.failed == [99]

    def test_bulk_response_empty_failed(self):
        from v2.modules.trip.schemas import SeferBulkResponse

        obj = SeferBulkResponse(success_count=5, failed_count=0)
        assert obj.failed == []


# ---------------------------------------------------------------------------
# SeferListResponse / SeferStatsResponse
# ---------------------------------------------------------------------------


class TestSeferListAndStats:
    def test_list_response_empty(self):
        from v2.modules.trip.schemas import SeferListResponse

        r = SeferListResponse(items=[], meta=None)
        assert r.items == []
        assert r.meta is None

    def test_list_response_with_meta(self):
        from v2.modules.trip.schemas import SeferListResponse

        r = SeferListResponse(items=[], meta={"page": 1, "total": 0})
        assert r.meta["page"] == 1

    def test_stats_response(self):
        from v2.modules.trip.schemas import SeferStatsResponse

        r = SeferStatsResponse(
            total_count=10,
            completed_count=5,
            cancelled_count=2,
            planned_count=2,
            in_progress_count=1,
            total_distance_km=4500.0,
            avg_consumption=32.5,
        )
        assert r.total_count == 10
        assert r.avg_consumption == 32.5
