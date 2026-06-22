"""Tractive modelini DEPOLANMIŞ route geometrisiyle offline doğrula (quota-bağımsız).

Open-Meteo daily quota tükendiğinde p51 yeni elevation çekemez. Ama geçmiş
p51 koşuları route_segments'e gerçek geometri + grade'i (Mapbox+Open-Meteo,
%100 elevation) zaten yazdı. Bu script her referans rota için EN YÜKSEK
elevation coverage'lı simülasyonu seçip, segmentlerini YENİ tractive motordan
(USE_SEGMENT_TRACTIVE_MODEL=True) geçirir → koşul-nötr (physics-only, hava
çarpansız) L/100km. Literatür bandlarıyla kıyaslar.

Çalıştır (backend container, lojinext-db): python -m scripts.validate_tractive_offline
"""

from __future__ import annotations

import asyncio

from sqlalchemy import text

import app.config as cfg
from app.core.ml.segment_simulator import SegmentInput, simulate_route
from app.database.connection import AsyncSessionLocal

# lokasyon_id → (ad, yük_t, band_low, band_high)
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


async def best_sim_for(s, lokasyon_id: int):
    row = await s.execute(
        text(
            "SELECT id, arac_yasi, elevation_coverage_pct FROM route_simulations "
            "WHERE lokasyon_id=:l ORDER BY elevation_coverage_pct DESC, id DESC LIMIT 1"
        ),
        {"l": lokasyon_id},
    )
    return row.first()


async def segments_for(s, sim_id: int):
    rows = await s.execute(
        text(
            "SELECT length_km, grade_pct, road_class, maxspeed_kmh, traffic_speed_kmh, "
            "congestion FROM route_segments WHERE simulation_id=:s ORDER BY seq"
        ),
        {"s": sim_id},
    )
    return [
        SegmentInput(
            length_km=float(r[0] or 0),
            grade_pct=float(r[1] or 0),
            road_class=r[2] or "",
            maxspeed_kmh=float(r[3]) if r[3] else None,
            traffic_speed_kmh=float(r[4]) if r[4] else None,
            congestion=r[5] or "low",
        )
        for r in rows
    ]


async def main():
    cfg.settings.USE_SEGMENT_TRACTIVE_MODEL = True
    green = yellow = red = 0
    print("=== Tractive offline validasyon (depolanmış geometri, koşul-nötr) ===")
    print(
        f"{'rota':10}{'yük':>5}{'elev%':>7}{'nötr':>8}{'band':>13}{'sapma%':>8}  sonuç"
    )
    async with AsyncSessionLocal() as s:
        for lid, (ad, ton, lo, hi) in ROUTES.items():
            sim = await best_sim_for(s, lid)
            if not sim:
                print(f"{ad:10} — sim yok")
                continue
            sim_id, yas, elev = sim
            segs = await segments_for(s, sim_id)
            summary = simulate_route(segs, ton=float(ton), arac_yasi=int(yas or 5))
            neutral = summary.avg_l_per_100km
            mid = (lo + hi) / 2.0
            sapma = (neutral - mid) / mid * 100.0
            if lo <= neutral <= hi:
                verdict = "GREEN"
                green += 1
            elif abs(sapma) <= 10:
                verdict = "YELLOW"
                yellow += 1
            else:
                verdict = "RED"
                red += 1
            print(
                f"{ad:10}{ton:5}{float(elev or 0):7.0f}{neutral:8.2f}"
                f"{f'{lo:.0f}-{hi:.0f}':>13}{sapma:8.1f}  {verdict}"
            )
    total = green + yellow + red
    print(f"\nAggregate: {green}/{total} GREEN, {yellow} YELLOW, {red} RED")


if __name__ == "__main__":
    asyncio.run(main())
