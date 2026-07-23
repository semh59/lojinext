"""Segment-tractive physics kalibrasyonu — 10 gerçek referans rotaya fit.

Payload slope (0.473 L/100km/ton) trailer_rolling_resistance=0.00738'den GELİR
ve sabittir. Bu script INTERCEPT + drag/parazit dengesini kalibre eder:
efektif Cd·A (yük-bağımsız, hız²) + parazit (zaman-bazlı).

NEDEN gerçek-rota fit (tek-nokta flat değil): Düz 80 km/h tek noktasında drag
ve parazit ikisi de ~sabit ekler → AYIRT EDİLEMEZ. 10 referans rota farklı
hızlarda (65-85 km/h) koşar → drag (v²) hızlı rotaları, parazit (zaman) yavaş
rotaları daha çok etkiler → ikisi ayrışır. Flat-80 fit Cd·A=7.6 (aşırı drag)
verip hızlı rotaları şişiriyordu; gerçek-rota fit Cd·A=6.80, parazit=4.0 kW
(VECTO non-aero + gerçekçi aksesuar) → 9/10 GREEN.

Bantlar koşul-nötr (physics-only); route_segments'teki gerçek geometri
(Mapbox+Open-Meteo, %100 elevation) kullanılır → Open-Meteo quota-bağımsız.
Fiziksel bant (overfit guard): Cd·A ∈ [5.3, 7.5], parazit ∈ [3, 12].

Çalıştır (backend container, lojinext-db): python -m scripts.calibrate_physics
"""

from __future__ import annotations

import asyncio

from sqlalchemy import text

import app.config as cfg
from v2.modules.platform_infra.database.connection import AsyncSessionLocal
from v2.modules.route_simulation.public import (
    SegmentInput,
    simulate_route,
)

# lokasyon_id → (ad, yük_t, band_low, band_high). Bandlar DAF/ICCT.
ROUTES = {
    3: ("IST-ANK", 20, 30.0, 35.0),
    4: ("IST-IZM", 18, 29.0, 33.0),
    5: ("BUR-IST", 12, 28.0, 32.0),
    6: ("ANK-KON", 25, 31.0, 36.0),
    7: ("IST-BOL", 22, 34.0, 40.0),
    8: ("IZM-AYD", 14, 28.0, 33.0),
    9: ("ANK-ESK", 19, 30.0, 35.0),
    10: ("IST-TEK", 16, 29.0, 34.0),
    11: ("KON-AKS", 23, 32.0, 37.0),
    12: ("BUR-BAL", 17, 30.0, 35.0),
}
CDA_BAND = (5.3, 7.5)
PAR_BAND = (3.0, 12.0)


async def _load_routes(s):
    out = []
    for lid, (ad, ton, lo, hi) in ROUTES.items():
        r = (
            await s.execute(
                text(
                    "SELECT id, arac_yasi FROM route_simulations WHERE lokasyon_id=:l "
                    "ORDER BY elevation_coverage_pct DESC, id DESC LIMIT 1"
                ),
                {"l": lid},
            )
        ).first()
        if not r:
            continue
        rows = await s.execute(
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
        out.append((ad, ton, lo, hi, int(r[1] or 5), segs))
    return out


def _score(routes):
    sse = 0.0
    green = 0
    for _ad, ton, lo, hi, yas, segs in routes:
        n = simulate_route(segs, ton=float(ton), arac_yasi=yas).avg_l_per_100km
        mid = (lo + hi) / 2.0
        sse += (n - mid) ** 2
        if lo <= n <= hi:
            green += 1
    return green, sse


async def main():
    cfg.settings.USE_SEGMENT_TRACTIVE_MODEL = True
    async with AsyncSessionLocal() as s:
        routes = await _load_routes(s)
    if not routes:
        raise SystemExit(
            "route_simulations boş — önce p51 koşulmalı (referans geometri)."
        )

    best = None
    cda = CDA_BAND[0]
    while cda <= CDA_BAND[1] + 1e-9:
        par = PAR_BAND[0]
        while par <= PAR_BAND[1] + 1e-9:
            cfg.settings.PHYSICS_DRAG_CDA_M2 = cda
            cfg.settings.PHYSICS_PARASITIC_KW = par
            green, sse = _score(routes)
            cand = (green, -sse, round(cda, 2), round(par, 1))
            if best is None or cand[:2] > best[:2]:
                best = cand
            par += 0.5
        cda += 0.1

    assert best is not None
    green, neg_sse, cda_fit, par_fit = best
    print("=== Segment-tractive 10-rota kalibrasyonu ===")
    print(
        f"En iyi: Cd·A={cda_fit} m², parazit={par_fit} kW "
        f"(GREEN={green}/{len(routes)}, SSE={-neg_sse:.2f})"
    )
    in_band = (
        CDA_BAND[0] <= cda_fit <= CDA_BAND[1] and PAR_BAND[0] <= par_fit <= PAR_BAND[1]
    )
    print(f"Fiziksel bant içinde: {in_band}")
    if not in_band:
        raise SystemExit("OVERFIT GUARD: fit fiziksel bant dışı — kök neden ara.")

    cfg.settings.PHYSICS_DRAG_CDA_M2 = cda_fit
    cfg.settings.PHYSICS_PARASITIC_KW = par_fit
    print(f"\n{'rota':10}{'yük':>5}{'nötr':>8}{'band':>10}{'sapma%':>8}  sonuç")
    for ad, ton, lo, hi, yas, segs in routes:
        n = simulate_route(segs, ton=float(ton), arac_yasi=yas).avg_l_per_100km
        mid = (lo + hi) / 2.0
        sap = (n - mid) / mid * 100.0
        v = "GREEN" if lo <= n <= hi else ("YELLOW" if abs(sap) <= 10 else "RED")
        print(f"{ad:10}{ton:5}{n:8.2f}{f'{lo:.0f}-{hi:.0f}':>10}{sap:8.1f}  {v}")
    print("\nconfig.py default önerisi:")
    print(f"  PHYSICS_DRAG_CDA_M2 = {cda_fit}")
    print(f"  PHYSICS_PARASITIC_KW = {par_fit}")


if __name__ == "__main__":
    asyncio.run(main())
