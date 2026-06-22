import hashlib
import hmac
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

import jwt

from app.config import settings
from app.infrastructure.logging.logger import get_logger

logger = get_logger(__name__)


def get_password_hash(password: str) -> str:
    """Hash a plain text password using bcrypt.

    Delegates to the single canonical implementation in ``app.core.security``
    so the 72-byte guard and cost factor (rounds=12) stay consistent across the
    codebase (previously this had no length guard — SEC-007).
    """
    from app.core.security import get_password_hash as _canonical_hash

    return _canonical_hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plain text password against a bcrypt hash.

    Delegates to ``app.core.security.verify_password`` (single implementation).
    """
    from app.core.security import verify_password as _canonical_verify

    return _canonical_verify(plain_password, hashed_password)


def hash_token(token: str) -> str:
    """SHA-256 hash of a token for storage. Tokens exceed bcrypt's 72-byte limit."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def verify_token_hash(token: str, token_hash: str) -> bool:
    """Constant-time comparison of a token against its stored SHA-256 hash."""
    return hmac.compare_digest(hash_token(token), token_hash)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Create a signed JWT access token.

    Delegates to ``app.core.security.create_access_token`` — single canonical
    implementation with RS256/HS256 branch logic and correct private-key handling.
    """
    from app.core.security import create_access_token as _canonical

    return _canonical(data, expires_delta)


def create_refresh_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Create a signed JWT refresh token.

    Refresh tokens use a *different* audience (`JWT_REFRESH_AUDIENCE`) so they
    cannot be presented to the access-token-protected API surface — even if
    leaked, they only validate at the `/auth/refresh` exchange.
    """
    to_encode = data.copy()
    now = datetime.now(timezone.utc)
    expire = now + (expires_delta or timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS))

    to_encode.update(
        {
            "exp": expire,
            "iat": now,
            "jti": str(uuid.uuid4()),
            "aud": settings.JWT_REFRESH_AUDIENCE,
            "iss": settings.JWT_ISSUER,
            "typ": "refresh",
        }
    )

    encoded_jwt = jwt.encode(
        to_encode, settings.SECRET_KEY.get_secret_value(), algorithm=settings.ALGORITHM
    )
    return encoded_jwt


def get_decode_key() -> str:
    """Return the JWT verification key matching the configured algorithm.

    RS256 verifies with the public key; HS256 (default) with the shared secret.
    Using the HS256 secret under RS256 silently fails every decode (PyJWTError).
    """
    if settings.ALGORITHM == "RS256" and settings.JWT_PUBLIC_KEY:
        return settings.JWT_PUBLIC_KEY.get_secret_value()
    return settings.SECRET_KEY.get_secret_value()


def decode_token(token: str, *, audience: Optional[str] = None) -> Dict[str, Any]:
    """Decode and validate a JWT token.

    Verifies `aud`, `iss`, `exp`. Defaults to the access-token audience; pass
    `audience=settings.JWT_REFRESH_AUDIENCE` (or call `decode_refresh_token`)
    when validating a refresh token so access tokens cannot stand in for one.
    """
    try:
        payload = jwt.decode(
            token,
            get_decode_key(),
            algorithms=[settings.ALGORITHM],
            audience=audience or settings.JWT_AUDIENCE,
            issuer=settings.JWT_ISSUER,
        )
        return payload
    except jwt.PyJWTError as e:
        logger.error(f"JWT decode error: {e}")
        raise e


def decode_refresh_token(token: str) -> Dict[str, Any]:
    """Decode and validate a refresh token.

    Enforces both the refresh audience and `typ == 'refresh'` so an access
    token cannot pass even if it were misissued with the refresh audience.
    """
    payload = decode_token(token, audience=settings.JWT_REFRESH_AUDIENCE)
    if payload.get("typ") != "refresh":
        raise jwt.InvalidTokenError("Token type is not 'refresh'")
    return payload
