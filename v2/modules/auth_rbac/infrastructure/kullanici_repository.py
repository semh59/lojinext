"""LojiNext - Kullanıcı repository katmanı. Pure data-access, `kullanicilar` tablosu."""

from datetime import datetime, timezone
from typing import Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.database.base_repository import BaseRepository
from v2.modules.auth_rbac.infrastructure.models import Kullanici


class KullaniciRepository(BaseRepository[Kullanici]):
    """Kullanıcı veritabanı operasyonları (Async)"""

    model = Kullanici

    async def get_by_email(self, email: str) -> Optional[Kullanici]:
        """Email ile kullanıcı bul (blind-index eşleşmesi). Rol ilişkisi eager yüklenir."""
        from app.infrastructure.security.pii_encryption import blind_index

        stmt = (
            select(self.model)
            .options(selectinload(self.model.rol))
            .where(self.model.email_bidx == blind_index(email))
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_reset_token(self, token: str) -> Optional[Kullanici]:
        """Sıfırlama token'ı ile kullanıcı bul. Token hash'i DB ile karşılaştırılır."""
        from v2.modules.auth_rbac.domain.jwt_handler import hash_token

        token_hash = hash_token(token)
        stmt = (
            select(self.model)
            .options(selectinload(self.model.rol))
            .where(
                self.model.sifre_sifir_token == token_hash,
                self.model.sifre_sifir_son > datetime.now(timezone.utc),
            )
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_rol_ids(self, rol_ids: List[int]) -> Dict[int, List[Kullanici]]:
        """Fetch active users for multiple role IDs in a single bulk query.

        Returns a dict mapping rol_id -> list of Kullanici objects, so callers
        can look up users per role in O(1) without issuing one query per rule.
        """
        if not rol_ids:
            return {}
        stmt = select(self.model).where(
            self.model.rol_id.in_(rol_ids),
            self.model.aktif == True,  # noqa: E712
        )
        result = await self.session.execute(stmt)
        users = result.scalars().all()
        grouped: Dict[int, List[Kullanici]] = {}
        for user in users:
            grouped.setdefault(user.rol_id, []).append(user)
        return grouped
