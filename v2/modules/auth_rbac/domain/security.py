import base64
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

import bcrypt
import jwt
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from app.config import settings
from v2.modules.platform_infra.logging.logger import get_logger

logger = get_logger(__name__)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verifies a password against its hash (English)."""
    try:
        if not plain_password or not hashed_password:
            return False
        return bcrypt.checkpw(
            plain_password.encode("utf-8"), hashed_password.encode("utf-8")
        )
    except Exception as e:
        logger.error(f"Password verification error: {e!s}")
        return False


def get_password_hash(password: str) -> str:
    """Generates a bcrypt hash for a password (English)."""
    if not password:
        raise ValueError("Password cannot be empty")
    password_bytes = password.encode("utf-8")
    if len(password_bytes) > 72:
        raise ValueError("Password too long")
    salt = bcrypt.gensalt(rounds=12)
    return bcrypt.hashpw(password_bytes, salt).decode("utf-8")


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Creates a JWT access token with RS256/HS256 support.

    Sets standard registered claims: `exp`, `iat`, `aud`, `iss`, plus the
    custom `typ="access"` discriminator. `aud` and `iss` come from
    `settings.JWT_AUDIENCE` / `JWT_ISSUER` and are verified at decode time.
    """
    to_encode = data.copy()
    now = datetime.now(timezone.utc)
    expire = now + (
        expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    to_encode.update(
        {
            "exp": expire,
            "iat": now,
            "jti": str(uuid.uuid4()),
            "aud": settings.JWT_AUDIENCE,
            "iss": settings.JWT_ISSUER,
            "typ": "access",
        }
    )

    key = settings.SECRET_KEY.get_secret_value()
    algorithm = "HS256"

    if settings.ALGORITHM == "RS256" and settings.JWT_PRIVATE_KEY:
        key = settings.JWT_PRIVATE_KEY.get_secret_value()
        algorithm = "RS256"

    return jwt.encode(to_encode, key, algorithm=algorithm)


_jwks_cache: Optional[Dict[str, List[Dict[str, Any]]]] = None


def get_jwks() -> Dict[str, List[Dict[str, Any]]]:
    """
    [B-08] Implementation of JWKS (JSON Web Key Set) for RS256.
    Allows other services to verify current service's tokens without sharing secret.
    Result is cached after first parse — the public key does not change at runtime.
    """
    global _jwks_cache
    if _jwks_cache is not None:
        return _jwks_cache

    if settings.ALGORITHM != "RS256" or not settings.JWT_PUBLIC_KEY:
        return {"keys": []}

    try:
        public_key_pem = settings.JWT_PUBLIC_KEY.get_secret_value()
        public_key = serialization.load_pem_public_key(
            public_key_pem.encode(), backend=default_backend()
        )
        # JWKS (RS256) requires an RSA key; narrow the load_pem union so
        # public_numbers().n/.e type-check (and reject a misconfigured key).
        if not isinstance(public_key, rsa.RSAPublicKey):
            raise ValueError("JWKS requires an RSA public key for RS256")
        numbers = public_key.public_numbers()

        def to_base64_url(n: int) -> str:
            n_bytes = n.to_bytes((n.bit_length() + 7) // 8, byteorder="big")
            return base64.urlsafe_b64encode(n_bytes).decode("utf-8").rstrip("=")

        jwk = {
            "kty": "RSA",
            "use": "sig",
            "alg": "RS256",
            "kid": "lojinext-v2-1",
            "n": to_base64_url(numbers.n),
            "e": to_base64_url(numbers.e),
        }
        _jwks_cache = {"keys": [jwk]}
        return _jwks_cache
    except Exception as e:
        logger.error(f"Failed to generate JWKS: {e!s}")
        return {"keys": []}
