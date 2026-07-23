"""IceriAktarimGecmisi ORM tablosu.

``app/database/models.py`` bölünmesi (dalga 16, task #58) — bu tablonun
sahibi import_excel modülü. ``relationship()`` yoktu (yalnız
``kullanicilar.id``'ye FK id kolonu) — mekanik taşıma, ilişki-temizliği
gerekmedi.
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import BigInteger, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from v2.modules.shared_kernel.infrastructure.base import Base


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
