"""ML predictor warm-up.

`app/main.py`'nin lifespan hook'undan dalga 17 (platform-infra) denetiminde
taşındı — bu, projenin ilk `<modül>.startup()`-tarzı hook'u: main.py artık
yalnız `schedule_predictor_warmup()`'ı çağırıp döndürülen task'ı kendi
`_bg_tasks` GC-koruma setine ekliyor (shutdown draining sorumluluğu
main.py'de kalıyor, bu fonksiyon yalnız task'ı yaratıp döndürüyor).

Aktif tüm araçların ensemble predictor'larını önceden initialize eder ki
ilk POST /trips ML cold-start için 4-10sn beklemesin (LRU cache miss).
Vehicle 0 (general fallback) her zaman dahil; aktif araç id'leri DB'den.
"""

import asyncio
import logging

from sqlalchemy import text

from prediction_ml_service.application.ensemble_service import get_ensemble_service
from v2.modules.platform_infra.public import AsyncSessionLocal

logger = logging.getLogger(__name__)


async def _warmup_all_predictors() -> None:
    ids: list[int] = [0]  # general/fallback
    try:
        # Raw SQL against `araclar` directly (same pattern as
        # scheduler_task.py's weekly retrain) -- the fleet.AracORM model
        # this used before Task 5's move physically lives in the main
        # backend's codebase, not this service's own vendored packages.
        async with AsyncSessionLocal() as session:
            rows = await session.execute(
                text("SELECT id FROM araclar WHERE aktif = TRUE AND is_deleted = FALSE")
            )
            ids.extend(r[0] for r in rows.all())
    except Exception as exc:
        logger.debug("Arac fetch for warm-up failed: %s", exc)

    def _init(arac_id: int) -> None:
        try:
            get_ensemble_service().get_predictor(arac_id)
        except Exception as exc:  # pragma: no cover
            logger.debug("Predictor warm-up %s skipped: %s", arac_id, exc)

    for arac_id in ids:
        await asyncio.to_thread(_init, arac_id)
    logger.info("ML predictor warm-up complete for %d models", len(ids))


def schedule_predictor_warmup() -> "asyncio.Task[None]":
    """Warm-up'ı arka plan task'ı olarak başlatır. Çağıran (main.py lifespan)
    döndürülen task'ı izleyip shutdown'da drain etmekten sorumludur."""
    return asyncio.create_task(_warmup_all_predictors())
