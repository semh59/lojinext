"""Rol / Kullanici / KullaniciOturumu / KullaniciAyari ORM tabloları.

``app/database/models.py`` bölünmesi (dalga 16, task #58) — bu 4 tablonun
sahibi auth_rbac modülü.

``Kullanici.bildirimler`` (notification'ın ``BildirimGecmisi``'ne) cross-module
``relationship()`` idi — kaldırıldı (modüller birbirinin tablosuna
relationship() ile sızmaz, B.1). ``BildirimGecmisi.kullanici`` karşı tarafı da
(``app/database/models.py``'de resident, notification henüz bu görevde
taşınmadı) aynı gerekçeyle kaldırıldı. Aynı şekilde henüz resident olan
``EgitimKuyrugu.tetikleyen``/``ModelVersiyon.egiten_kullanici`` (prediction_ml)
``Kullanici``'ye cross-module relationship taşıyordu — kaldırıldı, FK
kolonları (``tetikleyen_kullanici_id``/``egiten_kullanici_id``) yerinde kaldı.
``Kullanici.rol``/``.oturumlari``/``.ayarlar`` intra-module (Rol/
KullaniciOturumu/KullaniciAyari hepsi aynı anda taşındı) — değişmedi.
"""

from datetime import datetime
from typing import List, Optional

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship, validates

from v2.modules.shared_kernel.infrastructure.base import (
    Base,
    EncryptedPII,
    get_utc_now,
)


class Rol(Base):
    __tablename__ = "roller"

    id: Mapped[int] = mapped_column(primary_key=True)
    ad: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    yetkiler: Mapped[dict] = mapped_column(
        JSONB, server_default=text("'{}'"), nullable=False
    )
    olusturma: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class Kullanici(Base):
    __tablename__ = "kullanicilar"

    id: Mapped[int] = mapped_column(primary_key=True)
    # PII encryption-at-rest (Tier E madde 26): email is encrypted at rest;
    # email_bidx is the deterministic HMAC used for login lookup and the
    # UNIQUE constraint (see EncryptedPII docstring for why plaintext UNIQUE
    # doesn't work once the column is randomized-encrypted).
    email: Mapped[str] = mapped_column(EncryptedPII, nullable=False)
    email_bidx: Mapped[str] = mapped_column(
        String(64), unique=True, index=True, server_default=""
    )
    ad_soyad: Mapped[str] = mapped_column(EncryptedPII, nullable=False)
    sifre_hash: Mapped[str] = mapped_column(Text, nullable=False)
    rol_id: Mapped[int] = mapped_column(ForeignKey("roller.id"), nullable=False)
    aktif: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Oturum ve Güvenlik
    son_giris: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    son_giris_ip: Mapped[Optional[str]] = mapped_column(String(45))
    basarisiz_giris_sayisi: Mapped[int] = mapped_column(
        Integer, default=0, nullable=False
    )
    kilitli_kadar: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    # Şifre yönetimi
    sifre_degisim_tarihi: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    sifre_sifir_token: Mapped[Optional[str]] = mapped_column(Text)
    sifre_sifir_son: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    # Existing linkage
    sofor_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("soforler.id", ondelete="SET NULL"), index=True
    )

    # Zaman damgaları
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
    olusturan_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("kullanicilar.id", ondelete="SET NULL")
    )

    # Relationships (intra-module only — Rol/KullaniciOturumu/KullaniciAyari
    # hepsi bu modülle birlikte taşındı; notification'a cross-module
    # ``bildirimler`` relationship'i kaldırıldı, bkz. modül docstring'i)
    rol: Mapped["Rol"] = relationship()
    oturumlari: Mapped[List["KullaniciOturumu"]] = relationship(
        back_populates="kullanici", cascade="all, delete-orphan"
    )
    ayarlar: Mapped[List["KullaniciAyari"]] = relationship(
        back_populates="kullanici", cascade="all, delete-orphan"
    )

    @validates("email")
    def _sync_email_bidx(self, key, value):
        from app.infrastructure.security.pii_encryption import blind_index

        self.email_bidx = blind_index(value) if value else ""
        return value


class KullaniciOturumu(Base):
    __tablename__ = "kullanici_oturumlari"

    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"), primary_key=True
    )
    kullanici_id: Mapped[int] = mapped_column(
        ForeignKey("kullanicilar.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    access_token_hash: Mapped[str] = mapped_column(Text, nullable=False)
    refresh_token_hash: Mapped[Optional[str]] = mapped_column(Text)
    ip_adresi: Mapped[str] = mapped_column(String(45), nullable=False)
    tarayici: Mapped[Optional[str]] = mapped_column(Text)
    olusturma: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    son_aktivite: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
    access_bitis: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    refresh_bitis: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    aktif: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    iptal_sebebi: Mapped[Optional[str]] = mapped_column(Text)

    kullanici: Mapped["Kullanici"] = relationship(back_populates="oturumlari")


class KullaniciAyari(Base):
    """
    User-specific preferences for different modules and settings types.
    e.g. Saved filters for 'seferler' module or column visibility for 'araclar' table.
    """

    __tablename__ = "kullanici_ayarlari"

    id: Mapped[int] = mapped_column(primary_key=True)
    kullanici_id: Mapped[int] = mapped_column(
        ForeignKey("kullanicilar.id", ondelete="CASCADE"), index=True
    )
    modul: Mapped[str] = mapped_column(
        String(50), index=True
    )  # 'seferler', 'araclar', etc.
    ayar_tipi: Mapped[str] = mapped_column(String(50), index=True)  # 'filtre', 'sutun'
    deger: Mapped[dict] = mapped_column(JSONB, nullable=False)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)
    ad: Mapped[Optional[str]] = mapped_column(
        String(100)
    )  # Friendly name for saved filters

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), default=get_utc_now
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=get_utc_now
    )

    # Relationships
    kullanici: Mapped["Kullanici"] = relationship(back_populates="ayarlar")
