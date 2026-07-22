"""ORM temel sınıfı + tüm modüllerin paylaştığı column-level yardımcılar.

`Base` her v2 modülünün kendi `infrastructure/models.py`'sindeki ORM
sınıflarının ortak atası (models.py bölünmesi — dalga 16, task #58).
`EncryptedPII`/`get_utc_now` da aynı sebeple buradadır: ikisi de birden
fazla modülün tablosunda kullanılan generic column-tipi/default'tur
(EncryptedPII: driver.Sofor + auth_rbac.Kullanici; get_utc_now: hemen
hemen her tablonun created_at/updated_at default'u) — tek bir modülün
sahip olacağı iş mantığı değil, ORM altyapısı.
"""

from datetime import datetime, timezone

from sqlalchemy import Text, TypeDecorator
from sqlalchemy.ext.asyncio import AsyncAttrs
from sqlalchemy.orm import DeclarativeBase


class EncryptedPII(TypeDecorator):
    """Transparent Fernet encryption for PII columns (Tier E madde 26).

    ORM reads/writes see plaintext (`.email`, `.ad_soyad` etc. behave as
    normal Python str); the DB stores ciphertext only. Because Fernet is
    randomized, this column can NEVER be used in an equality/ILIKE WHERE
    clause or a UNIQUE constraint directly — pair it with a `_bidx` (blind
    index) column (and a trigram-index table for substring search) for that.
    Raw text() SQL bypasses this decorator entirely and sees ciphertext.
    """

    impl = Text
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        from v2.modules.platform_infra.security.pii_encryption import encrypt_pii

        return encrypt_pii(value)

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        from v2.modules.platform_infra.security.pii_encryption import decrypt_pii

        return decrypt_pii(value)


def get_utc_now(ctx=None, *args, **kwargs):
    return datetime.now(timezone.utc)


class Base(AsyncAttrs, DeclarativeBase):
    pass
