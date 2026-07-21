"""BildirimKurali / BildirimDurumu / BildirimGecmisi / PushSubscription ORM
tabloları.

``app/database/models.py`` bölünmesi (dalga 16, task #58) — bu 3 tablonun
(+ 1 enum) sahibi notification modülü. Hiçbirinde ``relationship()`` yoktu
(``Kullanici.bildirimler``/``BildirimGecmisi.kullanici`` cross-module
relationship çifti auth_rbac dalgasında zaten kaldırılmıştı, yalnız FK id
kolonları kaldı) — mekanik taşıma, ilişki-temizliği gerekmedi.
"""

import enum
from datetime import datetime
from typing import List, Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from v2.modules.shared_kernel.infrastructure.base import Base, get_utc_now


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
