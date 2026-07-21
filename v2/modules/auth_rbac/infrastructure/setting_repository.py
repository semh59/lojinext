from typing import List, Optional

from sqlalchemy import and_, select

from app.database.base_repository import BaseRepository
from app.database.models import KullaniciAyari


class SettingRepository(BaseRepository[KullaniciAyari]):
    """Repository for managing user settings and preferences."""

    model = KullaniciAyari

    async def get_user_settings(
        self, kullanici_id: int, modul: str, ayar_tipi: Optional[str] = None
    ) -> List[KullaniciAyari]:
        """Fetch settings for a specific user and module."""
        filters = [
            KullaniciAyari.kullanici_id == kullanici_id,
            KullaniciAyari.modul == modul,
        ]
        if ayar_tipi:
            filters.append(KullaniciAyari.ayar_tipi == ayar_tipi)

        stmt = (
            select(KullaniciAyari)
            .where(and_(*filters))
            .order_by(
                KullaniciAyari.is_default.desc(), KullaniciAyari.created_at.desc()
            )
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_default_setting(
        self, kullanici_id: int, modul: str, ayar_tipi: str
    ) -> Optional[KullaniciAyari]:
        """Fetch the default setting for a user, module, and type."""
        stmt = select(KullaniciAyari).where(
            and_(
                KullaniciAyari.kullanici_id == kullanici_id,
                KullaniciAyari.modul == modul,
                KullaniciAyari.ayar_tipi == ayar_tipi,
                KullaniciAyari.is_default.is_(True),
            )
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def clear_default(self, kullanici_id: int, modul: str, ayar_tipi: str):
        """Reset is_default flag for all settings of a specific type for a user."""
        from sqlalchemy import update

        stmt = (
            update(KullaniciAyari)
            .where(
                and_(
                    KullaniciAyari.kullanici_id == kullanici_id,
                    KullaniciAyari.modul == modul,
                    KullaniciAyari.ayar_tipi == ayar_tipi,
                )
            )
            .values(is_default=False)
        )
        await self.session.execute(stmt)
