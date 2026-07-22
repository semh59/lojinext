"""ErrorEvent / ErrorOccurrence ORM tabloları.

``app/database/models.py`` bölünmesi (dalga 16, task #58) — bu 2 tablonun
(+ 2 PG enum) gerçek sahibi yok: hiçbir prod kod bu ORM sınıflarını
kullanmıyor. `v2/modules/platform_infra/monitoring/` alt sistemi (13 dosya,
~2300 satır — probes, alarm_router, event_bus) `error_events`/
`error_occurrences` tablolarına yalnız ham SQL `INSERT`/`text()` ile yazıyor
(bkz. `v2/modules/platform_infra/monitoring/event_bus.py`); bu ORM sınıfları
yalnız Alembic'in `Base.metadata`'sında şema kaydı için var ve tek gerçek
Python tüketicisi `app/tests/integration/test_error_detector_integration.py`
(doğrulama amaçlı SELECT). `v2/modules/platform_infra/monitoring/models.py`'deki
aynı isimli `ErrorEvent` AYRI bir sınıf — düz `@dataclass` DTO, bu ORM
sınıfıyla ilgisi yok, taşınmadı.

Asıl `v2/modules/platform_infra/monitoring/` alt sisteminin (probes/alarm_router/
event_bus) v2'ye taşınması ayrı, çok daha büyük bir iş (muhtemelen
platform_infra/dalga 17) — bu dosya yalnız ORM tablo tanımlarını taşıyor,
o alt sistemin kendisini değil.
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import (
    CHAR,
    BigInteger,
    DateTime,
    ForeignKey,
    Identity,
    Index,
    Integer,
    String,
    Text,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import ENUM as PG_ENUM
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from v2.modules.shared_kernel.infrastructure.base import Base

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
