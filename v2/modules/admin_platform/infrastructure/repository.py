import threading
from typing import Any, Dict, List, Optional

from sqlalchemy import inspect, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.base_repository import BaseRepository
from v2.modules.admin_platform.infrastructure.models import KonfigGecmis, SistemKonfig

# Thread-safe singleton
_admin_config_repo_lock = threading.Lock()
_admin_config_repo: Optional["AdminConfigRepository"] = None


class AdminConfigRepository(BaseRepository[SistemKonfig]):
    """
    Configuration Repository for System Parameters.
    Handles dynamic values and change history.
    """

    model = SistemKonfig

    async def get_config(self, key: str) -> Optional[Dict[str, Any]]:
        """Retrieves full configuration record by key as dict."""
        config = await self.session.get(self.model, key)
        return self._to_dict(config) if config else None

    async def get_value(self, key: str, default: Any = None) -> Any:
        """Retrieves only the value (deger) for a key."""
        config = await self.get_config(key)
        return config["deger"] if config else default

    async def update_value(
        self,
        key: str,
        new_value: Any,
        updated_by_id: Optional[int] = None,
        reason: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Updates configuration value and logs to history.

        2026-07-01 prod-grade denetimi P1 (Dalga 3 madde 12): satır
        `SELECT ... FOR UPDATE` ile kilitlenir. Eskiden düz `session.get`
        kullanılıyordu — eşzamanlı iki `update_value` çağrısında, geç kalan
        çağrı ilkinin flush/commit'inden ÖNCE stale bir `deger` okuyup bunu
        `eski_deger` olarak audit history'ye yanlış yazıyordu. `FOR UPDATE`
        select anında kilitlediği için geç kalan çağrı ilkinin commit'ini
        bekler ve GÜNCEL değeri görür.
        """
        stmt = select(self.model).where(self.model.anahtar == key).with_for_update()
        result = await self.session.execute(stmt)
        config = result.scalar_one_or_none()
        if not config:
            raise ValueError(f"Configuration key not found: {key}")

        old_value = config.deger
        config.deger = new_value
        config.guncelleyen_id = (
            updated_by_id if updated_by_id and updated_by_id > 0 else None
        )

        history = KonfigGecmis(
            anahtar=key,
            eski_deger=old_value,
            yeni_deger=new_value,
            degisiklik_sebebi=reason,
            guncelleyen_id=updated_by_id
            if updated_by_id and updated_by_id > 0
            else None,
        )
        self.session.add(history)
        await self.session.flush()
        await self.session.refresh(config)
        return self._to_dict(config)

    async def get_by_group(self, group: str) -> List[Dict[str, Any]]:
        """Retrieves all configurations in a specific group."""
        stmt = select(self.model).where(self.model.grup == group)
        result = await self.session.execute(stmt)
        return [self._to_dict(o) for o in result.scalars().all()]

    async def get_all_configs(self) -> List[Dict[str, Any]]:
        """Retrieves every configuration (no group filter)."""
        stmt = select(self.model)
        result = await self.session.execute(stmt)
        return [self._to_dict(o) for o in result.scalars().all()]

    async def get_history(self, key: str, limit: int = 20) -> List[Dict[str, Any]]:
        """Retrieves change history for a key."""
        stmt = (
            select(KonfigGecmis)
            .where(KonfigGecmis.anahtar == key)
            .order_by(KonfigGecmis.zaman.desc())
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        mapper = inspect(KonfigGecmis).mapper
        return [
            {c.key: getattr(o, c.key) for c in mapper.column_attrs}
            for o in result.scalars().all()
        ]


def get_admin_config_repo(
    session: Optional[AsyncSession] = None,
) -> "AdminConfigRepository":
    """AdminConfigRepo Provider — thread-safe singleton, patchable in tests."""
    global _admin_config_repo
    if session:
        return AdminConfigRepository(session=session)
    with _admin_config_repo_lock:
        if _admin_config_repo is None:
            _admin_config_repo = AdminConfigRepository()
    return _admin_config_repo
