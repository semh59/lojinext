"""Phase 0 — Mapbox Directions canlı API probe.

3 koordinat çifti için /driving-traffic çağırır ve:
  1) Raw JSON'u docs/.../mapbox-samples/*.json'a kaydeder
  2) Bir özet raporu (.md) yazar:
     - road_class annotation gerçekten var mı (mapbox_client.py:146 bug teyit)
     - maxspeed doluluk oranı (none/unknown vs gerçek değer)
     - speed (gerçek hız) granularitesi — kaç segment, ortalama segment uzunluğu
     - congestion / congestion_numeric coverage
     - step.intersections.mapbox_streets_v8.class doluluk (road_class fallback için kritik)

Uyarı: Bu script gerçek API kotası tüketir. 3 çağrı, küçük cost.
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
from collections import Counter
from pathlib import Path
from typing import Any

import httpx

ROUTES = [
    {
        "name": "istanbul-ankara-otoyol",
        "label": "İstanbul → Ankara (450 km, otoyol-ağırlıklı)",
        "start": (28.9784, 41.0082),  # (lon, lat) Sultanahmet
        "end": (32.8597, 39.9334),  # Ankara Kızılay
    },
    {
        "name": "maslak-kadikoy-sehir",
        "label": "Maslak → Kadıköy (İstanbul içi, şehir)",
        "start": (29.0205, 41.1098),  # Maslak
        "end": (29.0257, 40.9897),  # Kadıköy
    },
    {
        "name": "bursa-antalya-daglik",
        "label": "Bursa → Antalya (~700 km, dağlık karışım)",
        "start": (29.0610, 40.1885),  # Bursa
        "end": (30.7133, 36.8841),  # Antalya
    },
]

BASE_URL = "https://api.mapbox.com/directions/v5/mapbox/driving-traffic"
SAMPLES_DIR = Path(
    "docs/superpowers/plans/2026-05-29-route-segment-simulation-plan-mapbox-samples"
)


def _load_token() -> str:
    token = os.environ.get("MAPBOX_API_KEY")
    if token:
        return token
    # .env fallback (CI'da env yoksa)
    env_path = Path(".env")
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            if line.startswith("MAPBOX_API_KEY="):
                return line.split("=", 1)[1].strip()
    print("ERROR: MAPBOX_API_KEY bulunamadı (env veya .env)", file=sys.stderr)
    sys.exit(1)


async def fetch_one(client: httpx.AsyncClient, route: dict, token: str) -> dict:
    lon1, lat1 = route["start"]
    lon2, lat2 = route["end"]
    coords = f"{lon1},{lat1};{lon2},{lat2}"
    url = f"{BASE_URL}/{coords}"
    # NOT: plan'a göre road_class annotation YOK. Yine de gönderip API'nin
    # tepkisini görelim — hata mı veriyor, sessizce yutuyor mu?
    # PHASE 0 BULGU: road_class annotation Mapbox tarafından kabul edilmiyor
    # (422 InvalidInput). Mapbox geçerli annotation listesi:
    #   duration, distance, speed, congestion, congestion_numeric, closure,
    #   state_of_charge, energy_levels, maxspeed
    # Yani mapbox_client.py:56 mevcut production string ("...road_class") TÜM
    # çağrılarda 422 alıyor — sessiz fallback varsa routing fiilen ölü.
    params = {
        "access_token": token,
        "geometries": "geojson",
        "overview": "full",
        "steps": "true",  # intersections.mapbox_streets_v8.class için kritik
        "annotations": "distance,duration,speed,maxspeed,congestion,congestion_numeric",
    }
    resp = await client.get(url, params=params, timeout=30.0)
    return {
        "status_code": resp.status_code,
        "url": str(resp.url).replace(token, "***TOKEN***"),
        "body": resp.json()
        if resp.headers.get("content-type", "").startswith("application/json")
        else resp.text,
    }


def _summarize_annotations(route_obj: dict) -> dict:
    """leg[*].annotation içeriğini analiz et."""
    legs = route_obj.get("legs", [])
    summary: dict[str, Any] = {
        "leg_count": len(legs),
        "has_road_class_annotation": False,
        "annotation_keys": set(),
        "segment_count_total": 0,
        "distance_segments_total_m": 0.0,
        "avg_segment_length_m": None,
        "maxspeed_breakdown": Counter(),
        "speed_present_pct": None,
        "congestion_breakdown": Counter(),
        "congestion_numeric_min": None,
        "congestion_numeric_max": None,
        "step_count_total": 0,
        "intersections_with_mapbox_streets_class_pct": None,
        "mapbox_streets_class_breakdown": Counter(),
    }

    total_distance = 0.0
    seg_count = 0
    maxspeed_total = 0
    maxspeed_unknown_or_none = 0
    speed_present = 0
    speed_total = 0
    congestion_numeric_vals: list[float] = []

    intersections_total = 0
    intersections_with_streets_class = 0
    step_total = 0

    for leg in legs:
        ann = leg.get("annotation", {})
        for k in ann.keys():
            summary["annotation_keys"].add(k)
        if "road_class" in ann and ann["road_class"]:
            summary["has_road_class_annotation"] = True

        distances = ann.get("distance", [])
        seg_count += len(distances)
        total_distance += sum(distances)

        for ms in ann.get("maxspeed", []) or []:
            maxspeed_total += 1
            if isinstance(ms, dict):
                if ms.get("unknown") or ms.get("none"):
                    maxspeed_unknown_or_none += 1
                    summary["maxspeed_breakdown"][
                        "unknown" if ms.get("unknown") else "none"
                    ] += 1
                else:
                    sp = ms.get("speed")
                    unit = ms.get("unit", "km/h")
                    summary["maxspeed_breakdown"][f"{sp}{unit}"] += 1

        for sp in ann.get("speed", []) or []:
            speed_total += 1
            if sp is not None:
                speed_present += 1

        for c in ann.get("congestion", []) or []:
            summary["congestion_breakdown"][c or "null"] += 1

        for cn in ann.get("congestion_numeric", []) or []:
            if cn is not None:
                congestion_numeric_vals.append(cn)

        for step in leg.get("steps", []) or []:
            step_total += 1
            for inter in step.get("intersections", []) or []:
                intersections_total += 1
                streets = inter.get("mapbox_streets_v8")
                if streets and streets.get("class"):
                    intersections_with_streets_class += 1
                    summary["mapbox_streets_class_breakdown"][streets["class"]] += 1

    summary["segment_count_total"] = seg_count
    summary["distance_segments_total_m"] = round(total_distance, 1)
    summary["avg_segment_length_m"] = (
        round(total_distance / seg_count, 1) if seg_count else None
    )
    summary["maxspeed_total_count"] = maxspeed_total
    summary["maxspeed_unknown_or_none_count"] = maxspeed_unknown_or_none
    summary["speed_present_pct"] = (
        round(speed_present / speed_total * 100, 1) if speed_total else None
    )
    if congestion_numeric_vals:
        summary["congestion_numeric_min"] = min(congestion_numeric_vals)
        summary["congestion_numeric_max"] = max(congestion_numeric_vals)
    summary["step_count_total"] = step_total
    summary["intersections_total"] = intersections_total
    summary["intersections_with_mapbox_streets_class_pct"] = (
        round(intersections_with_streets_class / intersections_total * 100, 1)
        if intersections_total
        else None
    )

    # JSON serializable
    summary["annotation_keys"] = sorted(summary["annotation_keys"])
    summary["maxspeed_breakdown"] = dict(summary["maxspeed_breakdown"].most_common(20))
    summary["congestion_breakdown"] = dict(summary["congestion_breakdown"])
    summary["mapbox_streets_class_breakdown"] = dict(
        summary["mapbox_streets_class_breakdown"]
    )
    return summary


async def main() -> int:
    token = _load_token()
    SAMPLES_DIR.mkdir(parents=True, exist_ok=True)

    summaries: list[dict] = []

    async with httpx.AsyncClient() as client:
        for route in ROUTES:
            print(f"Fetching: {route['label']} ...")
            result = await fetch_one(client, route, token)

            if result["status_code"] != 200:
                print(f"  ! HTTP {result['status_code']}")
                summaries.append(
                    {
                        "route": route["name"],
                        "label": route["label"],
                        "error": result["body"],
                    }
                )
                continue

            raw_path = SAMPLES_DIR / f"{route['name']}-raw.json"
            raw_path.write_text(
                json.dumps(result["body"], ensure_ascii=False, indent=2),
                encoding="utf-8",
            )

            route_obj = (result["body"].get("routes") or [{}])[0]
            sumry = _summarize_annotations(route_obj)
            sumry["route_distance_km"] = round(route_obj.get("distance", 0) / 1000.0, 1)
            sumry["route_duration_min"] = round(route_obj.get("duration", 0) / 60.0, 1)
            sumry["route"] = route["name"]
            sumry["label"] = route["label"]
            summaries.append(sumry)
            print(
                f"  OK {sumry['route_distance_km']} km, "
                f"{sumry['segment_count_total']} segment, "
                f"road_class_annotation={sumry['has_road_class_annotation']}"
            )

    report_path = SAMPLES_DIR / "_summary.md"
    lines = ["# Mapbox Directions Phase 0 — canlı API özeti", ""]
    lines.append(
        "Bu rapor `scripts/mapbox_phase0_probe.py` tarafından üretildi. "
        "Raw JSON dosyaları bu klasörde (`{route}-raw.json`)."
    )
    lines.append("")
    for s in summaries:
        lines.append(f"## {s.get('label', s.get('route'))}")
        if "error" in s:
            lines.append(f"- ERROR: `{s['error']}`")
            continue
        lines.append(
            f"- Distance: **{s['route_distance_km']} km**, "
            f"Duration: **{s['route_duration_min']} min**"
        )
        lines.append(f"- Annotation keys present: `{s['annotation_keys']}`")
        lines.append(
            f"- **road_class annotation present**: "
            f"`{s['has_road_class_annotation']}`  "
            f"← mapbox_client.py:146 bug teyit göstergesi"
        )
        lines.append(
            f"- Segment count: **{s['segment_count_total']}** "
            f"(avg length: **{s['avg_segment_length_m']} m**)"
        )
        lines.append(
            f"- speed annotation present: **{s['speed_present_pct']}%** of segments"
        )
        lines.append(
            f"- maxspeed total: {s['maxspeed_total_count']}, "
            f"unknown/none: {s['maxspeed_unknown_or_none_count']}"
        )
        lines.append(f"- maxspeed top values: `{s['maxspeed_breakdown']}`")
        lines.append(f"- congestion breakdown: `{s['congestion_breakdown']}`")
        if s.get("congestion_numeric_min") is not None:
            lines.append(
                f"- congestion_numeric range: "
                f"{s['congestion_numeric_min']} .. {s['congestion_numeric_max']}"
            )
        lines.append(f"- step count: {s['step_count_total']}")
        lines.append(
            f"- intersections with mapbox_streets_v8.class: "
            f"**{s['intersections_with_mapbox_streets_class_pct']}%** "
            f"(road_class reconcile fallback için kritik)"
        )
        lines.append(
            f"- mapbox_streets_v8.class breakdown: "
            f"`{s['mapbox_streets_class_breakdown']}`"
        )
        lines.append("")

    report_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"\nSummary report: {report_path}")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
