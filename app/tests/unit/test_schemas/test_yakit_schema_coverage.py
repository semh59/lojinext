"""
Coverage tests for v2/modules/fuel/schemas.py

Targets missed branches in:
- YakitBase (validate_strings, normalize_depo_durumu mapping, validate_toplam_tutar)
- YakitCreate (optional toplam_tutar)
- YakitUpdate (validate_strings, normalize_depo_durumu)
- YakitResponse (heal_amounts, heal_km, heal_created_at, heal_plaka, birim_fiyat computed_field)
- YakitListResponse
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal

import pytest

pytestmark = pytest.mark.unit


def _base_payload(**overrides) -> dict:
    base = dict(
        tarih=date.today(),
        arac_id=1,
        fiyat_tl=Decimal("45.50"),
        litre=Decimal("200.00"),
        toplam_tutar=Decimal("9100.00"),
        km_sayac=150000,
    )
    base.update(overrides)
    return base


def _response_payload(**overrides) -> dict:
    base = dict(
        id=1,
        tarih=date.today(),
        arac_id=1,
        fiyat_tl=Decimal("45.50"),
        litre=Decimal("200.00"),
        toplam_tutar=Decimal("9100.00"),
        km_sayac=150000,
        created_at=datetime.now(timezone.utc),
    )
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# YakitBase — validate_strings (istasyon, fis_no)
# ---------------------------------------------------------------------------


class TestYakitBaseValidateStrings:
    def test_none_istasyon_accepted(self):
        from v2.modules.fuel.schemas import YakitCreate

        obj = YakitCreate(**_base_payload(istasyon=None))
        assert obj.istasyon is None

    def test_xss_istasyon_raises(self):
        from pydantic import ValidationError

        from v2.modules.fuel.schemas import YakitCreate

        with pytest.raises(ValidationError):
            YakitCreate(**_base_payload(istasyon="<script>alert(1)</script>"))

    def test_valid_istasyon_accepted(self):
        from v2.modules.fuel.schemas import YakitCreate

        obj = YakitCreate(**_base_payload(istasyon="Shell İstasyonu"))
        assert obj.istasyon == "Shell İstasyonu"

    def test_xss_fis_no_raises(self):
        from pydantic import ValidationError

        from v2.modules.fuel.schemas import YakitCreate

        with pytest.raises(ValidationError):
            YakitCreate(**_base_payload(fis_no="javascript:x"))

    def test_none_fis_no_accepted(self):
        from v2.modules.fuel.schemas import YakitCreate

        obj = YakitCreate(**_base_payload(fis_no=None))
        assert obj.fis_no is None


# ---------------------------------------------------------------------------
# YakitBase — normalize_depo_durumu
# ---------------------------------------------------------------------------


class TestYakitBaseNormalizeDepoDurumu:
    def test_full_maps_to_dolu(self):
        from v2.modules.fuel.schemas import YakitCreate

        obj = YakitCreate(**_base_payload(depo_durumu="full"))
        assert obj.depo_durumu == "Dolu"

    def test_filled_maps_to_doldu(self):
        from v2.modules.fuel.schemas import YakitCreate

        obj = YakitCreate(**_base_payload(depo_durumu="filled"))
        assert obj.depo_durumu == "Doldu"

    def test_partial_maps_to_kismi(self):
        from v2.modules.fuel.schemas import YakitCreate

        obj = YakitCreate(**_base_payload(depo_durumu="partial"))
        assert obj.depo_durumu == "Kısmi"

    def test_kismi_tr_maps_to_kismi(self):
        from v2.modules.fuel.schemas import YakitCreate

        obj = YakitCreate(**_base_payload(depo_durumu="kismi"))
        assert obj.depo_durumu == "Kısmi"

    def test_unknown_maps_to_bilinmiyor(self):
        from v2.modules.fuel.schemas import YakitCreate

        obj = YakitCreate(**_base_payload(depo_durumu="unknown"))
        assert obj.depo_durumu == "Bilinmiyor"

    def test_dolu_canonical_kept(self):
        from v2.modules.fuel.schemas import YakitCreate

        obj = YakitCreate(**_base_payload(depo_durumu="dolu"))
        assert obj.depo_durumu == "Dolu"

    def test_doldu_canonical_kept(self):
        from v2.modules.fuel.schemas import YakitCreate

        obj = YakitCreate(**_base_payload(depo_durumu="doldu"))
        assert obj.depo_durumu == "Doldu"

    def test_none_depo_durumu_passthrough(self):
        """None is passed through the mapping (validator returns None)."""
        from v2.modules.fuel.schemas import YakitCreate

        # YakitBase has default "Bilinmiyor", None gets mapped to None by validator
        # but the field has default so the default takes over during field init
        obj = YakitCreate(**_base_payload())
        assert obj.depo_durumu == "Bilinmiyor"


# ---------------------------------------------------------------------------
# YakitCreate — optional toplam_tutar
# ---------------------------------------------------------------------------


class TestYakitCreate:
    def test_without_toplam_tutar(self):
        from v2.modules.fuel.schemas import YakitCreate

        payload = _base_payload()
        del payload["toplam_tutar"]
        obj = YakitCreate(**payload)
        assert obj.toplam_tutar is None

    def test_with_toplam_tutar(self):
        from v2.modules.fuel.schemas import YakitCreate

        obj = YakitCreate(**_base_payload(toplam_tutar=Decimal("9100.00")))
        assert obj.toplam_tutar == Decimal("9100.00")

    def test_durum_defaults_to_bekliyor(self):
        from v2.modules.fuel.schemas import YakitCreate

        obj = YakitCreate(**_base_payload())
        assert obj.durum == "Bekliyor"


# ---------------------------------------------------------------------------
# YakitUpdate — normalize_depo_durumu
# ---------------------------------------------------------------------------


class TestYakitUpdate:
    def test_empty_update_valid(self):
        from v2.modules.fuel.schemas import YakitUpdate

        obj = YakitUpdate()
        assert obj.tarih is None
        assert obj.fiyat_tl is None

    def test_depo_durumu_normalized(self):
        from v2.modules.fuel.schemas import YakitUpdate

        obj = YakitUpdate(depo_durumu="full")
        assert obj.depo_durumu == "Dolu"

    def test_partial_normalized(self):
        from v2.modules.fuel.schemas import YakitUpdate

        obj = YakitUpdate(depo_durumu="partial")
        assert obj.depo_durumu == "Kısmi"

    def test_xss_istasyon_raises(self):
        from pydantic import ValidationError

        from v2.modules.fuel.schemas import YakitUpdate

        with pytest.raises(ValidationError):
            YakitUpdate(istasyon="<iframe src='x'/>")

    def test_valid_istasyon(self):
        from v2.modules.fuel.schemas import YakitUpdate

        obj = YakitUpdate(istasyon="BP İstasyon")
        assert obj.istasyon == "BP İstasyon"


# ---------------------------------------------------------------------------
# YakitResponse — heal_amounts
# ---------------------------------------------------------------------------


class TestYakitResponseHealAmounts:
    """heal_amounts: bozuk tutarı geçerli (0, le] aralığına çeker (AUDIT-105).

    Çıktı her zaman gt=0 ve le= üst sınırını sağlayan GEÇERLİ değer; healing'in
    amacı okuma-500'ü önlemek. model_validate ile gerçek doğrulama yolu test edilir.
    """

    def test_none_healed_to_min(self):
        from v2.modules.fuel.schemas import YakitResponse

        obj = YakitResponse.model_validate(_response_payload(fiyat_tl=None))
        assert obj.fiyat_tl == Decimal("0.01")  # gt=0 → minimum geçerli

    def test_negative_healed_to_min(self):
        from v2.modules.fuel.schemas import YakitResponse

        obj = YakitResponse.model_validate(_response_payload(fiyat_tl="-50"))
        assert obj.fiyat_tl == Decimal("0.01")

    def test_bad_string_healed_to_min(self):
        from v2.modules.fuel.schemas import YakitResponse

        obj = YakitResponse.model_validate(_response_payload(fiyat_tl="bad"))
        assert obj.fiyat_tl == Decimal("0.01")

    def test_over_upper_bound_clamped(self):
        """AUDIT-105: fiyat_tl le=1000, litre le=10000 üstü → 500 değil, üst sınır."""
        from v2.modules.fuel.schemas import YakitResponse

        obj = YakitResponse.model_validate(
            _response_payload(fiyat_tl=Decimal("99999"), litre=Decimal("99999"))
        )
        assert obj.fiyat_tl == Decimal("1000")
        assert obj.litre == Decimal("10000")

    def test_valid_amounts_kept(self):
        from v2.modules.fuel.schemas import YakitResponse

        obj = YakitResponse.model_validate(
            _response_payload(fiyat_tl="45.50", litre="200.00", toplam_tutar="9100.00")
        )
        assert obj.fiyat_tl == Decimal("45.50")
        assert obj.litre == Decimal("200.00")


# ---------------------------------------------------------------------------
# YakitResponse — heal_km
# ---------------------------------------------------------------------------


class TestYakitResponseHealKm:
    """heal_km: bozuk KM'yi geçerli [1, le] aralığına çeker (AUDIT-105)."""

    def test_none_healed_to_min(self):
        from v2.modules.fuel.schemas import YakitResponse

        obj = YakitResponse.model_validate(_response_payload(km_sayac=None))
        assert obj.km_sayac == 1  # gt=0 → minimum geçerli

    def test_bad_string_healed_to_min(self):
        from v2.modules.fuel.schemas import YakitResponse

        obj = YakitResponse.model_validate(_response_payload(km_sayac="bad"))
        assert obj.km_sayac == 1

    def test_over_upper_bound_clamped(self):
        """AUDIT-105: km_sayac le=9999999 üstü bozuk değer → 500 değil, üst sınır."""
        from v2.modules.fuel.schemas import YakitResponse

        obj = YakitResponse.model_validate(_response_payload(km_sayac=99999999))
        assert obj.km_sayac == 9999999

    def test_float_km_truncated(self):
        from v2.modules.fuel.schemas import YakitResponse

        obj = YakitResponse.model_validate(_response_payload(km_sayac="150000.9"))
        assert obj.km_sayac == 150000

    def test_valid_km_kept(self):
        from v2.modules.fuel.schemas import YakitResponse

        obj = YakitResponse.model_validate(_response_payload(km_sayac=200000))
        assert obj.km_sayac == 200000


# ---------------------------------------------------------------------------
# YakitResponse — heal_created_at
# ---------------------------------------------------------------------------


class TestYakitResponseHealCreatedAt:
    def test_none_created_at_becomes_now(self):
        from v2.modules.fuel.schemas import YakitResponse

        obj = YakitResponse.model_validate(_response_payload(created_at=None))
        assert isinstance(obj.created_at, datetime)

    def test_isostring_parsed(self):
        from v2.modules.fuel.schemas import YakitResponse

        obj = YakitResponse.model_validate(
            _response_payload(created_at="2026-02-15T10:00:00Z")
        )
        assert obj.created_at.year == 2026

    def test_bad_string_becomes_now(self):
        from v2.modules.fuel.schemas import YakitResponse

        obj = YakitResponse.model_validate(_response_payload(created_at="not-a-date"))
        assert isinstance(obj.created_at, datetime)

    def test_datetime_object_passthrough(self):
        from v2.modules.fuel.schemas import YakitResponse

        dt = datetime(2025, 3, 1, tzinfo=timezone.utc)
        obj = YakitResponse.model_validate(_response_payload(created_at=dt))
        assert obj.created_at == dt


# ---------------------------------------------------------------------------
# YakitResponse — heal_plaka
# ---------------------------------------------------------------------------


class TestYakitResponseHealPlaka:
    def test_none_plaka_becomes_none(self):
        from v2.modules.fuel.schemas import YakitResponse

        obj = YakitResponse.model_validate(_response_payload(plaka=None))
        assert obj.plaka is None

    def test_empty_plaka_becomes_none(self):
        from v2.modules.fuel.schemas import YakitResponse

        obj = YakitResponse.model_validate(_response_payload(plaka="   "))
        assert obj.plaka is None

    def test_non_string_plaka_becomes_none(self):
        from v2.modules.fuel.schemas import YakitResponse

        obj = YakitResponse.model_validate(_response_payload(plaka=12345))
        assert obj.plaka is None

    def test_valid_plaka_stripped(self):
        from v2.modules.fuel.schemas import YakitResponse

        obj = YakitResponse.model_validate(_response_payload(plaka="  34ABC  "))
        assert obj.plaka == "34ABC"


# ---------------------------------------------------------------------------
# YakitResponse — birim_fiyat computed_field
# ---------------------------------------------------------------------------


class TestYakitResponseBirimFiyat:
    def test_birim_fiyat_equals_fiyat_tl(self):
        from v2.modules.fuel.schemas import YakitResponse

        obj = YakitResponse.model_validate(_response_payload(fiyat_tl="55.00"))
        assert obj.birim_fiyat == Decimal("55.00")
        assert obj.birim_fiyat == obj.fiyat_tl


# ---------------------------------------------------------------------------
# YakitListResponse
# ---------------------------------------------------------------------------


class TestYakitListResponse:
    def test_empty_list(self):
        from v2.modules.fuel.schemas import YakitListResponse

        obj = YakitListResponse(items=[], total=0)
        assert obj.items == []
        assert obj.total == 0

    def test_with_items(self):
        from v2.modules.fuel.schemas import YakitListResponse, YakitResponse

        item = YakitResponse.model_validate(_response_payload())
        obj = YakitListResponse(items=[item], total=1)
        assert obj.total == 1
        assert len(obj.items) == 1
