"""LojiNext - Oturum repository katmanı. Pure data-access, `kullanici_oturumlari` tablosu."""

from typing import List

from sqlalchemy import select

from v2.modules.auth_rbac.infrastructure.models import KullaniciOturumu
from v2.modules.shared_kernel.infrastructure.base_repository import BaseRepository


class SessionRepository(BaseRepository[KullaniciOturumu]):
    """
    Pure data access for User Sessions.
    """

    model = KullaniciOturumu

    async def get_active_sessions(self, kullanici_id: int) -> List[KullaniciOturumu]:
        """Get all currently active sessions for a user."""
        session = self.session
        stmt = select(self.model).where(
            self.model.kullanici_id == kullanici_id, self.model.aktif
        )
        result = await session.execute(stmt)
        return list(result.scalars().all())

    async def deactivate_all(self, kullanici_id: int):
        """Mark all sessions for a user as inactive. Commit is owned by the caller's UoW."""
        sessions = await self.get_active_sessions(kullanici_id)
        for s in sessions:
            s.aktif = False
        await self.session.flush()
