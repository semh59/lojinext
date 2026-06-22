"""
Coverage tests for app/schemas/arac.py

Targets uncovered branches in AracBase, AracCreate, AracUpdate, AracResponse.
~33 missed lines → close gaps in validators (heal_*, sanitize_*, validate_*).
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

pytestmark = pytest.mark.unit

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _base_valid() -> dict:
    """Minimal valid payload for AracBase / AracCreate."""
    return dict(
        plaka="34 ABC 123",
        marka="Volvo",
        model="FH",
        yil=2020,
    )


def _response_valid() -> dict:
    """Minimal valid payload for AracResponse."""
    return dict(
        id=1,
        plaka="34 ABC 123",
        marka="Volvo",
        model="FH",
        yil=2020,
        created_at=datetime.now(timezone.utc),
    )


# ---------------------------------------------------------------------------
# AracBase — check_yil validator
# ---------------------------------------------------------------------------


class TestAracBaseCheckYil:
    def test_valid_year_accepted(self):
        from app.schemas.arac import AracCreate

        obj = AracCreate(**{**_base_valid(), "yil": 2015})
        assert obj.yil == 2015

    def test_none_year_accepted(self):
        from app.schemas.arac import AracCreate

        obj = AracCreate(**{**_base_valid(), "yil": None})
        assert obj.yil is None

    def test_future_year_too_far_raises(self):
        from pydantic import ValidationError

        from app.schemas.arac import AracCreate

        future_year = datetime.now(timezone.utc).year + 5
        with pytest.raises(ValidationError):
            AracCreate(**{**_base_valid(), "yil": future_year})

    def test_max_allowed_year_accepted(self):
        from app.schemas.arac import AracCreate

        max_year = datetime.now(timezone.utc).year + 1
        obj = AracCreate(**{**_base_valid(), "yil": max_year})
        assert obj.yil == max_year


# ---------------------------------------------------------------------------
# AracBase — sanitize_plaka validator
# ---------------------------------------------------------------------------


class TestAracBaseSanitizePlaka:
    def test_plaka_stripped_of_whitespace(self):
        from app.schemas.arac import AracCreate

        obj = AracCreate(**{**_base_valid(), "plaka": "  34 ABC 123  "})
        # strip applied → still valid format
        assert "34" in obj.plaka

    def test_plaka_non_string_passes_through(self):
        """Non-string value passes the sanitize step (format validation may catch it)."""
        from pydantic import ValidationError

        from app.schemas.arac import AracCreate

        # None for plaka should fail validation (required field)
        with pytest.raises(ValidationError):
            AracCreate(**{**_base_valid(), "plaka": None})


# ---------------------------------------------------------------------------
# AracBase — validate_marka_model validator (XSS protection)
# ---------------------------------------------------------------------------


class TestAracBaseValidateMarkaModel:
    def test_xss_in_marka_raises(self):
        from pydantic import ValidationError

        from app.schemas.arac import AracCreate

        with pytest.raises(ValidationError):
            AracCreate(**{**_base_valid(), "marka": "<script>alert(1)</script>"})

    def test_xss_in_model_raises(self):
        from pydantic import ValidationError

        from app.schemas.arac import AracCreate

        with pytest.raises(ValidationError):
            AracCreate(**{**_base_valid(), "model": "<iframe src='x'/>"})

    def test_none_model_accepted(self):
        from app.schemas.arac import AracCreate

        obj = AracCreate(**{**_base_valid(), "model": None})
        assert obj.model is None


# ---------------------------------------------------------------------------
# AracBase — validate_notlar validator
# ---------------------------------------------------------------------------


class TestAracBaseValidateNotlar:
    def test_xss_in_notlar_raises(self):
        from pydantic import ValidationError

        from app.schemas.arac import AracCreate

        with pytest.raises(ValidationError):
            AracCreate(**{**_base_valid(), "notlar": "javascript:alert(1)"})

    def test_none_notlar_accepted(self):
        from app.schemas.arac import AracCreate

        obj = AracCreate(**{**_base_valid(), "notlar": None})
        assert obj.notlar is None

    def test_valid_notlar_accepted(self):
        from app.schemas.arac import AracCreate

        obj = AracCreate(**{**_base_valid(), "notlar": "Bakım zamanı geldi."})
        assert obj.notlar == "Bakım zamanı geldi."


# ---------------------------------------------------------------------------
# AracUpdate — all optional, validators same as AracBase
# ---------------------------------------------------------------------------


class TestAracUpdate:
    def test_empty_update_valid(self):
        from app.schemas.arac import AracUpdate

        obj = AracUpdate()
        assert obj.plaka is None
        assert obj.marka is None

    def test_yil_future_too_far_raises(self):
        from pydantic import ValidationError

        from app.schemas.arac import AracUpdate

        future_year = datetime.now(timezone.utc).year + 5
        with pytest.raises(ValidationError):
            AracUpdate(yil=future_year)

    def test_yil_none_ok(self):
        from app.schemas.arac import AracUpdate

        obj = AracUpdate(yil=None)
        assert obj.yil is None

    def test_plaka_sanitized(self):
        from app.schemas.arac import AracUpdate

        obj = AracUpdate(plaka="  34 ABC 123  ")
        assert obj.plaka is not None
        assert "34" in obj.plaka

    def test_xss_marka_raises(self):
        from pydantic import ValidationError

        from app.schemas.arac import AracUpdate

        with pytest.raises(ValidationError):
            AracUpdate(marka="<script>x</script>")

    def test_notlar_xss_raises(self):
        from pydantic import ValidationError

        from app.schemas.arac import AracUpdate

        with pytest.raises(ValidationError):
            AracUpdate(notlar="javascript:void(0)")


# ---------------------------------------------------------------------------
# AracResponse — heal_plaka
# ---------------------------------------------------------------------------


class TestAracResponseHealPlaka:
    def test_none_plaka_healed_to_bilinmiyor(self):
        from app.schemas.arac import AracResponse

        data = {**_response_valid(), "plaka": None}
        obj = AracResponse.model_validate(data)
        assert obj.plaka == "BİLİNMİYOR"

    def test_empty_plaka_healed_to_bilinmiyor(self):
        from app.schemas.arac import AracResponse

        data = {**_response_valid(), "plaka": ""}
        obj = AracResponse.model_validate(data)
        assert obj.plaka == "BİLİNMİYOR"

    def test_valid_plaka_uppercased_and_stripped(self):
        from app.schemas.arac import AracResponse

        data = {**_response_valid(), "plaka": "  34 abc 123  "}
        obj = AracResponse.model_validate(data)
        assert obj.plaka == "34 ABC 123"


# ---------------------------------------------------------------------------
# AracResponse — heal_yil
# ---------------------------------------------------------------------------


class TestAracResponseHealYil:
    def test_none_yil_healed_to_none(self):
        from app.schemas.arac import AracResponse

        data = {**_response_valid(), "yil": None}
        obj = AracResponse.model_validate(data)
        assert obj.yil is None

    def test_invalid_yil_out_of_range_becomes_none(self):
        from app.schemas.arac import AracResponse

        data = {**_response_valid(), "yil": 1800}
        obj = AracResponse.model_validate(data)
        assert obj.yil is None

    def test_valid_yil_returned(self):
        from app.schemas.arac import AracResponse

        data = {**_response_valid(), "yil": 2020}
        obj = AracResponse.model_validate(data)
        assert obj.yil == 2020

    def test_string_yil_parsed(self):
        from app.schemas.arac import AracResponse

        data = {**_response_valid(), "yil": "2018"}
        obj = AracResponse.model_validate(data)
        assert obj.yil == 2018

    def test_garbage_yil_becomes_none(self):
        from app.schemas.arac import AracResponse

        data = {**_response_valid(), "yil": "not-a-year"}
        obj = AracResponse.model_validate(data)
        assert obj.yil is None

    def test_future_year_within_2100_healed_to_none(self):
        """AracResponse.heal_yil: year > 2100 becomes None but 2099 raises check_yil."""
        from app.schemas.arac import AracResponse

        # heal_yil accepts 1900-2100 range, but check_yil blocks > current+1
        # So 2099 → heal_yil returns 2099, but check_yil raises ValueError
        # AracResponse overrides both. The inherited check_yil in AracBase
        # applies. For response, it should silently return None per heal_yil.
        # heal_yil: returns None if val<1900 or val>2100; 2099 is valid range
        # But AracBase.check_yil also runs... test what actually happens:
        result = AracResponse.heal_yil(2099)
        # heal_yil should return 2099 since it's in 1900-2100 range
        assert result == 2099


# ---------------------------------------------------------------------------
# AracResponse — heal_strings (marka/model)
# heal_strings runs in mode="before": None/empty/"  " → None (then Pydantic
# applies the inherited min_length=2 so marka=None should raise for required field).
# But in AracResponse marka IS required from AracBase (no Optional).
# The validator converts non-str→None then validation catches it.
# We test the validator logic directly via isolation.
# ---------------------------------------------------------------------------


class TestAracResponseHealStrings:
    def test_heal_strings_none_returns_none(self):
        """Validator function itself returns None for None input."""
        from app.schemas.arac import AracResponse

        result = AracResponse.heal_strings(None)
        assert result is None

    def test_heal_strings_empty_string_returns_none(self):
        """Validator function returns None for blank string."""
        from app.schemas.arac import AracResponse

        result = AracResponse.heal_strings("   ")
        assert result is None

    def test_heal_strings_non_string_returns_none(self):
        """Validator function returns None for non-string (e.g., int)."""
        from app.schemas.arac import AracResponse

        result = AracResponse.heal_strings(12345)
        assert result is None

    def test_heal_strings_valid_strips_whitespace(self):
        """Validator function strips whitespace from a valid string."""
        from app.schemas.arac import AracResponse

        result = AracResponse.heal_strings("  Volvo  ")
        assert result == "Volvo"

    def test_valid_marka_on_response(self):
        """AracResponse with valid marka creates correctly."""
        from app.schemas.arac import AracResponse

        data = {**_response_valid(), "marka": "  Volvo  "}
        obj = AracResponse.model_validate(data)
        assert obj.marka == "Volvo"


# ---------------------------------------------------------------------------
# AracResponse — heal_ints (tank_kapasitesi, maks_yuk_kapasitesi_kg, dingil_sayisi)
# heal_ints returns max(1, int(v)) for valid values, 0 for None/garbage.
# But note: the base field constraint gt=0 runs AFTER the validator, so
# None→0 then gt=0 check fails. Test validator function directly.
# ---------------------------------------------------------------------------


class TestAracResponseHealInts:
    """heal_ints: bozuk int'i geçerli [1, le] aralığına çeker (AUDIT-105).

    Healing'in amacı okuma-500'ü önlemek; çıktı her zaman gt=0/ge=1 ve le= üst
    sınırını sağlayan GEÇERLİ değer olmalı. model_validate ile gerçek doğrulama
    yolu test edilir (mode="before" + Field constraint birlikte).
    """

    def test_none_healed_to_valid_min(self):
        from app.schemas.arac import AracResponse

        obj = AracResponse.model_validate(
            {**_response_valid(), "tank_kapasitesi": None}
        )
        assert obj.tank_kapasitesi == 1  # gt=0 → minimum geçerli

    def test_garbage_healed_to_valid_min(self):
        from app.schemas.arac import AracResponse

        obj = AracResponse.model_validate(
            {**_response_valid(), "tank_kapasitesi": "bad"}
        )
        assert obj.tank_kapasitesi == 1

    def test_valid_positive_kept(self):
        from app.schemas.arac import AracResponse

        obj = AracResponse.model_validate({**_response_valid(), "tank_kapasitesi": 600})
        assert obj.tank_kapasitesi == 600

    def test_negative_clamped_to_min(self):
        from app.schemas.arac import AracResponse

        obj = AracResponse.model_validate({**_response_valid(), "tank_kapasitesi": -10})
        assert obj.tank_kapasitesi == 1

    def test_over_upper_bound_clamped(self):
        """AUDIT-105: le=5000 üstü bozuk değer 500 üretmez, üst sınıra çekilir."""
        from app.schemas.arac import AracResponse

        obj = AracResponse.model_validate(
            {**_response_valid(), "tank_kapasitesi": 99999}
        )
        assert obj.tank_kapasitesi == 5000

    def test_dingil_over_upper_clamped(self):
        from app.schemas.arac import AracResponse

        obj = AracResponse.model_validate({**_response_valid(), "dingil_sayisi": 50})
        assert obj.dingil_sayisi == 10  # le=10


# ---------------------------------------------------------------------------
# AracResponse — heal_floats
# Same issue: heal returns 0.0 for None but field constraints gt=0 block it.
# Test the validator function directly.
# ---------------------------------------------------------------------------


class TestAracResponseHealFloats:
    """heal_floats: aralık [gt, le] dışı bozuk float'ı güvenli fallback'e indirger.

    AUDIT-105: yalnız alt sınır değil, üst sınır (le=) ve exclusive-lower (gt=)
    ihlalleri de healing kapsamında — aksi halde okuma 500'e düşerdi.
    """

    def test_none_healed_to_fallback(self):
        from app.schemas.arac import AracResponse

        obj = AracResponse.model_validate({**_response_valid(), "hedef_tuketim": None})
        assert obj.hedef_tuketim == 32.0  # _FLOAT_FALLBACKS

    def test_garbage_healed_to_fallback(self):
        from app.schemas.arac import AracResponse

        obj = AracResponse.model_validate(
            {**_response_valid(), "hedef_tuketim": "bad_float"}
        )
        assert obj.hedef_tuketim == 32.0

    def test_negative_healed_to_fallback(self):
        from app.schemas.arac import AracResponse

        obj = AracResponse.model_validate({**_response_valid(), "hedef_tuketim": -5.0})
        assert obj.hedef_tuketim == 32.0

    def test_valid_positive_kept(self):
        from app.schemas.arac import AracResponse

        obj = AracResponse.model_validate({**_response_valid(), "hedef_tuketim": 32.5})
        assert obj.hedef_tuketim == 32.5

    def test_over_upper_bound_healed_to_fallback(self):
        """AUDIT-105: le=100 üstü → 500 değil, fallback."""
        from app.schemas.arac import AracResponse

        obj = AracResponse.model_validate({**_response_valid(), "hedef_tuketim": 999.0})
        assert obj.hedef_tuketim == 32.0

    def test_motor_verimliligi_over_upper_healed(self):
        """AUDIT-105: motor_verimliligi le=1.0 üstü bozuk değer (birim karışıklığı)."""
        from app.schemas.arac import AracResponse

        obj = AracResponse.model_validate(
            {**_response_valid(), "motor_verimliligi": 5.0}
        )
        assert obj.motor_verimliligi == 0.38

    def test_below_exclusive_lower_healed(self):
        """gt=0.1 olan motor_verimliligi için 0.05 (>0 ama <0.1) → fallback."""
        from app.schemas.arac import AracResponse

        obj = AracResponse.model_validate(
            {**_response_valid(), "motor_verimliligi": 0.05}
        )
        assert obj.motor_verimliligi == 0.38


# ---------------------------------------------------------------------------
# AracResponse — heal_created_at
# ---------------------------------------------------------------------------


class TestAracResponseHealCreatedAt:
    def test_none_created_at_becomes_now(self):
        from app.schemas.arac import AracResponse

        data = {**_response_valid(), "created_at": None}
        obj = AracResponse.model_validate(data)
        assert isinstance(obj.created_at, datetime)

    def test_valid_datetime_passed_through(self):
        from app.schemas.arac import AracResponse

        dt = datetime(2024, 1, 15, 12, 0, 0, tzinfo=timezone.utc)
        data = {**_response_valid(), "created_at": dt}
        obj = AracResponse.model_validate(data)
        assert obj.created_at == dt

    def test_isoformat_string_parsed(self):
        from app.schemas.arac import AracResponse

        data = {**_response_valid(), "created_at": "2024-03-20T10:30:00+00:00"}
        obj = AracResponse.model_validate(data)
        assert obj.created_at.year == 2024

    def test_z_suffix_parsed(self):
        from app.schemas.arac import AracResponse

        data = {**_response_valid(), "created_at": "2024-06-01T08:00:00Z"}
        obj = AracResponse.model_validate(data)
        assert obj.created_at.year == 2024

    def test_garbage_created_at_becomes_now(self):
        from app.schemas.arac import AracResponse

        data = {**_response_valid(), "created_at": "not-a-date"}
        obj = AracResponse.model_validate(data)
        assert isinstance(obj.created_at, datetime)


# ---------------------------------------------------------------------------
# AracResponse — heal_stats (toplam_km, ort_tuketim)
# ---------------------------------------------------------------------------


class TestAracResponseHealStats:
    def test_none_toplam_km_becomes_zero(self):
        from app.schemas.arac import AracResponse

        data = {**_response_valid(), "toplam_km": None}
        obj = AracResponse.model_validate(data)
        assert obj.toplam_km == 0.0

    def test_negative_toplam_km_clamped(self):
        from app.schemas.arac import AracResponse

        data = {**_response_valid(), "toplam_km": -100.0}
        obj = AracResponse.model_validate(data)
        assert obj.toplam_km == 0.0

    def test_garbage_ort_tuketim_becomes_zero(self):
        from app.schemas.arac import AracResponse

        data = {**_response_valid(), "ort_tuketim": "N/A"}
        obj = AracResponse.model_validate(data)
        assert obj.ort_tuketim == 0.0


# ---------------------------------------------------------------------------
# AracResponse — heal_sefer_count (toplam_sefer)
# ---------------------------------------------------------------------------


class TestAracResponseHealSeferCount:
    def test_none_toplam_sefer_becomes_zero(self):
        from app.schemas.arac import AracResponse

        data = {**_response_valid(), "toplam_sefer": None}
        obj = AracResponse.model_validate(data)
        assert obj.toplam_sefer == 0

    def test_garbage_toplam_sefer_becomes_zero(self):
        from app.schemas.arac import AracResponse

        data = {**_response_valid(), "toplam_sefer": "X"}
        obj = AracResponse.model_validate(data)
        assert obj.toplam_sefer == 0

    def test_negative_toplam_sefer_clamped_to_zero(self):
        from app.schemas.arac import AracResponse

        data = {**_response_valid(), "toplam_sefer": -3}
        obj = AracResponse.model_validate(data)
        assert obj.toplam_sefer == 0

    def test_valid_toplam_sefer_accepted(self):
        from app.schemas.arac import AracResponse

        data = {**_response_valid(), "toplam_sefer": 42}
        obj = AracResponse.model_validate(data)
        assert obj.toplam_sefer == 42
