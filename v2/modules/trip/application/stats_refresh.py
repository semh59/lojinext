"""Sefer istatistik materialized view'ini arka planda yeniler.

NOT: task dosyası (``TASKS/modules/trip.md`` madde 5) bu kümeyi hiç
listelemiyordu — envanterde eksikti (prediction_ml dalgasındaki
``route_similarity.py`` unutulmasıyla aynı türde bir boşluk). Burada ayrı
bir dosyaya çıkarıldı çünkü ``_bg_stats_tasks`` gerçek modül-seviyeli mutable
state (arka plan task'larını GC'den koruyan set — B.1 istisnası, MLService'in
``_locks`` dict'iyle aynı gerekçe kategorisi).
"""

from v2.modules.platform_infra.logging.logger import get_logger
from v2.modules.shared_kernel.infrastructure.unit_of_work import UnitOfWork

logger = get_logger(__name__)

# MV refresh için arka plan task'ları GC'den korumak adına modül bazlı set.
# Aksi halde task.add_done_callback hiç çalışmayabilir.
_bg_stats_tasks: set = set()


async def refresh_stats(uow: UnitOfWork) -> None:
    """İstatistik MV'sini arka planda yenile.

    Önceki davranış: sync REFRESH MATERIALIZED VIEW tüm POST'u 4-10 sn
    bloke ediyordu (PostgreSQL MV refresh O(N), her sefer ekleme/güncelleme
    sonrası tetikleniyor). Production'da yeni AsyncSession üzerinden
    fire-and-forget; test ortamında concurrent session ile çakışmamak
    için sync (UoW içinde) refresh tercih edilir.

    NOT: ``refresh_stats_mv`` şu an trip'in kendi ``infrastructure/
    repository.py``'sinde kalıyor — task dosyası bunu ``shared_kernel/
    infrastructure/mv_refresh.py``'ye taşımayı öneriyordu ama shared_kernel
    modülü (dalga 16) henüz oluşturulmadı. MV tüm sistem geneli olsa da,
    bu geçici kalış diğer modüllerin "henüz taşınmamış hedef" gotcha'larıyla
    (örn. prediction_ml'in analytics_executive'te bıraktığı 3 ML-param
    metodu) aynı kategoride — shared_kernel dalgası geldiğinde taşınacak.
    """
    import os

    # pytest fixture session'ları ile çakışmamak için test ortamında
    # mevcut UoW üzerinden sync refresh.
    if os.getenv("PYTEST_CURRENT_TEST"):
        try:
            await uow.sefer_repo.refresh_stats_mv()
        except Exception as e:
            logger.debug(f"Test sync stats refresh skipped: {e}")
        return

    async def _refresh_in_bg() -> None:
        from v2.modules.platform_infra.database.connection import AsyncSessionLocal
        from v2.modules.trip.infrastructure.repository import SeferRepository

        try:
            async with AsyncSessionLocal() as session:
                repo = SeferRepository(session=session)
                await repo.refresh_stats_mv()
                await session.commit()
        except Exception as e:
            logger.warning(f"Post-write stats refresh (bg) failed: {e}")

    import asyncio

    task = asyncio.create_task(_refresh_in_bg())
    _bg_stats_tasks.add(task)
    task.add_done_callback(_bg_stats_tasks.discard)
