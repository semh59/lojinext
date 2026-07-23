"""Segment-bazlı tractive yakıt motoru testleri (fiziksel doğruluk)."""

import pytest

from v2.modules.prediction_ml.domain.physics_fuel_predictor import (
    PhysicsBasedFuelPredictor,
)

pytestmark = pytest.mark.unit


def _p():
    return PhysicsBasedFuelPredictor()


def test_no_cross_segment_netting_vs_aggregate():
    # Büyük inişli rota: aggregate (predict_granular) inişi route geneline kredi
    # eder → düşük; tractive segment-floor'lu → daha YÜKSEK (netleştirme yok).
    p = _p()
    # 10km düz + 5km %6 iniş (delta_h negatif): (dist_m, v_ms, delta_h)
    segs = [(10000.0, 22.0, 0.0), (5000.0, 22.0, -300.0)]
    aggr = p.predict_granular(list(segs), load_ton=20.0)
    trac = p.predict_segment_tractive(
        list(segs), total_mass_kg=8000 + 6500 + 20000, arac_yasi=5
    )
    assert trac.consumption_l_100km > aggr.consumption_l_100km


def test_grade_clamped_to_max():
    # %20 eğimli segment → %9'a clamp (SRTM gürültüsü). Clamp'siz çok yüksek olurdu.
    p = _p()
    m = 8000 + 6500 + 20000
    steep = p.predict_segment_tractive(
        [(1000.0, 15.0, 200.0)], total_mass_kg=m, arac_yasi=5
    )  # %20
    capped = p.predict_segment_tractive(
        [(1000.0, 15.0, 90.0)], total_mass_kg=m, arac_yasi=5
    )  # %9
    assert steep.consumption_l_100km == pytest.approx(
        capped.consumption_l_100km, rel=1e-3
    )


def test_parasitic_base_adds_time_based_fuel(monkeypatch):
    # Parazit yük zaman-bazlı base ekler; etkisi YAVAŞ rotada (daha çok dk/km)
    # hızlı rotadan büyük olmalı. (Mutlak slow>fast değil — drag ∝v² hızlıda
    # domine eder; parazit etkisini KW toggle ile izole et.)
    from app.config import settings as s

    p = _p()
    m = 8000 + 6500 + 20000
    seg_slow = [(10000.0, 8.0, 0.0)]  # 28.8 km/h
    seg_fast = [(10000.0, 25.0, 0.0)]  # 90 km/h

    monkeypatch.setattr(s, "PHYSICS_PARASITIC_KW", 0.0)
    slow0 = p.predict_segment_tractive(seg_slow, total_mass_kg=m).consumption_l_100km
    fast0 = p.predict_segment_tractive(seg_fast, total_mass_kg=m).consumption_l_100km
    monkeypatch.setattr(s, "PHYSICS_PARASITIC_KW", 6.0)
    slow6 = p.predict_segment_tractive(seg_slow, total_mass_kg=m).consumption_l_100km
    fast6 = p.predict_segment_tractive(seg_fast, total_mass_kg=m).consumption_l_100km

    assert slow6 > slow0  # parazit yakıt ekler
    assert (slow6 - slow0) > (fast6 - fast0)  # yavaş rotada etki daha büyük


def test_predict_granular_delegates_when_flag_on(monkeypatch):
    from app.config import settings as s

    monkeypatch.setattr(s, "USE_SEGMENT_TRACTIVE_MODEL", True)
    p = _p()
    segs = [(10000.0, 22.0, 0.0), (5000.0, 22.0, -300.0)]
    out = p.predict_granular(list(segs), load_ton=20.0, arac_yasi=5)
    assert out.factors_used.get("model") == "tractive"


def test_predict_granular_legacy_when_flag_off(monkeypatch):
    from app.config import settings as s

    monkeypatch.setattr(s, "USE_SEGMENT_TRACTIVE_MODEL", False)
    p = _p()
    out = p.predict_granular([(10000.0, 22.0, 0.0)], load_ton=20.0, arac_yasi=5)
    assert out.factors_used.get("model") != "tractive"


def test_steep_descent_propulsion_zero_floor():
    # Dik iniş: F_trac<0 → propulsion 0, yalnız aksesuar tabanı → düşük ama pozitif.
    p = _p()
    m = 8000 + 6500 + 20000
    out = p.predict_segment_tractive(
        [(2000.0, 20.0, -160.0)], total_mass_kg=m, arac_yasi=5
    )  # %8 iniş
    assert 0.0 < out.consumption_l_100km < 12.0


def test_payload_slope_preserved():
    # Düz yol; 12t → 24t yük artışı L/100km'yi yaklaşık 0.473×12≈5.7 artırmalı.
    p = _p()
    flat = [(50000.0, 22.0, 0.0)]
    c12 = p.predict_segment_tractive(
        flat, total_mass_kg=8000 + 6500 + 12000, arac_yasi=5
    ).consumption_l_100km
    c24 = p.predict_segment_tractive(
        flat, total_mass_kg=8000 + 6500 + 24000, arac_yasi=5
    ).consumption_l_100km
    slope = (c24 - c12) / 12.0
    assert 0.40 <= slope <= 0.55
