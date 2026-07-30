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
(Mapbox+Open-Meteo, %100 elevation) kullanılır → Open-Meteo quota-bağımsız
(mevcut/depolanmış geometriyi okur, yeni API çağrısı yapmaz).
Fiziksel bant (overfit guard): Cd·A ∈ [5.3, 7.5], parazit ∈ [3, 12].

2026-07-30: fit mantığı (yükleme/skor/grid-search) `v2/modules/
route_simulation/application/physics_calibration.py`'ye çıkarıldı — aynı
mantığı haftalık otomatik `infrastructure/physics_recalibration_tasks.py`
Celery task'ı da paylaşıyor (Item C: tek-günlük fit'in aşırı-uyum riski
taşıdığı bulundu, çoklu-gün otomatik snapshot bu script'in manuel
tekrarını gereksiz kılıyor).

Çalıştır (backend container, lojinext-db): python -m scripts.calibrate_physics
"""

from __future__ import annotations

import asyncio

import app.config as cfg
from v2.modules.platform_infra.database.module_role import open_role_scoped_session
from v2.modules.route_simulation.application.physics_calibration import (
    grid_search_best_fit,
    load_reference_route_segments,
    score_routes,
)
from v2.modules.route_simulation.public import simulate_route


async def main():
    cfg.settings.USE_SEGMENT_TRACTIVE_MODEL = True
    async with open_role_scoped_session("m_ops") as s:
        routes = await load_reference_route_segments(s)
    if not routes:
        raise SystemExit(
            "route_simulations boş — önce p51 koşulmalı (referans geometri)."
        )

    fit = grid_search_best_fit(routes)
    print("=== Segment-tractive 10-rota kalibrasyonu ===")
    print(
        f"En iyi: Cd·A={fit.cda} m², parazit={fit.parasitic_kw} kW "
        f"(GREEN={fit.green}/{len(routes)}, SSE={fit.sse:.2f})"
    )
    print(f"Fiziksel bant içinde: {fit.in_physical_band}")
    if not fit.in_physical_band:
        raise SystemExit("OVERFIT GUARD: fit fiziksel bant dışı — kök neden ara.")

    cfg.settings.PHYSICS_DRAG_CDA_M2 = fit.cda
    cfg.settings.PHYSICS_PARASITIC_KW = fit.parasitic_kw
    green_final, _sse_final = score_routes(routes)
    print(f"\n{'rota':10}{'yük':>5}{'nötr':>8}{'band':>10}{'sapma%':>8}  sonuç")
    for r in routes:
        summary = simulate_route(
            r.segments, ton=float(r.load_tons), arac_yasi=r.arac_yasi
        )
        n = summary.avg_l_per_100km
        mid = (r.band_low + r.band_high) / 2.0
        sap = (n - mid) / mid * 100.0
        v = (
            "GREEN"
            if r.band_low <= n <= r.band_high
            else ("YELLOW" if abs(sap) <= 10 else "RED")
        )
        print(
            f"{r.name:10}{r.load_tons:5}{n:8.2f}"
            f"{f'{r.band_low:.0f}-{r.band_high:.0f}':>10}{sap:8.1f}  {v}"
        )
    print("\nconfig.py default önerisi:")
    print(f"  PHYSICS_DRAG_CDA_M2 = {fit.cda}")
    print(f"  PHYSICS_PARASITIC_KW = {fit.parasitic_kw}")
    assert green_final == fit.green  # sanity: re-score matches grid-search winner


if __name__ == "__main__":
    asyncio.run(main())
