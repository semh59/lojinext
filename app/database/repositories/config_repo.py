from typing import Any, Dict

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from app.database.base_repository import BaseRepository
from app.database.models import SistemKonfig


class ConfigRepository(BaseRepository[SistemKonfig]):
    """
    Asynchronous repository for System Settings (SistemKonfig / Ayarlar).
    Handles key-value pair persists and upsert operations.
    """

    model = SistemKonfig

    async def get_value(self, key: str, default: Any = None) -> Any:
        """Retrieves a configuration value by key."""
        stmt = select(self.model.deger).where(self.model.anahtar == key)
        result = await self.session.execute(stmt)
        val = result.scalar_one_or_none()
        return val if val is not None else default

    async def set_value(self, key: str, value: Any, description: str = "") -> None:
        """
        Sets or updates a configuration value (Upsert).
        Ensures PostgreSQL conflict handling for concurrent updates.
        """
        stmt = (
            insert(self.model)
            .values(anahtar=key, deger=str(value), aciklama=description)
            .on_conflict_do_update(
                index_elements=["anahtar"],
                set_={"deger": str(value), "aciklama": description},
            )
        )
        await self.session.execute(stmt)

    async def get_all_settings(self) -> Dict[str, Any]:
        """Returns all system settings as a dictionary."""
        settings = await self.get_all()
        return {s["anahtar"]: s["deger"] for s in settings}
