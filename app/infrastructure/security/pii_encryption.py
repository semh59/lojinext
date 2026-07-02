"""PII encryption-at-rest (Tier E madde 26).

Fernet gives randomized (IV-based) confidentiality — the same plaintext never
encrypts to the same ciphertext twice, so it cannot be used for equality
lookups or UNIQUE constraints directly. For fields that need exact-match
lookup/uniqueness (email, driver name) or substring search (driver name),
a deterministic HMAC-SHA256 "blind index" is stored alongside the encrypted
value: the index leaks nothing about the plaintext beyond equality/trigram
membership, but never needs decryption to query.
"""

import hashlib
import hmac
import re
from functools import lru_cache
from typing import List

from cryptography.fernet import Fernet

from app.config import settings


@lru_cache(maxsize=1)
def _fernet() -> Fernet:
    return Fernet(settings.PII_ENCRYPTION_KEY.get_secret_value().encode("ascii"))


@lru_cache(maxsize=1)
def _hmac_key() -> bytes:
    return settings.PII_ENCRYPTION_KEY.get_secret_value().encode("ascii")


def encrypt_pii(value: str) -> str:
    """Randomized encryption — confidentiality only, not searchable."""
    return _fernet().encrypt(value.encode("utf-8")).decode("ascii")


def decrypt_pii(value: str) -> str:
    return _fernet().decrypt(value.encode("ascii")).decode("utf-8")


def decrypt_pii_or(value, default=None):
    """Decrypt-or-passthrough for raw-SQL result rows.

    Raw text() SQL bypasses the EncryptedPII TypeDecorator entirely, so any
    repository method selecting an encrypted column as raw text must run its
    result rows through this before returning them to a caller — otherwise
    the caller (dashboard, PDF, coaching message, ...) displays ciphertext.
    Passing through non-str/None values keeps this safe to call defensively
    on already-decrypted or missing fields.
    """
    if not isinstance(value, str) or not value:
        return default if value is None else value
    try:
        return decrypt_pii(value)
    except Exception:
        # Already-plaintext or corrupt value — never crash a display path.
        return value


def normalize_pii_text(value: str) -> str:
    """Canonical form used for all blind-index computation (case/space-insensitive)."""
    return re.sub(r"\s+", " ", value.strip().upper())


def blind_index(value: str) -> str:
    """Deterministic HMAC for exact-match lookup / uniqueness without decryption."""
    return hmac.new(
        _hmac_key(), normalize_pii_text(value).encode("utf-8"), hashlib.sha256
    ).hexdigest()


def trigram_blind_indexes(value: str) -> List[str]:
    """HMAC of every 3-char substring of the normalized value.

    Used as a candidate-filter index for substring (ILIKE-style) search on an
    encrypted column: the query side computes the same trigrams for the
    search term and looks up rows sharing at least one trigram hash, then the
    caller must decrypt and re-check the actual substring on the (small)
    candidate set to rule out false positives from trigram collisions.
    """
    normalized = normalize_pii_text(value)
    if len(normalized) < 3:
        return [blind_index(normalized)] if normalized else []
    trigrams = {normalized[i : i + 3] for i in range(len(normalized) - 2)}
    key = _hmac_key()
    return [
        hmac.new(key, t.encode("utf-8"), hashlib.sha256).hexdigest() for t in trigrams
    ]
