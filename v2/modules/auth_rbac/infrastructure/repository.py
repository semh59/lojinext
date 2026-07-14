"""LojiNext - Auth/RBAC Repository katmanı.

Kullanıcı, rol ve oturum tabloları için pure data-access. Üç repo tek
dosyada tutulur (driver/fleet modüllerindeki `infrastructure/repository.py`
deseniyle aynı) — üçü de `kullanicilar`/`roller`/`kullanici_oturumlari`
tablolarının birbirine yakından bağlı erişim katmanı, ayrı dosyalara
bölünmesi gereken bağımsız use-case'ler değil.
"""

from datetime import datetime, timezone
from typing import Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.database.base_repository import BaseRepository
from app.database.models import Kullanici, KullaniciOturumu, Rol


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

    async def update(
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
