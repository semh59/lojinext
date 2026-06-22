"""MapboxClient._reconcile_segment_road_classes — Phase 0 bulgu testleri.

Mapbox Directions API'de `road_class` annotation YOK (Phase 0 canlı API
teyidi, bkz. docs/superpowers/plans/2026-05-29-route-segment-simulation-
plan-mapbox-samples/_summary.md). Bunun yerine
`step.intersections[*].mapbox_streets_v8.class` (~99.9% doluluk) kullanılır.

Bu test'ler:
- Synthetic fixture'lar ile reconcile mantığını doğrular (geometry_index
  → segment class miras)
- Gerçek Mapbox sample JSON'larıyla smoke (3 rota)
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.infrastructure.routing.mapbox_client import MapboxClient

SAMPLES_DIR = Path(
    "docs/superpowers/plans/2026-05-29-route-segment-simulation-plan-mapbox-samples"
)


def _build_route(
    *, distances: list[float], intersection_points: list[tuple[int, str]]
) -> dict:
    """Tek leg + tek step + verilen intersection'larla synthetic route."""
    intersections = [
        {"geometry_index": gi, "mapbox_streets_v8": {"class": cls}}
        for gi, cls in intersection_points
    ]
    return {
        "legs": [
            {
                "annotation": {"distance": distances},
                "steps": [
                    {"intersections": intersections},
                ],
            }
        ]
    }


def test_reconcile_returns_class_per_segment():
    route = _build_route(
        distances=[10.0, 20.0, 30.0, 40.0],
        intersection_points=[(0, "motorway"), (2, "primary")],
    )
    classes = MapboxClient._reconcile_segment_road_classes(route)
    assert classes == ["motorway", "motorway", "primary", "primary"]


def test_reconcile_empty_intersections_yields_blank_strings():
    route = _build_route(distances=[1.0, 2.0], intersection_points=[])
    classes = MapboxClient._reconcile_segment_road_classes(route)
    assert classes == ["", ""]


def test_reconcile_empty_route_returns_empty_list():
    assert MapboxClient._reconcile_segment_road_classes({}) == []
    assert MapboxClient._reconcile_segment_road_classes({"legs": []}) == []


def test_reconcile_handles_unsorted_intersections():
    # Intersections farklı sırada gelmiş olabilir; geometry_index'e göre
    # sıralanmalı.
    route = _build_route(
        distances=[1.0, 1.0, 1.0, 1.0, 1.0],
        intersection_points=[(3, "street"), (0, "trunk"), (1, "primary")],
    )
    classes = MapboxClient._reconcile_segment_road_classes(route)
    assert classes == ["trunk", "primary", "primary", "street", "street"]


def test_reconcile_multi_leg_offsets_geometry_index_per_leg():
    # 2 leg, her birinde 3 segment. Her leg'in intersection geometry_index'i
    # KENDİ leg içinde local — reconcile leg ofseti eklemeli.
    route = {
        "legs": [
            {
                "annotation": {"distance": [1.0, 1.0, 1.0]},
                "steps": [
                    {
                        "intersections": [
                            {
                                "geometry_index": 0,
                                "mapbox_streets_v8": {"class": "motorway"},
                            }
                        ]
                    }
                ],
            },
            {
                "annotation": {"distance": [1.0, 1.0, 1.0]},
                "steps": [
                    {
                        "intersections": [
                            {
                                "geometry_index": 0,
                                "mapbox_streets_v8": {"class": "street"},
                            }
                        ]
                    }
                ],
            },
        ]
    }
    classes = MapboxClient._reconcile_segment_road_classes(route)
    assert classes == ["motorway", "motorway", "motorway", "street", "street", "street"]


def test_reconcile_skips_intersections_without_class():
    route = _build_route(
        distances=[1.0, 1.0, 1.0],
        intersection_points=[(0, "motorway")],
    )
    # Class'sız intersection eklenirse atlanmalı, sequence bozulmamalı
    route["legs"][0]["steps"][0]["intersections"].append(
        {"geometry_index": 1, "mapbox_streets_v8": {}}  # no class
    )
    classes = MapboxClient._reconcile_segment_road_classes(route)
    assert classes == ["motorway", "motorway", "motorway"]


# ---------- Gerçek sample JSON ile smoke ----------


@pytest.mark.parametrize(
    "sample_name,min_seg,expected_top_class",
    [
        ("istanbul-ankara-otoyol-raw.json", 5000, "motorway"),
        ("maslak-kadikoy-sehir-raw.json", 500, "primary"),
        ("bursa-antalya-daglik-raw.json", 5000, "trunk"),
    ],
)
def test_real_mapbox_sample_reconciles_full_coverage(
    sample_name, min_seg, expected_top_class
):
    sample = SAMPLES_DIR / sample_name
    if not sample.exists():
        pytest.skip(f"Sample {sample_name} yok — Phase 0 probe çalıştırılmamış.")

    data = json.loads(sample.read_text(encoding="utf-8"))
    route = data["routes"][0]

    classes = MapboxClient._reconcile_segment_road_classes(route)
    expected_seg_count = sum(
        len(leg["annotation"]["distance"]) for leg in route["legs"]
    )

    assert len(classes) == expected_seg_count
    assert expected_seg_count >= min_seg, "Sample'da beklenen segment yoğunluğu yok"

    # En az %95'i dolu olmalı — kalan (_link) variant'lar veya
    # intersection'sız edge case'ler için boş kalmış olabilir
    non_empty = sum(1 for c in classes if c)
    assert non_empty / expected_seg_count >= 0.95

    # En yaygın class beklenenle uyumlu olmalı (rotanın karakteri)
    from collections import Counter

    top = Counter(classes).most_common(1)[0][0]
    # _link variant olabilir
    assert top.startswith(expected_top_class) or expected_top_class in top
