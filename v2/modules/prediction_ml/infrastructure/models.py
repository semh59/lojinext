"""EgitimKuyrugu / ModelVersiyon / PredictionResult ORM tabloları.

``app/database/models.py`` bölünmesi (dalga 16, task #58) — bu 3 tablonun
sahibi prediction_ml modülü. Hiçbirinde ``relationship()`` yoktu (yalnız
``araclar.id``/``kullanicilar.id``'ye FK id kolonları; ``Kullanici``'ye
işaret eden relationship'ler auth_rbac dalgasında zaten kaldırılmıştı) —
mekanik taşıma, ilişki-temizliği gerekmedi.
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
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
from sqlalchemy.orm import Mapped, mapped_column

from v2.modules.shared_kernel.infrastructure.base import Base, get_utc_now


class EgitimKuyrugu(Base):
    """ML Model eğitim görev kuyruğu"""

    __tablename__ = "egitim_kuyrugu"
    __table_args__ = (
        CheckConstraint(
            "durum IN ('WAITING', 'RUNNING', 'COMPLETED', 'FAILED', 'CANCELED')",
            name="check_egitim_kuyrugu_durum_enum",
        ),
        {"schema": "prediction_ml"},
    )

    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"), primary_key=True
    )
    arac_id: Mapped[int] = mapped_column(
        ForeignKey("fleet.araclar.id", ondelete="CASCADE"), index=True
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
        ForeignKey("auth_rbac.kullanicilar.id", ondelete="SET NULL")
    )


class ModelVersiyon(Base):
    """Model versiyonları - Versiyonlama ve Rollback için"""

    __tablename__ = "model_versiyonlar"

    id: Mapped[int] = mapped_column(primary_key=True)
    arac_id: Mapped[int] = mapped_column(
        ForeignKey("fleet.araclar.id", ondelete="CASCADE"), index=True
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
        ForeignKey("auth_rbac.kullanicilar.id", ondelete="SET NULL")
    )
    tetikleyici: Mapped[str] = mapped_column(String(50), default="otomatik")

    __table_args__ = (
        CheckConstraint(
            "NOT (aktif = TRUE AND fizik_only_mod = TRUE)",
            name="check_model_versiyon_aktif_fizik_xor",
        ),
        UniqueConstraint("arac_id", "versiyon", name="uq_arac_versiyon"),
        Index("idx_model_arac_versiyon", "arac_id", text("versiyon DESC")),
        {"schema": "prediction_ml"},
    )


class PredictionResult(Base):
    """
    Kuyruklu tahmin sonuçlarının kalıcı kaydı (task_id bazlı).
    """

    __tablename__ = "prediction_results"
    __table_args__ = {"schema": "prediction_ml"}

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
        ForeignKey("auth_rbac.kullanicilar.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
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
