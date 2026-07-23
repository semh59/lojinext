"""PageView ORM tablosu.

``app/database/models.py`` bölünmesi (dalga 16, task #58) — bu tablonun
sahibi reports modülü (page_views tablosu zaten dalga 11'de reports'a
taşınmıştı, bkz. ``page_view_repo.py`` docstring'i). Modülün kendi
repository'si (``page_view_repo.py``) bu ORM sınıfını hiç kullanmıyor —
tüm CRUD ham SQL ile yapılıyor; bu ORM sınıfı yalnız Alembic şema kaydı
için var (gerçek Python tüketicisi yok — mekanik taşıma).
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, String, text
from sqlalchemy.orm import Mapped, mapped_column

from v2.modules.shared_kernel.infrastructure.base import Base


class PageView(Base):
    """Faz 3 — sayfa görüntüleme kaydı (kullanım analitiği)."""

    __tablename__ = "page_views"
    __table_args__ = {"schema": "reports"}

    id: Mapped[int] = mapped_column(primary_key=True)
    route: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    user_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("auth_rbac.kullanicilar.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=text("now()"),
        nullable=False,
        index=True,
    )
