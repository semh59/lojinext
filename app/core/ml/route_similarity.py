"""Güzergah benzerlik motoru — benzer geçmiş seferleri bulur."""

from __future__ import annotations

from typing import Dict, List

import numpy as np

SIMILARITY_THRESHOLD = 0.85


def encode_route(route_analysis: Dict) -> np.ndarray:
    """Güzergahı 8 boyutlu vektöre çevir: [motorway, trunk, primary, secondary, residential, other, ascent, descent]."""
    road_keys = ["motorway", "trunk", "primary", "secondary", "residential", "other"]
    vect = []
    for k in road_keys:
        cat = route_analysis.get(k) or {}
        vect.append(float(cat.get("flat", 0) or 0))
    vect.append(float(route_analysis.get("ascent_m") or 0))
    vect.append(float(route_analysis.get("descent_m") or 0))
    return np.array(vect, dtype=np.float32)


def cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    norm_a, norm_b = np.linalg.norm(a), np.linalg.norm(b)
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return float(np.dot(a, b) / (norm_a * norm_b))


async def find_similar_trips(
    route_analysis: Dict,
    mesafe_km: float,
    limit: int = 5,
) -> List[Dict]:
    """Son 90 günden benzer güzergahlı seferleri döndürür."""
    from app.database.unit_of_work import UnitOfWork

    query_vec = encode_route(route_analysis)

    async with UnitOfWork() as uow:
        recent = await uow.sefer_repo.get_with_route_analysis(days=90, limit=200)

    similar = []
    for sefer in recent:
        if not sefer.get("route_analysis"):
            continue
        dist_diff = abs(sefer.get("mesafe_km", 0) - mesafe_km) / max(mesafe_km, 1)
        if dist_diff > 0.20:
            continue
        sim = cosine_similarity(query_vec, encode_route(sefer["route_analysis"]))
        if sim >= SIMILARITY_THRESHOLD:
            similar.append(
                {
                    "sefer_id": sefer["id"],
                    "similarity": round(sim, 3),
                    "gercek_tuketim": sefer.get("gercek_tuketim"),
                    "mesafe_km": sefer.get("mesafe_km"),
                }
            )

    return sorted(similar, key=lambda x: x["similarity"], reverse=True)[:limit]
