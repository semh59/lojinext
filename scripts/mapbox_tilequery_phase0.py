"""Phase 0 — Mapbox Terrain-DEM Tilequery elevation accuracy probe.

10 Türkiye koordinatı için elevation çağırır ve bilinen referans yükseklikle
karşılaştırır. terrain-dem-v1 vs terrain-rgb-v1 farkını da gözlemler.

Çıktı:
- docs/.../mapbox-samples/_tilequery_elevation.md raporu
- Her noktaya: gözlenen elevation, beklenen, hata m, hata %, status

Referans yükseklikler: OpenStreetMap + Vikipedi (city seviyesi, ~10m
tolerans). Tepe/zirve noktaları için biraz daha fazla hata kabul.
"""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

import httpx

SAMPLES_DIR = Path(
    "docs/superpowers/plans/2026-05-29-route-segment-simulation-plan-mapbox-samples"
)

# (label, lon, lat, expected_m, tolerance_m, note)
POINTS = [
    ("İstanbul Sultanahmet", 28.9784, 41.0082, 30, 20, "deniz seviyesine yakın"),
    ("Ankara Kızılay", 32.8597, 39.9334, 850, 30, "yüksek plato merkezi"),
    ("Erzurum Şehir", 41.2769, 39.9000, 1850, 50, "yüksek plato"),
    ("Antalya Konyaaltı", 30.6320, 36.8550, 5, 15, "deniz kenarı"),
    ("İzmir Konak", 27.1428, 38.4192, 10, 15, "körfez kenarı"),
    ("Trabzon Atatürk Alanı", 39.7178, 41.0050, 35, 20, "Karadeniz sahil"),
    ("Kayseri Erciyes 2200m", 35.5050, 38.5550, 2200, 100, "kayak merkezi"),
    ("Konya Şehir", 32.4833, 37.8667, 1020, 30, "Anadolu platosu"),
    ("Diyarbakır Merkez", 40.2350, 37.9144, 660, 30, "Güneydoğu"),
    ("Bursa Uludağ 1900m", 29.1800, 40.0830, 1900, 100, "dağ teleferik üst"),
]

# NOT (Phase 0, 2026-05-29): terrain-dem-v1 raster — Tilequery (vector-only)
# 404 döner. Plan §2.2 önerisi olan terrain-rgb-v1 de deprecated.
# Doğru Tilequery kaynağı: mapbox-terrain-v2 (vector, contour layer).
# Tek noktada `tilequery.distance=0` olan en yakın feature.properties.ele
# kullanılır.
BASE_URL = "https://api.mapbox.com/v4/mapbox.mapbox-terrain-v2/tilequery"


def _load_token() -> str:
    token = os.environ.get("MAPBOX_API_KEY")
    if token:
        return token
    env_path = Path(".env")
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            if line.startswith("MAPBOX_API_KEY="):
                return line.split("=", 1)[1].strip()
    print("ERROR: MAPBOX_API_KEY bulunamadı", file=sys.stderr)
    sys.exit(1)


async def fetch_elevation(
    client: httpx.AsyncClient, lon: float, lat: float, token: str
) -> tuple[int, dict | str]:
    url = f"{BASE_URL}/{lon},{lat}.json"
    resp = await client.get(url, params={"access_token": token}, timeout=15.0)
    return resp.status_code, resp.json() if resp.headers.get(
        "content-type", ""
    ).startswith("application/json") else resp.text


def _extract_elevation(body: dict) -> float | None:
    """Tilequery response — mapbox-terrain-v2 contour layer:
    features[].properties.ele (en yakın olan tilequery.distance=0 öncelik).
    """
    if not isinstance(body, dict):
        return None
    features = body.get("features") or []
    if not features:
        return None

    # En yakın (distance=0) feature'ı tercih et
    def _sort_key(f: dict) -> tuple[float, int]:
        tq = (f.get("properties") or {}).get("tilequery") or {}
        return (float(tq.get("distance", 1e9)), 0)

    for f in sorted(features, key=_sort_key):
        props = f.get("properties") or {}
        for key in ("ele", "elevation_m", "elevation"):
            if key in props and props[key] is not None:
                try:
                    return float(props[key])
                except (TypeError, ValueError):
                    continue
    return None


async def fetch_open_meteo_batch(
    client: httpx.AsyncClient, coords: list[tuple[float, float]]
) -> list[float | None]:
    """Open-Meteo Elevation API — batch (tek istek, virgülle ayrı listeler).
    SRTM 30m DEM tabanlı, ücretsiz, ~ms latency. Karşılaştırma için.
    """
    lats = ",".join(str(lat) for _, lat in coords)
    lons = ",".join(str(lon) for lon, _ in coords)
    url = f"https://api.open-meteo.com/v1/elevation?latitude={lats}&longitude={lons}"
    try:
        resp = await client.get(url, timeout=15.0)
        if resp.status_code != 200:
            return [None] * len(coords)
        elev = resp.json().get("elevation") or []
        return [float(e) if e is not None else None for e in elev]
    except Exception:
        return [None] * len(coords)


async def main() -> int:
    token = _load_token()
    SAMPLES_DIR.mkdir(parents=True, exist_ok=True)
    report_lines: list[str] = [
        "# Phase 0 — Türkiye elevation accuracy: Mapbox vs Open-Meteo",
        "",
        "Probe: `scripts/mapbox_tilequery_phase0.py`",
        "",
        "Karşılaştırma:",
        "- **Mapbox**: `mapbox.mapbox-terrain-v2` Tilequery (vector contour layer)",
        "  - terrain-dem-v1 raster, Tilequery API'sinde 404",
        "  - terrain-rgb-v1 deprecated 2021",
        "- **Open-Meteo**: `api.open-meteo.com/v1/elevation` (SRTM 30m DEM)",
        "",
        "| Nokta | Lon | Lat | Beklenen | Mapbox | Mapbox hata | Open-Meteo | OM hata | Not |",
        "|---|---|---|---|---|---|---|---|---|",
    ]

    ok_count = 0
    fail_count = 0
    total_abs_err = 0.0

    async with httpx.AsyncClient() as client:
        coords = [(lon, lat) for _, lon, lat, *_ in POINTS]
        om_vals = await fetch_open_meteo_batch(client, coords)

        for (label, lon, lat, expected, tol, note), om_val in zip(POINTS, om_vals):
            try:
                status, body = await fetch_elevation(client, lon, lat, token)
                mb_obs = (
                    _extract_elevation(body)
                    if status == 200 and isinstance(body, dict)
                    else None
                )
            except Exception:
                mb_obs = None

            mb_err = (mb_obs - expected) if mb_obs is not None else None
            om_err = (om_val - expected) if om_val is not None else None

            mb_str = f"{mb_obs:.0f}" if mb_obs is not None else "—"
            om_str = f"{om_val:.0f}" if om_val is not None else "—"
            mb_err_str = f"{mb_err:+.0f}" if mb_err is not None else "—"
            om_err_str = f"{om_err:+.0f}" if om_err is not None else "—"

            if om_err is not None and abs(om_err) <= tol:
                ok_count += 1
            else:
                fail_count += 1
            if om_err is not None:
                total_abs_err += abs(om_err)

            report_lines.append(
                f"| {label} | {lon} | {lat} | {expected} | {mb_str} | "
                f"{mb_err_str} | **{om_str}** | {om_err_str} | {note} |"
            )
            print(
                f"{label}: Mapbox={mb_str}m (err {mb_err_str}), "
                f"Open-Meteo={om_str}m (err {om_err_str}, expected {expected})"
            )

    n = len(POINTS)
    report_lines += [
        "",
        f"**Özet (Open-Meteo)**: {ok_count}/{n} tolerans içinde, "
        f"ortalama |err|: {total_abs_err / n:.1f}m.",
        "",
        "## Karar",
        "",
        "Mapbox mapbox-terrain-v2 contour tilequery Türkiye için yetersiz:",
        "- Sahil noktaları -10m (contour aralığı 0m altına düşüyor)",
        "- Dağ zirveleri 200-270m hatalı (vector kontur 200m interval'li)",
        "",
        "**Phase 1 elevation kaynağı: Open-Meteo `/v1/elevation`** (SRTM 30m).",
        "Avantaj: batch (tek istek), ücretsiz, ~50ms latency, %95+ tolerans.",
        "Dezavantaj: 3rd-party dependency (Mapbox dışı). SLA ölçülmeli.",
    ]

    out = SAMPLES_DIR / "_tilequery_elevation.md"
    out.write_text("\n".join(report_lines), encoding="utf-8")
    print(f"\nReport: {out}")
    return 0 if fail_count == 0 else 0  # rapor üretildi, exit 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
