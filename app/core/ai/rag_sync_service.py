import asyncio

from app.core.ai.rag_engine import get_rag_engine
from app.infrastructure.events.event_bus import Event, EventType, get_event_bus
from app.infrastructure.logging.logger import get_logger

logger = get_logger(__name__)


class RAGSyncService:
    """
    Veritabanı kayıtlarını RAG (Vector Store) ile senkronize tutan servis.
    Hem başlangıç senkronizasyonunu hem de olay bazlı güncellemeleri yönetir.
    """

    def __init__(self):
        self.rag = get_rag_engine()
        self._sync_lock = asyncio.Lock()
        self._is_syncing = False

    async def initialize(self):
        """Servisi başlat ve olaylara abone ol."""
        eb = get_event_bus()

        # Abonelikler
        eb.subscribe(EventType.ARAC_ADDED, self._on_arac_changed)
        eb.subscribe(EventType.ARAC_UPDATED, self._on_arac_changed)

        eb.subscribe(EventType.SOFOR_ADDED, self._on_sofor_changed)
        eb.subscribe(EventType.SOFOR_UPDATED, self._on_sofor_changed)

        eb.subscribe(EventType.SEFER_ADDED, self._on_sefer_changed)
        eb.subscribe(EventType.SEFER_UPDATED, self._on_sefer_changed)

        logger.info("RAGSyncService initialized and subscribed to data events.")

        # Arka planda ilk senkronizasyonu başlat
        asyncio.create_task(self.initial_sync())

    async def initial_sync(self):
        """Tüm DB'yi tarayıp RAG'e indeksle (Initial Load)."""
        if self._is_syncing:
            return

        async with self._sync_lock:
            self._is_syncing = True
            try:
                logger.info("Starting initial RAG synchronization...")

                from app.database.unit_of_work import UnitOfWork

                # get_arac_repo()/get_sofor_repo()/get_sefer_repo() return
                # session-less singletons — raw-SQL-backed get_all() crashes
                # with "Database session not initialized" outside a UnitOfWork
                # (root CLAUDE.md gotcha). Use uow.<repo> instead.
                async with UnitOfWork() as uow:
                    # 1. Araçlar
                    araclar = await uow.arac_repo.get_all(sadece_aktif=True)
                    for arac in araclar:
                        await self.rag.index_vehicle(arac)

                    # 2. Şoförler
                    soforler = await uow.sofor_repo.get_all(sadece_aktif=True)
                    for sofor in soforler:
                        await self.rag.index_driver(sofor)

                    # 3. Seferler (Zaman serisi olduğu için son 1000 kayıt)
                    seferler = await uow.sefer_repo.get_all(limit=1000)
                    for sefer in seferler:
                        await self.rag.index_trip(sefer)

                logger.info(
                    f"Initial RAG sync complete. Vehicles: {len(araclar)}, Drivers: {len(soforler)}, Trips: {len(seferler)}"  # noqa: E501
                )

                # Persistence: Diske kaydet
                self.rag.save_to_disk()
                logger.info("RAG vector store saved to disk.")

            except Exception as e:
                logger.error(f"RAG initial sync failed: {e}")
            finally:
                self._is_syncing = False

    async def _on_arac_changed(self, event: Event):
        """Araç eklendiğinde veya güncellendiğinde tetiklenir."""
        data = event.data.get("result")
        if data and isinstance(data, dict):
            await self.rag.index_vehicle(data)
        elif isinstance(
            data, int
        ):  # Sadece ID geldiyse repodan çek (opsiyonel iyileştirme)
            from v2.modules.fleet.infrastructure.vehicle_repository import get_arac_repo

            arac = await get_arac_repo().get_by_id(data)
            if arac:
                await self.rag.index_vehicle(arac)

    async def _on_sofor_changed(self, event: Event):
        """Şoför değiştiğinde tetiklenir."""
        data = event.data.get("result")
        if data and isinstance(data, dict):
            await self.rag.index_driver(data)
        elif isinstance(data, int):  # Sadece ID geldiyse repodan çek
            from v2.modules.driver.public import get_sofor_repo

            sofor = await get_sofor_repo().get_by_id(data)
            if sofor:
                await self.rag.index_driver(sofor)

    async def _on_sefer_changed(self, event: Event):
        """Sefer değiştiğinde tetiklenir."""
        data = event.data.get("result")
        if data and isinstance(data, dict):
            await self.rag.index_trip(data)


# Singleton
_rag_sync_service = None


def get_rag_sync_service() -> RAGSyncService:
    global _rag_sync_service
    if _rag_sync_service is None:
        _rag_sync_service = RAGSyncService()
    return _rag_sync_service
