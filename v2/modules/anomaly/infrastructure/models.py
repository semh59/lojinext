"""Anomaly / FuelInvestigation ORM tabloları.

``app/database/models.py`` bölünmesi (dalga 16, task #58) — bu 2 tablonun
sahibi anomaly modülü. Hiçbirinde ``relationship()`` yoktu (yalnız
``kullanicilar.id``/``anomalies.id``'ye FK id kolonları, ikincisi
intra-module) — mekanik taşıma, ilişki-temizliği gerekmedi.
"""

from datetime import date, datetime
from typing import Optional

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from v2.modules.shared_kernel.infrastructure.base import Base, get_utc_now


class Anomaly(Base):
    """Anomali kayıtları - AI Tespit sonuçlarını saklar"""

    __tablename__ = "anomalies"

    id: Mapped[int] = mapped_column(primary_key=True)
    tarih: Mapped[date] = mapped_column(Date, index=True)
    tip: Mapped[str] = mapped_column(String(50), index=True)  # tuketim, maliyet, sefer
    kaynak_tip: Mapped[str] = mapped_column(String(50))  # arac, sofor, sefer, yakit
    kaynak_id: Mapped[int] = mapped_column(Integer, index=True)
    deger: Mapped[float] = mapped_column(Float)
    beklenen_deger: Mapped[float] = mapped_column(Float)
    sapma_yuzde: Mapped[float] = mapped_column(Float)
    severity: Mapped[str] = mapped_column(String(20))  # low, medium, high, critical
    aciklama: Mapped[str] = mapped_column(Text)
    rca_summary: Mapped[Optional[str]] = mapped_column(Text)
    suggested_action: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), default=get_utc_now
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        default=get_utc_now,
        onupdate=get_utc_now,
    )

    # Anomali eylem alanları — operatör atamalı iş akışı (acknowledge → resolve).
    acknowledged_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )
    acknowledged_by: Mapped[Optional[int]] = mapped_column(
        ForeignKey("auth_rbac.kullanicilar.id", ondelete="SET NULL"), nullable=True
    )
    resolved_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )
    resolved_by: Mapped[Optional[int]] = mapped_column(
        ForeignKey("auth_rbac.kullanicilar.id", ondelete="SET NULL"), nullable=True
    )
    resolution_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    __table_args__ = (
        Index("idx_anomaly_kaynak", "kaynak_tip", "kaynak_id"),
        Index("idx_anomaly_status_combo", "resolved_at", "acknowledged_at"),
        # 2026-07-01 prod-grade denetimi P1 (Dalga 3 madde 15): DB-seviye
        # kısıt yoktu, typo'lu bir severity hiç engellenmiyordu.
        CheckConstraint(
            "severity IN ('low', 'medium', 'high', 'critical')",
            name="check_anomaly_severity_enum",
        ),
        {"schema": "anomaly"},
    )


class FuelInvestigation(Base):
    """Feature B.2 — yakıt hırsızlığı soruşturma akış kaydı.

    Bir anomaly için tek soruşturma olur (anomaly_id unique).
    Status akışı: open → assigned → investigating → resolved → closed.
    resolution_type değerleri (string, B.2 endpoint validate eder):
        real_theft, false_alarm, data_error, inconclusive

    Migration: alembic/versions/0014_fuel_investigation.py
    """

    __tablename__ = "fuel_investigations"
    __table_args__ = (
        Index("ix_fuel_inv_status", "status"),
        Index("ix_fuel_inv_assigned_to_user_id", "assigned_to_user_id"),
        Index("ix_fuel_inv_created_at", "created_at"),
        CheckConstraint(
            "status IN ('open','assigned','investigating','resolved','closed')",
            name="chk_fuel_inv_status",
        ),
        {"schema": "anomaly"},
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    anomaly_id: Mapped[int] = mapped_column(
        ForeignKey("anomaly.anomalies.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )
    status: Mapped[str] = mapped_column(String(20), default="open", nullable=False)
    suspicion_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    suspicion_level: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    assigned_to_user_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("auth_rbac.kullanicilar.id", ondelete="SET NULL"), nullable=True
    )
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    resolution_type: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)
    evidence_files: Mapped[list] = mapped_column(
        JSONB, default=list, nullable=False, server_default="[]"
    )
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
    closed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_by_user_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("auth_rbac.kullanicilar.id", ondelete="SET NULL"), nullable=True
    )
