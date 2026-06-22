"""
validators.py — 2nd pass coverage.

Targets remaining uncovered branches in app/schemas/validators.py (~79% → higher):
- sanitize_string: control chars removal (preserves \\n \\r \\t, removes others)
- check_xss: object/embed/form/style/link/meta/svg/math/base/data/vbscript/expression patterns
- check_sql_injection: semicolon--comment, OR/AND quote pattern, DELETE FROM, INSERT INTO
- validate_safe_string: non-string passthrough
- validate_username: sanitize path (strips whitespace)
- validate_name: name with dots and hyphens (valid)
- mask_phone: exactly 4 digits (boundary)
- validate_dict_size: custom max_keys
- validate_password_complexity: non-string passthrough
- create_* factory functions: verify they return a validator callable
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# sanitize_string — control character removal
# ---------------------------------------------------------------------------


class TestSanitizeStringExtended:
    def test_preserves_newline(self):
        from app.schemas.validators import sanitize_string

        result = sanitize_string("line1\nline2")
        assert "\n" in result

    def test_preserves_tab(self):
        from app.schemas.validators import sanitize_string

        result = sanitize_string("col1\tcol2")
        assert "\t" in result

    def test_preserves_carriage_return(self):
        from app.schemas.validators import sanitize_string

        result = sanitize_string("line1\rline2")
        assert "\r" in result

    def test_removes_control_chars(self):
        from app.schemas.validators import sanitize_string

        # \x01 is a control character that should be removed
        result = sanitize_string("hello\x01world")
        assert "\x01" not in result
        assert "hello" in result
        assert "world" in result

    def test_unicode_nfc_normalisation(self):
        """Unicode NFC normalization: NFD combining char → NFC composed."""
        import unicodedata

        from app.schemas.validators import sanitize_string

        # Compose: e + combining acute accent → é (NFC)
        nfd_string = "é"  # NFD form: e + ́
        result = sanitize_string(nfd_string)
        assert unicodedata.is_normalized("NFC", result)

    def test_empty_string_passthrough(self):
        from app.schemas.validators import sanitize_string

        assert sanitize_string("") == ""

    def test_only_whitespace_becomes_empty(self):
        from app.schemas.validators import sanitize_string

        result = sanitize_string("   ")
        assert result == ""


# ---------------------------------------------------------------------------
# check_xss — remaining patterns
# ---------------------------------------------------------------------------


class TestCheckXssAllPatterns:
    def test_object_tag_raises(self):
        from app.schemas.validators import check_xss

        with pytest.raises(ValueError):
            check_xss("<object data='x'></object>")

    def test_embed_tag_raises(self):
        from app.schemas.validators import check_xss

        with pytest.raises(ValueError):
            check_xss("<embed src='x'>")

    def test_form_tag_raises(self):
        from app.schemas.validators import check_xss

        with pytest.raises(ValueError):
            check_xss("<form action='x'>")

    def test_style_tag_raises(self):
        from app.schemas.validators import check_xss

        with pytest.raises(ValueError):
            check_xss("<style>body{}</style>")

    def test_link_tag_raises(self):
        from app.schemas.validators import check_xss

        with pytest.raises(ValueError):
            check_xss("<link rel='stylesheet'>")

    def test_meta_tag_raises(self):
        from app.schemas.validators import check_xss

        with pytest.raises(ValueError):
            check_xss("<meta http-equiv='refresh'>")

    def test_svg_tag_raises(self):
        from app.schemas.validators import check_xss

        with pytest.raises(ValueError):
            check_xss("<svg onload='alert(1)'>")

    def test_math_tag_raises(self):
        from app.schemas.validators import check_xss

        with pytest.raises(ValueError):
            check_xss("<math><mfrac>")

    def test_base_tag_raises(self):
        from app.schemas.validators import check_xss

        with pytest.raises(ValueError):
            check_xss("<base href='http://evil.com'>")

    def test_data_uri_allowed_in_free_text(self):
        # AUDIT-106: "data:" XSS pattern'inden kaldırıldı (serbest-metin notlarda
        # meşru; React çıktı-escaping korur). <h1> tehlikeli pattern değil → geçer.
        from app.schemas.validators import check_xss

        assert (
            check_xss("data:text/html,<h1>test</h1>") == "data:text/html,<h1>test</h1>"
        )
        # Gerçek XSS hâlâ bloklanır (koruma kaybolmadı):
        with pytest.raises(ValueError):
            check_xss("<script>alert(1)</script>")

    def test_vbscript_raises(self):
        from app.schemas.validators import check_xss

        with pytest.raises(ValueError):
            check_xss("vbscript:msgbox(1)")

    def test_css_expression_raises(self):
        from app.schemas.validators import check_xss

        with pytest.raises(ValueError):
            check_xss("background: expression(alert(1))")

    def test_case_insensitive_script(self):
        """Pattern is case-insensitive: SCRIPT should also raise."""
        from app.schemas.validators import check_xss

        with pytest.raises(ValueError):
            check_xss("<SCRIPT>alert(1)</SCRIPT>")

    def test_space_inside_tag(self):
        """< script> (with space) also detected."""
        from app.schemas.validators import check_xss

        with pytest.raises(ValueError):
            check_xss("< script>alert(1)</ script>")

    def test_normal_html_content_safe(self):
        """Normal text with < > that doesn't match patterns."""
        from app.schemas.validators import check_xss

        # This is just text comparison, not a tag
        result = check_xss("price > 100 and cost < 200")
        assert result == "price > 100 and cost < 200"


# ---------------------------------------------------------------------------
# check_sql_injection — remaining patterns
# ---------------------------------------------------------------------------


class TestCheckSqlInjectionAllPatterns:
    def test_semicolon_comment_raises(self):
        from app.schemas.validators import check_sql_injection

        with pytest.raises(ValueError):
            check_sql_injection("value; -- drop table")

    def test_or_quote_pattern_raises(self):
        from app.schemas.validators import check_sql_injection

        with pytest.raises(ValueError):
            check_sql_injection("' OR '1'='1")

    def test_and_quote_pattern_raises(self):
        from app.schemas.validators import check_sql_injection

        with pytest.raises(ValueError):
            check_sql_injection("' AND '1'='1")

    def test_delete_from_raises(self):
        from app.schemas.validators import check_sql_injection

        with pytest.raises(ValueError):
            check_sql_injection("DELETE FROM kullanicilar WHERE 1=1")

    def test_insert_into_raises(self):
        from app.schemas.validators import check_sql_injection

        with pytest.raises(ValueError):
            check_sql_injection("INSERT INTO users VALUES (1, 'x')")

    def test_case_insensitive_union(self):
        """UNION SELECT is case-insensitive."""
        from app.schemas.validators import check_sql_injection

        with pytest.raises(ValueError):
            check_sql_injection("union select * from users")

    def test_normal_sql_keywords_in_text_safe(self):
        """Normal text with SQL keywords is safe (not matching patterns)."""
        from app.schemas.validators import check_sql_injection

        # "selection" contains "select" but not "UNION SELECT"
        result = check_sql_injection("My route selection criteria")
        assert result == "My route selection criteria"


# ---------------------------------------------------------------------------
# validate_safe_string — non-string passthrough
# ---------------------------------------------------------------------------


class TestValidateSafeStringExtended:
    def test_non_string_passthrough(self):
        from app.schemas.validators import validate_safe_string

        assert validate_safe_string(42) == 42

    def test_list_passthrough(self):
        from app.schemas.validators import validate_safe_string

        lst = [1, 2, 3]
        assert validate_safe_string(lst) == lst

    def test_empty_string_returns_empty(self):
        from app.schemas.validators import validate_safe_string

        assert validate_safe_string("") == ""


# ---------------------------------------------------------------------------
# validate_username — sanitize path
# ---------------------------------------------------------------------------


class TestValidateUsernameExtended:
    def test_strips_whitespace_before_validation(self):
        from app.schemas.validators import validate_username

        # After sanitize, "admin " becomes "admin" → valid alphanumeric
        result = validate_username("admin ")
        assert result == "admin"

    def test_empty_string_raises(self):
        from app.schemas.validators import validate_username

        with pytest.raises(ValueError):
            validate_username("@#$")


# ---------------------------------------------------------------------------
# validate_name — valid patterns
# ---------------------------------------------------------------------------


class TestValidateNameExtended:
    def test_name_with_hyphen_and_dot(self):
        from app.schemas.validators import validate_name

        # Hyphen and dot are allowed
        result = validate_name("Ali-Veli Yılmaz.")
        assert result == "Ali-Veli Yılmaz."

    def test_turkish_chars_valid(self):
        from app.schemas.validators import validate_name

        result = validate_name("İğüşöçĞÜŞÖÇ")
        assert "İ" in result

    def test_numbers_in_name_raise(self):
        from app.schemas.validators import validate_name

        with pytest.raises(ValueError):
            validate_name("Ali123")


# ---------------------------------------------------------------------------
# mask_phone — boundary conditions
# ---------------------------------------------------------------------------


class TestMaskPhoneExtended:
    def test_exactly_4_digits(self):
        """Exactly 4 digits: >= 4 so masking applies."""
        from app.schemas.validators import mask_phone

        result = mask_phone("1234")
        assert result is not None
        assert result.startswith("1234")

    def test_empty_string_returns_empty(self):
        from app.schemas.validators import mask_phone

        result = mask_phone("")
        assert result == ""

    def test_long_phone_masked(self):
        from app.schemas.validators import mask_phone

        result = mask_phone("+90 532 123 45 67")
        assert "***" in result


# ---------------------------------------------------------------------------
# validate_dict_size — custom max_keys
# ---------------------------------------------------------------------------


class TestValidateDictSizeExtended:
    def test_custom_max_keys(self):
        from app.schemas.validators import validate_dict_size

        d = {str(i): i for i in range(5)}
        assert validate_dict_size(d, max_keys=10) == d

    def test_exceeds_custom_max_keys(self):
        from app.schemas.validators import validate_dict_size

        d = {str(i): i for i in range(6)}
        with pytest.raises(ValueError, match="5"):
            validate_dict_size(d, max_keys=5)

    def test_exactly_at_limit_passes(self):
        from app.schemas.validators import validate_dict_size

        d = {str(i): i for i in range(100)}
        result = validate_dict_size(d, max_keys=100)
        assert len(result) == 100


# ---------------------------------------------------------------------------
# validate_password_complexity — non-string passthrough
# ---------------------------------------------------------------------------


class TestValidatePasswordComplexityExtended:
    def test_none_passthrough(self):
        from app.schemas.validators import validate_password_complexity

        assert validate_password_complexity(None) is None

    def test_valid_complex_password(self):
        from app.schemas.validators import validate_password_complexity

        result = validate_password_complexity("SecurePass1!")
        assert result == "SecurePass1!"

    def test_valid_turkish_password(self):
        from app.schemas.validators import validate_password_complexity

        result = validate_password_complexity("ŞifreGüçlü1")
        assert "1" in result


# ---------------------------------------------------------------------------
# validate_phone — edge cases
# ---------------------------------------------------------------------------


class TestValidatePhoneExtended:
    def test_empty_string_returns_none(self):
        from app.schemas.validators import validate_phone

        result = validate_phone("")
        assert result is None

    def test_exactly_10_digits_valid(self):
        from app.schemas.validators import validate_phone

        result = validate_phone("0532123456")
        assert result == "0532123456"

    def test_exactly_15_digits_valid(self):
        from app.schemas.validators import validate_phone

        result = validate_phone("905321234567890")
        assert "9053" in result


# ---------------------------------------------------------------------------
# Factory functions — smoke test they return callable validators
# ---------------------------------------------------------------------------


class TestValidatorFactories:
    def test_create_safe_string_validator(self):
        from app.schemas.validators import create_safe_string_validator

        # Returns a Pydantic descriptor proxy (not directly callable in Pydantic v2)
        validator = create_safe_string_validator("name")
        assert validator is not None

    def test_create_username_validator(self):
        from app.schemas.validators import create_username_validator

        validator = create_username_validator("username")
        assert validator is not None

    def test_create_name_validator(self):
        from app.schemas.validators import create_name_validator

        validator = create_name_validator("ad_soyad")
        assert validator is not None

    def test_create_password_validator(self):
        from app.schemas.validators import create_password_validator

        validator = create_password_validator("password")
        assert validator is not None

    def test_create_phone_validator(self):
        from app.schemas.validators import create_phone_validator

        validator = create_phone_validator("telefon")
        assert validator is not None

    def test_create_safe_string_validator_in_model(self):
        """Factory validator works inside a Pydantic model."""
        from pydantic import BaseModel

        from app.schemas.validators import create_safe_string_validator

        class TestModel(BaseModel):
            name: str | None = None
            _validate_name = create_safe_string_validator("name")

        m = TestModel(name="  Ahmet  ")
        assert m.name == "Ahmet"

    def test_factory_blocks_xss_in_model(self):
        """XSS content raises ValidationError inside a model using factory."""
        from pydantic import BaseModel, ValidationError

        from app.schemas.validators import create_safe_string_validator

        class TestModel(BaseModel):
            content: str | None = None
            _validate_content = create_safe_string_validator("content")

        with pytest.raises((ValidationError, ValueError)):
            TestModel(content="<script>alert(1)</script>")
