"""
Pydantic Schemas için ortak güvenlik validatorları.

Bu modül tüm şemalarda kullanılacak güvenlik kontrollerini sağlar:
- XSS/HTML injection koruması
- Null byte koruması
- SQL injection karakterleri kontrolü
- Unicode normalizasyonu
"""

import re
import unicodedata
from typing import Optional

from pydantic import field_validator

# Tehlikeli HTML/XSS pattern'leri — yalnız gerçekten tehlikeli yapılar.
# "data:" URL-bağlamında tehlikeli ama serbest metin notlarda meşru
# ("data: aktarımı" gibi) → kaldırıldı; React çıktı-escaping zaten korur.
# SQL injection blocklist kaldırıldı: tüm sorgular parameterized query
# kullanıyor; meşru Türkçe metin "DELETE FROM listesi" gibi içerik
# yanlış 422 üretiyordu.
XSS_PATTERNS = [
    re.compile(r"<\s*script", re.IGNORECASE),
    re.compile(r"javascript\s*:", re.IGNORECASE),
    re.compile(r"on\w+\s*=", re.IGNORECASE),  # onclick, onerror vb.
    re.compile(r"<\s*iframe", re.IGNORECASE),
    re.compile(r"<\s*object", re.IGNORECASE),
    re.compile(r"<\s*embed", re.IGNORECASE),
    re.compile(r"<\s*form", re.IGNORECASE),
    re.compile(r"<\s*style", re.IGNORECASE),
    re.compile(r"<\s*link", re.IGNORECASE),
    re.compile(r"<\s*meta", re.IGNORECASE),
    re.compile(r"<\s*svg", re.IGNORECASE),
    re.compile(r"<\s*math", re.IGNORECASE),
    re.compile(r"<\s*base", re.IGNORECASE),
    re.compile(r"vbscript\s*:", re.IGNORECASE),
    re.compile(r"expression\s*\(", re.IGNORECASE),  # CSS expression
]

# SQL injection blocklist — free-text alanlarda KULLANILMAZ.
# Gerçek SQLi koruması parameterized query ile sağlanır.
# Bu liste yalnız özel yapısal kontroller için saklandı (username vb.)
SQL_DANGEROUS_PATTERNS = [
    re.compile(r";\s*--", re.IGNORECASE),
    re.compile(r"'\s*(OR|AND)\s*'", re.IGNORECASE),
    re.compile(r"UNION\s+SELECT", re.IGNORECASE),
    re.compile(r"DROP\s+TABLE", re.IGNORECASE),
    re.compile(r"DELETE\s+FROM", re.IGNORECASE),
    re.compile(r"INSERT\s+INTO", re.IGNORECASE),
]

# Alfanumerik + alt çizgi pattern (username için)
ALPHANUMERIC_PATTERN = re.compile(r"^[a-zA-Z0-9_]+$")

# Türkçe karakterlerle birlikte alfanumerik (isim için)
TURKISH_NAME_PATTERN = re.compile(r"^[a-zA-ZğüşöçıİĞÜŞÖÇ\s\-\.]+$")

# Plaka formatı (Permissive) — tek kaynak. 2026-07-02 prod-grade denetimi P2
# (Tier B madde 7): eskiden `schemas/arac.py` (bu pattern, 2 kopya) ve
# `core/services/import_service.py` (daha dar, Türkçe karakter yok, azami
# 3 harf) AYRI regex'ler kullanıyordu — aynı plaka doğrudan API POST'ta kabul
# edilirken Excel import'ta reddedilebiliyordu. Artık her ikisi de bu tek
# pattern'i kullanıyor.
PLAKA_PATTERN_STR = r"^[0-9]{2}[\s-]?[A-ZÇĞİÖŞÜ]{1,5}[\s-]?[0-9]{2,4}$"
PLAKA_PATTERN = re.compile(PLAKA_PATTERN_STR)


def sanitize_string(value: str) -> str:
    """
    String değeri güvenli hale getirir.

    - Null byte temizleme
    - Unicode normalizasyonu (NFC)
    - Whitespace strip
    - Control karakterleri temizleme
    """
    if not isinstance(value, str):
        return value

    # Null byte temizle
    value = value.replace("\x00", "")

    # Unicode normalleştir (NFC - Canonical Decomposition, followed by Canonical Composition)
    value = unicodedata.normalize("NFC", value)

    # Control karakterleri temizle (newline, tab hariç)
    value = "".join(
        char
        for char in value
        if not unicodedata.category(char).startswith("C") or char in "\n\r\t"
    )

    # Whitespace strip
    value = value.strip()

    return value


def check_xss(value: str) -> str:
    """
    XSS/HTML injection kontrolü yapar.
    Tehlikeli pattern bulunursa ValueError fırlatır.
    """
    if not isinstance(value, str):
        return value

    for pattern in XSS_PATTERNS:
        if pattern.search(value):
            raise ValueError(f"Potansiyel XSS içeriği tespit edildi: {pattern.pattern}")

    return value


def check_sql_injection(value: str) -> str:
    """
    SQL injection pattern kontrolü yapar.
    Tehlikeli pattern bulunursa ValueError fırlatır.

    NOT: Bu ek bir güvenlik katmanıdır. Asıl koruma parameterized query kullanımıdır.
    """
    if not isinstance(value, str):
        return value

    for pattern in SQL_DANGEROUS_PATTERNS:
        if pattern.search(value):
            raise ValueError("Potansiyel SQL injection içeriği tespit edildi")

    return value


def validate_safe_string(value: Optional[str]) -> Optional[str]:
    """
    Serbest metin alanları için güvenlik validasyonu.

    SQL injection koruması parameterized query'den gelir; serbest metne
    SQL blocklist uygulamak meşru içeriği 422 ile reddeder.
    """
    if value is None:
        return None

    if not isinstance(value, str):
        return value

    # Sanitize
    value = sanitize_string(value)

    # XSS kontrolü (script injection, event-handler enjeksiyonu vb.)
    value = check_xss(value)

    return value


def validate_username(value: str) -> str:
    """
    Kullanıcı adı validasyonu.
    Sadece alfanumerik ve alt çizgi kabul eder.
    """
    if not isinstance(value, str):
        return value

    value = sanitize_string(value)

    if not ALPHANUMERIC_PATTERN.match(value):
        raise ValueError("Kullanıcı adı sadece harf, rakam ve alt çizgi içerebilir")

    return value


def validate_name(value: str) -> str:
    """
    İsim validasyonu (ad_soyad gibi).
    Türkçe karakterler, boşluk, tire ve nokta kabul eder.
    """
    if not isinstance(value, str):
        return value

    value = sanitize_string(value)

    if not TURKISH_NAME_PATTERN.match(value):
        raise ValueError("İsim sadece harf, boşluk, tire ve nokta içerebilir")

    return value


def mask_phone(phone: Optional[str]) -> Optional[str]:
    """
    Telefon numarasını maskeler.
    Örnek: 0532 123 45 67 -> 0532 *** ** 67
    """
    if not phone:
        return phone

    # Sadece rakamları al
    digits = "".join(filter(str.isdigit, phone))

    if len(digits) < 4:
        return phone

    # İlk 4 ve son 2 rakamı göster, gerisini maskele
    return f"{digits[:4]} *** ** {digits[-2:]}"


def validate_dict_size(value: Optional[dict], max_keys: int = 100) -> Optional[dict]:
    """
    Dict boyutu kontrolü (DoS koruması).
    """
    if value is None:
        return None

    if not isinstance(value, dict):
        return value

    if len(value) > max_keys:
        raise ValueError(f"Dict en fazla {max_keys} anahtar içerebilir")

    return value


def validate_password_complexity(v: str) -> str:
    """Şifre karmaşıklığı kontrolü."""
    if not isinstance(v, str):
        return v
    if len(v) < 8:
        raise ValueError("Şifre en az 8 karakter olmalıdır.")
    if not any(c.isupper() for c in v):
        raise ValueError("Şifre en az bir büyük harf içermelidir.")
    if not any(c.islower() for c in v):
        raise ValueError("Şifre en az bir küçük harf içermelidir.")
    if not any(c.isdigit() for c in v):
        raise ValueError("Şifre en az bir rakam içermelidir.")
    return v


def validate_phone(v: Optional[str]) -> Optional[str]:
    """Telefon formatı kontrolü."""
    if v is None or (isinstance(v, str) and not v.strip()):
        return v if v is None else None

    # Sadece rakamları al
    digits = "".join(filter(str.isdigit, v))
    if not digits:
        raise ValueError("Telefon numarası rakam içermelidir.")
    if len(digits) < 10:
        raise ValueError("Telefon numarası en az 10 rakamdan oluşmalıdır.")
    if len(digits) > 15:
        raise ValueError("Telefon numarası 15 rakamdan fazla olamaz.")
    return v


# Validator factory fonksiyonları - Pydantic field_validator ile kullanım için


def create_safe_string_validator(*fields: str):
    """SafeString validator oluşturur."""

    @field_validator(*fields, mode="before")
    @classmethod
    def validate_safe(cls, v: Optional[str]) -> Optional[str]:
        return validate_safe_string(v)

    return validate_safe


def create_username_validator(*fields: str):
    """Username validator oluşturur."""

    @field_validator(*fields, mode="before")
    @classmethod
    def validate_user(cls, v: str) -> str:
        return validate_username(v)

    return validate_user


def create_name_validator(*fields: str):
    """Name validator oluşturur."""

    @field_validator(*fields, mode="before")
    @classmethod
    def validate_name_field(cls, v: str) -> str:
        return validate_name(v)

    return validate_name_field


def create_password_validator(*fields: str):
    """Password validator oluşturur."""

    @field_validator(*fields, mode="after")
    @classmethod
    def validate_pw(cls, v: str) -> str:
        return validate_password_complexity(v)

    return validate_pw


def create_phone_validator(*fields: str):
    """Phone validator oluşturur."""

    @field_validator(*fields, mode="after")
    @classmethod
    def validate_ph(cls, v: Optional[str]) -> Optional[str]:
        return validate_phone(v)

    return validate_ph
