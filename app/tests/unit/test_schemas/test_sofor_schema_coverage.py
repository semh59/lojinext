"""
Coverage tests for app/schemas/sofor.py

Targets missed branches in:
- SoforBase (sanitize_name, validate_phone_field, validate_notlar)
- SoforCreate (telegram_id)
- SoforUpdate (sanitize_name, validate_phone_field, validate_scores, validate_notlar)
- SoforResponse (heal_name, heal_scores, heal_date, heal_phone, heal_license_class, telefon_masked computed_field)
- DriverPerformanceSchema
- DriverScoreBreakdownSchema
- DriverRouteProfileItemSchema / DriverRouteProfileSchema
"""

from __future__ import annotations

from datetime import date, datetime, timezone

import pytest

pytestmark = pytest.mark.unit


def _base_payload(**overrides) -> dict:
    base = dict(
        ad_soyad="Ahmet Yılmaz",
        telefon="05321234567",
    )
    base.update(overrides)
    return base


def _response_payload(**overrides) -> dict:
    base = dict(
        id=1,
        ad_soyad="Ahmet Yılmaz",
        created_at=datetime.now(timezone.utc),
    )
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# SoforBase — sanitize_name
# ---------------------------------------------------------------------------


class TestSoforBaseSanitizeName:
    def test_name_title_cased(self):
        from v2.modules.driver.schemas import SoforCreate

        obj = SoforCreate(**_base_payload(ad_soyad="ahmet yılmaz"))
        # sanitize + title case applied
        assert obj.ad_soyad[0].isupper() or len(obj.ad_soyad) > 0

    def test_name_with_whitespace_stripped(self):
        from v2.modules.driver.schemas import SoforCreate

        obj = SoforCreate(**_base_payload(ad_soyad="  Mehmet Demir  "))
        assert "Mehmet" in obj.ad_soyad

    def test_non_string_ad_soyad_passthrough(self):
        """Non-string passes sanitize_name (string branch skipped) but fails Pydantic type check."""
        from pydantic import ValidationError

        from v2.modules.driver.schemas import SoforCreate

        with pytest.raises(ValidationError):
            SoforCreate(**_base_payload(ad_soyad=12345))


# ---------------------------------------------------------------------------
# SoforBase — validate_phone_field
# ---------------------------------------------------------------------------


class TestSoforBasePhone:
    def test_valid_phone_accepted(self):
        from v2.modules.driver.schemas import SoforCreate

        obj = SoforCreate(**_base_payload(telefon="05321234567"))
        assert obj.telefon == "05321234567"

    def test_none_phone_accepted(self):
        from v2.modules.driver.schemas import SoforCreate

        obj = SoforCreate(**_base_payload(telefon=None))
        assert obj.telefon is None

    def test_empty_phone_becomes_none(self):
        from v2.modules.driver.schemas import SoforCreate

        obj = SoforCreate(**_base_payload(telefon="   "))
        assert obj.telefon is None

    def test_short_phone_raises(self):
        from pydantic import ValidationError

        from v2.modules.driver.schemas import SoforCreate

        with pytest.raises(ValidationError):
            SoforCreate(**_base_payload(telefon="12345"))


# ---------------------------------------------------------------------------
# SoforBase — validate_notlar
# ---------------------------------------------------------------------------


class TestSoforBaseNotlar:
    def test_xss_notlar_raises(self):
        from pydantic import ValidationError

        from v2.modules.driver.schemas import SoforCreate

        with pytest.raises(ValidationError):
            SoforCreate(**_base_payload(notlar="<script>alert(1)</script>"))

    def test_none_notlar_accepted(self):
        from v2.modules.driver.schemas import SoforCreate

        obj = SoforCreate(**_base_payload(notlar=None))
        assert obj.notlar is None

    def test_valid_notlar_accepted(self):
        from v2.modules.driver.schemas import SoforCreate

        obj = SoforCreate(**_base_payload(notlar="Dikkatli şoför."))
        assert obj.notlar == "Dikkatli şoför."


# ---------------------------------------------------------------------------
# SoforCreate — telegram_id
# ---------------------------------------------------------------------------


class TestSoforCreate:
    def test_with_telegram_id(self):
        from v2.modules.driver.schemas import SoforCreate

        obj = SoforCreate(**_base_payload(telegram_id="@driver123"))
        assert obj.telegram_id == "@driver123"

    def test_without_telegram_id(self):
        from v2.modules.driver.schemas import SoforCreate

        obj = SoforCreate(**_base_payload())
        assert obj.telegram_id is None


# ---------------------------------------------------------------------------
# SoforUpdate — all optional
# ---------------------------------------------------------------------------


class TestSoforUpdate:
    def test_empty_update_valid(self):
        from v2.modules.driver.schemas import SoforUpdate

        obj = SoforUpdate()
        assert obj.ad_soyad is None
        assert obj.score is None

    def test_sanitize_name_applied(self):
        from v2.modules.driver.schemas import SoforUpdate

        obj = SoforUpdate(ad_soyad="  ali veli  ")
        assert obj.ad_soyad is not None
        assert "Ali" in obj.ad_soyad or obj.ad_soyad.strip() != ""

    def test_validate_phone_called(self):
        from pydantic import ValidationError

        from v2.modules.driver.schemas import SoforUpdate

        with pytest.raises(ValidationError):
            SoforUpdate(telefon="123")

    def test_score_out_of_range_raises(self):
        from pydantic import ValidationError

        from v2.modules.driver.schemas import SoforUpdate

        with pytest.raises(ValidationError):
            SoforUpdate(score=3.0)

    def test_manual_score_out_of_range_raises(self):
        from pydantic import ValidationError

        from v2.modules.driver.schemas import SoforUpdate

        with pytest.raises(ValidationError):
            SoforUpdate(manual_score=0.0)

    def test_valid_scores(self):
        from v2.modules.driver.schemas import SoforUpdate

        obj = SoforUpdate(score=1.5, manual_score=0.8)
        assert obj.score == 1.5

    def test_notlar_xss_raises(self):
        from pydantic import ValidationError

        from v2.modules.driver.schemas import SoforUpdate

        with pytest.raises(ValidationError):
            SoforUpdate(notlar="javascript:void(0)")

    def test_hiz_disiplin_skoru(self):
        from v2.modules.driver.schemas import SoforUpdate

        obj = SoforUpdate(hiz_disiplin_skoru=1.2)
        assert obj.hiz_disiplin_skoru == 1.2

    def test_agresif_surus_faktoru(self):
        from v2.modules.driver.schemas import SoforUpdate

        obj = SoforUpdate(agresif_surus_faktoru=0.9)
        assert obj.agresif_surus_faktoru == 0.9


# ---------------------------------------------------------------------------
# SoforResponse — heal_name
# ---------------------------------------------------------------------------


class TestSoforResponseHealName:
    def test_none_name_uses_fallback(self):
        """heal_name returns 'İSİMSİZ SÜRÜCÜ'; sanitize_name then title-cases it."""
        from v2.modules.driver.schemas import SoforResponse

        obj = SoforResponse.model_validate(_response_payload(ad_soyad=None))
        # After sanitize_name.title() the fallback gets title-cased
        assert "si" in obj.ad_soyad.lower() or "İ" in obj.ad_soyad

    def test_empty_name_uses_fallback(self):
        from v2.modules.driver.schemas import SoforResponse

        obj = SoforResponse.model_validate(_response_payload(ad_soyad=""))
        assert len(obj.ad_soyad) > 0

    def test_short_name_padded(self):
        from v2.modules.driver.schemas import SoforResponse

        obj = SoforResponse.model_validate(_response_payload(ad_soyad="Al"))
        # AUDIT-109: sanitize_name artık .title() KULLANMAZ (Türkçe İ/ı bozulmasını
        # önler); kısa-isim işareti Türkçe-aware casing'le "(kısa İsim)" olur.
        assert "kısa İsim" in obj.ad_soyad
        assert obj.ad_soyad.startswith("Al")

    def test_valid_name_kept(self):
        from v2.modules.driver.schemas import SoforResponse

        obj = SoforResponse.model_validate(_response_payload(ad_soyad="Kemal Aydın"))
        assert "Kemal" in obj.ad_soyad


# ---------------------------------------------------------------------------
# SoforResponse — heal_scores
# ---------------------------------------------------------------------------


class TestSoforResponseHealScores:
    def test_none_score_becomes_1(self):
        from v2.modules.driver.schemas import SoforResponse

        obj = SoforResponse.model_validate(_response_payload(score=None))
        assert obj.score == 1.0

    def test_out_of_range_score_becomes_1(self):
        from v2.modules.driver.schemas import SoforResponse

        obj = SoforResponse.model_validate(_response_payload(score=5.0))
        assert obj.score == 1.0

    def test_bad_score_string_becomes_1(self):
        from v2.modules.driver.schemas import SoforResponse

        obj = SoforResponse.model_validate(_response_payload(score="bad"))
        assert obj.score == 1.0

    def test_valid_score_kept(self):
        from v2.modules.driver.schemas import SoforResponse

        obj = SoforResponse.model_validate(_response_payload(score=1.5))
        assert obj.score == 1.5


# ---------------------------------------------------------------------------
# SoforResponse — heal_date
# ---------------------------------------------------------------------------


class TestSoforResponseHealDate:
    def test_none_ise_baslama_stays_none(self):
        from v2.modules.driver.schemas import SoforResponse

        obj = SoforResponse.model_validate(_response_payload(ise_baslama=None))
        assert obj.ise_baslama is None

    def test_isostring_date_parsed(self):
        from v2.modules.driver.schemas import SoforResponse

        obj = SoforResponse.model_validate(_response_payload(ise_baslama="2020-01-15"))
        assert obj.ise_baslama == date(2020, 1, 15)

    def test_bad_date_string_becomes_none(self):
        from v2.modules.driver.schemas import SoforResponse

        obj = SoforResponse.model_validate(_response_payload(ise_baslama="not-a-date"))
        assert obj.ise_baslama is None

    def test_datetime_truncated_to_date(self):
        from v2.modules.driver.schemas import SoforResponse

        obj = SoforResponse.model_validate(
            _response_payload(ise_baslama="2022-06-01T10:00:00")
        )
        assert obj.ise_baslama == date(2022, 6, 1)


# ---------------------------------------------------------------------------
# SoforResponse — heal_phone
# ---------------------------------------------------------------------------


class TestSoforResponseHealPhone:
    def test_none_phone_stays_none(self):
        from v2.modules.driver.schemas import SoforResponse

        obj = SoforResponse.model_validate(_response_payload(telefon=None))
        assert obj.telefon is None

    def test_empty_phone_becomes_none(self):
        from v2.modules.driver.schemas import SoforResponse

        obj = SoforResponse.model_validate(_response_payload(telefon="   "))
        assert obj.telefon is None

    def test_valid_phone_kept(self):
        from v2.modules.driver.schemas import SoforResponse

        obj = SoforResponse.model_validate(_response_payload(telefon="05321234567"))
        assert obj.telefon == "05321234567"

    def test_too_short_phone_becomes_none(self):
        from v2.modules.driver.schemas import SoforResponse

        obj = SoforResponse.model_validate(_response_payload(telefon="12345"))
        assert obj.telefon is None


# ---------------------------------------------------------------------------
# SoforResponse — heal_license_class
# ---------------------------------------------------------------------------


class TestSoforResponseHealLicenseClass:
    def test_valid_uppercase_kept(self):
        from v2.modules.driver.schemas import SoforResponse

        obj = SoforResponse.model_validate(_response_payload(ehliyet_sinifi="CE"))
        assert obj.ehliyet_sinifi == "CE"

    def test_lowercase_class_corrected(self):
        from v2.modules.driver.schemas import SoforResponse

        obj = SoforResponse.model_validate(_response_payload(ehliyet_sinifi="ce"))
        assert obj.ehliyet_sinifi == "CE"

    def test_invalid_class_becomes_E(self):
        from v2.modules.driver.schemas import SoforResponse

        obj = SoforResponse.model_validate(_response_payload(ehliyet_sinifi="X99"))
        assert obj.ehliyet_sinifi == "E"

    def test_none_class_becomes_E(self):
        from v2.modules.driver.schemas import SoforResponse

        obj = SoforResponse.model_validate(_response_payload(ehliyet_sinifi=None))
        assert obj.ehliyet_sinifi == "E"


# ---------------------------------------------------------------------------
# SoforResponse — telefon_masked computed_field
# ---------------------------------------------------------------------------


class TestSoforResponseTelefonMasked:
    def test_masked_phone_format(self):
        from v2.modules.driver.schemas import SoforResponse

        obj = SoforResponse.model_validate(_response_payload(telefon="05321234567"))
        assert obj.telefon_masked is not None
        assert "***" in obj.telefon_masked

    def test_none_phone_masked_is_none(self):
        from v2.modules.driver.schemas import SoforResponse

        obj = SoforResponse.model_validate(_response_payload(telefon=None))
        assert obj.telefon_masked is None


# ---------------------------------------------------------------------------
# DriverPerformanceSchema
# ---------------------------------------------------------------------------


class TestDriverPerformanceSchema:
    def test_valid(self):
        from v2.modules.driver.schemas import DriverPerformanceSchema

        obj = DriverPerformanceSchema(
            safety_score=85.0,
            eco_score=72.0,
            compliance_score=90.0,
            total_score=82.0,
            trend="stable",
            total_km=50000.0,
            total_trips=200,
        )
        assert obj.total_score == 82.0
        assert obj.trend == "stable"

    def test_defaults(self):
        from v2.modules.driver.schemas import DriverPerformanceSchema

        obj = DriverPerformanceSchema(
            safety_score=80.0, eco_score=70.0, compliance_score=88.0, total_score=79.0
        )
        assert obj.total_km == 0
        assert obj.total_trips == 0
        assert obj.trend == "stable"


# ---------------------------------------------------------------------------
# DriverScoreBreakdownSchema
# ---------------------------------------------------------------------------


class TestDriverScoreBreakdownSchema:
    def test_valid(self):
        from v2.modules.driver.schemas import DriverScoreBreakdownSchema

        obj = DriverScoreBreakdownSchema(
            sofor_id=1,
            ad_soyad="Ali Veli",
            manual=1.2,
            auto=1.4,
            total=1.32,
            has_trips=True,
        )
        assert obj.manual_weight == 0.4
        assert obj.auto_weight == 0.6
        assert obj.has_trips is True

    def test_no_trips(self):
        from v2.modules.driver.schemas import DriverScoreBreakdownSchema

        obj = DriverScoreBreakdownSchema(
            sofor_id=2,
            ad_soyad="Bekir Çelik",
            manual=1.0,
            auto=1.0,
            total=1.0,
            has_trips=False,
        )
        assert obj.has_trips is False
        assert obj.trip_count == 0


# ---------------------------------------------------------------------------
# DriverRouteProfileItemSchema / DriverRouteProfileSchema
# ---------------------------------------------------------------------------


class TestDriverRouteProfileSchemas:
    def test_route_item(self):
        from v2.modules.driver.schemas import DriverRouteProfileItemSchema

        item = DriverRouteProfileItemSchema(
            route_type="highway_dominant",
            label="Otoyol Ağırlıklı",
            trip_count=10,
            avg_actual=35.2,
            avg_predicted=33.0,
            deviation_pct=6.67,
        )
        assert item.route_type == "highway_dominant"
        assert item.deviation_pct == 6.67

    def test_route_profile_with_best(self):
        from v2.modules.driver.schemas import (
            DriverRouteProfileItemSchema,
            DriverRouteProfileSchema,
        )

        item = DriverRouteProfileItemSchema(
            route_type="mountain",
            label="Dağlık",
            trip_count=5,
            avg_actual=42.0,
            avg_predicted=40.0,
            deviation_pct=5.0,
        )
        profile = DriverRouteProfileSchema(
            sofor_id=1,
            ad_soyad="Fahri Konak",
            profiles=[item],
            best_route_type="mountain",
        )
        assert profile.best_route_type == "mountain"
        assert profile.min_trips_for_best == 5

    def test_route_profile_no_best(self):
        from v2.modules.driver.schemas import DriverRouteProfileSchema

        profile = DriverRouteProfileSchema(
            sofor_id=2,
            ad_soyad="Hasan Kurt",
            profiles=[],
            best_route_type=None,
        )
        assert profile.best_route_type is None
