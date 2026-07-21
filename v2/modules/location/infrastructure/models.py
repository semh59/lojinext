"""Lokasyon / LokasyonSegment ORM tabloları.

``app/database/models.py`` bölünmesi (dalga 16, task #58) — bu 2 tablonun
sahibi location modülü. ``Lokasyon.kalibrasyonlar``↔``GuzergahKalibrasyon.
lokasyon`` cross-module relationship çifti route_simulation dalgasında zaten
kaldırılmıştı (yalnız FK id kaldı). ``Lokasyon.segments``↔``LokasyonSegment.
lokasyon`` intra-module ilişkisi KORUNDU.
"""

from datetime import datetime
from typing import List, Optional

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from v2.modules.shared_kernel.infrastructure.base import Base, get_utc_now


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
