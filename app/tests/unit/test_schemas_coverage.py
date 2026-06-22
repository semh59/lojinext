"""Coverage tests for app/schemas/api_responses.py and app/schemas/validators.py."""

from datetime import datetime, timezone
from decimal import Decimal

import pytest

pytestmark = pytest.mark.unit


# ─── api_responses: ComponentHealth ─────────────────────────────────────────


class TestComponentHealth:
    def test_healthy_minimal(self):
        from app.schemas.api_responses import ComponentHealth

        ch = ComponentHealth(status="healthy")
        assert ch.status == "healthy"
        assert ch.latency_ms is None
        assert ch.error is None

    def test_with_latency_and_error(self):
        from app.schemas.api_responses import ComponentHealth

        ch = ComponentHealth(status="degraded", latency_ms=42.5, error="timeout")
        assert ch.latency_ms == 42.5
        assert ch.error == "timeout"

    def test_extra_fields_allowed(self):
        from app.schemas.api_responses import ComponentHealth

        ch = ComponentHealth(status="unhealthy", extra_field="something")
        assert ch.extra_field == "something"


# ─── api_responses: HealthCheckResponse ─────────────────────────────────────


class TestHealthCheckResponse:
    def test_basic(self):
        from app.schemas.api_responses import ComponentHealth, HealthCheckResponse

        r = HealthCheckResponse(
            status="healthy",
            uptime_seconds=120,
            components={"db": ComponentHealth(status="healthy", latency_ms=5.0)},
        )
        assert r.uptime_seconds == 120
        assert r.components["db"].status == "healthy"

    def test_extra_allowed(self):
        from app.schemas.api_responses import HealthCheckResponse

        r = HealthCheckResponse(
            status="healthy",
            uptime_seconds=0,
            components={},
            custom="val",
        )
        assert r.custom == "val"


# ─── api_responses: AdminHealthResponse ──────────────────────────────────────


class TestAdminHealthResponse:
    def test_full(self):
        from app.schemas.api_responses import AdminHealthResponse, ComponentHealth

        r = AdminHealthResponse(
            status="healthy",
            uptime_seconds=300,
            components={"redis": ComponentHealth(status="healthy")},
            sentry={"connected": True},
            circuit_breakers={"api": "closed"},
            backups={"last": "2026-06-01"},
        )
        assert r.sentry == {"connected": True}
        assert r.backups["last"] == "2026-06-01"


# ─── api_responses: ImportHistoryItem validators ─────────────────────────────


class TestImportHistoryItem:
    def test_valid(self):
        from app.schemas.api_responses import ImportHistoryItem

        item = ImportHistoryItem(
            id=1,
            dosya_adi="test.xlsx",
            aktarim_tipi="sefer",
            durum="success",
            toplam=10,
            basarili=9,
            hatali=1,
        )
        assert item.dosya_adi == "test.xlsx"
        assert item.basarili == 9

    def test_none_strings_become_bilinmiyor(self):
        from app.schemas.api_responses import ImportHistoryItem

        item = ImportHistoryItem(
            id=2,
            dosya_adi=None,
            aktarim_tipi="",
            durum="  ",
            toplam=0,
            basarili=0,
            hatali=0,
        )
        assert item.dosya_adi == "BİLİNMİYOR"
        assert item.aktarim_tipi == "BİLİNMİYOR"
        assert item.durum == "BİLİNMİYOR"

    def test_negative_ints_become_zero(self):
        from app.schemas.api_responses import ImportHistoryItem

        item = ImportHistoryItem(
            id=3,
            dosya_adi="f",
            aktarim_tipi="t",
            durum="d",
            toplam=-5,
            basarili=None,
            hatali="bad",
        )
        assert item.toplam == 0
        assert item.basarili == 0
        assert item.hatali == 0

    def test_datetime_from_isostring(self):
        from app.schemas.api_responses import ImportHistoryItem

        item = ImportHistoryItem(
            id=4,
            dosya_adi="f",
            aktarim_tipi="t",
            durum="d",
            toplam=1,
            basarili=1,
            hatali=0,
            baslama_zamani="2026-01-15T10:00:00Z",
        )
        assert isinstance(item.baslama_zamani, datetime)

    def test_datetime_bad_value_becomes_none(self):
        from app.schemas.api_responses import ImportHistoryItem

        item = ImportHistoryItem(
            id=5,
            dosya_adi="f",
            aktarim_tipi="t",
            durum="d",
            toplam=0,
            basarili=0,
            hatali=0,
            baslama_zamani="not-a-date",
        )
        assert item.baslama_zamani is None


# ─── api_responses: NotificationItemResponse validators ──────────────────────


class TestNotificationItemResponse:
    def test_valid(self):
        from app.schemas.api_responses import NotificationItemResponse

        item = NotificationItemResponse(
            id=1,
            baslik="Alert",
            icerik="Content",
            kanal="email",
            durum="sent",
            okundu=False,
            olusturma_tarihi="2026-01-01T00:00:00",
        )
        assert item.baslik == "Alert"

    def test_empty_baslik_becomes_bilinmiyor(self):
        from app.schemas.api_responses import NotificationItemResponse

        item = NotificationItemResponse(
            id=2,
            baslik=None,
            icerik="x",
            kanal="sms",
            durum="ok",
            okundu=True,
            olusturma_tarihi="2026-01-01",
        )
        assert item.baslik == "BİLİNMİYOR"

    def test_optional_olay_tipi_empty_becomes_none(self):
        from app.schemas.api_responses import NotificationItemResponse

        item = NotificationItemResponse(
            id=3,
            baslik="x",
            icerik="y",
            olay_tipi="  ",
            kanal="push",
            durum="ok",
            okundu=False,
            olusturma_tarihi="2026-01-01",
        )
        assert item.olay_tipi is None

    def test_datetime_object_converts(self):
        from app.schemas.api_responses import NotificationItemResponse

        now = datetime.now(timezone.utc)
        item = NotificationItemResponse(
            id=4,
            baslik="x",
            icerik="y",
            kanal="push",
            durum="ok",
            okundu=False,
            olusturma_tarihi=now,
        )
        assert "T" in item.olusturma_tarihi


# ─── api_responses: MaintenanceRecordResponse validators ─────────────────────


class TestMaintenanceRecordResponse:
    def test_valid(self):
        from app.schemas.api_responses import MaintenanceRecordResponse

        rec = MaintenanceRecordResponse(
            id=1,
            bakim_tipi="Oil Change",
            km_bilgisi=50000,
            bakim_tarihi=datetime.now(timezone.utc),
            maliyet=Decimal("500.00"),
        )
        assert rec.km_bilgisi == 50000
        assert rec.maliyet == Decimal("500.00")

    def test_empty_bakim_tipi_fallback(self):
        from app.schemas.api_responses import MaintenanceRecordResponse

        rec = MaintenanceRecordResponse(
            id=2,
            bakim_tipi=None,
            km_bilgisi=0,
            bakim_tarihi=datetime.now(timezone.utc),
        )
        assert rec.bakim_tipi == "BİLİNMİYOR"

    def test_negative_km_becomes_zero(self):
        from app.schemas.api_responses import MaintenanceRecordResponse

        rec = MaintenanceRecordResponse(
            id=3,
            bakim_tipi="X",
            km_bilgisi=-100,
            bakim_tarihi=datetime.now(timezone.utc),
        )
        assert rec.km_bilgisi == 0

    def test_negative_maliyet_becomes_zero(self):
        from app.schemas.api_responses import MaintenanceRecordResponse

        rec = MaintenanceRecordResponse(
            id=4,
            bakim_tipi="X",
            km_bilgisi=0,
            bakim_tarihi=datetime.now(timezone.utc),
            maliyet="-100",
        )
        assert rec.maliyet == Decimal("0")

    def test_bad_maliyet_becomes_zero(self):
        from app.schemas.api_responses import MaintenanceRecordResponse

        rec = MaintenanceRecordResponse(
            id=5,
            bakim_tipi="X",
            km_bilgisi=0,
            bakim_tarihi=datetime.now(timezone.utc),
            maliyet="not-a-number",
        )
        assert rec.maliyet == Decimal("0")

    def test_detaylar_empty_becomes_none(self):
        from app.schemas.api_responses import MaintenanceRecordResponse

        rec = MaintenanceRecordResponse(
            id=6,
            bakim_tipi="X",
            km_bilgisi=0,
            bakim_tarihi=datetime.now(timezone.utc),
            detaylar="   ",
        )
        assert rec.detaylar is None

    def test_bakim_tarihi_from_isostring(self):
        from app.schemas.api_responses import MaintenanceRecordResponse

        rec = MaintenanceRecordResponse(
            id=7,
            bakim_tipi="X",
            km_bilgisi=0,
            bakim_tarihi="2026-03-01T00:00:00Z",
        )
        assert isinstance(rec.bakim_tarihi, datetime)

    def test_bakim_tarihi_bad_value_becomes_now(self):
        from app.schemas.api_responses import MaintenanceRecordResponse

        rec = MaintenanceRecordResponse(
            id=8,
            bakim_tipi="X",
            km_bilgisi=0,
            bakim_tarihi="not-a-date",
        )
        assert isinstance(rec.bakim_tarihi, datetime)


# ─── api_responses: FuelStatsResponse validators ─────────────────────────────


class TestFuelStatsResponse:
    def test_valid(self):
        from app.schemas.api_responses import FuelStatsResponse

        r = FuelStatsResponse(
            toplam_litre=1000.0,
            toplam_maliyet=45000.0,
            ortalama_birim_fiyat=45.0,
            kayit_sayisi=22,
        )
        assert r.toplam_litre == 1000.0

    def test_negative_float_becomes_none(self):
        from app.schemas.api_responses import FuelStatsResponse

        r = FuelStatsResponse(toplam_litre=-1.0)
        assert r.toplam_litre is None

    def test_bad_float_becomes_none(self):
        from app.schemas.api_responses import FuelStatsResponse

        r = FuelStatsResponse(toplam_litre="bad")
        assert r.toplam_litre is None

    def test_negative_count_becomes_none(self):
        from app.schemas.api_responses import FuelStatsResponse

        r = FuelStatsResponse(kayit_sayisi=-5)
        assert r.kayit_sayisi is None


# ─── api_responses: RouteInfoResponse validators ─────────────────────────────


class TestRouteInfoResponse:
    def test_valid(self):
        from app.schemas.api_responses import RouteInfoResponse

        r = RouteInfoResponse(distance_km=450.0, duration_min=300.0, source="mapbox")
        assert r.distance_km == 450.0
        assert r.source == "mapbox"

    def test_negative_distance_becomes_none(self):
        from app.schemas.api_responses import RouteInfoResponse

        r = RouteInfoResponse(distance_km=-10.0)
        assert r.distance_km is None

    def test_empty_source_becomes_none(self):
        from app.schemas.api_responses import RouteInfoResponse

        r = RouteInfoResponse(source="  ")
        assert r.source is None

    def test_extra_fields_allowed(self):
        from app.schemas.api_responses import RouteInfoResponse

        r = RouteInfoResponse(distance_km=100.0, geometry="linestring...")
        assert r.geometry == "linestring..."


# ─── api_responses: RouteAnalysisResponse ────────────────────────────────────


class TestRouteAnalysisResponse:
    def test_with_difficulty(self):
        from app.schemas.api_responses import RouteAnalysisResponse

        r = RouteAnalysisResponse(distance_km=500.0, difficulty="Dik/Dağlık")
        assert r.difficulty == "Dik/Dağlık"

    def test_empty_difficulty_becomes_none(self):
        from app.schemas.api_responses import RouteAnalysisResponse

        r = RouteAnalysisResponse(distance_km=100.0, difficulty="")
        assert r.difficulty is None


# ─── validators: sanitize_string ─────────────────────────────────────────────


class TestSanitizeString:
    def test_strips_whitespace(self):
        from app.schemas.validators import sanitize_string

        assert sanitize_string("  hello  ") == "hello"

    def test_removes_null_bytes(self):
        from app.schemas.validators import sanitize_string

        assert "\x00" not in sanitize_string("hel\x00lo")

    def test_non_string_passthrough(self):
        from app.schemas.validators import sanitize_string

        assert sanitize_string(123) == 123

    def test_unicode_normalisation(self):
        from app.schemas.validators import sanitize_string

        # NFC normalisation should not break regular strings
        result = sanitize_string("Türkçe")
        assert result == "Türkçe"


# ─── validators: check_xss ───────────────────────────────────────────────────


class TestCheckXss:
    def test_clean_string_passes(self):
        from app.schemas.validators import check_xss

        assert check_xss("Hello World") == "Hello World"

    def test_script_tag_raises(self):
        from app.schemas.validators import check_xss

        with pytest.raises(ValueError, match="XSS"):
            check_xss("<script>alert(1)</script>")

    def test_javascript_colon_raises(self):
        from app.schemas.validators import check_xss

        with pytest.raises(ValueError):
            check_xss("javascript:void(0)")

    def test_iframe_raises(self):
        from app.schemas.validators import check_xss

        with pytest.raises(ValueError):
            check_xss("<iframe src='x'></iframe>")

    def test_onerror_raises(self):
        from app.schemas.validators import check_xss

        with pytest.raises(ValueError):
            check_xss('<img onerror="alert(1)">')

    def test_non_string_passthrough(self):
        from app.schemas.validators import check_xss

        assert check_xss(42) == 42


# ─── validators: check_sql_injection ─────────────────────────────────────────


class TestCheckSqlInjection:
    def test_clean_string_passes(self):
        from app.schemas.validators import check_sql_injection

        assert check_sql_injection("Istanbul") == "Istanbul"

    def test_union_select_raises(self):
        from app.schemas.validators import check_sql_injection

        with pytest.raises(ValueError, match="SQL injection"):
            check_sql_injection("UNION SELECT * FROM users")

    def test_drop_table_raises(self):
        from app.schemas.validators import check_sql_injection

        with pytest.raises(ValueError):
            check_sql_injection("DROP TABLE seferler")

    def test_non_string_passthrough(self):
        from app.schemas.validators import check_sql_injection

        assert check_sql_injection(None) is None


# ─── validators: validate_safe_string ────────────────────────────────────────


class TestValidateSafeString:
    def test_none_passthrough(self):
        from app.schemas.validators import validate_safe_string

        assert validate_safe_string(None) is None

    def test_clean_value_returned(self):
        from app.schemas.validators import validate_safe_string

        assert validate_safe_string("  Ankara  ") == "Ankara"

    def test_xss_blocked(self):
        from app.schemas.validators import validate_safe_string

        with pytest.raises(ValueError):
            validate_safe_string("<script>alert(1)</script>")

    def test_sql_not_blocked_in_free_text(self):
        # AUDIT-106: serbest-metin alanlarda SQL blocklist KALDIRILDI (gerçek
        # koruma parameterized query'den gelir; blocklist meşru içeriği 422'liyordu).
        from app.schemas.validators import validate_safe_string

        assert validate_safe_string("DELETE FROM users") == "DELETE FROM users"
        # XSS koruması korunur:
        with pytest.raises(ValueError):
            validate_safe_string("<script>alert(1)</script>")


# ─── validators: validate_username ───────────────────────────────────────────


class TestValidateUsername:
    def test_valid(self):
        from app.schemas.validators import validate_username

        assert validate_username("admin_user1") == "admin_user1"

    def test_invalid_chars_raise(self):
        from app.schemas.validators import validate_username

        with pytest.raises(ValueError, match="alt çizgi"):
            validate_username("user@name!")

    def test_non_string_passthrough(self):
        from app.schemas.validators import validate_username

        assert validate_username(99) == 99


# ─── validators: validate_name ───────────────────────────────────────────────


class TestValidateName:
    def test_valid_turkish(self):
        from app.schemas.validators import validate_name

        assert validate_name("Ahmet Yılmaz") == "Ahmet Yılmaz"

    def test_invalid_chars_raise(self):
        from app.schemas.validators import validate_name

        with pytest.raises(ValueError):
            validate_name("Name<script>")

    def test_non_string_passthrough(self):
        from app.schemas.validators import validate_name

        assert validate_name(0) == 0


# ─── validators: mask_phone ──────────────────────────────────────────────────


class TestMaskPhone:
    def test_masks_correctly(self):
        from app.schemas.validators import mask_phone

        masked = mask_phone("05321234567")
        assert masked.startswith("0532")
        assert "***" in masked
        assert masked.endswith("67")

    def test_none_returns_none(self):
        from app.schemas.validators import mask_phone

        assert mask_phone(None) is None

    def test_short_phone_returned_as_is(self):
        from app.schemas.validators import mask_phone

        assert mask_phone("123") == "123"


# ─── validators: validate_dict_size ──────────────────────────────────────────


class TestValidateDictSize:
    def test_within_limit(self):
        from app.schemas.validators import validate_dict_size

        d = {str(i): i for i in range(10)}
        assert validate_dict_size(d) == d

    def test_exceeds_limit_raises(self):
        from app.schemas.validators import validate_dict_size

        d = {str(i): i for i in range(101)}
        with pytest.raises(ValueError, match="100"):
            validate_dict_size(d)

    def test_none_returns_none(self):
        from app.schemas.validators import validate_dict_size

        assert validate_dict_size(None) is None

    def test_non_dict_passthrough(self):
        from app.schemas.validators import validate_dict_size

        assert validate_dict_size("not-a-dict") == "not-a-dict"


# ─── validators: validate_password_complexity ────────────────────────────────


class TestValidatePasswordComplexity:
    def test_valid_password(self):
        from app.schemas.validators import validate_password_complexity

        assert validate_password_complexity("Password1") == "Password1"

    def test_too_short_raises(self):
        from app.schemas.validators import validate_password_complexity

        with pytest.raises(ValueError, match="8 karakter"):
            validate_password_complexity("Ab1")

    def test_no_uppercase_raises(self):
        from app.schemas.validators import validate_password_complexity

        with pytest.raises(ValueError, match="büyük harf"):
            validate_password_complexity("password1")

    def test_no_lowercase_raises(self):
        from app.schemas.validators import validate_password_complexity

        with pytest.raises(ValueError, match="küçük harf"):
            validate_password_complexity("PASSWORD1")

    def test_no_digit_raises(self):
        from app.schemas.validators import validate_password_complexity

        with pytest.raises(ValueError, match="rakam"):
            validate_password_complexity("PasswordOnly")

    def test_non_string_passthrough(self):
        from app.schemas.validators import validate_password_complexity

        assert validate_password_complexity(42) == 42


# ─── validators: validate_phone ──────────────────────────────────────────────


class TestValidatePhone:
    def test_valid_phone(self):
        from app.schemas.validators import validate_phone

        result = validate_phone("0532 123 45 67")
        assert result == "0532 123 45 67"

    def test_none_returns_none(self):
        from app.schemas.validators import validate_phone

        assert validate_phone(None) is None

    def test_empty_string_returns_none(self):
        from app.schemas.validators import validate_phone

        assert validate_phone("  ") is None

    def test_no_digits_raises(self):
        from app.schemas.validators import validate_phone

        with pytest.raises(ValueError, match="rakam"):
            validate_phone("abcdefghij")

    def test_too_short_raises(self):
        from app.schemas.validators import validate_phone

        with pytest.raises(ValueError, match="10 rakam"):
            validate_phone("12345")

    def test_too_long_raises(self):
        from app.schemas.validators import validate_phone

        with pytest.raises(ValueError, match="15 rakam"):
            validate_phone("1234567890123456")
