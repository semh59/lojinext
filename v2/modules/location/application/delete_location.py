"""Use-case: delete a location/route record (smart delete: active->inactive, inactive->hard)."""

from app.infrastructure.events.event_bus import EventType, publishes
from app.infrastructure.logging.logger import get_logger
from v2.modules.location.infrastructure.repository import LokasyonRepository

logger = get_logger(__name__)


@publishes(EventType.LOKASYON_DELETED)
async def delete_location(repo: LokasyonRepository, lokasyon_id: int) -> bool:
    """Güzergah sil (Smart Delete: Aktif->Pasif, Pasif->Hard)"""
    try:
        # include_inactive=True: smart-delete state machine, ikinci
        # çağrıda (aktif=False → hard-delete) zaten pasif kaydı görmesi
        # gerekiyor.
        current = await repo.get_by_id(lokasyon_id, include_inactive=True)
        if not current:
            return False

        if current.get("aktif"):
            # Soft Delete
            success = await repo.update(lokasyon_id, aktif=False)
            if success:
                logger.info(f"Güzergah pasife alındı (Soft Deleted): ID {lokasyon_id}")
            return success
        else:
            # Hard Delete
            try:
                success = await repo.hard_delete(lokasyon_id)
                if success:
                    logger.info(
                        f"Güzergah tamamen silindi (Hard Deleted): ID {lokasyon_id}"
                    )
                return success
            except Exception as e:
                logger.warning(f"Hard delete engellendi: {e}")
                raise ValueError("Bu güzergah silinemez (bağımlı veriler olabilir).")
    except ValueError:
        raise
    except Exception as e:
        logger.error(f"Lokasyon silme hatasi: {e}")
        raise ValueError("Silme işlemi sırasında bir hata oluştu.")
