from datetime import date, datetime
from decimal import Decimal
from typing import List, Optional

from sqlalchemy import (
    CHAR,
    BigInteger,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Identity,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import ENUM as PG_ENUM
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import (
    Mapped,
    mapped_column,
    relationship,
)

from v2.modules.shared_kernel.infrastructure.base import (
    Base,
    get_utc_now,
)


class Lokasyon(Base):
    __tablename__ = "lokasyonlar"
    __table_args__ = (
        UniqueConstraint("cikis_yeri", "varis_yeri", name="uq_cikis_varis"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    cikis_yeri: Mapped[str] = mapped_column(String(100))
    varis_yeri: Mapped[str] = mapped_column(String(100))
    mesafe_km: Mapped[float] = mapped_column(Float)
    tahmini_sure_saat: Mapped[Optional[float]] = mapped_column(Float)
    zorluk: Mapped[str] = mapped_column(String(20), default="Normal")

    # Coordinates
    cikis_lat: Mapped[Optional[float]] = mapped_column(Float)
    cikis_lon: Mapped[Optional[float]] = mapped_column(Float)
    varis_lat: Mapped[Optional[float]] = mapped_column(Float)
    varis_lon: Mapped[Optional[float]] = mapped_column(Float)

    # API Metrics
    api_mesafe_km: Mapped[Optional[float]] = mapped_column(Float)
    api_sure_saat: Mapped[Optional[float]] = mapped_column(Float)
    ascent_m: Mapped[Optional[float]] = mapped_column(Float)
    descent_m: Mapped[Optional[float]] = mapped_column(Float)
    flat_distance_km: Mapped[float] = mapped_column(Float, default=0.0)
    otoban_mesafe_km: Mapped[Optional[float]] = mapped_column(Float)
    sehir_ici_mesafe_km: Mapped[Optional[float]] = mapped_column(Float)
    tahmini_yakit_lt: Mapped[Optional[float]] = mapped_column(Float)
    last_api_call: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

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
        nullable=False,
    )

    # PostGIS Spatial Data (Removed temporarily due to missing columns/extension)
    # cikis_geom: Mapped[Optional[Any]] = mapped_column(Geometry("POINT", srid=4326))
    # varis_geom: Mapped[Optional[Any]] = mapped_column(Geometry("POINT", srid=4326))
    # rota_geom: Mapped[Optional[Any]] = mapped_column(Geometry("LINESTRING", srid=4326))

    route_analysis: Mapped[Optional[dict]] = mapped_column(JSONB)
    distributions: Mapped[Optional[dict]] = mapped_column(JSONB)
    source: Mapped[Optional[str]] = mapped_column(String(50))
    is_corrected: Mapped[bool] = mapped_column(Boolean, default=False)
    correction_reason: Mapped[Optional[str]] = mapped_column(Text)
    notlar: Mapped[Optional[str]] = mapped_column(Text)
    aktif: Mapped[bool] = mapped_column(
        Boolean, default=True, server_default=text("true")
    )
    is_deleted: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default=text("false"), index=True
    )

    # Phase 3 — güzergah kaydı zenginleştirme
    # ad: kullanıcı verdiği takma isim ("Sabah Kargosu — İST-BUR")
    ad: Mapped[Optional[str]] = mapped_column(String(150), nullable=True)
    # hydrated_at: son LokasyonHydrator çalışma zamanı
    hydrated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    raw_segment_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default=text("0")
    )
    resampled_segment_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default=text("0")
    )
    elevation_coverage_pct: Mapped[float] = mapped_column(
        Float, nullable=False, default=0.0, server_default=text("0.0")
    )

    # Relationships (kalibrasyonlar -> GuzergahKalibrasyon route_simulation'a
    # taşındı, cross-module relationship() kaldırıldı — dalga 16 task #58)
    segments: Mapped[List["LokasyonSegment"]] = relationship(
        back_populates="lokasyon",
        cascade="all, delete-orphan",
        order_by="LokasyonSegment.seq",
    )


class LokasyonSegment(Base):
    """Lokasyonun STATİK 500m segment verisi (Phase 3.5).

    Yolun değişmez fiziksel haritası — kullanıcı bir kere kaydedince
    güncellenmez: length / grade / road_class / maxspeed.

    Trafik (sim_speed/traffic_speed/congestion) bu tabloda YOK — zamansal
    veri statik haritada yer almamalı. Sefer simülasyonu Mapbox cache
    (Phase 2.3, 24h TTL) ile o anki trafiği çekip route_segments'a yazar.

    Migration: alembic 0017 oluşturdu, 0019 traffic kolonlarını drop etti.
    """

    __tablename__ = "lokasyon_segments"
    __table_args__ = (
        UniqueConstraint(
            "lokasyon_id", "seq", name="uq_lokasyon_segments_lokasyon_seq"
        ),
        Index("ix_lokasyon_segments_lokasyon_id", "lokasyon_id"),
    )

    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"), primary_key=True
    )
    lokasyon_id: Mapped[int] = mapped_column(
        ForeignKey("lokasyonlar.id", ondelete="CASCADE"), nullable=False
    )
    seq: Mapped[int] = mapped_column(Integer, nullable=False)

    length_km: Mapped[float] = mapped_column(Float, nullable=False)
    grade_pct: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    road_class: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    maxspeed_kmh: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    mid_lon: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    mid_lat: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    lokasyon: Mapped["Lokasyon"] = relationship(back_populates="segments")


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


class OutboxEvent(Base):
    """Transactional Outbox for reliable event delivery."""

    __tablename__ = "outbox_events"
    __table_args__ = (
        Index("idx_outbox_processed", "processed"),
        Index("idx_outbox_created", "created_at"),
    )

    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"), primary_key=True
    )
    event_type: Mapped[str] = mapped_column(String(100), nullable=False)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    correlation_id: Mapped[str] = mapped_column(String(64), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        default=get_utc_now,
        onupdate=get_utc_now,
        nullable=False,
    )
    processed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    processed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    retry_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    error_message: Mapped[Optional[str]] = mapped_column(Text)


# ---------------------------------------------------------------------------
# Error Monitoring Tables (Task 2 — error detector system)
# ---------------------------------------------------------------------------

_error_layer_enum = PG_ENUM(
    "db",
    "celery",
    "api",
    "service",
    "frontend",
    "external",
    "security",
    "ml",
    name="error_layer",
    create_type=False,
)
_error_severity_enum = PG_ENUM(
    "critical",
    "error",
    "warning",
    "info",
    name="error_severity",
    create_type=False,
)


class ErrorEvent(Base):
    """Aggregated error table — one active row per unique fingerprint."""

    __tablename__ = "error_events"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    fingerprint: Mapped[str] = mapped_column(CHAR(16), nullable=False)
    layer: Mapped[str] = mapped_column(_error_layer_enum, nullable=False)
    category: Mapped[str] = mapped_column(String(60), nullable=False)
    severity: Mapped[str] = mapped_column(_error_severity_enum, nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1")
    first_seen: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    last_seen: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    trace_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    user_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("kullanicilar.id", ondelete="SET NULL"), nullable=True
    )
    path: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    stack_trace: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    # "metadata" is reserved by SQLAlchemy's DeclarativeBase; use attribute alias
    extra: Mapped[dict] = mapped_column(
        "metadata", JSONB, nullable=False, server_default="{}"
    )
    resolved_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    resolved_by: Mapped[Optional[int]] = mapped_column(
        ForeignKey("kullanicilar.id", ondelete="SET NULL"), nullable=True
    )

    __table_args__ = (
        Index(
            "idx_error_events_fingerprint_active",
            "fingerprint",
            unique=True,
            postgresql_where=text("resolved_at IS NULL"),
        ),
        Index("idx_error_events_layer_sev", "layer", "severity", "last_seen"),
        Index(
            "idx_error_events_trace_id",
            "trace_id",
            postgresql_where=text("trace_id IS NOT NULL"),
        ),
    )


class ErrorOccurrence(Base):
    """Raw time-series error log — RANGE-partitioned by occurred_at (month)."""

    __tablename__ = "error_occurrences"

    # For partitioned tables, SQLAlchemy ORM requires a declared primary key.
    # PostgreSQL requires the partition key (occurred_at) to be part of the PK.
    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        primary_key=True,
    )
    fingerprint: Mapped[str] = mapped_column(CHAR(16), nullable=False)
    layer: Mapped[str] = mapped_column(_error_layer_enum, nullable=False)
    severity: Mapped[str] = mapped_column(_error_severity_enum, nullable=False)
    trace_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    # "metadata" is reserved by SQLAlchemy's DeclarativeBase; use attribute alias
    extra: Mapped[dict] = mapped_column(
        "metadata", JSONB, nullable=False, server_default="{}"
    )

    __table_args__ = (
        Index("idx_error_occurrences_time", "occurred_at", "layer"),
        # postgresql_partition_by tells SQLAlchemy this is a declarative-only hint;
        # the actual PARTITION BY clause was written in the Alembic migration.
        {"postgresql_partition_by": "RANGE (occurred_at)"},
    )


class PageView(Base):
    """Faz 3 — sayfa görüntüleme kaydı (kullanım analitiği)."""

    __tablename__ = "page_views"

    id: Mapped[int] = mapped_column(primary_key=True)
    route: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    user_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("kullanicilar.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=text("now()"),
        nullable=False,
        index=True,
    )
