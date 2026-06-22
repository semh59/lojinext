"""segment_simulator → predict_granular flag delegasyonu (uçtan uca)."""

import pytest

from app.core.ml.segment_simulator import SegmentInput, simulate_route

pytestmark = pytest.mark.unit


def _route():
    # Düz + iniş + tırmanış karışık sentetik rota
    return [
        SegmentInput(length_km=10.0, grade_pct=0.0, road_class="motorway"),
        SegmentInput(length_km=5.0, grade_pct=-6.0, road_class="motorway"),
        SegmentInput(length_km=5.0, grade_pct=4.0, road_class="primary"),
    ]


def test_simulate_route_uses_tractive_when_flag_on(monkeypatch):
    from app.config import settings as s

    monkeypatch.setattr(s, "USE_SEGMENT_TRACTIVE_MODEL", False)
    legacy = simulate_route(_route(), ton=20.0, arac_yasi=5)

    monkeypatch.setattr(s, "USE_SEGMENT_TRACTIVE_MODEL", True)
    tractive = simulate_route(_route(), ton=20.0, arac_yasi=5)

    # İki motor farklı sonuç vermeli (delegasyon aktif); tractive iniş kredisi
    # vermediği için toplam yakıt legacy'den yüksek olmalı.
    assert tractive.total_l != pytest.approx(legacy.total_l, rel=1e-3)
    assert tractive.total_l > legacy.total_l
    assert tractive.avg_l_per_100km > 0
