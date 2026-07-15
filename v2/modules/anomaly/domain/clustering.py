"""Faz 8 — anomali kümeleme (DBSCAN).

Tekrarlayan anomali desenlerini ('pattern') yüzeye çıkarır. Saf fonksiyon:
DB/LLM bağımlılığı yok; endpoint ve günlük task çağırır.
"""

from __future__ import annotations

from collections import Counter
from typing import Any

_TIP_CODES = {"tuketim": 0, "maliyet": 1, "sefer": 2}
_KAYNAK_CODES = {"arac": 0, "sofor": 1, "sefer": 2, "yakit": 3}
_SEVERITY_ORD = {"low": 0, "medium": 1, "high": 2, "critical": 3}


def _feature_row(a: dict) -> list[float]:
    # Kategorik kodlar deseni belirler (aynı tip+kaynak+severity = aynı desen);
    # sapma_yuzde /50 ile kategorik kodlarla kıyaslanabilir küçük ölçeğe çekilir
    # (25% → 0.5). StandardScaler KULLANILMAZ: tek-varyanslı kolonu büyütüp
    # benzer anomalileri eps dışına itiyordu.
    return [
        float(_TIP_CODES.get(str(a.get("tip")), 9)),
        float(_KAYNAK_CODES.get(str(a.get("kaynak_tip")), 9)),
        float(_SEVERITY_ORD.get(str(a.get("severity")), 0)),
        float(a.get("sapma_yuzde") or 0.0) / 50.0,
    ]


def _label(members: list[dict]) -> str:
    tip = Counter(str(m.get("tip")) for m in members).most_common(1)[0][0]
    sev = Counter(str(m.get("severity")) for m in members).most_common(1)[0][0]
    kaynak = Counter(str(m.get("kaynak_tip")) for m in members).most_common(1)[0][0]
    return f"{len(members)} adet {sev} {tip} anomalisi ({kaynak} kaynaklı)"


def cluster_anomalies(
    rows: list[dict], *, eps: float = 0.6, min_samples: int = 2
) -> list[dict[str, Any]]:
    """Anomali dict listesini DBSCAN ile kümeler.

    Returns: küme listesi (büyükten küçüğe). Her küme:
        {cluster_id, size, dominant_tip, dominant_kaynak_tip,
         severity_dagilim, member_ids, label}
    Noise (label=-1) atılır; <min_samples gruplar küme sayılmaz.
    """
    if len(rows) < min_samples:
        return []
    import numpy as np
    from sklearn.cluster import DBSCAN

    X = np.array([_feature_row(a) for a in rows], dtype=float)
    labels = DBSCAN(eps=eps, min_samples=min_samples).fit_predict(X)

    groups: dict[int, list[dict]] = {}
    for a, lbl in zip(rows, labels):
        if lbl == -1:
            continue
        groups.setdefault(int(lbl), []).append(a)

    clusters: list[dict[str, Any]] = []
    for cid, members in groups.items():
        sev_dist = dict(Counter(str(m.get("severity")) for m in members))
        clusters.append(
            {
                "cluster_id": cid,
                "size": len(members),
                "dominant_tip": Counter(str(m.get("tip")) for m in members).most_common(
                    1
                )[0][0],
                "dominant_kaynak_tip": Counter(
                    str(m.get("kaynak_tip")) for m in members
                ).most_common(1)[0][0],
                "severity_dagilim": sev_dist,
                "member_ids": [m.get("id") for m in members],
                "label": _label(members),
            }
        )
    clusters.sort(key=lambda c: c["size"], reverse=True)
    return clusters
