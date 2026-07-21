import enum
from datetime import date, datetime
from decimal import Decimal
from typing import Any, List, Optional

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
    LargeBinary,
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

# hedef_path stores a route's "golden path" as raw WKB bytes in a BYTEA column.
# There is no PostGIS in dev/CI/prod (verified: pg_extension has no postgis,
# the column is bytea), and geoalchemy2's Geometry type binds/reads through
# PostGIS functions (ST_GeomFromEWKB) that raise on writes without the
# extension — which broke calibrate_route_from_trip in production. Use a plain
# LargeBinary so writes store the WKB bytes directly; no PostGIS required and
# no DDL change (the column was already BYTEA).
_LINESTRING_TYPE = LargeBinary()


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

    # Relationships
    kalibrasyonlar: Mapped[List["GuzergahKalibrasyon"]] = relationship(
        back_populates="lokasyon", cascade="all, delete-orphan"
    )
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


class RoutePath(Base):
    """Rota Geometrisi Önbelleği - API Kota Tasarrufu için"""

    __tablename__ = "route_paths"
    __table_args__ = (
        UniqueConstraint(
            "origin_lat", "origin_lon", "dest_lat", "dest_lon", name="uq_route_coords"
        ),
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


class EgitimKuyrugu(Base):
    """ML Model eğitim görev kuyruğu"""

    __tablename__ = "egitim_kuyrugu"
    __table_args__ = (
        CheckConstraint(
            "durum IN ('WAITING', 'RUNNING', 'COMPLETED', 'FAILED', 'CANCELED')",
            name="check_egitim_kuyrugu_durum_enum",
        ),
    )

    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"), primary_key=True
    )
    arac_id: Mapped[int] = mapped_column(
        ForeignKey("araclar.id", ondelete="CASCADE"), index=True
    )
    hedef_versiyon: Mapped[int] = mapped_column(Integer, nullable=False)

    # Durumlar: WAITING, RUNNING, COMPLETED, FAILED, CANCELED
    durum: Mapped[str] = mapped_column(
        String(20), default="WAITING", index=True, nullable=False
    )
    ilerleme: Mapped[float] = mapped_column(
        Float, default=0.0, nullable=False
    )  # 0.0 - 100.0

    # Hata yonetimi
    hata_detay: Mapped[Optional[str]] = mapped_column(Text)
    yeniden_deneme_sayisi: Mapped[int] = mapped_column(
        Integer, default=0, nullable=False
    )

    # Zamanlayıcılar
    baslangic_zaman: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    bitis_zaman: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    olusturma: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    guncelleme: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    # İsteğe bağlı, kimin veya sistemin tetiklediği (FK id kalır; Kullanici
    # auth_rbac'a taşındı, relationship() cross-module olduğu için kaldırıldı
    # — dalga 16 task #58)
    tetikleyen_kullanici_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("kullanicilar.id", ondelete="SET NULL")
    )


class ModelVersiyon(Base):
    """Model versiyonları - Versiyonlama ve Rollback için"""

    __tablename__ = "model_versiyonlar"

    id: Mapped[int] = mapped_column(primary_key=True)
    arac_id: Mapped[int] = mapped_column(
        ForeignKey("araclar.id", ondelete="CASCADE"), index=True
    )
    versiyon: Mapped[int] = mapped_column(Integer, nullable=False)
    egitim_tarihi: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        default=get_utc_now,
    )
    veri_sayisi: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # Performans metrikleri
    r2_skoru: Mapped[Optional[float]] = mapped_column(Float)
    mae: Mapped[Optional[float]] = mapped_column(Float)
    mape: Mapped[Optional[float]] = mapped_column(Float)
    rmse: Mapped[Optional[float]] = mapped_column(Float)

    # Model detayları
    model_dosya_yolu: Mapped[Optional[str]] = mapped_column(Text)
    model_boyut_kb: Mapped[Optional[int]] = mapped_column(Integer)
    egitim_suresi_sn: Mapped[Optional[float]] = mapped_column(Float)
    kullanilan_ozellikler: Mapped[Optional[dict]] = mapped_column(JSONB)

    # Model ağırlıkları (ensemble)
    xgboost_agirligi: Mapped[Optional[float]] = mapped_column(Float)
    lightgbm_agirligi: Mapped[Optional[float]] = mapped_column(Float)
    rf_agirligi: Mapped[Optional[float]] = mapped_column(Float)
    gb_agirligi: Mapped[Optional[float]] = mapped_column(Float)
    fizik_agirligi: Mapped[Optional[float]] = mapped_column(Float)

    # Durum
    aktif: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    fizik_only_mod: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    fizik_only_sebebi: Mapped[Optional[str]] = mapped_column(Text)

    # Meta
    notlar: Mapped[Optional[str]] = mapped_column(Text)
    # FK id kalır; Kullanici auth_rbac'a taşındı, relationship() cross-module
    # olduğu için kaldırıldı (dalga 16 task #58)
    egiten_kullanici_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("kullanicilar.id", ondelete="SET NULL")
    )
    tetikleyici: Mapped[str] = mapped_column(String(50), default="otomatik")

    __table_args__ = (
        CheckConstraint(
            "NOT (aktif = TRUE AND fizik_only_mod = TRUE)",
            name="check_model_versiyon_aktif_fizik_xor",
        ),
        UniqueConstraint("arac_id", "versiyon", name="uq_arac_versiyon"),
        Index("idx_model_arac_versiyon", "arac_id", text("versiyon DESC")),
    )


class IceriAktarimGecmisi(Base):
    """
    Import History for bulk data ingestion tracking and rollback capability.
    """

    __tablename__ = "iceri_aktarim_gecmisi"

    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"), primary_key=True
    )
    dosya_adi: Mapped[str] = mapped_column(String(255), nullable=False)
    aktarim_tipi: Mapped[str] = mapped_column(
        String(50), nullable=False, index=True
    )  # e.g. "arac", "surucu"

    # Durumlar: PENDING, VALIDATING, PROCESSING, COMPLETED, FAILED, ROLLED_BACK
    durum: Mapped[str] = mapped_column(
        String(50), nullable=False, default="PENDING", index=True
    )

    toplam_kayit: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    basarili_kayit: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    hatali_kayit: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    islem_haritasi: Mapped[Optional[dict]] = mapped_column(
        JSONB
    )  # Storing row-to-DB ID mappings for rollback
    hatalar: Mapped[Optional[dict]] = mapped_column(JSONB)  # Detailed errors per row

    yukleyen_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("kullanicilar.id", ondelete="SET NULL"), index=True
    )

    baslama_zamani: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    bitis_zamani: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    # Optional constraint check tracking for safe deletions
    rollback_baglantilari: Mapped[Optional[dict]] = mapped_column(JSONB)


class GuzergahKalibrasyon(Base):
    __tablename__ = "guzergah_kalibrasyonlari"

    id: Mapped[int] = mapped_column(primary_key=True)
    lokasyon_id: Mapped[int] = mapped_column(
        ForeignKey("lokasyonlar.id", ondelete="CASCADE"), index=True
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

    # Relationships
    lokasyon: Mapped["Lokasyon"] = relationship(back_populates="kalibrasyonlar")


class BildirimKurali(Base):
    __tablename__ = "bildirim_kurallari"

    id: Mapped[int] = mapped_column(primary_key=True)
    olay_tipi: Mapped[str] = mapped_column(String(50), index=True)
    kanallar: Mapped[List[str]] = mapped_column(JSONB)
    alici_rol_id: Mapped[int] = mapped_column(
        ForeignKey("roller.id", ondelete="RESTRICT"), index=True
    )
    aktif: Mapped[bool] = mapped_column(Boolean, default=True)


class BildirimDurumu(str, enum.Enum):
    SENT = "SENT"
    FAILED = "FAILED"
    READ = "READ"


class BildirimGecmisi(Base):
    __tablename__ = "bildirim_gecmisi"

    id: Mapped[int] = mapped_column(primary_key=True)
    kullanici_id: Mapped[int] = mapped_column(
        ForeignKey("kullanicilar.id", ondelete="CASCADE"), index=True
    )
    baslik: Mapped[str] = mapped_column(String(200))
    icerik: Mapped[str] = mapped_column(Text)
    olay_tipi: Mapped[Optional[str]] = mapped_column(String(50), index=True)
    kanal: Mapped[str] = mapped_column(String(20))
    durum: Mapped[BildirimDurumu] = mapped_column(
        String(20), default=BildirimDurumu.SENT
    )
    okundu_tarihi: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    olusturma_tarihi: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), default=get_utc_now
    )


class PredictionResult(Base):
    """
    Kuyruklu tahmin sonuçlarının kalıcı kaydı (task_id bazlı).
    """

    __tablename__ = "prediction_results"

    id: Mapped[int] = mapped_column(primary_key=True)
    task_id: Mapped[str] = mapped_column(
        String(128), unique=True, nullable=False, index=True
    )
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="queued", index=True
    )
    answer: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    finished_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    user_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("kullanicilar.id", ondelete="SET NULL"), nullable=True, index=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), default=get_utc_now
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=get_utc_now,
        nullable=False,
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


class PushSubscription(Base):
    """Reports v2 RV2.PWA — Web Push (VAPID) abonelik kaydı.

    Bir kullanıcının birden çok cihazı (tarayıcı / PWA install) olabilir.
    endpoint unique → çakışma durumunda upsert mantığı endpoint katmanında.

    Migration: alembic/versions/0015_push_subscriptions.py
    """

    __tablename__ = "push_subscriptions"
    __table_args__ = (Index("ix_push_subscriptions_user_id", "user_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("kullanicilar.id", ondelete="CASCADE"), nullable=False
    )
    endpoint: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    p256dh: Mapped[str] = mapped_column(Text, nullable=False)
    auth: Mapped[str] = mapped_column(Text, nullable=False)
    user_agent: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        default=get_utc_now,
        nullable=False,
    )
    last_used_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
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
    )

    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"), primary_key=True
    )
    kullanici_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("kullanicilar.id", ondelete="SET NULL"), index=True, nullable=True
    )
    # Phase 3.3: hangi kayıtlı güzergaha bağlı (varsa). Lokasyon silinince
    # simülasyon kaydı sürer ama bağ kaybedilir (SET NULL).
    lokasyon_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("lokasyonlar.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    # 0034: hangi araç seçildi (varsa). VehicleSpecs araç teknik değerlerinden
    # türetildi; araç silinince simülasyon kaydı korunur bağ düşer (SET NULL).
    arac_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("araclar.id", ondelete="SET NULL"),
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
    )

    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"), primary_key=True
    )
    simulation_id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"),
        ForeignKey("route_simulations.id", ondelete="CASCADE"),
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
