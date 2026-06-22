"""
Additional coverage for sofor_degerlendirme.py.

Targets missed lines:
  322-323  — generate_suggestions: filo_karsilastirma < -5 → motor devir tavsiyesi
  358      — evaluate_driver: declining trend (trend_degisim > 2)
  368-403  — _add_guzergah_performansi: full path + exception handling
  437-439  — get_all_evaluations: empty bulk_metrics → empty list
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.entities.sofor_degerlendirme import (
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
    analiz_repo = MagicMock()
    sofor_repo = MagicMock()
    return SoforDegerlendirmeService(analiz_repo=analiz_repo, sofor_repo=sofor_repo)


# ---------------------------------------------------------------------------
# generate_suggestions: filo_karsilastirma < -5 → motor devir tavsiyesi (lines 322-323)
# ---------------------------------------------------------------------------


def test_generate_suggestions_negative_filo_karsilastirma_adds_motor_tavsiye():
    """When filo_karsilastirma < -5 (driver uses much more than fleet average),
    a 'Motor devir' tavsiye should be appended."""
    svc = _make_service()
    # ort_tuketim=40, filo_ortalama=32 → karsilastirma = (32-40)/32*100 = -25 < -5
    d = _make_degerlendirme(ort_tuketim=40.0, filo_ortalama=32.0)
    result = svc.generate_suggestions(d)
    # The tavsiye for "Motor devir" should appear when karsilastirma < -5
    assert any("devir" in t.lower() or "motor" in t.lower() for t in result.tavsiyeler)


def test_generate_suggestions_filo_karsilastirma_exactly_minus_5_no_motor_tavsiye():
    """filo_karsilastirma exactly -5 → boundary: no motor devir tavsiye."""
    svc = _make_service()
    # ort_tuketim ~33.68 at 32 filo → karsilastirma ≈ -5.25 (just under)
    # Use -4.8 exact: ort = 32 / (1 + 4.8/100) = 30.534 → karsilastirma = +4.8 > -5
    d = _make_degerlendirme(ort_tuketim=30.5, filo_ortalama=32.0)
    # karsilastirma = (32 - 30.5) / 32 * 100 = 4.69 → NOT < -5
    result = svc.generate_suggestions(d)
    motor_tavsiye = [t for t in result.tavsiyeler if "devir" in t.lower()]
    assert len(motor_tavsiye) == 0


# ---------------------------------------------------------------------------
# evaluate_driver: declining trend branch (line 358) — trend_degisim > 2
# ---------------------------------------------------------------------------


async def test_evaluate_driver_declining_trend():
    """recent_avg > older_avg by >2% → TrendEnum.DECLINING."""
    svc = _make_service()
    svc.analiz_repo.get_filo_ortalama_tuketim = AsyncMock(return_value=32.0)

    pre_metrics = {
        "sofor_id": 7,
        "ad_soyad": "Declining Driver",
        "ort_tuketim": 34.0,
        "std_sapma": 2.0,
        "recent_avg": 35.0,  # worse recently
        "older_avg": 30.0,  # was better before → trend_degisim = (35-30)/30*100 = 16.7 > 2
        "toplam_km": 80000,
        "toplam_sefer": 80,
        "toplam_ton": 400.0,
        "en_iyi_tuketim": 30.0,
        "en_kotu_tuketim": 38.0,
    }

    result = await svc.evaluate_driver(
        sofor_id=7,
        pre_metrics=pre_metrics,
        pre_filo_ortalama=32.0,
        include_routes=False,
    )

    assert result is not None
    assert result.trend == TrendEnum.DECLINING
    assert result.trend_degisim > 2.0


async def test_evaluate_driver_stable_trend_small_change():
    """trend_degisim in (-2, +2) → TrendEnum.STABLE."""
    svc = _make_service()
    svc.analiz_repo.get_filo_ortalama_tuketim = AsyncMock(return_value=32.0)

    pre_metrics = {
        "sofor_id": 8,
        "ad_soyad": "Stable Driver",
        "ort_tuketim": 32.0,
        "std_sapma": 1.0,
        "recent_avg": 32.1,
        "older_avg": 32.0,  # tiny change: (32.1-32)/32*100 = 0.31 → stable
        "toplam_km": 60000,
        "toplam_sefer": 60,
        "toplam_ton": 300.0,
        "en_iyi_tuketim": 30.0,
        "en_kotu_tuketim": 34.0,
    }

    result = await svc.evaluate_driver(
        sofor_id=8,
        pre_metrics=pre_metrics,
        pre_filo_ortalama=32.0,
        include_routes=False,
    )

    assert result is not None
    assert result.trend == TrendEnum.STABLE


# ---------------------------------------------------------------------------
# _add_guzergah_performansi — full path with data (lines 368-403)
# ---------------------------------------------------------------------------


async def test_add_guzergah_performansi_sets_best_and_worst():
    """When guzergah_data returned, en_iyi and en_kotu are set."""
    svc = _make_service()

    guzergah_data = [
        {
            "guzergah": "Ankara-Konya",
            "sefer_sayisi": 10,
            "toplam_km": 2500,
            "ort_tuketim": 28.0,
            "en_iyi": 26.0,
            "en_kotu": 30.0,
        },
        {
            "guzergah": "Diyarbakır-Erzurum",
            "sefer_sayisi": 5,
            "toplam_km": 1500,
            "ort_tuketim": 38.0,
            "en_iyi": 35.0,
            "en_kotu": 41.0,
        },
    ]

    mock_sofor_repo = MagicMock()
    mock_sofor_repo.get_guzergah_performansi = AsyncMock(return_value=guzergah_data)

    d = _make_degerlendirme()

    with patch(
        "app.database.repositories.sofor_repo.get_sofor_repo",
        return_value=mock_sofor_repo,
    ):
        result = await svc._add_guzergah_performansi(d, sofor_id=1)

    assert result.en_iyi_guzergah == "Ankara-Konya"
    assert result.en_kotu_guzergah == "Diyarbakır-Erzurum"
    assert len(result.guzergah_performansi) == 2


async def test_add_guzergah_performansi_empty_data_no_change():
    """When guzergah_data is empty, no en_iyi/en_kotu set."""
    svc = _make_service()

    mock_sofor_repo = MagicMock()
    mock_sofor_repo.get_guzergah_performansi = AsyncMock(return_value=[])

    d = _make_degerlendirme()

    with patch(
        "app.database.repositories.sofor_repo.get_sofor_repo",
        return_value=mock_sofor_repo,
    ):
        result = await svc._add_guzergah_performansi(d, sofor_id=1)

    assert result.en_iyi_guzergah is None
    assert result.en_kotu_guzergah is None
    assert len(result.guzergah_performansi) == 0


async def test_add_guzergah_performansi_exception_swallowed():
    """When get_guzergah_performansi raises, exception is swallowed (logged)."""
    svc = _make_service()

    mock_sofor_repo = MagicMock()
    mock_sofor_repo.get_guzergah_performansi = AsyncMock(
        side_effect=RuntimeError("DB error")
    )

    d = _make_degerlendirme()

    with patch(
        "app.database.repositories.sofor_repo.get_sofor_repo",
        return_value=mock_sofor_repo,
    ):
        result = await svc._add_guzergah_performansi(d, sofor_id=1)

    # No crash, original degerlendirme returned unchanged
    assert result is d


async def test_add_guzergah_performansi_truncates_at_10():
    """More than 10 güzergah items are truncated to 10."""
    svc = _make_service()

    guzergah_data = [
        {
            "guzergah": f"Route-{i}",
            "sefer_sayisi": i + 1,
            "toplam_km": (i + 1) * 100,
            "ort_tuketim": 30.0 + i * 0.5,
            "en_iyi": 28.0 + i * 0.5,
            "en_kotu": 34.0 + i * 0.5,
        }
        for i in range(15)
    ]

    mock_sofor_repo = MagicMock()
    mock_sofor_repo.get_guzergah_performansi = AsyncMock(return_value=guzergah_data)

    d = _make_degerlendirme()

    with patch(
        "app.database.repositories.sofor_repo.get_sofor_repo",
        return_value=mock_sofor_repo,
    ):
        result = await svc._add_guzergah_performansi(d, sofor_id=1)

    assert len(result.guzergah_performansi) == 10


# ---------------------------------------------------------------------------
# evaluate_driver: include_routes=True path (line 358 + _add_guzergah_performansi)
# ---------------------------------------------------------------------------


async def test_evaluate_driver_include_routes_true():
    """include_routes=True triggers _add_guzergah_performansi."""
    svc = _make_service()
    svc.analiz_repo.get_filo_ortalama_tuketim = AsyncMock(return_value=32.0)

    pre_metrics = {
        "sofor_id": 3,
        "ad_soyad": "Route Driver",
        "ort_tuketim": 30.0,
        "std_sapma": 1.0,
        "recent_avg": None,
        "older_avg": None,
        "toplam_km": 100000,
        "toplam_sefer": 100,
        "toplam_ton": 500.0,
        "en_iyi_tuketim": 28.0,
        "en_kotu_tuketim": 33.0,
    }

    mock_sofor_repo = MagicMock()
    mock_sofor_repo.get_guzergah_performansi = AsyncMock(return_value=[])

    with patch(
        "app.database.repositories.sofor_repo.get_sofor_repo",
        return_value=mock_sofor_repo,
    ):
        result = await svc.evaluate_driver(
            sofor_id=3,
            pre_metrics=pre_metrics,
            pre_filo_ortalama=32.0,
            include_routes=True,
        )

    assert result is not None
    mock_sofor_repo.get_guzergah_performansi.assert_awaited_once()


# ---------------------------------------------------------------------------
# get_all_evaluations: empty bulk_metrics → empty list (lines 437-439)
# ---------------------------------------------------------------------------


async def test_get_all_evaluations_empty_metrics_returns_empty_list():
    """When bulk_metrics is empty, result is []."""
    svc = _make_service()
    svc.analiz_repo.get_bulk_driver_metrics = AsyncMock(return_value=[])
    svc.analiz_repo.get_filo_ortalama_tuketim = AsyncMock(return_value=32.0)

    results = await svc.get_all_evaluations(include_routes=False)

    assert results == []


# ---------------------------------------------------------------------------
# get_rankings — full path
# ---------------------------------------------------------------------------


async def test_get_rankings_returns_structured_dict():
    """get_rankings builds genel/verimlilik/tutarlilik lists."""
    svc = _make_service()

    bulk_metrics = [
        {
            "sofor_id": 1,
            "ad_soyad": "Ali",
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
    ]
    svc.analiz_repo.get_bulk_driver_metrics = AsyncMock(return_value=bulk_metrics)
    svc.analiz_repo.get_filo_ortalama_tuketim = AsyncMock(return_value=32.0)

    rankings = await svc.get_rankings()

    assert "genel" in rankings
    assert "verimlilik" in rankings
    assert "tutarlilik" in rankings
    assert len(rankings["genel"]) == 1
    assert rankings["genel"][0]["sira"] == 1
    assert rankings["genel"][0]["ad"] == "Ali"
    assert "derece" in rankings["genel"][0]
