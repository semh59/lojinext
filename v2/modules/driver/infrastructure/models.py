"""Sofor / SoforAdSoyadTrigram / SoforAdaptasyon / CoachingDelivery ORM tabloları.

``app/database/models.py`` bölünmesi (dalga 16, task #58) — bu 4 tablonun
sahibi driver modülü.

Bu 4 sınıfın hiçbirinde cross-module ``relationship()`` yoktu (trip'in
dalgasında ``Sofor.seferler``/``.belgeler`` zaten kaldırılmıştı) — mekanik
taşıma, ilişki-temizliği gerekmedi.
"""

from datetime import date, datetime
from typing import Optional

from sqlalchemy import (
    CHAR,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, validates

from v2.modules.shared_kernel.infrastructure.base import (
    Base,
    EncryptedPII,
    get_utc_now,
)


class Sofor(Base):
    __tablename__ = "soforler"
    __table_args__ = (
        Index("idx_sofor_aktif", "aktif"),
        Index("idx_sofor_is_deleted", "is_deleted"),
        CheckConstraint("score >= 0.1 AND score <= 2.0", name="chk_sofor_score_range"),
        CheckConstraint(
            "manual_score >= 0.1 AND manual_score <= 2.0",
            name="chk_sofor_manual_score_range",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    # PII encryption-at-rest (Tier E madde 26): ad_soyad is encrypted at rest
    # (EncryptedPII TypeDecorator — transparent Python-side plaintext).
    # ad_soyad_bidx is the deterministic HMAC used for exact-match lookup /
    # the UNIQUE constraint (plaintext UNIQUE is meaningless once encrypted —
    # Fernet ciphertext is randomized). Substring search uses
    # SoforAdSoyadTrigram instead of Postgres ILIKE.
    ad_soyad: Mapped[str] = mapped_column(EncryptedPII)
    ad_soyad_bidx: Mapped[str] = mapped_column(
        String(64), unique=True, index=True, server_default=""
    )
    telefon: Mapped[Optional[str]] = mapped_column(EncryptedPII)
    ise_baslama: Mapped[Optional[date]] = mapped_column(Date)
    ehliyet_sinifi: Mapped[str] = mapped_column(String(10), default="E")

    # Behavioral Stats
    score: Mapped[float] = mapped_column(
        Float, default=1.0
    )  # Driver performance score (0.1 - 2.0)
    manual_score: Mapped[float] = mapped_column(Float, default=1.0)  # Manual evaluation
    hiz_disiplin_skoru: Mapped[float] = mapped_column(Float, default=1.0)
    agresif_surus_faktoru: Mapped[float] = mapped_column(Float, default=1.0)
    # Phase 5A: Driver Factors
    ramp_skoru: Mapped[float] = mapped_column(
        Float, default=1.0, server_default=text("1.0")
    )  # Slope behavior
    istikrar_skoru: Mapped[float] = mapped_column(
        Float, default=1.0, server_default=text("1.0")
    )  # Consistency

    aktif: Mapped[bool] = mapped_column(Boolean, default=True)
    is_deleted: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default=text("false")
    )
    notlar: Mapped[Optional[str]] = mapped_column(Text)
    telegram_id: Mapped[Optional[str]] = mapped_column(
        String(50), unique=True, nullable=True, index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), default=get_utc_now
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        default=get_utc_now,
        onupdate=get_utc_now,
    )

    @validates("ad_soyad")
    def _sync_ad_soyad_bidx(self, key, value):
        from app.infrastructure.security.pii_encryption import blind_index

        self.ad_soyad_bidx = blind_index(value) if value else ""
        return value


class SoforAdSoyadTrigram(Base):
    """Substring-search index for the encrypted Sofor.ad_soyad (Tier E madde 26).

    One row per (sofor_id, 3-char HMAC trigram) pair — a name has several
    trigrams, so this is a genuine one-to-many child table, not a scalar bidx
    column. Populated/replaced by SoforRepository on create/update; queried
    by trigram_hash to build a candidate set for a driver-name search term,
    which the caller must then decrypt and re-verify (trigram hits are a
    superset — collisions across different names are possible and expected).
    """

    __tablename__ = "sofor_ad_soyad_trigram"
    __table_args__ = (
        UniqueConstraint("sofor_id", "trigram_hash", name="uq_sofor_trigram"),
        Index("ix_sofor_trigram_hash", "trigram_hash"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    sofor_id: Mapped[int] = mapped_column(
        ForeignKey("soforler.id", ondelete="CASCADE"), nullable=False
    )
    trigram_hash: Mapped[str] = mapped_column(CHAR(64), nullable=False)


class SoforAdaptasyon(Base):
    __tablename__ = "sofor_adaptasyon"

    id: Mapped[int] = mapped_column(primary_key=True)
    surucu_id: Mapped[int] = mapped_column(
        ForeignKey("soforler.id", ondelete="CASCADE"), unique=True, index=True
    )
    guvenlik_skoru: Mapped[float] = mapped_column(Float, default=100.0)
    verimlilik_skoru: Mapped[float] = mapped_column(Float, default=100.0)
    eco_driving_basarisi: Mapped[float] = mapped_column(Float, default=0.0)
    rutin_disi_davranis_orani: Mapped[float] = mapped_column(Float, default=0.0)
    son_degerlendirme_tarihi: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True)
    )
    onerilen_modul: Mapped[Optional[str]] = mapped_column(String(100))
    risk_kategorisi: Mapped[str] = mapped_column(String(50), default="Düşük")

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), onupdate=func.now()
    )


class CoachingDelivery(Base):
    """Feature A.5 — gönderilen koçluk mesajının ve 14 gün sonraki skor
    deltası ile etki ölçüm kaydı.

    Migration: alembic/versions/0013_coaching_delivery.py
    Caveat (UI'da gösterilir): skor değişimi yalnız koçluğa atfedilemez —
    mevsim, güzergah ve operasyonel faktörler etkilidir.
    """

    __tablename__ = "coaching_deliveries"
    __table_args__ = (
        Index(
            "ix_coaching_deliveries_sofor_id_sent_at",
            "sofor_id",
            "sent_at",
        ),
        Index("ix_coaching_deliveries_evaluated_at", "evaluated_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    sofor_id: Mapped[int] = mapped_column(
        ForeignKey("soforler.id", ondelete="CASCADE"), index=True
    )
    score_before: Mapped[float] = mapped_column(Float)
    score_after_2w: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    score_delta_pct: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    sent_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), default=get_utc_now
    )
    evaluated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    channel: Mapped[str] = mapped_column(String(20), default="telegram")
    insight_category: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)
    message_excerpt: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    sent_by_user_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("kullanicilar.id", ondelete="SET NULL"), nullable=True
    )
