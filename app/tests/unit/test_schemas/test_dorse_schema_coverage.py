"""
Coverage tests for app/schemas/dorse.py

Targets missed branches in:
- DorseBase (check_yil, sanitize_plaka, validate_strings/notlar)
- DorseCreate (pass-through)
- DorseUpdate (optional fields, plaka pattern)
- DorseResponse (heal_plaka, heal_yil, heal_strings, heal_floats, heal_ints, heal_datetime)
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

pytestmark = pytest.mark.unit


def _base_payload(**overrides) -> dict:
    base = dict(plaka="34ABC123")
    base.update(overrides)
    return base


def _response_payload(**overrides) -> dict:
    now = datetime.now(timezone.utc)
    base = dict(
        id=1,
        plaka="34ABC123",
        created_at=now,
        updated_at=now,
    )
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# DorseBase — check_yil
# ---------------------------------------------------------------------------


class TestDorseBaseCheckYil:
    def test_none_yil_accepted(self):
        from v2.modules.fleet.schemas import DorseCreate

        obj = DorseCreate(**_base_payload(yil=None))
        assert obj.yil is None

    def test_valid_yil_accepted(self):
        from v2.modules.fleet.schemas import DorseCreate

        obj = DorseCreate(**_base_payload(yil=2018))
        assert obj.yil == 2018

    def test_future_yil_too_far_raises(self):
        from pydantic import ValidationError

        from v2.modules.fleet.schemas import DorseCreate

        too_far = datetime.now(timezone.utc).year + 5
        with pytest.raises(ValidationError, match="büyük olamaz"):
            DorseCreate(**_base_payload(yil=too_far))

    def test_max_allowed_yil_accepted(self):
        from v2.modules.fleet.schemas import DorseCreate

        max_yil = datetime.now(timezone.utc).year + 1
        obj = DorseCreate(**_base_payload(yil=max_yil))
        assert obj.yil == max_yil

    def test_min_allowed_yil_accepted(self):
        from v2.modules.fleet.schemas import DorseCreate

        obj = DorseCreate(**_base_payload(yil=1990))
        assert obj.yil == 1990


# ---------------------------------------------------------------------------
# DorseBase — sanitize_plaka
# ---------------------------------------------------------------------------


class TestDorseBaseSanitizePlaka:
    def test_whitespace_stripped(self):
        from v2.modules.fleet.schemas import DorseCreate

        obj = DorseCreate(**_base_payload(plaka="  34ABC123  "))
        assert obj.plaka == "34ABC123"

    def test_non_string_plaka_passthrough(self):
        """Non-string skips the sanitize branch."""
        from pydantic import ValidationError

        from v2.modules.fleet.schemas import DorseCreate

        with pytest.raises(ValidationError):
            DorseCreate(**_base_payload(plaka=None))


# ---------------------------------------------------------------------------
# DorseBase — validate_strings (marka, tipi)
# ---------------------------------------------------------------------------


class TestDorseBaseValidateStrings:
    def test_xss_marka_raises(self):
        from pydantic import ValidationError

        from v2.modules.fleet.schemas import DorseCreate

        with pytest.raises(ValidationError):
            DorseCreate(**_base_payload(marka="<script>x</script>"))

    def test_none_marka_accepted(self):
        from v2.modules.fleet.schemas import DorseCreate

        obj = DorseCreate(**_base_payload(marka=None))
        assert obj.marka is None

    def test_xss_tipi_raises(self):
        from pydantic import ValidationError

        from v2.modules.fleet.schemas import DorseCreate

        with pytest.raises(ValidationError):
            DorseCreate(**_base_payload(tipi="javascript:void(0)"))

    def test_valid_tipi_accepted(self):
        from v2.modules.fleet.schemas import DorseCreate

        obj = DorseCreate(**_base_payload(tipi="Frigo"))
        assert obj.tipi == "Frigo"


# ---------------------------------------------------------------------------
# DorseCreate — basic creation
# ---------------------------------------------------------------------------


class TestDorseCreate:
    def test_minimal_creation(self):
        from v2.modules.fleet.schemas import DorseCreate

        obj = DorseCreate(plaka="06XY9999")
        assert obj.bos_agirlik_kg == 6000.0
        assert obj.maks_yuk_kapasitesi_kg == 24000
        assert obj.lastik_sayisi == 6
        assert obj.aktif is True

    def test_full_creation(self):
        from v2.modules.fleet.schemas import DorseCreate

        obj = DorseCreate(
            plaka="35ZZ1234",
            marka="Schmitz",
            tipi="Frigo",
            yil=2022,
            bos_agirlik_kg=7000.0,
            maks_yuk_kapasitesi_kg=22000,
            lastik_sayisi=8,
        )
        assert obj.marka == "Schmitz"
        assert obj.lastik_sayisi == 8


# ---------------------------------------------------------------------------
# DorseUpdate — optional fields
# ---------------------------------------------------------------------------


class TestDorseUpdate:
    def test_empty_update_valid(self):
        from v2.modules.fleet.schemas import DorseUpdate

        obj = DorseUpdate()
        assert obj.plaka is None
        assert obj.yil is None

    def test_update_aktif(self):
        from v2.modules.fleet.schemas import DorseUpdate

        obj = DorseUpdate(aktif=False)
        assert obj.aktif is False

    def test_update_plaka(self):
        from v2.modules.fleet.schemas import DorseUpdate

        obj = DorseUpdate(plaka="34ABC123")
        assert obj.plaka == "34ABC123"

    def test_update_muayene_tarihi(self):
        from datetime import date

        from v2.modules.fleet.schemas import DorseUpdate

        obj = DorseUpdate(muayene_tarihi=date(2027, 6, 1))
        assert obj.muayene_tarihi == date(2027, 6, 1)


# ---------------------------------------------------------------------------
# DorseResponse — heal_plaka
# ---------------------------------------------------------------------------


class TestDorseResponseHealPlaka:
    def test_none_plaka_becomes_bilinmiyor(self):
        from v2.modules.fleet.schemas import DorseResponse

        obj = DorseResponse.model_validate(_response_payload(plaka=None))
        assert obj.plaka == "BİLİNMİYOR"

    def test_empty_plaka_becomes_bilinmiyor(self):
        from v2.modules.fleet.schemas import DorseResponse

        obj = DorseResponse.model_validate(_response_payload(plaka=""))
        assert obj.plaka == "BİLİNMİYOR"

    def test_lowercase_plaka_uppercased(self):
        from v2.modules.fleet.schemas import DorseResponse

        obj = DorseResponse.model_validate(_response_payload(plaka="06xy99"))
        assert obj.plaka == "06XY99"

    def test_valid_plaka_stripped(self):
        from v2.modules.fleet.schemas import DorseResponse

        obj = DorseResponse.model_validate(_response_payload(plaka="  34ABC  "))
        assert obj.plaka == "34ABC"


# ---------------------------------------------------------------------------
# DorseResponse — heal_yil
# ---------------------------------------------------------------------------


class TestDorseResponseHealYil:
    def test_none_yil_stays_none(self):
        from v2.modules.fleet.schemas import DorseResponse

        obj = DorseResponse.model_validate(_response_payload(yil=None))
        assert obj.yil is None

    def test_valid_yil_returned(self):
        from v2.modules.fleet.schemas import DorseResponse

        obj = DorseResponse.model_validate(_response_payload(yil=2019))
        assert obj.yil == 2019

    def test_out_of_range_yil_becomes_none(self):
        from v2.modules.fleet.schemas import DorseResponse

        obj = DorseResponse.model_validate(_response_payload(yil=1800))
        assert obj.yil is None

    def test_future_range_yil_above_2100_becomes_none(self):
        from v2.modules.fleet.schemas import DorseResponse

        obj = DorseResponse.model_validate(_response_payload(yil=2200))
        assert obj.yil is None

    def test_bad_string_yil_becomes_none(self):
        from v2.modules.fleet.schemas import DorseResponse

        obj = DorseResponse.model_validate(_response_payload(yil="bad"))
        assert obj.yil is None

    def test_string_yil_parsed(self):
        from v2.modules.fleet.schemas import DorseResponse

        obj = DorseResponse.model_validate(_response_payload(yil="2020"))
        assert obj.yil == 2020


# ---------------------------------------------------------------------------
# DorseResponse — heal_strings (marka, tipi)
# ---------------------------------------------------------------------------


class TestDorseResponseHealStrings:
    def test_none_marka_becomes_none(self):
        from v2.modules.fleet.schemas import DorseResponse

        obj = DorseResponse.model_validate(_response_payload(marka=None))
        assert obj.marka is None

    def test_empty_marka_becomes_none(self):
        from v2.modules.fleet.schemas import DorseResponse

        obj = DorseResponse.model_validate(_response_payload(marka="   "))
        assert obj.marka is None

    def test_valid_marka_stripped(self):
        from v2.modules.fleet.schemas import DorseResponse

        obj = DorseResponse.model_validate(_response_payload(marka="  Schmitz  "))
        assert obj.marka == "Schmitz"

    def test_non_string_marka_becomes_none(self):
        from v2.modules.fleet.schemas import DorseResponse

        obj = DorseResponse.model_validate(_response_payload(marka=12345))
        assert obj.marka is None


# ---------------------------------------------------------------------------
# DorseResponse — heal_floats
# ---------------------------------------------------------------------------


class TestDorseResponseHealFloats:
    def test_heal_floats_none_returns_zero(self):
        """Validator function returns 0.0 for None; field gt=0 constraint blocks it in full validation."""
        from v2.modules.fleet.schemas import DorseResponse

        result = DorseResponse.heal_floats(None)
        assert result == 0.0

    def test_heal_floats_negative_clamped(self):
        from v2.modules.fleet.schemas import DorseResponse

        result = DorseResponse.heal_floats(-100.0)
        assert result == 0.0

    def test_heal_floats_bad_string_becomes_zero(self):
        from v2.modules.fleet.schemas import DorseResponse

        result = DorseResponse.heal_floats("bad")
        assert result == 0.0

    def test_valid_float_kept(self):
        from v2.modules.fleet.schemas import DorseResponse

        obj = DorseResponse.model_validate(_response_payload(bos_agirlik_kg=6500.0))
        assert obj.bos_agirlik_kg == 6500.0


# ---------------------------------------------------------------------------
# DorseResponse — heal_ints
# ---------------------------------------------------------------------------


class TestDorseResponseHealInts:
    def test_heal_ints_none_returns_zero(self):
        """Validator function returns 0 for None; gt/ge field constraints block it in full validation."""
        from v2.modules.fleet.schemas import DorseResponse

        result = DorseResponse.heal_ints(None)
        assert result == 0

    def test_heal_ints_negative_clamped(self):
        from v2.modules.fleet.schemas import DorseResponse

        result = DorseResponse.heal_ints(-4)
        assert result == 0

    def test_heal_ints_bad_string_becomes_zero(self):
        from v2.modules.fleet.schemas import DorseResponse

        result = DorseResponse.heal_ints("bad")
        assert result == 0

    def test_valid_int_kept(self):
        from v2.modules.fleet.schemas import DorseResponse

        obj = DorseResponse.model_validate(_response_payload(lastik_sayisi=8))
        assert obj.lastik_sayisi == 8


# ---------------------------------------------------------------------------
# DorseResponse — heal_datetime
# ---------------------------------------------------------------------------


class TestDorseResponseHealDatetime:
    def test_none_created_at_becomes_now(self):
        from v2.modules.fleet.schemas import DorseResponse

        obj = DorseResponse.model_validate(_response_payload(created_at=None))
        assert isinstance(obj.created_at, datetime)

    def test_isostring_parsed(self):
        from v2.modules.fleet.schemas import DorseResponse

        obj = DorseResponse.model_validate(
            _response_payload(created_at="2026-01-01T00:00:00Z")
        )
        assert obj.created_at.year == 2026

    def test_bad_string_becomes_now(self):
        from v2.modules.fleet.schemas import DorseResponse

        obj = DorseResponse.model_validate(_response_payload(created_at="not-a-date"))
        assert isinstance(obj.created_at, datetime)

    def test_datetime_object_passthrough(self):
        from v2.modules.fleet.schemas import DorseResponse

        dt = datetime(2025, 6, 1, tzinfo=timezone.utc)
        obj = DorseResponse.model_validate(_response_payload(created_at=dt))
        assert obj.created_at == dt

    def test_updated_at_healed_as_well(self):
        from v2.modules.fleet.schemas import DorseResponse

        obj = DorseResponse.model_validate(_response_payload(updated_at=None))
        assert isinstance(obj.updated_at, datetime)
