"""
Unit tests for sofor_degerlendirme — pure logic, no DB.
Targeting ≥80% coverage.
"""

import math

import pytest

from app.core.entities.sofor_degerlendirme import (
    DereceEnum,
    GuzergahPerformans,
    SoforDegerlendirme,
    SoforDegerlendirmeService,
    TrendEnum,
)

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_degerlendirme(**kwargs) -> SoforDegerlendirme:
    defaults = dict(
        sofor_id=1,
        ad_soyad="Test Şoför",
        verimlilik_puani=50.0,
        tutarlilik_puani=50.0,
        deneyim_puani=50.0,
        trend_puani=50.0,
    )
    defaults.update(kwargs)
    return SoforDegerlendirme(**defaults)


def _make_service():
    analiz_repo = pytest.importorskip("unittest.mock").MagicMock()
    sofor_repo = pytest.importorskip("unittest.mock").MagicMock()
    return SoforDegerlendirmeService(analiz_repo=analiz_repo, sofor_repo=sofor_repo)


# ---------------------------------------------------------------------------
# DereceEnum / genel_puan / derece / yildiz
# ---------------------------------------------------------------------------


def test_genel_puan_weighted_formula():
    d = _make_degerlendirme(
        verimlilik_puani=80.0,
        tutarlilik_puani=60.0,
        deneyim_puani=40.0,
        trend_puani=20.0,
    )
    expected = 80 * 0.40 + 60 * 0.25 + 40 * 0.20 + 20 * 0.15
    assert d.genel_puan == pytest.approx(expected, abs=0.1)


def test_derece_A_at_90():
    d = _make_degerlendirme(
        verimlilik_puani=100.0,
        tutarlilik_puani=100.0,
        deneyim_puani=100.0,
        trend_puani=100.0,
    )
    assert d.derece == DereceEnum.A
    assert d.genel_puan == 100.0


def test_derece_B_at_75():
    # Construct a puan close to 76
    d = _make_degerlendirme(
        verimlilik_puani=76.0,
        tutarlilik_puani=76.0,
        deneyim_puani=76.0,
        trend_puani=76.0,
    )
    assert d.derece == DereceEnum.B


def test_derece_C_at_60():
    d = _make_degerlendirme(
        verimlilik_puani=60.0,
        tutarlilik_puani=60.0,
        deneyim_puani=60.0,
        trend_puani=60.0,
    )
    assert d.derece == DereceEnum.C


def test_derece_D_at_40():
    d = _make_degerlendirme(
        verimlilik_puani=40.0,
        tutarlilik_puani=40.0,
        deneyim_puani=40.0,
        trend_puani=40.0,
    )
    assert d.derece == DereceEnum.D


def test_derece_F_below_40():
    d = _make_degerlendirme(
        verimlilik_puani=0.0,
        tutarlilik_puani=0.0,
        deneyim_puani=0.0,
        trend_puani=0.0,
    )
    assert d.derece == DereceEnum.F
    assert d.genel_puan == 0.0


def test_yildiz_5_at_85():
    d = _make_degerlendirme(
        verimlilik_puani=100.0,
        tutarlilik_puani=100.0,
        deneyim_puani=100.0,
        trend_puani=100.0,
    )
    assert d.yildiz == 5


def test_yildiz_4_at_70():
    d = _make_degerlendirme(
        verimlilik_puani=70.0,
        tutarlilik_puani=70.0,
        deneyim_puani=70.0,
        trend_puani=70.0,
    )
    assert d.yildiz == 4


def test_yildiz_3_at_55():
    d = _make_degerlendirme(
        verimlilik_puani=55.0,
        tutarlilik_puani=55.0,
        deneyim_puani=55.0,
        trend_puani=55.0,
    )
    assert d.yildiz == 3


def test_yildiz_2_at_40():
    d = _make_degerlendirme(
        verimlilik_puani=40.0,
        tutarlilik_puani=40.0,
        deneyim_puani=40.0,
        trend_puani=40.0,
    )
    assert d.yildiz == 2


def test_yildiz_1_below_40():
    d = _make_degerlendirme(
        verimlilik_puani=0.0,
        tutarlilik_puani=0.0,
        deneyim_puani=0.0,
        trend_puani=0.0,
    )
    assert d.yildiz == 1


def test_filo_karsilastirma_positive_when_below_average():
    # Driver uses 28 L/100km, fleet avg 32 → +12.5% better
    d = _make_degerlendirme(ort_tuketim=28.0, filo_ortalama=32.0)
    expected = round(((32.0 - 28.0) / 32.0) * 100, 1)
    assert d.filo_karsilastirma == pytest.approx(expected, abs=0.01)


def test_filo_karsilastirma_zero_when_filo_zero():
    d = _make_degerlendirme(filo_ortalama=0.0, ort_tuketim=30.0)
    assert d.filo_karsilastirma == 0.0


# ---------------------------------------------------------------------------
# Service: calculate_verimlilik_puan
# ---------------------------------------------------------------------------


def test_verimlilik_puan_equal_to_average_is_50():
    svc = _make_service()
    assert svc.calculate_verimlilik_puan(32.0, 32.0) == 50.0


def test_verimlilik_puan_much_better_than_average_caps_at_100():
    svc = _make_service()
    # Driver uses 20, fleet 32 → fark=37.5% → 50 + 37.5*5 = 237.5 → clamped 100
    result = svc.calculate_verimlilik_puan(20.0, 32.0)
    assert result == 100.0


def test_verimlilik_puan_much_worse_than_average_floors_at_0():
    svc = _make_service()
    # Driver uses 50, fleet 32 → fark=-56.25% → 50 - 281 = floor 0
    result = svc.calculate_verimlilik_puan(50.0, 32.0)
    assert result == 0.0


def test_verimlilik_puan_zero_filo_returns_50():
    svc = _make_service()
    assert svc.calculate_verimlilik_puan(30.0, 0.0) == 50.0


# ---------------------------------------------------------------------------
# Service: calculate_tutarlilik_puan
# ---------------------------------------------------------------------------


def test_tutarlilik_puan_zero_std_is_100():
    svc = _make_service()
    assert svc.calculate_tutarlilik_puan(0.0) == 100.0


def test_tutarlilik_puan_std_2_is_80():
    svc = _make_service()
    assert svc.calculate_tutarlilik_puan(2.0) == 80.0


def test_tutarlilik_puan_std_5_is_50():
    svc = _make_service()
    assert svc.calculate_tutarlilik_puan(5.0) == 50.0


def test_tutarlilik_puan_std_10_floors_at_0():
    svc = _make_service()
    assert svc.calculate_tutarlilik_puan(10.0) == 0.0


def test_tutarlilik_puan_high_std_floors_at_0():
    svc = _make_service()
    assert svc.calculate_tutarlilik_puan(20.0) == 0.0


# ---------------------------------------------------------------------------
# Service: calculate_deneyim_puan
# ---------------------------------------------------------------------------


def test_deneyim_puan_zero_km_zero_sefer():
    svc = _make_service()
    result = svc.calculate_deneyim_puan(0, 0)
    # log10(1) = 0 for both
    assert result == 0.0


def test_deneyim_puan_large_km_and_sefer_caps():
    svc = _make_service()
    # 1 000 000 km, 1000 sefer → both caps hit
    km_puan = min(50, math.log10(1_000_000) * 10)
    sefer_puan = min(50, math.log10(1000) * 15)
    expected = round(km_puan + sefer_puan, 1)
    result = svc.calculate_deneyim_puan(1_000_000, 1000)
    assert result == pytest.approx(expected, abs=0.1)


def test_deneyim_puan_moderate_values():
    svc = _make_service()
    result = svc.calculate_deneyim_puan(100_000, 100)
    assert 0 < result <= 100


# ---------------------------------------------------------------------------
# Service: calculate_trend_puan
# ---------------------------------------------------------------------------


def test_trend_puan_zero_change_is_50():
    svc = _make_service()
    assert svc.calculate_trend_puan(0.0) == 50.0


def test_trend_puan_improving_negative_change_above_50():
    svc = _make_service()
    # trend_degisim = -5 (improving) → 50 - (-5 * 10) = 100
    result = svc.calculate_trend_puan(-5.0)
    assert result == 100.0


def test_trend_puan_declining_positive_change_below_50():
    svc = _make_service()
    # trend_degisim = +3 → 50 - 30 = 20
    result = svc.calculate_trend_puan(3.0)
    assert result == 20.0


def test_trend_puan_floors_at_0():
    svc = _make_service()
    result = svc.calculate_trend_puan(10.0)
    assert result == 0.0


# ---------------------------------------------------------------------------
# Service: generate_suggestions
# ---------------------------------------------------------------------------


def test_generate_suggestions_high_efficiency_adds_guclu():
    svc = _make_service()
    d = _make_degerlendirme(
        verimlilik_puani=80.0, tutarlilik_puani=80.0, deneyim_puani=80.0
    )
    d.trend = TrendEnum.IMPROVING
    result = svc.generate_suggestions(d)
    assert any("verimli" in g.lower() for g in result.guclu_yanlar)


def test_generate_suggestions_low_efficiency_adds_tavsiye():
    svc = _make_service()
    d = _make_degerlendirme(verimlilik_puani=30.0)
    result = svc.generate_suggestions(d)
    assert any(
        "yakıt" in t.lower() or "ekonomik" in t.lower() for t in result.tavsiyeler
    )


def test_generate_suggestions_low_tutarlilik_adds_iyilestirme():
    svc = _make_service()
    d = _make_degerlendirme(tutarlilik_puani=30.0)
    result = svc.generate_suggestions(d)
    assert any(
        "değişkenlik" in i.lower() or "tüketim" in i.lower()
        for i in result.iyilestirme_alanlari
    )


def test_generate_suggestions_declining_trend():
    svc = _make_service()
    d = _make_degerlendirme()
    d.trend = TrendEnum.DECLINING
    result = svc.generate_suggestions(d)
    assert any("düşüş" in i.lower() for i in result.iyilestirme_alanlari)


def test_generate_suggestions_best_and_worst_route():
    svc = _make_service()
    d = _make_degerlendirme()
    d.en_iyi_guzergah = "Ankara-İstanbul"
    d.en_kotu_guzergah = "Diyarbakır-Erzurum"
    result = svc.generate_suggestions(d)
    assert any("Ankara" in g for g in result.guclu_yanlar)
    assert any("Diyarbakır" in t for t in result.tavsiyeler)


def test_generate_suggestions_low_general_score_adds_bakim():
    svc = _make_service()
    d = _make_degerlendirme(
        verimlilik_puani=0.0,
        tutarlilik_puani=0.0,
        deneyim_puani=0.0,
        trend_puani=0.0,
    )
    result = svc.generate_suggestions(d)
    assert any("bakım" in t.lower() for t in result.tavsiyeler)


# ---------------------------------------------------------------------------
# Service: evaluate_driver with pre_metrics
# ---------------------------------------------------------------------------


async def test_evaluate_driver_with_pre_metrics():
    from unittest.mock import AsyncMock

    svc = _make_service()
    svc.analiz_repo.get_filo_ortalama_tuketim = AsyncMock(return_value=32.0)

    pre_metrics = {
        "sofor_id": 42,
        "ad_soyad": "Ali Yılmaz",
        "ort_tuketim": 30.0,
        "std_sapma": 2.0,
        "recent_avg": 29.0,
        "older_avg": 31.0,
        "toplam_km": 100000,
        "toplam_sefer": 100,
        "toplam_ton": 500.0,
        "en_iyi_tuketim": 28.0,
        "en_kotu_tuketim": 35.0,
    }

    result = await svc.evaluate_driver(
        sofor_id=42,
        pre_metrics=pre_metrics,
        pre_filo_ortalama=32.0,
        include_routes=False,
    )

    assert result is not None
    assert result.ad_soyad == "Ali Yılmaz"
    assert result.genel_puan > 0
    assert result.trend == TrendEnum.IMPROVING


async def test_evaluate_driver_no_metrics_returns_none():
    from unittest.mock import AsyncMock

    svc = _make_service()
    svc.analiz_repo.get_bulk_driver_metrics = AsyncMock(return_value=[])

    result = await svc.evaluate_driver(sofor_id=99)
    assert result is None


async def test_evaluate_driver_stable_trend_when_no_recent():
    from unittest.mock import AsyncMock

    svc = _make_service()
    svc.analiz_repo.get_filo_ortalama_tuketim = AsyncMock(return_value=32.0)

    pre_metrics = {
        "sofor_id": 1,
        "ad_soyad": "Test",
        "ort_tuketim": 32.0,
        "std_sapma": 1.0,
        "recent_avg": None,
        "older_avg": None,
        "toplam_km": 50000,
        "toplam_sefer": 50,
        "toplam_ton": 200.0,
        "en_iyi_tuketim": 30.0,
        "en_kotu_tuketim": 34.0,
    }

    result = await svc.evaluate_driver(
        sofor_id=1,
        pre_metrics=pre_metrics,
        pre_filo_ortalama=32.0,
        include_routes=False,
    )

    assert result is not None
    assert result.trend == TrendEnum.STABLE


# ---------------------------------------------------------------------------
# SoforDegerlendirmeService __init__ validation
# ---------------------------------------------------------------------------


def test_service_init_raises_if_repos_none():
    with pytest.raises(ValueError, match="requires"):
        SoforDegerlendirmeService(analiz_repo=None, sofor_repo=None)


# ---------------------------------------------------------------------------
# GuzergahPerformans model
# ---------------------------------------------------------------------------


def test_guzergah_performans_model():
    g = GuzergahPerformans(
        guzergah="Ankara-Konya",
        sefer_sayisi=10,
        toplam_km=500,
        ort_tuketim=30.5,
        en_iyi=28.0,
        en_kotu=34.0,
    )
    assert g.guzergah == "Ankara-Konya"
    assert g.sefer_sayisi == 10
    assert g.en_iyi == 28.0


def test_guzergah_performans_optional_fields_none():
    g = GuzergahPerformans(
        guzergah="X-Y",
        sefer_sayisi=1,
        toplam_km=100,
        ort_tuketim=32.0,
    )
    assert g.en_iyi is None
    assert g.en_kotu is None


# ---------------------------------------------------------------------------
# get_all_evaluations
# ---------------------------------------------------------------------------


async def test_get_all_evaluations_sorted_by_puan():
    from unittest.mock import AsyncMock

    svc = _make_service()

    bulk_metrics = [
        {
            "sofor_id": 1,
            "ad_soyad": "A",
            "ort_tuketim": 28.0,
            "std_sapma": 1.0,
            "recent_avg": None,
            "older_avg": None,
            "toplam_km": 200000,
            "toplam_sefer": 200,
            "toplam_ton": 800.0,
            "en_iyi_tuketim": 26.0,
            "en_kotu_tuketim": 30.0,
        },
        {
            "sofor_id": 2,
            "ad_soyad": "B",
            "ort_tuketim": 40.0,
            "std_sapma": 5.0,
            "recent_avg": None,
            "older_avg": None,
            "toplam_km": 10000,
            "toplam_sefer": 10,
            "toplam_ton": 50.0,
            "en_iyi_tuketim": 38.0,
            "en_kotu_tuketim": 44.0,
        },
    ]

    svc.analiz_repo.get_bulk_driver_metrics = AsyncMock(return_value=bulk_metrics)
    svc.analiz_repo.get_filo_ortalama_tuketim = AsyncMock(return_value=32.0)

    results = await svc.get_all_evaluations(include_routes=False)

    assert len(results) == 2
    # Sorted descending by genel_puan
    assert results[0].genel_puan >= results[1].genel_puan
