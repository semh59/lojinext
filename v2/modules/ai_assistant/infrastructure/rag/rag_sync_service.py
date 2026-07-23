import asyncio

from v2.modules.ai_assistant.infrastructure.rag.rag_engine import get_rag_engine
from v2.modules.platform_infra.events.event_bus import Event, EventType, get_event_bus
from v2.modules.platform_infra.logging.logger import get_logger

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

                from v2.modules.shared_kernel.infrastructure.unit_of_work import (
                    UnitOfWork,
                )

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
        """Araç eklendiğinde veya güncellendiğinde tetiklenir.

        Gerçek publisher'lar (`fleet/application/{create,update}_vehicle.py`)
        her zaman `{"result": <int id>}` gönderiyor — dict dalı hiç
        tetiklenmiyor, int dalı HER ZAMAN çalışıyor. 2026-07-17 dedektif
        denetiminde bulundu: `get_arac_repo()` session'sız bir singleton
        döndürüyor, `UnitOfWork` olmadan `.get_by_id()` çağırmak
        `RuntimeError` fırlatıyordu (event-bus bunu sessizce yutup
        logluyordu — RAG hiç artımlı güncellenmiyordu). Fix:
        `initial_sync()`'in zaten yaptığı gibi `UnitOfWork` içinde çağır.
        """
        data = event.data.get("result")
        if data and isinstance(data, dict):
            await self.rag.index_vehicle(data)
        elif isinstance(data, int):
            from v2.modules.shared_kernel.infrastructure.unit_of_work import UnitOfWork

            async with UnitOfWork() as uow:
                arac = await uow.arac_repo.get_by_id(data)
            if arac:
                await self.rag.index_vehicle(arac)

    async def _on_sofor_changed(self, event: Event):
        """Şoför değiştiğinde tetiklenir (bkz. `_on_arac_changed` docstring'i — aynı fix)."""
        data = event.data.get("result")
        if data and isinstance(data, dict):
            await self.rag.index_driver(data)
        elif isinstance(data, int):
            from v2.modules.shared_kernel.infrastructure.unit_of_work import UnitOfWork

            async with UnitOfWork() as uow:
                sofor = await uow.sofor_repo.get_by_id(data)
            if sofor:
                await self.rag.index_driver(sofor)

    async def _on_sefer_changed(self, event: Event):
        """Sefer değiştiğinde tetiklenir.

        Gerçek publisher'lar `"result"` anahtarını HİÇ kullanmıyor —
        `sefer_write_service.py` `{"sefer_id": ..., "sefer_no": ...}`,
        `sefer_analiz_service.py` `{"id": ..., "tuketim": ...}`,
        `physics_handler.py`/`anomaly/attribute_loss.py`/
        `import_excel/execute_import.py` `{"sefer_id": ..., ...}` gönderiyor
        (anahtar isimleri publisher'lar arasında tutarsız — ayrı bir mimari
        sorun, burada dokunulmadı). 2026-07-17 dedektif denetiminde
        bulundu: eski kod yalnız `"result"` dict'ini kontrol ediyordu,
        hiçbir gerçek publisher'la eşleşmiyordu — sefer RAG senkronu
        prod'da hep no-op'tu, yalnız `initial_sync()`'in tek seferlik
        taramasıyla (limit=1000) sınırlıydı. Fix: hem `"sefer_id"` hem
        `"id"` anahtarını (int) kontrol et, `UnitOfWork` üzerinden çek.
        """
        data = event.data.get("result")
        if data and isinstance(data, dict):
            await self.rag.index_trip(data)
            return

        sefer_id = event.data.get("sefer_id")
        if not isinstance(sefer_id, int):
            sefer_id = event.data.get("id")
        if isinstance(sefer_id, int):
            from v2.modules.shared_kernel.infrastructure.unit_of_work import UnitOfWork

            async with UnitOfWork() as uow:
                sefer = await uow.sefer_repo.get_by_id(sefer_id)
            if sefer:
                await self.rag.index_trip(sefer)


# Singleton
_rag_sync_service = None


def get_rag_sync_service() -> RAGSyncService:
    global _rag_sync_service
    if _rag_sync_service is None:
        _rag_sync_service = RAGSyncService()
    return _rag_sync_service
