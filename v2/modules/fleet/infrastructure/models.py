"""Arac / Dorse / VehicleEventLog / AracBakim / VehicleSpecTimeline ORM tabloları.

``app/database/models.py`` bölünmesi (dalga 16, task #58) — bu 5 tablonun
sahibi fleet modülü.

Cross-module ``relationship()`` alanları BİLİNÇLİ OLARAK KALDIRILDI (FK
kolonları aynen kalıyor): ``Arac.yakit_alimlari``/``.yakit_periyotlari``/
``.formul`` (fuel modülünün tabloları) ve ``VehicleSpecTimeline.degistiren``
(auth_rbac'ın ``Kullanici``'si). Hepsi grep ile ORM-seviyesinde sıfır gerçek
tüketici olduğu doğrulandı (dalga 16 task #58 ön-doğrulaması) — yalnız
tanımlı, hiç kullanılmıyorlardı.

Intra-fleet relationship'ler (Arac↔Dorse↔AracBakim↔VehicleEventLog↔
VehicleSpecTimeline) aynı dosyada oldukları için aynen kalıyor.
"""

import enum
from datetime import date, datetime
from decimal import Decimal
from typing import List, Optional

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
    Text,
    func,
    text,
)
from sqlalchemy.ext.asyncio import AsyncAttrs
from sqlalchemy.orm import Mapped, mapped_column, relationship

from v2.modules.shared_kernel.infrastructure.base import Base, get_utc_now


class BakimTipi(str, enum.Enum):
    PERIYODIK = "PERIYODIK"
    ARIZA = "ARIZA"
    ACIL = "ACIL"


class Arac(Base):
    __tablename__ = "araclar"
    __table_args__ = (
        CheckConstraint("tank_kapasitesi > 0", name="check_tank_kapasitesi_positive"),
        Index("idx_arac_aktif", "aktif"),
        {"schema": "fleet"},
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    plaka: Mapped[str] = mapped_column(String(20), unique=True, index=True)
    marka: Mapped[str] = mapped_column(String(50))
    model: Mapped[Optional[str]] = mapped_column(String(50))
    yil: Mapped[Optional[int]] = mapped_column(Integer)
    tank_kapasitesi: Mapped[int] = mapped_column(
        Integer, server_default=text("600"), default=600
    )
    hedef_tuketim: Mapped[float] = mapped_column(
        Float, server_default=text("32.0"), default=32.0
    )
    muayene_tarihi: Mapped[Optional[date]] = mapped_column(Date)
    sigorta_tarihi: Mapped[Optional[date]] = mapped_column(Date)
    motor_no: Mapped[Optional[str]] = mapped_column(String(50))
    sasi_no: Mapped[Optional[str]] = mapped_column(String(50))

    # Technical Specs
    bos_agirlik_kg: Mapped[float] = mapped_column(
        Float, server_default=text("8000.0"), default=8000.0
    )
    hava_direnc_katsayisi: Mapped[float] = mapped_column(
        Float, server_default=text("0.7"), default=0.7
    )  # Cd
    on_kesit_alani_m2: Mapped[float] = mapped_column(
        Float, server_default=text("8.5"), default=8.5
    )  # Frontal Area
    motor_verimliligi: Mapped[float] = mapped_column(
        Float, server_default=text("0.38"), default=0.38
    )
    lastik_direnc_katsayisi: Mapped[float] = mapped_column(
        Float, server_default=text("0.007"), default=0.007
    )
    maks_yuk_kapasitesi_kg: Mapped[int] = mapped_column(
        Integer, server_default=text("26000"), default=26000
    )

    aktif: Mapped[bool] = mapped_column(
        Boolean, default=True, server_default=text("true")
    )
    is_deleted: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default=text("false"), index=True
    )
    notlar: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        default=get_utc_now,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        default=get_utc_now,
        onupdate=get_utc_now,
    )
    onay_tarihi: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    olusturan_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("auth_rbac.kullanicilar.id", ondelete="SET NULL")
    )

    # Relationships (intra-fleet only — bkz. modül docstring'i)
    spec_timeline: Mapped[List["VehicleSpecTimeline"]] = relationship(
        back_populates="arac",
        cascade="all, delete-orphan",
        order_by="VehicleSpecTimeline.gecerlilik_tarihi.desc()",
    )
    bakimlar: Mapped[List["AracBakim"]] = relationship(
        back_populates="arac", cascade="all, delete-orphan"
    )
    event_logs: Mapped[List["VehicleEventLog"]] = relationship(
        back_populates="arac", cascade="all, delete-orphan"
    )


class Dorse(Base):
    __tablename__ = "dorseler"
    __table_args__ = (Index("idx_dorse_aktif", "aktif"), {"schema": "fleet"})

    id: Mapped[int] = mapped_column(primary_key=True)
    plaka: Mapped[str] = mapped_column(String(20), unique=True, index=True)
    marka: Mapped[Optional[str]] = mapped_column(String(50))
    model: Mapped[Optional[str]] = mapped_column(String(50))
    # Brandali, Frigorifik, Konteyner, Tanker vs.
    tipi: Mapped[str] = mapped_column(String(50), default="Standart")
    yil: Mapped[Optional[int]] = mapped_column(Integer)

    # Physics Metrics
    bos_agirlik_kg: Mapped[float] = mapped_column(
        Float, server_default=text("6000.0"), default=6000.0
    )
    maks_yuk_kapasitesi_kg: Mapped[int] = mapped_column(
        Integer, server_default=text("24000"), default=24000
    )
    lastik_sayisi: Mapped[int] = mapped_column(
        Integer, server_default=text("6"), default=6
    )
    dorse_lastik_direnc_katsayisi: Mapped[float] = mapped_column(
        Float, server_default=text("0.006"), default=0.006
    )
    dorse_hava_direnci: Mapped[float] = mapped_column(Float, default=0.2)

    muayene_tarihi: Mapped[Optional[date]] = mapped_column(Date)
    notlar: Mapped[Optional[str]] = mapped_column(Text)
    aktif: Mapped[bool] = mapped_column(
        Boolean, default=True, server_default=text("true")
    )
    is_deleted: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default=text("false"), index=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        default=get_utc_now,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=get_utc_now,
    )

    # Relationships
    bakimlar: Mapped[List["AracBakim"]] = relationship(
        back_populates="dorse", cascade="all, delete-orphan"
    )


class VehicleEventLog(Base, AsyncAttrs):
    __tablename__ = "vehicle_event_log"
    __table_args__ = {"schema": "fleet"}

    id: Mapped[int] = mapped_column(primary_key=True)
    arac_id: Mapped[int] = mapped_column(
        ForeignKey("fleet.araclar.id", ondelete="CASCADE"), index=True
    )
    event_type: Mapped[str] = mapped_column(String(50), index=True)
    old_status: Mapped[Optional[str]] = mapped_column(String(50))
    new_status: Mapped[Optional[str]] = mapped_column(String(50))
    triggered_by: Mapped[Optional[str]] = mapped_column(String(100), index=True)
    details: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        default=get_utc_now,
    )

    arac: Mapped["Arac"] = relationship(back_populates="event_logs")


class AracBakim(Base):
    __tablename__ = "arac_bakimlari"
    __table_args__ = {"schema": "fleet"}

    # Modifying maintenance logic to support either an Arac or a Dorse
    id: Mapped[int] = mapped_column(primary_key=True)
    arac_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("fleet.araclar.id", ondelete="CASCADE"), index=True
    )
    dorse_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("fleet.dorseler.id", ondelete="CASCADE"), index=True
    )
    bakim_tipi: Mapped[BakimTipi] = mapped_column(
        String(20), default=BakimTipi.PERIYODIK
    )
    km_bilgisi: Mapped[int] = mapped_column(Integer)
    bakim_tarihi: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    maliyet: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=0.0)
    detaylar: Mapped[Optional[str]] = mapped_column(Text)
    tamamlandi: Mapped[bool] = mapped_column(Boolean, default=False)

    guncelleme_tarihi: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    arac: Mapped[Optional["Arac"]] = relationship(back_populates="bakimlar")
    dorse: Mapped[Optional["Dorse"]] = relationship(back_populates="bakimlar")


class VehicleSpecTimeline(Base):
    """Historical timeline of vehicle specifications for audit and calculation consistency."""

    __tablename__ = "vehicle_spec_timeline"
    __table_args__ = (
        Index("idx_spec_arac_tarih", "arac_id", "gecerlilik_tarihi"),
        {"schema": "fleet"},
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    arac_id: Mapped[int] = mapped_column(
        ForeignKey("fleet.araclar.id", ondelete="CASCADE"), nullable=False
    )

    # Tracked Specs
    dingil_sayisi: Mapped[int] = mapped_column(Integer, default=2)
    yakit_tipi: Mapped[str] = mapped_column(String(20), default="DIZEL")
    bos_agirlik_kg: Mapped[int] = mapped_column(Integer, default=8000)
    kapasite_kg: Mapped[int] = mapped_column(Integer, default=26000)

    gecerlilik_tarihi: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    degistiren_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("auth_rbac.kullanicilar.id", ondelete="SET NULL")
    )
    notlar: Mapped[Optional[str]] = mapped_column(Text)

    # Relationships
    arac: Mapped["Arac"] = relationship(back_populates="spec_timeline")
