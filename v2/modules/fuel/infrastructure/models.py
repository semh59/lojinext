"""YakitAlimi / YakitPeriyot / YakitFormul ORM tabloları.

``app/database/models.py`` bölünmesi (dalga 16, task #58) — bu 3 tablonun
sahibi fuel modülü. İlişki yoktu (mekanik taşıma).

**Ad çakışması**: ``v2/modules/fuel/domain/entities.py`` zaten Pydantic
``YakitAlimi`` (BaseEntity) sınıfını tanımlıyor — bu ORM sınıfıyla aynı isim,
farklı sınıf. ``public.py``'de bu yüzden ORM sınıfı ``YakitAlimiORM`` olarak
export edilir (aynı gerekçe: prediction_ml'in ``PredictionResult`` → ``PredictionResultORM``).
"""

from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from v2.modules.shared_kernel.infrastructure.base import Base, get_utc_now


class YakitAlimi(Base):
    __tablename__ = "yakit_alimlari"
    __table_args__ = (
        Index("idx_yakit_arac_tarih", "arac_id", "tarih"),
        # Composite performance index (created by 0004_composite_indexes migration)
        # tarih DESC matches the sort direction used in the 0004 migration.
        Index("ix_yakit_alimlari_arac_id_tarih", "arac_id", text("tarih DESC")),
        CheckConstraint("litre > 0", name="check_yakit_litre_positive"),
        CheckConstraint("fiyat_tl > 0", name="check_yakit_fiyat_positive"),
        CheckConstraint(
            "durum IN ('Bekliyor', 'Onaylandı', 'Reddedildi')",
            name="check_yakit_durum_enum",
        ),
        Index("idx_yakit_aktif", "aktif"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    tarih: Mapped[date] = mapped_column(Date, index=True)
    arac_id: Mapped[int] = mapped_column(
        ForeignKey("araclar.id", ondelete="RESTRICT"), index=True
    )
    istasyon: Mapped[Optional[str]] = mapped_column(String(100))
    fiyat_tl: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    litre: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    toplam_tutar: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    km_sayac: Mapped[int] = mapped_column(Integer)
    fis_no: Mapped[Optional[str]] = mapped_column(String(50))
    depo_durumu: Mapped[str] = mapped_column(String(20), default="Bilinmiyor")
    durum: Mapped[str] = mapped_column(
        String(20), default="Bekliyor"
    )  # Bekliyor, Onaylandı, Reddedildi
    aktif: Mapped[bool] = mapped_column(Boolean, default=True)  # Soft delete flag
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), default=get_utc_now
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        default=get_utc_now,
        onupdate=get_utc_now,
    )
    route_analysis: Mapped[Optional[dict]] = mapped_column(JSONB)
    last_fetched: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class YakitPeriyot(Base):
    __tablename__ = "yakit_periyotlari"
    __table_args__ = (
        UniqueConstraint("arac_id", "alim1_id", "alim2_id", name="uq_yakit_periyodu"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    arac_id: Mapped[int] = mapped_column(ForeignKey("araclar.id", ondelete="RESTRICT"))
    alim1_id: Mapped[int] = mapped_column(
        ForeignKey("yakit_alimlari.id", ondelete="CASCADE")
    )
    alim2_id: Mapped[int] = mapped_column(
        ForeignKey("yakit_alimlari.id", ondelete="CASCADE")
    )

    alim1_tarih: Mapped[Optional[date]] = mapped_column(Date)
    alim1_km: Mapped[Optional[int]] = mapped_column(Integer)
    alim1_litre: Mapped[Optional[float]] = mapped_column(Float)

    alim2_tarih: Mapped[Optional[date]] = mapped_column(Date)
    alim2_km: Mapped[Optional[int]] = mapped_column(Integer)

    ara_mesafe: Mapped[Optional[int]] = mapped_column(Integer)
    toplam_yakit: Mapped[Optional[float]] = mapped_column(Float)
    ort_tuketim: Mapped[Optional[float]] = mapped_column(Float)
    sefer_sayisi: Mapped[int] = mapped_column(Integer, default=0)
    durum: Mapped[Optional[str]] = mapped_column(String(50))


class YakitFormul(Base):
    __tablename__ = "yakit_formul"

    id: Mapped[int] = mapped_column(primary_key=True)
    arac_id: Mapped[int] = mapped_column(
        ForeignKey("araclar.id", ondelete="RESTRICT"), unique=True
    )
    katsayilar: Mapped[dict] = mapped_column(JSONB)  # JSONB type for katsayilar
    r2_score: Mapped[Optional[float]] = mapped_column(Float)
    sample_count: Mapped[Optional[int]] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        default=get_utc_now,
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        default=get_utc_now,
        onupdate=get_utc_now,
    )
