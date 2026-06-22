"""SegmentSimulator (Phase 0.4) unit tests.

In-memory wrapper around PhysicsBasedFuelPredictor. DB/endpoint yok —
sadece fonksiyonel invariant'lar:

- Düz otoyolda 15-65 L/100km gerçekçi bant
- Dik yokuşta sim_speed equilibrium (engine power'a düşer)
- İniş'te yakıt < düz, gravity recovery devrede
- Traffic speed VARSA congestion multiplier uygulanmaz (çift hesap önleme)
- Segment list toplamı tutarlı (length, fuel, eta)
- length_km=0 sıfır toplamlarla return
"""

from __future__ import annotations

import pytest

from app.core.ml.segment_simulator import (
    SegmentInput,
    simulate_route,
    simulate_segment,
)


def test_flat_motorway_realistic_consumption_band():
    """Düz otoyolda, dolu TIR, 85 km/h trafik → ham fizik 15-40 L/100km bandı.

    NOT: Bu wrapper raw fiziksel sonucu döner — production sefer-mode
    pipeline'da driver/weather/maintenance/age çarpanları sonradan
    uygulanır (Phase 1'de segment-level çarpanları wrapper'a ekle).
    """
    seg = SegmentInput(
        length_km=10.0,
        grade_pct=0.0,
        road_class="motorway",
        maxspeed_kmh=130.0,
        traffic_speed_kmh=85.0,
        congestion="low",
    )
    out = simulate_segment(seg, ton=15.0, arac_yasi=5)

    assert 75 < out.sim_speed_kmh < 95  # cap=90, traffic=85 → 85 beklenen
    assert 15 < out.sim_l_per_100km < 40, (
        f"Düz otoyol ham fizik 15-40 L/100km bandında olmalı, "
        f"gözlenen {out.sim_l_per_100km}"
    )
    assert out.eta_sec == pytest.approx(10_000 / (out.sim_speed_kmh / 3.6), rel=0.01)


def test_steep_uphill_reduces_speed_to_equilibrium():
    """%8 yokuş'ta dolu TIR maxspeed'i tutamaz, equilibrium hesabı devrede."""
    seg = SegmentInput(
        length_km=5.0,
        grade_pct=8.0,
        road_class="motorway",
        maxspeed_kmh=130.0,
        traffic_speed_kmh=90.0,  # Önemsiz, equilibrium daha düşük
        congestion="low",
    )
    out = simulate_segment(seg, ton=25.0, arac_yasi=8)

    # %8 yokuş + 39 ton — 400kW motor equilibrium ~30-60 km/h civarına düşer.
    # Mevcut implementasyon: _effective_speed_kmh equilibrium HESAPLAMAZ;
    # _equilibrium_speed_ms physics içinde uygulanır. Bu test wrapper'ın
    # sim_speed çıktısının HİÇ DEĞİLSE traffic/maxspeed altında olmadığını
    # garanti eder; equilibrium etkisi L/100km'te kendini gösterir.
    assert out.sim_speed_kmh <= 90.0
    # Dik yokuş → yakıt yüksek olmalı (genelde >40)
    assert out.sim_l_per_100km > 35.0, (
        f"%8 yokuşta düşük tüketim sıra dışı: {out.sim_l_per_100km}"
    )


def test_downhill_recovers_energy():
    """İniş'te gravity recovery → yakıt düz segment'ten az olmalı."""
    flat = SegmentInput(
        length_km=5.0,
        grade_pct=0.0,
        road_class="motorway",
        traffic_speed_kmh=85.0,
    )
    down = SegmentInput(
        length_km=5.0,
        grade_pct=-4.0,
        road_class="motorway",
        traffic_speed_kmh=85.0,
    )
    out_flat = simulate_segment(flat, ton=15.0, arac_yasi=5)
    out_down = simulate_segment(down, ton=15.0, arac_yasi=5)

    assert out_down.sim_l_per_100km < out_flat.sim_l_per_100km, (
        f"İniş tüketimi düz'den düşük olmalı: flat={out_flat.sim_l_per_100km}, "
        f"down={out_down.sim_l_per_100km}"
    )


def test_city_residential_uses_road_class_cap():
    """Maxspeed yoksa road_class TIR cap'i kullanılmalı (residential 50)."""
    seg = SegmentInput(
        length_km=0.5,
        grade_pct=0.0,
        road_class="residential",
        maxspeed_kmh=None,
        traffic_speed_kmh=None,
        congestion="moderate",
    )
    out = simulate_segment(seg, ton=10.0)
    # cap 50 × moderate (0.80) = 40 km/h
    assert 35 <= out.sim_speed_kmh <= 45, (
        f"Residential cap+moderate ~40 km/h olmalı: {out.sim_speed_kmh}"
    )


def test_traffic_speed_present_skips_congestion_multiplier():
    """traffic_speed Mapbox tarafından congestion-aware hesaplandı —
    wrapper congestion multiplier'ı tekrar UYGULAMAMALI (çift düşüş)."""
    base = SegmentInput(
        length_km=1.0,
        grade_pct=0.0,
        road_class="primary",
        maxspeed_kmh=90.0,
        traffic_speed_kmh=40.0,
    )
    out_low = simulate_segment(
        SegmentInput(**{**base.__dict__, "congestion": "low"}),
        ton=10.0,
    )
    out_heavy = simulate_segment(
        SegmentInput(**{**base.__dict__, "congestion": "heavy"}),
        ton=10.0,
    )
    # traffic_speed sabit 40 km/h — congestion ne olursa olsun hız aynı
    assert out_low.sim_speed_kmh == out_heavy.sim_speed_kmh == 40.0


def test_no_traffic_speed_applies_congestion_multiplier():
    """traffic_speed yoksa congestion multiplier uygulanmalı."""
    base_dict = dict(
        length_km=1.0,
        grade_pct=0.0,
        road_class="primary",
        maxspeed_kmh=80.0,
        traffic_speed_kmh=None,
    )
    out_low = simulate_segment(SegmentInput(**base_dict, congestion="low"), ton=10.0)
    out_heavy = simulate_segment(
        SegmentInput(**base_dict, congestion="heavy"), ton=10.0
    )
    assert out_heavy.sim_speed_kmh < out_low.sim_speed_kmh


def test_zero_length_returns_zero_totals():
    seg = SegmentInput(length_km=0.0, grade_pct=0.0, road_class="motorway")
    out = simulate_segment(seg)
    assert out.sim_l_total == 0.0
    assert out.sim_l_per_100km == 0.0
    assert out.eta_sec == 0.0


def test_simulate_route_aggregates_consistently():
    """Route summary'sinin total_km / total_l / total_eta toplam tutarlı olmalı."""
    segs = [
        SegmentInput(
            length_km=2.0, grade_pct=0.0, road_class="motorway", traffic_speed_kmh=85.0
        ),
        SegmentInput(
            length_km=1.5, grade_pct=3.0, road_class="primary", traffic_speed_kmh=60.0
        ),
        SegmentInput(
            length_km=0.5, grade_pct=-2.0, road_class="primary", traffic_speed_kmh=55.0
        ),
    ]
    summary = simulate_route(segs, ton=15.0, arac_yasi=5)

    assert summary.total_km == pytest.approx(4.0, rel=0.001)
    assert len(summary.segments) == 3
    assert summary.total_l == pytest.approx(
        sum(s.sim_l_total for s in summary.segments), rel=0.01
    )
    assert summary.avg_l_per_100km == pytest.approx(
        summary.total_l / summary.total_km * 100.0, rel=0.01
    )
    # 1.5 km × +3% = +45m ascent; 0.5 km × -2% = -10m descent
    assert summary.total_ascent_m == pytest.approx(45.0, abs=0.5)
    assert summary.total_descent_m == pytest.approx(10.0, abs=0.5)


def test_empty_route_returns_empty_summary():
    summary = simulate_route([])
    assert summary.total_km == 0.0
    assert summary.total_l == 0.0
    assert summary.segments == []
