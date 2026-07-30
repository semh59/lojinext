"""Item C follow-up (2026-07-30) — weekly segment-tractive physics
recalibration snapshot.

A single day's live p51 validation showed the segment-tractive model's
`PHYSICS_DRAG_CDA_M2`/`PHYSICS_PARASITIC_KW` calibration drifting between
runs (a fit against stored/historical route_segments geometry no longer
matched a fresh live-traffic/live-weather run against the same 10
reference routes). Re-fitting once is not enough to tell drift from
single-day noise -- this task refreshes the 10 reference routes' live
geometry and re-runs the same grid-search fit every week, appending a
dated snapshot to a log file. `config.py`'s physics defaults are NOT
auto-updated by this task -- a human reviews the accumulated snapshots
(several weeks of data) before deciding whether/how to adjust them. See
docs/superpowers/plans/backlog/2026-07-30-consolidated-open-items-
backlog.md item 1 for the full investigation this follows up on.

Beat task: ``physics.weekly_recalibration_snapshot`` -- Sunday 02:30 UTC
(before ml.weekly_retrain_all_vehicles at 03:00, after db-backup-verify).
"""

from __future__ import annotations

import asyncio
import json
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import text

from v2.modules.platform_infra.background.celery_app import celery_app
from v2.modules.platform_infra.logging.logger import get_logger

logger = get_logger(__name__)

_LOG_PATH = Path("data/calibration/physics_recalibration_log.jsonl")

# Same reference vehicle p51_real_world_validation.py uses -- already
# exists in the DB from any prior p51/calibration run.
_REFERENCE_VEHICLE_PLAKA = "34 VAL 2026"
_REFERENCE_ARAC_YASI = 5
_SEGMENT_LENGTH_M = 500


async def _refresh_reference_route(
    uow: Any, lokasyon_id: int, arac_id: int, load_tons: int
) -> None:
    """Trigger one fresh live simulation (real Mapbox+Open-Meteo) for a
    reference route, so load_reference_route_segments() picks up today's
    geometry instead of a stale/historical one."""
    from v2.modules.route_simulation.application.create_route_simulation import (
        create_route_simulation,
    )
    from v2.modules.route_simulation.application.simulate_route import (
        get_route_simulator,
    )

    row = (
        await uow.session.execute(
            text(
                "SELECT cikis_lat, cikis_lon, varis_lat, varis_lon "
                "FROM lokasyonlar WHERE id = :id"
            ),
            {"id": lokasyon_id},
        )
    ).first()
    if row is None or any(v is None for v in row):
        logger.warning(
            "physics_recalibration: lokasyon_id=%s has no coordinates, skipping",
            lokasyon_id,
        )
        return

    cikis_lat, cikis_lon, varis_lat, varis_lon = row
    await create_route_simulation(
        uow.session,
        get_route_simulator(),
        lokasyon_id=lokasyon_id,
        arac_id=arac_id,
        cikis_lon=cikis_lon,
        cikis_lat=cikis_lat,
        varis_lon=varis_lon,
        varis_lat=varis_lat,
        ton=float(load_tons),
        arac_yasi=_REFERENCE_ARAC_YASI,
        segment_length_m=_SEGMENT_LENGTH_M,
        current_user_id=None,
    )


async def _refresh_all_reference_routes(uow: Any) -> int | None:
    """Resolve the reference vehicle and refresh all 10 routes' live
    geometry. Returns the vehicle id, or None if it doesn't exist yet."""
    from v2.modules.route_simulation.domain.physics_reference_routes import (
        REFERENCE_ROUTES,
    )

    arac = await uow.arac_repo.get_by_plaka(_REFERENCE_VEHICLE_PLAKA)
    if arac is None:
        logger.warning(
            "physics_recalibration: reference vehicle %s not found -- "
            "run scripts.p51_real_world_validation once to create it",
            _REFERENCE_VEHICLE_PLAKA,
        )
        return None

    arac_id = int(arac["id"])
    for lokasyon_id, (_name, load_tons, _lo, _hi) in REFERENCE_ROUTES.items():
        await _refresh_reference_route(uow, lokasyon_id, arac_id, load_tons)
    await uow.commit()
    return arac_id


def _build_snapshot(
    fit: Any, route_count: int, cda: float, par: float
) -> dict[str, Any]:
    return {
        "date": date.today().isoformat(),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "green": fit.green,
        "total": route_count,
        "sse": round(fit.sse, 2),
        "cda_fit": fit.cda,
        "parasitic_kw_fit": fit.parasitic_kw,
        "in_physical_band": fit.in_physical_band,
        "current_config_cda": cda,
        "current_config_parasitic_kw": par,
    }


def _append_snapshot(snapshot: dict[str, Any]) -> None:
    _LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with _LOG_PATH.open("a", encoding="utf-8") as fp:
        fp.write(json.dumps(snapshot, ensure_ascii=False) + "\n")


async def _run_weekly_physics_recalibration() -> dict[str, Any]:
    import app.config as cfg
    from v2.modules.route_simulation.application.physics_calibration import (
        grid_search_best_fit,
        load_reference_route_segments,
    )
    from v2.modules.shared_kernel.infrastructure.unit_of_work import UnitOfWork

    cda, par = cfg.settings.PHYSICS_DRAG_CDA_M2, cfg.settings.PHYSICS_PARASITIC_KW
    previous_flag = cfg.settings.USE_SEGMENT_TRACTIVE_MODEL
    cfg.settings.USE_SEGMENT_TRACTIVE_MODEL = True

    try:
        async with UnitOfWork() as uow:
            if await _refresh_all_reference_routes(uow) is None:
                return {"skipped": "reference_vehicle_missing"}
            routes = await load_reference_route_segments(uow.session)
    finally:
        cfg.settings.USE_SEGMENT_TRACTIVE_MODEL = previous_flag

    if not routes:
        return {"skipped": "no_routes_loaded"}

    fit = grid_search_best_fit(routes)
    cfg.settings.PHYSICS_DRAG_CDA_M2 = cda
    cfg.settings.PHYSICS_PARASITIC_KW = par

    snapshot = _build_snapshot(fit, len(routes), cda, par)
    _append_snapshot(snapshot)
    logger.info(
        "physics_recalibration_snapshot: green=%d/%d cda=%.2f parazit=%.1f "
        "(current config: cda=%.2f parazit=%.1f)",
        fit.green,
        len(routes),
        fit.cda,
        fit.parasitic_kw,
        cda,
        par,
    )
    return snapshot


@celery_app.task(
    bind=True,
    name="physics.weekly_recalibration_snapshot",
    max_retries=1,
    acks_late=True,
)
def weekly_recalibration_snapshot(self) -> dict[str, Any]:
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(_run_weekly_physics_recalibration())
    except (ConnectionError, TimeoutError, OSError) as exc:
        raise self.retry(exc=exc, countdown=300)
    except Exception:
        logger.exception("physics weekly recalibration snapshot failed permanently")
        raise
    finally:
        loop.close()
