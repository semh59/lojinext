"""P5.1 — Real-world validation runner.

Bilinen Türkiye rotalarında SeferFuelEstimator tahminlerinin literatür
bandında olup olmadığını doğrular. Backend container içinde çalıştırılır
(USE_SEFER_FUEL_ESTIMATOR=true zorunlu).

Çalıştırma:
    docker compose exec backend python -m scripts.p51_real_world_validation

Çıktı:
    - STDOUT: markdown tablo + per-rota breakdown
    - data/validation/p51_results_<UTC>.json
    - docs/p51-validation-results-<date>.md
"""

from __future__ import annotations

import asyncio
import json
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

from app.config import settings
from v2.modules.location.public import LokasyonCreate, create_location
from v2.modules.shared_kernel.infrastructure.unit_of_work import UnitOfWork
from v2.modules.trip.application.sefer_fuel_estimator import (
    SeferFuelEstimator,
    SeferFuelInput,
)

# ---------------------------------------------------------------------------
# Test verisi
# ---------------------------------------------------------------------------

REFERENCE_VEHICLE = {
    "plaka": "34 VAL 2026",
    "marka": "Mercedes-Benz",
    "model": "Actros 1851",
    "yil": 2022,
    "tank_kapasitesi": 600,
    "hedef_tuketim": 32.0,
    "bos_agirlik_kg": 8800.0,
    "hava_direnc_katsayisi": 0.55,
    "on_kesit_alani_m2": 8.5,
    "motor_verimliligi": 0.40,
    "lastik_direnc_katsayisi": 0.006,
    "maks_yuk_kapasitesi_kg": 26000,
    "notlar": "P5.1 validation referans aracı — silmeyin",
}

REFERENCE_DRIVER = {
    "ad_soyad": "Validasyon Surucusu",
    "ehliyet_sinifi": "CE",
    "score": 1.0,
    "manual_score": 1.0,
    "notlar": "P5.1 validation — silmeyin",
}

ROUTES = [
    {
        "ad": "VAL-IST-ANK-450",
        "cikis_yeri": "Istanbul Hadimkoy",
        "varis_yeri": "Ankara Esenboga",
        "cikis_lat": 41.110,
        "cikis_lon": 28.732,
        "varis_lat": 39.985,
        "varis_lon": 32.789,
        "mesafe_km": 450,
        "net_kg": 20000,  # 20 ton
        "expected_low": 30.0,
        "expected_high": 35.0,
        "literature_note": "TEM otoyol, ICCT baseline + 20t yük",
    },
    {
        "ad": "VAL-IST-IZM-485",
        "cikis_yeri": "Istanbul Hadimkoy",
        "varis_yeri": "Izmir Aliaga",
        "cikis_lat": 41.110,
        "cikis_lon": 28.732,
        "varis_lat": 38.802,
        "varis_lon": 26.984,
        "mesafe_km": 485,
        "net_kg": 18000,
        "expected_low": 29.0,
        "expected_high": 33.0,
        "literature_note": "O-5+O-31 düz otoyol, 18t yük",
    },
    {
        "ad": "VAL-BUR-IST-155",
        "cikis_yeri": "Bursa Nilufer",
        "varis_yeri": "Istanbul Hadimkoy",
        "cikis_lat": 40.232,
        "cikis_lon": 28.910,
        "varis_lat": 41.110,
        "varis_lon": 28.732,
        "mesafe_km": 155,
        "net_kg": 12000,
        "expected_low": 28.0,
        "expected_high": 32.0,
        "literature_note": "Köprü+kısa otoyol, hafif yük",
    },
    {
        "ad": "VAL-ANK-KON-260",
        "cikis_yeri": "Ankara Esenboga",
        "varis_yeri": "Konya Selcuklu",
        "cikis_lat": 39.985,
        "cikis_lon": 32.789,
        "varis_lat": 37.911,
        "varis_lon": 32.464,
        "mesafe_km": 260,
        "net_kg": 25000,
        "expected_low": 31.0,
        "expected_high": 36.0,
        "literature_note": "Düz step otoyol, 25t yük",
    },
    {
        "ad": "VAL-IST-BOL-265",
        "cikis_yeri": "Istanbul Hadimkoy",
        "varis_yeri": "Bolu Otogar",
        "cikis_lat": 41.110,
        "cikis_lon": 28.732,
        "varis_lat": 40.736,
        "varis_lon": 31.606,
        "mesafe_km": 265,
        "net_kg": 22000,
        "expected_low": 34.0,
        "expected_high": 40.0,
        "literature_note": "Bolu dağı ~800m ascent, 22t yük",
    },
    {
        "ad": "VAL-IZM-AYD-130",
        "cikis_yeri": "Izmir Aliaga",
        "varis_yeri": "Aydin Efeler",
        "cikis_lat": 38.802,
        "cikis_lon": 26.984,
        "varis_lat": 37.848,
        "varis_lon": 27.845,
        "mesafe_km": 130,
        "net_kg": 14000,
        "expected_low": 28.0,
        "expected_high": 33.0,
        "literature_note": (
            "DAF XF480/ICCT modeli C=25.1+0.473×(payload_t-2.6); 14t→30.5 ±2.5. "
            "O-31 düz otoyol."
        ),
    },
    {
        "ad": "VAL-ANK-ESK-235",
        "cikis_yeri": "Ankara Esenboga",
        "varis_yeri": "Eskisehir Tepebasi",
        "cikis_lat": 39.985,
        "cikis_lon": 32.789,
        "varis_lat": 39.776,
        "varis_lon": 30.480,
        "mesafe_km": 235,
        "net_kg": 19000,
        "expected_low": 30.0,
        "expected_high": 35.0,
        "literature_note": (
            "DAF XF480/ICCT modeli C=25.1+0.473×(payload_t-2.6); 19t→32.9 ±2.5. "
            "Düz iç anadolu otoyolu (ICCT 40t baseline 33.1 ile uyumlu)."
        ),
    },
    {
        "ad": "VAL-IST-TEK-130",
        "cikis_yeri": "Istanbul Hadimkoy",
        "varis_yeri": "Tekirdag Suleymanpasa",
        "cikis_lat": 41.110,
        "cikis_lon": 28.732,
        "varis_lat": 40.978,
        "varis_lon": 27.511,
        "mesafe_km": 130,
        "net_kg": 16000,
        "expected_low": 29.0,
        "expected_high": 34.0,
        "literature_note": (
            "DAF XF480/ICCT modeli C=25.1+0.473×(payload_t-2.6); 16t→31.4 ±2.5. "
            "D-110 Trakya düz."
        ),
    },
    {
        "ad": "VAL-KON-AKS-150",
        "cikis_yeri": "Konya Selcuklu",
        "varis_yeri": "Aksaray Merkez",
        "cikis_lat": 37.911,
        "cikis_lon": 32.464,
        "varis_lat": 38.368,
        "varis_lon": 34.030,
        "mesafe_km": 150,
        "net_kg": 23000,
        "expected_low": 32.0,
        "expected_high": 37.0,
        "literature_note": (
            "DAF XF480/ICCT modeli C=25.1+0.473×(payload_t-2.6); 23t→34.8 ±2.5. "
            "Düz step otoyol, ağır yük (max payload yakını)."
        ),
    },
    {
        "ad": "VAL-BUR-BAL-150",
        "cikis_yeri": "Bursa Nilufer",
        "varis_yeri": "Balikesir Altieylul",
        "cikis_lat": 40.232,
        "cikis_lon": 28.910,
        "varis_lat": 39.648,
        "varis_lon": 27.886,
        "mesafe_km": 150,
        "net_kg": 17000,
        "expected_low": 30.0,
        "expected_high": 35.0,
        "literature_note": (
            "DAF XF480/ICCT modeli C=25.1+0.473×(payload_t-2.6); 17t→31.9, "
            "+terrain≈32.9 ±2.5. Hafif tepelik D-200."
        ),
    },
]


# ---------------------------------------------------------------------------
# Setup helpers (idempotent)
# ---------------------------------------------------------------------------


async def get_or_create_vehicle(uow: UnitOfWork) -> int:
    existing = await uow.arac_repo.get_by_plaka(REFERENCE_VEHICLE["plaka"])
    if existing:
        print(f"[setup] Vehicle exists id={existing['id']} plaka={existing['plaka']}")
        return int(existing["id"])

    arac = await uow.arac_repo.add(
        plaka=REFERENCE_VEHICLE["plaka"],
        marka=REFERENCE_VEHICLE["marka"],
        model=REFERENCE_VEHICLE["model"],
        yil=REFERENCE_VEHICLE["yil"],
        tank_kapasitesi=REFERENCE_VEHICLE["tank_kapasitesi"],
        hedef_tuketim=REFERENCE_VEHICLE["hedef_tuketim"],
        bos_agirlik_kg=REFERENCE_VEHICLE["bos_agirlik_kg"],
        hava_direnc_katsayisi=REFERENCE_VEHICLE["hava_direnc_katsayisi"],
        on_kesit_alani_m2=REFERENCE_VEHICLE["on_kesit_alani_m2"],
        motor_verimliligi=REFERENCE_VEHICLE["motor_verimliligi"],
        lastik_direnc_katsayisi=REFERENCE_VEHICLE["lastik_direnc_katsayisi"],
        maks_yuk_kapasitesi_kg=REFERENCE_VEHICLE["maks_yuk_kapasitesi_kg"],
        notlar=REFERENCE_VEHICLE["notlar"],
    )
    await uow.session.flush()
    print(f"[setup] Vehicle CREATED id={arac.id} plaka={arac.plaka}")
    return int(arac.id)


async def get_or_create_driver(uow: UnitOfWork) -> int:
    # repo'da get_by_ad_soyad yoksa raw SQL
    from sqlalchemy import text

    row = (
        await uow.session.execute(
            text("SELECT id FROM soforler WHERE ad_soyad = :name LIMIT 1"),
            {"name": REFERENCE_DRIVER["ad_soyad"]},
        )
    ).first()
    if row:
        print(f"[setup] Driver exists id={row[0]}")
        return int(row[0])

    sofor_id = await uow.sofor_repo.add(
        ad_soyad=REFERENCE_DRIVER["ad_soyad"],
        ehliyet_sinifi=REFERENCE_DRIVER["ehliyet_sinifi"],
        score=REFERENCE_DRIVER["score"],
        manual_score=REFERENCE_DRIVER["manual_score"],
        notlar=REFERENCE_DRIVER["notlar"],
    )
    print(f"[setup] Driver CREATED id={sofor_id}")
    return sofor_id


async def get_or_create_location(uow: UnitOfWork, route: Dict[str, Any]) -> int:
    from sqlalchemy import text

    # Title-case cikis/varis for duplicate check
    cikis_norm = route["cikis_yeri"].strip().title()
    varis_norm = route["varis_yeri"].strip().title()

    row = (
        await uow.session.execute(
            text(
                "SELECT id FROM lokasyonlar "
                "WHERE cikis_yeri = :cikis AND varis_yeri = :varis "
                "AND is_deleted = FALSE LIMIT 1"
            ),
            {"cikis": cikis_norm, "varis": varis_norm},
        )
    ).first()
    if row:
        print(f"[setup] Location exists id={row[0]} {cikis_norm} -> {varis_norm}")
        return int(row[0])

    payload = LokasyonCreate(
        ad=route["ad"],
        cikis_yeri=route["cikis_yeri"],
        varis_yeri=route["varis_yeri"],
        mesafe_km=route["mesafe_km"],
        cikis_lat=route["cikis_lat"],
        cikis_lon=route["cikis_lon"],
        varis_lat=route["varis_lat"],
        varis_lon=route["varis_lon"],
        notlar=route["literature_note"],
    )
    lokasyon_id = await create_location(uow.lokasyon_repo, payload)
    print(f"[setup] Location CREATED id={lokasyon_id} {cikis_norm} -> {varis_norm}")
    return lokasyon_id


# ---------------------------------------------------------------------------
# Sefer create + tahmin toplama
# ---------------------------------------------------------------------------


def neutral_estimate(breakdown) -> float:
    """Faz 7 — koşul-nötr tahmin: çevresel/mevsimsel çarpanlar HARİÇ
    (physics × araç/şoför faktörleri). Literatür bandları koşul-nötr
    olduğundan birincil GREEN/RED kararı bununla verilir (like-for-like)."""
    from v2.modules.prediction_ml.public import combine_factors

    return round(
        breakdown.physics_baseline
        * combine_factors(
            driver=breakdown.driver,
            vehicle_age=breakdown.vehicle_age,
            maintenance=breakdown.maintenance,
        ),
        2,
    )


async def predict_via_estimator(
    arac_id: int,
    sofor_id: int,
    lokasyon_id: int,
    route: Dict[str, Any],
) -> Dict[str, Any]:
    """SeferFuelEstimator'ı direkt çağır (sefer create timeout bypass).

    Sefer kayıt akışı 2.5s timeout uyguluyor — cold cache'de Mapbox+Open-Meteo
    bunu aşıyor. Validation için estimator'ı doğrudan çağırıp asıl pipeline'ın
    çıktısını ölçüyoruz.
    """
    today = date.today()

    inp = SeferFuelInput(
        arac_id=arac_id,
        sofor_id=sofor_id,
        target_date=today,
        ton=float(route["net_kg"]) / 1000.0,
        lokasyon_id=lokasyon_id,
        bos_sefer=False,
    )

    estimator = SeferFuelEstimator()

    try:
        # predict() kendi session'ını açar + persist=True ile route_simulations'ı
        # commit eder; harici session/uow geçilmez (Phase 4.4 imza güncellemesi).
        estimate = await estimator.predict(inp, persist=True)
        if estimate is None:
            return {
                "route": route["ad"],
                "status": "FAILED",
                "verdict": "❌ NO_PREDICTION",
                "error": "estimator returned None (Mapbox/Open-Meteo unavailable?)",
                "expected_band": [route["expected_low"], route["expected_high"]],
            }
    except Exception as exc:
        return {
            "route": route["ad"],
            "status": "FAILED",
            "verdict": "❌ ERROR",
            "error": f"{type(exc).__name__}: {exc}",
            "expected_band": [route["expected_low"], route["expected_high"]],
        }

    # Faz 7 — BİRİNCİL karar koşul-nötr değerle (literatür bandları koşul-nötr).
    tahmin_full = float(estimate.tahmini_tuketim)
    tahmin = neutral_estimate(estimate.breakdown)
    band_low = route["expected_low"]
    band_high = route["expected_high"]
    band_mid = (band_low + band_high) / 2.0

    in_band = band_low <= tahmin <= band_high
    sapma_pct = (tahmin - band_mid) / band_mid * 100.0

    if in_band:
        verdict = "✅ GREEN"
    elif abs(sapma_pct) <= 10:
        verdict = "⚠️ YELLOW"
    else:
        verdict = "❌ RED"

    # SANITY: koşul-uygulanmış (tam) çıktı band üst sınırını >%12 aşmamalı.
    sanity_ok = tahmin_full <= band_high * 1.12

    breakdown = estimate.breakdown
    return {
        "route": route["ad"],
        "status": "OK",
        "simulation_id": estimate.simulation_id,
        "mesafe_input_km": route["mesafe_km"],
        "mesafe_mapbox_km": round(estimate.distance_km, 1),
        "net_kg": route["net_kg"],
        "tahmin_l_100km": round(tahmin, 2),
        "tahmin_full_l_100km": round(tahmin_full, 2),
        "sanity_ok": sanity_ok,
        "total_l_estimate": round(estimate.total_l, 1),
        "duration_min": round(estimate.duration_min, 0),
        "elevation_coverage_pct": round(estimate.elevation_coverage_pct, 1),
        "raw_segment_count": estimate.raw_segment_count,
        "resampled_segment_count": estimate.resampled_segment_count,
        "expected_band": [band_low, band_high],
        "sapma_pct_from_mid": round(sapma_pct, 2),
        "verdict": verdict,
        "breakdown": {
            "physics_baseline": round(breakdown.physics_baseline, 2),
            "driver": round(breakdown.driver, 3),
            "vehicle_age": round(breakdown.vehicle_age, 3),
            "maintenance": round(breakdown.maintenance, 3),
            "weather_temperature": round(breakdown.weather_temperature, 3),
            "weather_wind": round(breakdown.weather_wind, 3),
            "weather_precipitation": round(breakdown.weather_precipitation, 3),
            "seasonal": round(breakdown.seasonal, 3),
            "ml_correction_weight": round(breakdown.ml_correction_weight, 3),
            "final": round(breakdown.final, 2),
        },
    }


# ---------------------------------------------------------------------------
# Rapor formatlama
# ---------------------------------------------------------------------------


def render_summary(results: List[Dict[str, Any]]) -> str:
    lines = []
    lines.append("# P5.1 Real-World Validation Results")
    lines.append(f"\nTarih: {datetime.now(timezone.utc).isoformat()}")
    lines.append(f"USE_SEFER_FUEL_ESTIMATOR={settings.USE_SEFER_FUEL_ESTIMATOR}")
    lines.append(
        "Yöntem: SeferFuelEstimator.predict() doğrudan çağrı (sefer create timeout bypass)"
    )
    lines.append("")
    lines.append("## Özet tablo\n")
    lines.append(
        "Birincil karar **koşul-nötr** tahminle (physics×araç/şoför, çevresel "
        "çarpanlar hariç) verilir — literatür bandları koşul-nötr. `Tam` sütunu "
        "koşul-uygulanmış çıktı; `Sanity` = tam çıktı ≤ band üst sınırı ×1.12.\n"
    )
    lines.append(
        "| Rota | Mesafe (km) | Yük (kg) | Nötr (L/100km) | Tam (L/100km) | Beklenen band | Sapma % | Sonuç | Sanity |"
    )
    lines.append(
        "|------|-------------|----------|----------------|---------------|---------------|---------|-------|--------|"
    )
    for r in results:
        if r["status"] != "OK":
            band = f"{r['expected_band'][0]:.1f} - {r['expected_band'][1]:.1f}"
            err = r.get("error", "")
            lines.append(
                f"| {r['route']} | — | — | — | — | {band} | — | {r['verdict']} ({err[:50]}) | — |"
            )
            continue
        band = f"{r['expected_band'][0]:.1f} - {r['expected_band'][1]:.1f}"
        sapma = f"{r['sapma_pct_from_mid']:+.1f}%"
        mesafe = f"{r['mesafe_mapbox_km']:.0f}"
        tahmin = f"{r['tahmin_l_100km']:.1f}"
        tam = f"{r['tahmin_full_l_100km']:.1f}"
        sanity = "✅" if r.get("sanity_ok") else "❌"
        lines.append(
            f"| {r['route']} | {mesafe} | {r['net_kg']} | {tahmin} | {tam} "
            f"| {band} | {sapma} | {r['verdict']} | {sanity} |"
        )

    # Verdict aggregate
    ok = sum(1 for r in results if r.get("verdict") == "✅ GREEN")
    yellow = sum(1 for r in results if r.get("verdict") == "⚠️ YELLOW")
    red = sum(
        1
        for r in results
        if r.get("verdict") in ("❌ RED", "❌ NO_PREDICTION", "❌ ERROR")
    )
    ok_results = [r for r in results if r["status"] == "OK"]
    sanity_ok = sum(1 for r in ok_results if r.get("sanity_ok"))
    lines.append("")
    lines.append(
        f"**Aggregate (koşul-nötr)**: ✅ {ok}/{len(results)} GREEN, "
        f"⚠️ {yellow} YELLOW, ❌ {red} RED"
    )
    lines.append(
        f"**Sanity (tam çıktı ≤ band×1.12)**: {sanity_ok}/{len(ok_results)} geçti"
    )
    lines.append("")

    # Per-rota breakdown
    lines.append("## Per-rota faktör breakdown\n")
    for r in results:
        if r["status"] != "OK":
            continue
        b = r["breakdown"]
        lines.append(f"### {r['route']}")
        lines.append(f"- simulation_id: {r['simulation_id']}")
        lines.append(
            f"- Mapbox mesafe: {r['mesafe_mapbox_km']} km "
            f"(input: {r['mesafe_input_km']} km, Δ={r['mesafe_mapbox_km'] - r['mesafe_input_km']:+.0f})"
        )
        lines.append(f"- Tahmini süre: {r['duration_min']:.0f} dakika")
        lines.append(f"- Toplam tahmini yakıt: {r['total_l_estimate']:.1f} L")
        lines.append(
            f"- Segment: raw={r['raw_segment_count']}, "
            f"resampled={r['resampled_segment_count']}, "
            f"elevation_coverage={r['elevation_coverage_pct']}%"
        )
        lines.append(f"- **Physics baseline**: {b['physics_baseline']} L/100km")
        lines.append(
            f"- Factors: driver={b['driver']}, vehicle_age={b['vehicle_age']}, "
            f"maint={b['maintenance']}"
        )
        lines.append(
            f"  - weather: temp={b['weather_temperature']}, wind={b['weather_wind']}, "
            f"precip={b['weather_precipitation']}, seasonal={b['seasonal']}"
        )
        lines.append(
            f"- **Koşul-nötr L/100km**: {r['tahmin_l_100km']} (birincil karar)"
        )
        lines.append(
            f"- **Tam çıktı L/100km**: {r['tahmin_full_l_100km']} "
            f"(sanity: {'✅' if r.get('sanity_ok') else '❌'})"
        )
        lines.append(f"- **Final L/100km**: {b['final']}")
        lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


async def main():
    print("=" * 70)
    print("P5.1 Real-World Validation")
    print(f"USE_SEFER_FUEL_ESTIMATOR={settings.USE_SEFER_FUEL_ESTIMATOR}")
    print("=" * 70)

    if not settings.USE_SEFER_FUEL_ESTIMATOR:
        print("⚠️  USE_SEFER_FUEL_ESTIMATOR=False — tahmin tetiklenmeyecek!")
        print("    Container'da env'i true yapın ve restart edin.")

    # Setup
    async with UnitOfWork() as uow:
        arac_id = await get_or_create_vehicle(uow)
        sofor_id = await get_or_create_driver(uow)
        lokasyon_ids = []
        for route in ROUTES:
            lid = await get_or_create_location(uow, route)
            lokasyon_ids.append((route, lid))
        await uow.commit()

    print("")
    print(
        f"[setup] arac_id={arac_id}, sofor_id={sofor_id}, locations={len(lokasyon_ids)}"
    )
    print("")

    # Estimator predict (sefer create timeout bypass).
    # Rotalar arası bekleme: Open-Meteo free-tier minutely limiti tek rotanın
    # elevation+weather çağrılarını kaldırır ama 5 rota arka arkaya saturate
    # edip 429 → eksik veri → physics underestimate yapar (CLAUDE.md gotcha).
    # PACE_SECONDS ile her rota taze dakikalık bütçe alır (env ile ayarlanır).
    import os as _os

    pace = int(_os.environ.get("P51_PACE_SECONDS", "65"))
    results = []
    for idx, (route, lokasyon_id) in enumerate(lokasyon_ids, 1):
        if idx > 1 and pace > 0:
            print(f"[pace] Open-Meteo limiti için {pace}s bekleniyor…")
            await asyncio.sleep(pace)
        print(f"[predict {idx}/{len(lokasyon_ids)}] {route['ad']}...")
        result = await predict_via_estimator(arac_id, sofor_id, lokasyon_id, route)
        results.append(result)
        print(
            f"    -> {result.get('verdict')} tahmin={result.get('tahmin_l_100km')} "
            f"band={result.get('expected_band')}"
        )

    # Rapor
    summary_md = render_summary(results)
    print("")
    print(summary_md)

    # Persistance
    out_dir = Path("/app/data/validation")
    out_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    json_path = out_dir / f"p51_results_{ts}.json"
    md_path = out_dir / f"p51_results_{ts}.md"

    with json_path.open("w", encoding="utf-8") as fp:
        json.dump(results, fp, indent=2, ensure_ascii=False, default=str)
    with md_path.open("w", encoding="utf-8") as fp:
        fp.write(summary_md)
    print(f"\n[output] {json_path}")
    print(f"[output] {md_path}")


if __name__ == "__main__":
    asyncio.run(main())
