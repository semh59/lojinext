"""Faz 1 — Tahminisiz seferleri SeferFuelEstimator ile dolduran backfill servisi.

Sefer create yolundaki 2.5s timeout (bkz CLAUDE.md) cold cache'de tahminisiz
sefer bırakır. Bu servis o seferleri **timeout'suz** estimator ile doldurur;
gece Celery beat task'i (prediction.backfill_missing) ya da admin tetik çağırır.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)


class PredictionBackfillService:
    """tahmini_tuketim=NULL seferleri estimator ile doldurur.

    estimator ve uow opsiyonel inject edilir (test edilebilirlik). Üretimde
    None geçilirse lazy default'lar kullanılır.
    """

    def __init__(
        self,
        *,
        uow: Optional[Any] = None,
        estimator: Optional[Any] = None,
        throttle_s: float = 0.5,
    ) -> None:
        self._uow = uow
        self._estimator = estimator
        self._throttle_s = throttle_s

    def _get_uow(self) -> Any:
        if self._uow is not None:
            return self._uow
        from v2.modules.shared_kernel.infrastructure.unit_of_work import UnitOfWork

        return UnitOfWork()

    def _get_estimator(self) -> Any:
        if self._estimator is not None:
            return self._estimator
        from v2.modules.trip.public import (
            get_sefer_fuel_estimator,
        )

        return get_sefer_fuel_estimator()

    async def backfill(
        self, *, limit: int = 50, sefer_ids: Optional[list[int]] = None
    ) -> dict[str, int]:
        """Tahminisiz seferleri doldur. {processed, filled, failed, skipped} döner.

        - estimator None döndürürse (Mapbox/route çözememe) -> skipped.
        - estimator exception atarsa -> failed (batch devam eder).
        - Başarılı -> sefer.tahmini_tuketim + route_simulation_id + tahmin_meta yazılır.
        """
        from v2.modules.trip.public import SeferFuelInput

        estimator = self._get_estimator()
        processed = filled = failed = skipped = 0

        # Step 1: ID listesini kısa bir UoW ile al — bağlantı hemen serbest kalır.
        async with self._get_uow() as uow:
            ids = sefer_ids or await uow.sefer_repo.get_ids_missing_prediction(
                limit=limit
            )

        # Step 2: Her sefer için: kısa UoW → oku → kapat → predict (dış IO) → kısa UoW → yaz
        # Böylece Mapbox/Open-Meteo süresince hiç DB bağlantısı tutulmaz.
        for sid in ids:
            processed += 1
            try:
                async with self._get_uow() as uow:
                    sefer = await uow.sefer_repo.get_by_id(sid)

                if not sefer:
                    skipped += 1
                    continue

                if sefer.get("tahmini_tuketim") is not None:
                    # İkincil savunma (2026-07-01 P0 #4): visibility_timeout
                    # yanlış-hizalanması nedeniyle bu sefer'in ID listesi
                    # başka bir worker'a da redelivered olmuş ve o worker
                    # bu satırı bizden önce doldurmuş olabilir — dış IO
                    # (Mapbox/Open-Meteo) çağrısı israfını atlamak için
                    # burada erken çık.
                    skipped += 1
                    continue

                ton = float(sefer.get("ton") or (sefer.get("net_kg") or 0) / 1000.0)
                inp = SeferFuelInput(
                    arac_id=sefer["arac_id"],
                    sofor_id=sefer.get("sofor_id"),
                    dorse_id=sefer.get("dorse_id"),
                    ton=ton,
                    target_date=sefer["tarih"],
                    bos_sefer=bool(sefer.get("bos_sefer")),
                    lokasyon_id=sefer.get("guzergah_id"),
                )
                # Dış IO (Mapbox + Open-Meteo) — DB bağlantısı yok.
                estimate = await estimator.predict(inp, persist=True)
                if estimate is None:
                    skipped += 1
                    continue

                async with self._get_uow() as uow:
                    await uow.sefer_repo.update(
                        sid,
                        tahmini_tuketim=estimate.tahmini_tuketim,
                        route_simulation_id=estimate.simulation_id,
                        tahmin_meta=estimate.to_legacy_prediction_dict(),
                    )
                    await uow.commit()

                filled += 1
            except Exception as exc:  # noqa: BLE001 — batch'i bir sefer bozmasın
                failed += 1
                logger.warning("backfill sefer=%s başarısız: %s", sid, exc)
            if self._throttle_s:
                await asyncio.sleep(self._throttle_s)

        logger.info(
            "PredictionBackfill done: processed=%s filled=%s failed=%s skipped=%s",
            processed,
            filled,
            failed,
            skipped,
        )
        return {
            "processed": processed,
            "filled": filled,
            "failed": failed,
            "skipped": skipped,
        }
