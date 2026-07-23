"""ORM temel sınıfı + tüm modüllerin paylaştığı column-level yardımcılar.

`Base` her v2 modülünün kendi `infrastructure/models.py`'sindeki ORM
sınıflarının ortak atası (models.py bölünmesi — dalga 16, task #58).
`EncryptedPII`/`get_utc_now` da aynı sebeple buradadır: ikisi de birden
fazla modülün tablosunda kullanılan generic column-tipi/default'tur
(EncryptedPII: driver.Sofor + auth_rbac.Kullanici; get_utc_now: hemen
hemen her tablonun created_at/updated_at default'u) — tek bir modülün
sahip olacağı iş mantığı değil, ORM altyapısı.

**Bilinçli, dar istisna (2026-07-23, bağımsız dedektif denetiminde
bulundu, kök `CLAUDE.md`/`shared_kernel/CLAUDE.md`'de dokümante)**:
`EncryptedPII` şifreleme çekirdeğini (`encrypt_pii`/`decrypt_pii`) dalga
17'de `platform_infra.security.pii_encryption`'a taşınan koddan
kullanıyor — shared_kernel'in "hiçbir dış bağımlılığı yok, herkes
serbestçe import eder" ilkesinin TEK ihlali. `.importlinter`'da hiçbir
kontrat bunu izlemiyor (shared_kernel'in kasıtlı olarak kendi kontratı
yok). Risk düşük tutuluyor çünkü: (1) import fonksiyon-içi (lazy,
modül-seviyesinde DEĞİL) — platform_infra'nın kendisi shared_kernel'e
bağımlı olsa bile (ki öyle) gerçek bir dairesel import patlaması
üretmez, yalnız çağrı anında çözülür; (2) `pii_encryption.py` durum-suz
saf kripto yardımcıları (Fernet/HMAC), platform_infra'ya özgü bir
runtime servisi (cache/events/monitoring) KULLANMIYOR. Doğru uzun-vadeli
çözüm bu dosyayı shared_kernel'e taşımak olurdu ama bunun 30+ tüketici
(7 modül + testler, çoğu `platform_infra.public` üzerinden) için blast
radius'u bu denetim turunun "belge/hata düzeltme" kapsamını aşıyor —
ayrı bir refactor kararı olarak bırakıldı.
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
