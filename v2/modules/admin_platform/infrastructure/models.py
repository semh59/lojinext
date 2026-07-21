"""EntegrasyonAyari / AdminAuditLog / SistemKonfig / KonfigGecmis /
IdempotencyKey ORM tabloları.

``app/database/models.py`` bölünmesi (dalga 16, task #58) — bu 5 tablonun
sahibi admin_platform modülü. Hiçbirinde ``relationship()`` yoktu (yalnız
``kullanicilar.id``'ye FK id kolonları) — mekanik taşıma, ilişki-temizliği
gerekmedi.
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from v2.modules.shared_kernel.infrastructure.base import Base, get_utc_now


class EntegrasyonAyari(Base):
    """Admin-configurable external API keys (Mapbox/OpenRoute/Groq).

    `deger_sifreli` deliberately does NOT use the `EncryptedPII` type
    decorator — that decorator decrypts transparently on every ORM read,
    which is the opposite of what this table needs (write-only: nobody,
    not even an admin, can ever read the plaintext back). It stores raw
    Fernet ciphertext; the ONLY place that ever calls decrypt_pii() on it
    is v2.modules.admin_platform.application.integration_secrets.get_integration_secret(),
    used exclusively to build outbound API requests — never returned in
    any response, never written to admin_audit_log.
    """

    __tablename__ = "entegrasyon_ayarlari"

    id: Mapped[int] = mapped_column(primary_key=True)
    servis_adi: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    deger_sifreli: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    guncelleyen_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("kullanicilar.id", ondelete="SET NULL")
    )
    guncellenme_tarihi: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True)
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class AdminAuditLog(Base):
    __tablename__ = "admin_audit_log"

    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"), primary_key=True
    )
    kullanici_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("kullanicilar.id", ondelete="SET NULL"), index=True
    )
    kullanici_email: Mapped[Optional[str]] = mapped_column(String(255))
    aksiyon_tipi: Mapped[str] = mapped_column(String(100), nullable=False)
    hedef_tablo: Mapped[Optional[str]] = mapped_column(String(100))
    hedef_id: Mapped[Optional[str]] = mapped_column(Text)
    aciklama: Mapped[Optional[str]] = mapped_column(Text)
    eski_deger: Mapped[Optional[dict]] = mapped_column(JSONB)
    yeni_deger: Mapped[Optional[dict]] = mapped_column(JSONB)
    ip_adresi: Mapped[Optional[str]] = mapped_column(String(45))
    tarayici: Mapped[Optional[str]] = mapped_column(Text)
    istek_id: Mapped[Optional[str]] = mapped_column(String(36))  # UUID as string
    basarili: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    hata_mesaji: Mapped[Optional[str]] = mapped_column(Text)
    sure_ms: Mapped[Optional[int]] = mapped_column(Integer)
    zaman: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class SistemKonfig(Base):
    __tablename__ = "sistem_konfig"

    anahtar: Mapped[str] = mapped_column(String(100), primary_key=True)
    deger: Mapped[dict] = mapped_column(JSONB, nullable=False)
    tip: Mapped[str] = mapped_column(
        String(20), nullable=False
    )  # string, number, boolean, json
    birim: Mapped[Optional[str]] = mapped_column(String(20))
    min_deger: Mapped[Optional[float]] = mapped_column(Float)
    max_deger: Mapped[Optional[float]] = mapped_column(Float)
    grup: Mapped[str] = mapped_column(String(50), nullable=False)
    aciklama: Mapped[Optional[str]] = mapped_column(Text)
    yeniden_baslat: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    son_guncelleme: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
    guncelleyen_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("kullanicilar.id", ondelete="SET NULL")
    )


class KonfigGecmis(Base):
    __tablename__ = "konfig_gecmis"

    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"), primary_key=True
    )
    anahtar: Mapped[str] = mapped_column(String(100), index=True, nullable=False)
    eski_deger: Mapped[dict] = mapped_column(JSONB, nullable=False)
    yeni_deger: Mapped[dict] = mapped_column(JSONB, nullable=False)
    degisiklik_sebebi: Mapped[Optional[str]] = mapped_column(Text)
    guncelleyen_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("kullanicilar.id", ondelete="SET NULL"), index=True
    )
    zaman: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class IdempotencyKey(Base):
    """2026-07-01 prod-grade denetimi P1 (Dalga 4 madde 19): client-timeout+
    retry senaryosunda çift kayıt (yakıt/sefer) oluşmasını engeller.

    Client `Idempotency-Key` header'ı gönderirse: aynı (key, endpoint) için
    aynı istek gövdesiyle tekrar POST edilirse önbelleklenen yanıt aynen
    dönülür (yeni kayıt oluşturulmaz); farklı bir gövdeyle tekrar edilirse
    409 (anahtar zaten farklı bir istekle kullanılmış).

    Migration: alembic/versions/0037_idempotency_keys.py

    NOT: kayıtlar süresiz saklanır — büyüme kaygısı olursa ayrı bir retention
    task'ı eklenebilir (bu madde kapsamında değil).
    """

    __tablename__ = "idempotency_keys"
    __table_args__ = (
        UniqueConstraint("key", "endpoint", name="uq_idempotency_key_endpoint"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    key: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    endpoint: Mapped[str] = mapped_column(String(100), nullable=False)
    request_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    response_status_code: Mapped[int] = mapped_column(Integer, nullable=False)
    response_body: Mapped[dict] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        default=get_utc_now,
        nullable=False,
    )
