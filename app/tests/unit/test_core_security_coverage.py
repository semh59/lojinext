"""
Coverage tests for app/core/security.py
Tests verify_password, get_password_hash, create_access_token, get_jwks.
"""

from __future__ import annotations

from datetime import timedelta
from unittest.mock import MagicMock, patch

import pytest

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# verify_password
# ---------------------------------------------------------------------------


def test_verify_password_correct():
    from app.core.security import get_password_hash, verify_password

    pw = "s3cr3tP@ss"
    hashed = get_password_hash(pw)
    assert verify_password(pw, hashed) is True


def test_verify_password_wrong():
    from app.core.security import get_password_hash, verify_password

    hashed = get_password_hash("correct_password")
    assert verify_password("wrong_password", hashed) is False


def test_verify_password_empty_plain():
    from app.core.security import verify_password

    assert verify_password("", "$2b$12$fakehash") is False


def test_verify_password_empty_hashed():
    from app.core.security import verify_password

    assert verify_password("password", "") is False


def test_verify_password_both_empty():
    from app.core.security import verify_password

    assert verify_password("", "") is False


def test_verify_password_bad_hash_returns_false():
    """A malformed bcrypt hash should not crash — returns False."""
    from app.core.security import verify_password

    result = verify_password("password", "not_a_bcrypt_hash")
    assert result is False


# ---------------------------------------------------------------------------
# get_password_hash
# ---------------------------------------------------------------------------


def test_get_password_hash_returns_bcrypt_string():
    from app.core.security import get_password_hash

    h = get_password_hash("test_password")
    assert h.startswith("$2b$")


def test_get_password_hash_empty_raises():
    from app.core.security import get_password_hash

    with pytest.raises(ValueError, match="empty"):
        get_password_hash("")


def test_get_password_hash_too_long_raises():
    from app.core.security import get_password_hash

    # 73 bytes = > 72 byte bcrypt limit
    long_pw = "a" * 73
    with pytest.raises(ValueError, match="too long"):
        get_password_hash(long_pw)


def test_get_password_hash_exactly_72_bytes_ok():
    from app.core.security import get_password_hash

    pw = "a" * 72
    h = get_password_hash(pw)
    assert h.startswith("$2b$")


def test_get_password_hash_unique_salts():
    from app.core.security import get_password_hash

    h1 = get_password_hash("same_password")
    h2 = get_password_hash("same_password")
    assert h1 != h2  # different salts each time


# ---------------------------------------------------------------------------
# create_access_token (HS256 default path)
# ---------------------------------------------------------------------------


def test_create_access_token_returns_string():
    from app.core.security import create_access_token

    token = create_access_token({"sub": "user42"})
    assert isinstance(token, str)
    assert len(token) > 20


def test_create_access_token_custom_expiry():
    import jwt

    from app.config import settings
    from app.core.security import create_access_token

    token = create_access_token({"sub": "user1"}, expires_delta=timedelta(hours=2))
    payload = jwt.decode(
        token,
        settings.SECRET_KEY.get_secret_value(),
        algorithms=["HS256"],
        audience=settings.JWT_AUDIENCE,
        issuer=settings.JWT_ISSUER,
        options={"verify_exp": False},
    )
    assert payload["sub"] == "user1"
    assert payload["typ"] == "access"


def test_create_access_token_includes_standard_claims():
    import jwt

    from app.config import settings
    from app.core.security import create_access_token

    token = create_access_token({"sub": "tester"})
    payload = jwt.decode(
        token,
        settings.SECRET_KEY.get_secret_value(),
        algorithms=["HS256"],
        audience=settings.JWT_AUDIENCE,
        issuer=settings.JWT_ISSUER,
        options={"verify_exp": False},
    )
    assert "exp" in payload
    assert "iat" in payload
    assert payload["aud"] == settings.JWT_AUDIENCE
    assert payload["iss"] == settings.JWT_ISSUER
    assert payload["typ"] == "access"


def test_create_access_token_default_expiry_used_when_none():
    """When expires_delta is not provided, settings.ACCESS_TOKEN_EXPIRE_MINUTES is used."""
    import jwt

    from app.config import settings
    from app.core.security import create_access_token

    token = create_access_token({"sub": "default_exp"})
    payload = jwt.decode(
        token,
        settings.SECRET_KEY.get_secret_value(),
        algorithms=["HS256"],
        audience=settings.JWT_AUDIENCE,
        issuer=settings.JWT_ISSUER,
        options={"verify_exp": False},
    )
    # exp - iat should be approximately ACCESS_TOKEN_EXPIRE_MINUTES minutes
    delta = payload["exp"] - payload["iat"]
    expected_seconds = settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
    assert abs(delta - expected_seconds) < 5  # within 5 seconds tolerance


def test_create_access_token_rs256_path():
    """When ALGORITHM=RS256 and JWT_PRIVATE_KEY is set, use RS256."""
    from app.core.security import create_access_token

    mock_settings = MagicMock()
    mock_settings.ACCESS_TOKEN_EXPIRE_MINUTES = 30
    mock_settings.JWT_AUDIENCE = "lojinext"
    mock_settings.JWT_ISSUER = "lojinext"
    mock_settings.ALGORITHM = "RS256"

    # Build a tiny RSA key pair for test
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import rsa

    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048,
    )
    pem_private = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.TraditionalOpenSSL,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode()

    mock_pk = MagicMock()
    mock_pk.get_secret_value.return_value = pem_private

    mock_settings.JWT_PRIVATE_KEY = mock_pk
    mock_settings.SECRET_KEY = MagicMock()
    mock_settings.SECRET_KEY.get_secret_value.return_value = "fallback_secret"

    with patch("app.core.security.settings", mock_settings):
        token = create_access_token({"sub": "rs256_user"})

    # token should decode with RS256
    import jwt

    pub_pem = (
        private_key.public_key()
        .public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        .decode()
    )

    payload = jwt.decode(
        token,
        pub_pem,
        algorithms=["RS256"],
        audience="lojinext",
        issuer="lojinext",
        options={"verify_exp": False},
    )
    assert payload["sub"] == "rs256_user"


# ---------------------------------------------------------------------------
# get_jwks
# ---------------------------------------------------------------------------


def test_get_jwks_returns_empty_keys_for_hs256():
    """HS256 algorithm → JWKS endpoint returns empty keys list."""
    import app.core.security as sec

    # Reset cache
    sec._jwks_cache = None

    mock_settings = MagicMock()
    mock_settings.ALGORITHM = "HS256"
    mock_settings.JWT_PUBLIC_KEY = None

    with patch("app.core.security.settings", mock_settings):
        result = sec.get_jwks()

    assert result == {"keys": []}


def test_get_jwks_caches_result():
    """Second call returns the cached result without re-parsing."""
    import app.core.security as sec

    cached = {"keys": [{"kty": "RSA", "cached": True}]}
    sec._jwks_cache = cached

    result = sec.get_jwks()
    assert result is cached

    # Reset for other tests
    sec._jwks_cache = None


def test_get_jwks_rs256_returns_rsa_key():
    """RS256 + valid public key → JWKS contains RSA key."""
    import app.core.security as sec

    sec._jwks_cache = None

    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import rsa

    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    pub_pem = (
        private_key.public_key()
        .public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        .decode()
    )

    mock_settings = MagicMock()
    mock_settings.ALGORITHM = "RS256"
    mock_pk = MagicMock()
    mock_pk.get_secret_value.return_value = pub_pem
    mock_settings.JWT_PUBLIC_KEY = mock_pk

    with patch("app.core.security.settings", mock_settings):
        result = sec.get_jwks()

    assert "keys" in result
    assert len(result["keys"]) == 1
    key = result["keys"][0]
    assert key["kty"] == "RSA"
    assert key["alg"] == "RS256"
    assert "n" in key
    assert "e" in key

    # Reset cache
    sec._jwks_cache = None


def test_get_jwks_rs256_bad_key_returns_empty():
    """RS256 + invalid PEM → exception caught, empty keys returned."""
    import app.core.security as sec

    sec._jwks_cache = None

    mock_settings = MagicMock()
    mock_settings.ALGORITHM = "RS256"
    mock_pk = MagicMock()
    mock_pk.get_secret_value.return_value = "INVALID PEM DATA"
    mock_settings.JWT_PUBLIC_KEY = mock_pk

    with patch("app.core.security.settings", mock_settings):
        result = sec.get_jwks()

    assert result == {"keys": []}
    sec._jwks_cache = None
