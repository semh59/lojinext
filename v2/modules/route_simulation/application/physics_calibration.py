"""Segment-tractive physics calibration — shared fit logic.

Used by both `scripts/calibrate_physics.py` (one-off manual run) and
`infrastructure/physics_recalibration_tasks.py` (weekly Celery snapshot,
see that module's docstring for why calibration needs periodic re-fitting
against live route geometry rather than a one-time value).
"""

from __future__ import annotations

from typing import NamedTuple

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from v2.modules.route_simulation.domain.physics_reference_routes import (
    CDA_BAND,
    PAR_BAND,
    REFERENCE_ROUTES,
)
from v2.modules.route_simulation.public import SegmentInput, simulate_route


class ReferenceRouteData(NamedTuple):
    name: str
    load_tons: int
    band_low: float
    band_high: float
    arac_yasi: int
    segments: list[SegmentInput]


async def load_reference_route_segments(
    session: AsyncSession,
) -> list[ReferenceRouteData]:
    """Load the most-recently-simulated segment geometry for each of the
    10 reference routes (highest elevation coverage first, newest as
    tiebreaker) -- whatever is currently in route_simulations/
    route_segments, stored or freshly live."""
    out: list[ReferenceRouteData] = []
    for lid, (name, ton, lo, hi) in REFERENCE_ROUTES.items():
        r = (
            await session.execute(
                text(
                    "SELECT id, arac_yasi FROM route_simulations WHERE lokasyon_id=:l "
                    "ORDER BY elevation_coverage_pct DESC, id DESC LIMIT 1"
                ),
                {"l": lid},
            )
        ).first()
        if not r:
            continue
        rows = await session.execute(
            text(
                "SELECT length_km, grade_pct, road_class, maxspeed_kmh, "
                "traffic_speed_kmh, congestion FROM route_segments "
                "WHERE simulation_id=:s ORDER BY seq"
            ),
            {"s": r[0]},
        )
        segs = [
            SegmentInput(
                length_km=float(a or 0),
                grade_pct=float(b or 0),
                road_class=c or "",
                maxspeed_kmh=float(d) if d else None,
                traffic_speed_kmh=float(e) if e else None,
                congestion=f or "low",
            )
            for a, b, c, d, e, f in rows
        ]
        out.append(ReferenceRouteData(name, ton, lo, hi, int(r[1] or 5), segs))
    return out


def score_routes(routes: list[ReferenceRouteData]) -> tuple[int, float]:
    """(green_count, sum_squared_error_vs_band_midpoint) for the CURRENT
    app.config.settings physics constants."""
    sse = 0.0
    green = 0
    for r in routes:
        summary = simulate_route(
            r.segments, ton=float(r.load_tons), arac_yasi=r.arac_yasi
        )
        n = summary.avg_l_per_100km
        mid = (r.band_low + r.band_high) / 2.0
        sse += (n - mid) ** 2
        if r.band_low <= n <= r.band_high:
            green += 1
    return green, sse


class CalibrationFit(NamedTuple):
    green: int
    sse: float
    cda: float
    parasitic_kw: float
    in_physical_band: bool


def grid_search_best_fit(routes: list[ReferenceRouteData]) -> CalibrationFit:
    """Grid-search PHYSICS_DRAG_CDA_M2/PHYSICS_PARASITIC_KW over their
    physical bands, maximizing GREEN count (SSE as tiebreaker). Mutates
    app.config.settings as a side effect of scoring each candidate --
    caller decides whether to keep the winning values applied or restore
    the previous ones (this module does not persist config.py itself)."""
    import app.config as cfg

    best: tuple[int, float, float, float] | None = None
    cda = CDA_BAND[0]
    while cda <= CDA_BAND[1] + 1e-9:
        par = PAR_BAND[0]
        while par <= PAR_BAND[1] + 1e-9:
            cfg.settings.PHYSICS_DRAG_CDA_M2 = cda
            cfg.settings.PHYSICS_PARASITIC_KW = par
            green, sse = score_routes(routes)
            cand = (green, -sse, round(cda, 2), round(par, 1))
            if best is None or cand[:2] > best[:2]:
                best = cand
            par += 0.5
        cda += 0.1

    assert best is not None
    green, neg_sse, cda_fit, par_fit = best
    in_band = (
        CDA_BAND[0] <= cda_fit <= CDA_BAND[1] and PAR_BAND[0] <= par_fit <= PAR_BAND[1]
    )
    return CalibrationFit(green, -neg_sse, cda_fit, par_fit, in_band)
