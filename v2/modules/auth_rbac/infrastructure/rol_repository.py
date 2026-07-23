"""LojiNext - Rol repository katmanı. Pure data-access, `roller` tablosu."""

from typing import Dict, List, Optional

from sqlalchemy import select

from v2.modules.auth_rbac.infrastructure.models import Kullanici, Rol
from v2.modules.shared_kernel.infrastructure.base_repository import BaseRepository


class RolRepository(BaseRepository[Rol]):
    """Role veritabanı operasyonları (Async).

    Commit'i bu sınıf yapmaz — UnitOfWork sorumludur.
    """

    model = Rol

    async def get_all(self) -> List[Rol]:  # type: ignore[override]
        result = await self.session.execute(select(Rol).order_by(Rol.ad))
        return list(result.scalars().all())

    async def get_by_id(self, role_id: int) -> Optional[Rol]:  # type: ignore[override]
        return await self.session.get(Rol, role_id)

    async def get_by_name(self, ad: str) -> Optional[Rol]:
        result = await self.session.execute(select(Rol).where(Rol.ad == ad))
        return result.scalar_one_or_none()

    async def create(self, ad: str, yetkiler: Dict[str, bool]) -> Rol:  # type: ignore[override]
        """Yeni rol oluşturur. Commit çağırmaz — çağıran (UoW) sorumludur."""
        existing = await self.get_by_name(ad)
        if existing:
            raise ValueError(f"Bu isimde bir rol zaten var: {ad!r}")
        role = Rol(ad=ad, yetkiler=yetkiler)
        self.session.add(role)
        await self.session.flush()
        return role

    async def update(  # type: ignore[override]
        self,
        role_id: int,
        ad: Optional[str] = None,
        yetkiler: Optional[Dict[str, bool]] = None,
    ) -> Optional[Rol]:
        """Rol adı/yetkilerini günceller. Commit çağırmaz (UoW sorumlu)."""
        role = await self.get_by_id(role_id)
        if role is None:
            return None
        if ad is not None and ad != role.ad:
            clash = await self.get_by_name(ad)
            if clash and clash.id != role_id:
                raise ValueError(f"Bu isimde bir rol zaten var: {ad!r}")
            role.ad = ad
        if yetkiler is not None:
            role.yetkiler = yetkiler
        await self.session.flush()
        return role

    async def count_users_with_role(self, role_id: int) -> int:
        """Bu role atanmış kullanıcı sayısı (silme guard'ı için)."""
        from sqlalchemy import func

        result = await self.session.execute(
            select(func.count())
            .select_from(Kullanici)
            .where(Kullanici.rol_id == role_id)
        )
        return int(result.scalar() or 0)

    async def delete(self, role_id: int) -> bool:  # type: ignore[override]
        """Rolü kalıcı siler. Commit çağırmaz (UoW sorumlu).

        Çağıran (endpoint) kullanım + sistem-rolü guard'larını uygulamalı.
        """
        role = await self.get_by_id(role_id)
        if role is None:
            return False
        await self.session.delete(role)
        await self.session.flush()
        return True
