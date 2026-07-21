"""Sefer / SeferLog / SeferBelge ORM tabloları.

``app/database/models.py`` bölünmesi (dalga 16, task #58) — bu 3 tablonun
sahibi trip modülü (yazan modül sahiptir ilkesi).

Cross-module ``relationship()`` alanları (``Sefer.arac/.dorse/.sofor/
.guzergah/.created_by/.updated_by``, ``SeferBelge.sofor``) BİLİNÇLİ OLARAK
KALDIRILDI — FK kolonları (``arac_id``, ``sofor_id`` vb.) aynen kalıyor,
yalnız ORM-seviyeli cross-module join-relationship'ler silindi (modüller
birbirinin tablosuna ``relationship()`` ile sızmaz, yalnız FK id taşır).
Bu 6 relationship'in tek gerçek ORM-seviye tüketicisi
``SeferRepository._with_relations()``/``_row_to_dict()``'ti (arac/sofor/
dorse/guzergah joinedload) — açık batch-query'e çevrildi, bkz.
``infrastructure/repository.py``. ``SeferBelge.sofor`` ve ``created_by``/
``updated_by`` hiçbir yerde ORM-seviyede kullanılmıyordu (grep ile
doğrulandı, dalga 16 task #58 ön-doğrulaması).
"""

from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import (
    BigInteger,
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
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship, validates

from v2.modules.shared_kernel.infrastructure.base import Base, get_utc_now


class Sefer(Base):
    __tablename__ = "seferler"
    __table_args__ = (
        Index("idx_seferler_durum_tarih", "durum", "tarih"),
        # Composite performance indexes (created by 0004_composite_indexes migration)
        # tarih DESC matches the sort direction used in the 0004 migration.
        Index("ix_seferler_arac_id_tarih", "arac_id", text("tarih DESC")),
        Index("ix_seferler_sofor_id_tarih", "sofor_id", text("tarih DESC")),
        Index("ix_seferler_arac_id_durum", "arac_id", "durum"),
        CheckConstraint("mesafe_km > 0", name="check_sefer_mesafe_positive"),
        CheckConstraint(
            "net_kg = dolu_agirlik_kg - bos_agirlik_kg", name="check_sefer_net_kg_calc"
        ),
        CheckConstraint("bos_agirlik_kg >= 0", name="check_sefer_bos_agirlik_positive"),
        CheckConstraint(
            "dolu_agirlik_kg >= 0", name="check_sefer_dolu_agirlik_positive"
        ),
        CheckConstraint("net_kg >= 0", name="check_sefer_net_kg_positive"),
        CheckConstraint(
            "durum IN ('Planned', 'Completed', 'Cancelled')",
            name="check_sefer_durum_enum",
        ),
        # 2026-07-01 prod-grade denetimi P1 (Dalga 3 madde 15): DB-seviye
        # kısıt yoktu. NULL="web-girildi" hâlâ serbest (CHECK NULL'da
        # otomatik geçer — IN (...) NULL karşısında UNKNOWN döner).
        CheckConstraint(
            "onay_durumu IS NULL OR onay_durumu IN "
            "('beklemede', 'onaylandi', 'reddedildi')",
            name="check_sefer_onay_durumu_enum",
        ),
        Index("idx_seferler_rota_detay_gin", "rota_detay", postgresql_using="gin"),
        Index("idx_seferler_tahmin_meta_gin", "tahmin_meta", postgresql_using="gin"),
        # Partial index for approval-queue queries (0009_onay_durumu_index migration)
        Index(
            "ix_seferler_onay_durumu",
            "onay_durumu",
            postgresql_where=text("onay_durumu IS NOT NULL"),
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    sefer_no: Mapped[Optional[str]] = mapped_column(
        String(50), unique=True, index=True
    )  # Business Key (e.g. SEF-001)
    tarih: Mapped[date] = mapped_column(Date, index=True)
    saat: Mapped[Optional[str]] = mapped_column(String(5))
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False, index=True)

    # Foreign Keys
    guzergah_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("lokasyonlar.id", ondelete="RESTRICT"), index=True, nullable=True
    )
    route_pair_id: Mapped[Optional[str]] = mapped_column(
        String(64), index=True
    )  # Unified V2.1 Contract
    # Phase 4.4: SeferFuelEstimator tahmininin route_simulations row'una bağı
    route_simulation_id: Mapped[Optional[int]] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"),
        ForeignKey("route_simulations.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    arac_id: Mapped[int] = mapped_column(
        ForeignKey("araclar.id", ondelete="RESTRICT"), index=True
    )
    dorse_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("dorseler.id", ondelete="SET NULL"), index=True
    )
    sofor_id: Mapped[int] = mapped_column(
        ForeignKey("soforler.id", ondelete="RESTRICT"), index=True
    )
    periyot_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("yakit_periyotlari.id", ondelete="SET NULL"), index=True
    )  # 2026-07-01 P1 madde 14: gerçek FK (bkz. migration 0035)

    # Weight Info
    bos_agirlik_kg: Mapped[int] = mapped_column(
        Integer, server_default=text("0"), default=0
    )
    dolu_agirlik_kg: Mapped[int] = mapped_column(
        Integer, server_default=text("0"), default=0
    )
    net_kg: Mapped[int] = mapped_column(
        Integer, server_default=text("0"), default=0
    )  # Computed: Dolu - Boş
    ton: Mapped[float] = mapped_column(
        Float, server_default=text("0.0"), default=0.0
    )  # Computed

    # Location Info
    cikis_yeri: Mapped[str] = mapped_column(String(100))
    varis_yeri: Mapped[str] = mapped_column(String(100))
    mesafe_km: Mapped[float] = mapped_column(Float)
    baslangic_km: Mapped[Optional[int]] = mapped_column(Integer)
    bitis_km: Mapped[Optional[int]] = mapped_column(Integer)

    # Trip Status & Details
    bos_sefer: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default=text("false")
    )
    durum: Mapped[str] = mapped_column(
        String(20), default="Planned", server_default=text("'Planned'")
    )
    notlar: Mapped[Optional[str]] = mapped_column(String(255))
    # Manual attribution override audit (AttributionService.override_attribution):
    # marks a trip whose arac/sofor was manually re-assigned, with the reason.
    is_corrected: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default=text("false"), nullable=False
    )
    correction_reason: Mapped[Optional[str]] = mapped_column(Text)

    # Fuel & API Data
    dagitilan_yakit: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2))
    tahmini_tuketim: Mapped[Optional[float]] = mapped_column(
        Float
    )  # AI predicted consumption
    tahmin_meta: Mapped[Optional[dict]] = mapped_column(JSONB)
    rota_detay: Mapped[Optional[dict]] = mapped_column(JSONB)  # Route path and details
    tuketim: Mapped[Optional[float]] = mapped_column(Float)
    ascent_m: Mapped[Optional[float]] = mapped_column(Float)
    descent_m: Mapped[Optional[float]] = mapped_column(Float)
    flat_distance_km: Mapped[float] = mapped_column(Float, default=0.0)
    otoban_mesafe_km: Mapped[Optional[float]] = mapped_column(Float)
    sehir_ici_mesafe_km: Mapped[Optional[float]] = mapped_column(Float)
    duration_min: Mapped[Optional[int]] = mapped_column(
        Integer
    )  # Time proxy for fatigue

    # Audit Logs
    created_by_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("kullanicilar.id", ondelete="SET NULL"), index=True
    )
    updated_by_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("kullanicilar.id", ondelete="SET NULL"), index=True
    )
    iptal_nedeni: Mapped[Optional[str]] = mapped_column(String(255))
    # B-004: Optimistic Locking — her update'te version +1 artar
    version: Mapped[int] = mapped_column(
        Integer, default=1, server_default=text("1"), nullable=False
    )

    # Telegram onay akışı
    onay_durumu: Mapped[Optional[str]] = mapped_column(
        String(20), nullable=True
    )  # NULL=web-girildi, beklemede, onaylandi, reddedildi
    onaylayan_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("kullanicilar.id", ondelete="SET NULL"), nullable=True
    )

    # Meta
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), default=get_utc_now
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=get_utc_now,
    )

    @validates("mesafe_km")
    def validate_mesafe(self, key, value):
        if value is not None and value <= 0:
            raise ValueError(f"Mesafe (km) 0'dan büyük olmalıdır: {value}")
        return value

    @validates("net_kg")
    def validate_net_kg(self, key, value):
        if value is not None and value < 0:
            raise ValueError(f"Net ağırlık (kg) negatif olamaz: {value}")
        return value


class SeferLog(Base):
    __tablename__ = "seferler_log"
    id: Mapped[int] = mapped_column(primary_key=True)
    sefer_id: Mapped[int] = mapped_column(
        ForeignKey("seferler.id", ondelete="CASCADE"), index=True
    )
    degisen_alan: Mapped[Optional[str]] = mapped_column(String(50))
    eski_deger: Mapped[Optional[str]] = mapped_column(String)
    yeni_deger: Mapped[Optional[str]] = mapped_column(String)
    degistiren_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("kullanicilar.id", ondelete="SET NULL"), nullable=True
    )
    islem_tipi: Mapped[str] = mapped_column(String(20))  # INSERT, UPDATE, DELETE
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )
    sefer: Mapped["Sefer"] = relationship()


class SeferBelge(Base):
    """Şoförlerden Telegram üzerinden gelen fotoğraf + OCR sonuçları"""

    __tablename__ = "sefer_belgeler"

    id: Mapped[int] = mapped_column(primary_key=True)
    sofor_id: Mapped[int] = mapped_column(
        ForeignKey("soforler.id", ondelete="CASCADE"), nullable=False, index=True
    )
    sefer_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("seferler.id", ondelete="SET NULL"), nullable=True, index=True
    )
    telegram_mesaj_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    belge_tipi: Mapped[str] = mapped_column(
        String(30), nullable=False
    )  # yakit_fisi, sefer_fisi, tir_ekran
    dosya_yolu: Mapped[str] = mapped_column(String(500), nullable=False)
    ocr_ham: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    ocr_veri: Mapped[Optional[dict]] = mapped_column(
        JSONB, nullable=True
    )  # {tarih, tutar, litre, istasyon, km}
    ocr_durumu: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default="bekliyor", index=True
    )  # bekliyor, islendi, hata
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
