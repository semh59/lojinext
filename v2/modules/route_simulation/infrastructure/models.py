"""RoutePath / GuzergahKalibrasyon / RouteSimulation / RouteSegment ORM
tabloları.

``app/database/models.py`` bölünmesi (dalga 16, task #58) — bu 4 tablonun
sahibi route_simulation modülü.

``GuzergahKalibrasyon.lokasyon`` (location'ın ``Lokasyon``'una) cross-module
``relationship()`` idi — kaldırıldı (modüller birbirinin tablosuna
relationship() ile sızmaz, B.1). Karşı taraf ``Lokasyon.kalibrasyonlar`` da
(o sırada ``app/database/models.py``'de resident, location henüz bu görevde
taşınmamıştı — artık ``v2/modules/location/infrastructure/models.py``'de)
aynı gerekçeyle kaldırıldı — ``lokasyon_id`` FK kolonu yerinde.
``RouteSimulation.segments``/``RouteSegment.simulation`` intra-module
(ikisi de aynı anda taşındı) — değişmedi.
"""

from datetime import datetime
from typing import Any, Optional

from sqlalchemy import (
    BigInteger,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    LargeBinary,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from v2.modules.shared_kernel.infrastructure.base import Base, get_utc_now

# hedef_path stores a route's "golden path" as raw WKB bytes in a BYTEA column.
# There is no PostGIS in dev/CI/prod (verified: pg_extension has no postgis,
# the column is bytea), and geoalchemy2's Geometry type binds/reads through
# PostGIS functions (ST_GeomFromEWKB) that raise on writes without the
# extension — which broke calibrate_route_from_trip in production. Use a plain
# LargeBinary so writes store the WKB bytes directly; no PostGIS required and
# no DDL change (the column was already BYTEA).
_LINESTRING_TYPE = LargeBinary()


class RoutePath(Base):
    """Rota Geometrisi Önbelleği - API Kota Tasarrufu için"""

    __tablename__ = "route_paths"
    __table_args__ = (
        UniqueConstraint(
            "origin_lat", "origin_lon", "dest_lat", "dest_lon", name="uq_route_coords"
        ),
        {"schema": "route_simulation"},
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    # 4 ayrı tekil index (index=True) kasıtlı olarak KALDIRILDI (Tier B madde
    # 14): `uq_route_coords` UniqueConstraint zaten bu 4 kolonu kapsayan
    # composite bir btree index oluşturuyor ve tek gerçek sorgu deseni olan
    # `RouteRepository.get_by_coords`'un 4-kolonlu AND-range filtresi bunu
    # kullanıyor (EXPLAIN ANALYZE ile doğrulandı — Index Scan, tek kolon
    # index'leri olmadan da aynı plan/hız). Tek kolon üzerinden sorgu yapan
    # başka bir kod yolu yok — 4 index sadece INSERT/UPDATE maliyetiydi.
    origin_lat: Mapped[float] = mapped_column(Float)
    origin_lon: Mapped[float] = mapped_column(Float)
    dest_lat: Mapped[float] = mapped_column(Float)
    dest_lon: Mapped[float] = mapped_column(Float)

    distance_km: Mapped[float] = mapped_column(Float)
    duration_min: Mapped[float] = mapped_column(Float)
    ascent_m: Mapped[float] = mapped_column(Float, default=0.0)
    descent_m: Mapped[float] = mapped_column(Float, default=0.0)
    flat_distance_km: Mapped[float] = mapped_column(Float, default=0.0)
    otoban_mesafe_km: Mapped[Optional[float]] = mapped_column(Float)
    sehir_ici_mesafe_km: Mapped[Optional[float]] = mapped_column(Float)
    difficulty: Mapped[Optional[str]] = mapped_column(String(20))
    geometry: Mapped[dict] = mapped_column(JSONB)  # GeoJSONB formatında rota çizgisi
    fuel_estimate_cache: Mapped[Optional[dict]] = mapped_column(
        JSONB
    )  # Tahmin sonucu önbelleği

    route_analysis: Mapped[Optional[dict]] = mapped_column(JSONB)
    last_fetched: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class GuzergahKalibrasyon(Base):
    __tablename__ = "guzergah_kalibrasyonlari"
    __table_args__ = {"schema": "route_simulation"}

    id: Mapped[int] = mapped_column(primary_key=True)
    lokasyon_id: Mapped[int] = mapped_column(
        ForeignKey("location.lokasyonlar.id", ondelete="CASCADE"), index=True
    )

    # Calibration details — stores the "golden path" WKB geometry for spatial matching
    hedef_path: Mapped[Optional[Any]] = mapped_column(_LINESTRING_TYPE, nullable=True)
    buffer_meters: Mapped[float] = mapped_column(
        Float, default=250.0
    )  # Acceptable deviation

    # Accuracy stats
    match_count: Mapped[int] = mapped_column(Integer, default=0)
    avg_deviation_dist: Mapped[float] = mapped_column(Float, default=0.0)

    olusturma_tarihi: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), default=get_utc_now
    )


class RouteSimulation(Base):
    """Route Segment Simulation cache (Plan §5).

    POST /api/v1/routes/simulate sonuçlarının persist edildiği header
    tablo. İlgili 500m bucket'lar route_segments'ta. Migration:
    alembic/versions/0016_route_simulations.py
    """

    __tablename__ = "route_simulations"
    __table_args__ = (
        Index(
            "ix_route_simulations_kullanici_created",
            "kullanici_id",
            "created_at",
        ),
        {"schema": "route_simulation"},
    )

    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"), primary_key=True
    )
    kullanici_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("auth_rbac.kullanicilar.id", ondelete="SET NULL"),
        index=True,
        nullable=True,
    )
    # Phase 3.3: hangi kayıtlı güzergaha bağlı (varsa). Lokasyon silinince
    # simülasyon kaydı sürer ama bağ kaybedilir (SET NULL).
    lokasyon_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("location.lokasyonlar.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    # 0034: hangi araç seçildi (varsa). VehicleSpecs araç teknik değerlerinden
    # türetildi; araç silinince simülasyon kaydı korunur bağ düşer (SET NULL).
    arac_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("fleet.araclar.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # Input snapshot
    cikis_lon: Mapped[float] = mapped_column(Float, nullable=False)
    cikis_lat: Mapped[float] = mapped_column(Float, nullable=False)
    varis_lon: Mapped[float] = mapped_column(Float, nullable=False)
    varis_lat: Mapped[float] = mapped_column(Float, nullable=False)
    ton: Mapped[float] = mapped_column(Float, nullable=False, default=15.0)
    arac_yasi: Mapped[int] = mapped_column(Integer, nullable=False, default=5)
    target_length_km: Mapped[float] = mapped_column(Float, nullable=False, default=0.5)

    # Pipeline meta
    raw_segment_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    resampled_segment_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0
    )
    elevation_coverage_pct: Mapped[float] = mapped_column(
        Float, nullable=False, default=0.0
    )

    # Aggregate result
    total_km: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    total_l: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    avg_l_per_100km: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    total_eta_sec: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    total_ascent_m: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    total_descent_m: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)

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

    segments: Mapped[list["RouteSegment"]] = relationship(
        back_populates="simulation",
        cascade="all, delete-orphan",
        order_by="RouteSegment.seq",
    )


class RouteSegment(Base):
    """Route Simulation segmentleri (500m bucket'lar).

    Migration: alembic/versions/0016_route_simulations.py
    """

    __tablename__ = "route_segments"
    __table_args__ = (
        UniqueConstraint(
            "simulation_id", "seq", name="uq_route_segments_simulation_seq"
        ),
        Index("ix_route_segments_simulation_id", "simulation_id"),
        {"schema": "route_simulation"},
    )

    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"), primary_key=True
    )
    simulation_id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"),
        ForeignKey("route_simulation.route_simulations.id", ondelete="CASCADE"),
        nullable=False,
    )
    seq: Mapped[int] = mapped_column(Integer, nullable=False)

    length_km: Mapped[float] = mapped_column(Float, nullable=False)
    grade_pct: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    road_class: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    maxspeed_kmh: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    traffic_speed_kmh: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    congestion: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)

    sim_speed_kmh: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    sim_l_per_100km: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    sim_l_total: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    eta_sec: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)

    # Boundary midpoint (UI'da segment popup için)
    mid_lon: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    mid_lat: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    simulation: Mapped["RouteSimulation"] = relationship(back_populates="segments")
