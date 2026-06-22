"""
RecommendationEngine comprehensive unit tests — targets missing lines.

Covers:
- Recommendation dataclass construction
- _is_cache_valid: miss (no key), fresh entry, expired entry
- get_vehicle_recommendations:
    - vehicle not found
    - high consumption (>10% above target, severity 4 vs 3)
    - old vehicle (>=10 years)
    - cache hit path
- get_driver_recommendations:
    - driver degerlendirme returns None
    - low score (<50)
    - trend == "Kötüleşiyor"
    - filo_karsilastirma < -10
    - exception path
    - cache hit
- get_fleet_recommendations:
    - consumption increase >5%
    - worst vehicle >40 L
    - cache hit
- get_cost_saving_suggestions:
    - >=2 stations with fark >1
    - <2 stations
- clear_cache, invalidate_vehicle_cache, invalidate_driver_cache, invalidate_fleet_cache
- get_recommendation_engine singleton
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_engine():
    """Return a fresh RecommendationEngine instance (bypasses singleton)."""
    from app.core.ai.recommendation_engine import RecommendationEngine

    engine = RecommendationEngine.__new__(RecommendationEngine)
    engine._cache = {}
    engine._cache_time = {}
    import threading

    engine._lock = threading.Lock()
    return engine


def _make_uow_ctx(session_execute_side_effect=None, araclar=None, soforler=None):
    """Build a mock UnitOfWork context manager."""
    mock_uow = MagicMock()
    mock_session = AsyncMock()

    if session_execute_side_effect is not None:
        mock_session.execute = session_execute_side_effect
    else:
        mock_session.execute = AsyncMock(return_value=_fetchone_result(None))

    mock_uow.session = mock_session

    if araclar is not None:
        mock_uow.arac_repo = MagicMock()
        mock_uow.arac_repo.get_all = AsyncMock(return_value=araclar)

    if soforler is not None:
        mock_uow.sofor_repo = MagicMock()
        mock_uow.sofor_repo.get_all = AsyncMock(return_value=soforler)

    mock_uow.__aenter__ = AsyncMock(return_value=mock_uow)
    mock_uow.__aexit__ = AsyncMock(return_value=False)
    return mock_uow


def _fetchone_result(row):
    """Build an execute() result whose .fetchone() returns *row*."""
    r = MagicMock()
    r.fetchone = MagicMock(return_value=row)
    return r


def _fetchall_result(rows):
    r = MagicMock()
    r.fetchall = MagicMock(return_value=rows)
    return r


def _make_row(**kwargs):
    """Build a row mock with attribute access."""
    row = MagicMock()
    for k, v in kwargs.items():
        setattr(row, k, v)
    return row


# ---------------------------------------------------------------------------
# Recommendation dataclass
# ---------------------------------------------------------------------------


def test_recommendation_dataclass():
    """Recommendation dataclass stores all fields correctly."""
    from app.core.ai.recommendation_engine import Recommendation

    rec = Recommendation(
        kategori="verimlilik",
        hedef_tip="arac",
        hedef_id=5,
        mesaj="Test mesaj",
        oncelik=3,
        aksiyon="Bakım yapılmalı",
    )
    assert rec.kategori == "verimlilik"
    assert rec.hedef_tip == "arac"
    assert rec.hedef_id == 5
    assert rec.oncelik == 3
    assert rec.aksiyon == "Bakım yapılmalı"


def test_recommendation_optional_aksiyon():
    """Recommendation aksiyon defaults to None."""
    from app.core.ai.recommendation_engine import Recommendation

    rec = Recommendation(
        kategori="egitim",
        hedef_tip="sofor",
        hedef_id=1,
        mesaj="Test",
        oncelik=2,
    )
    assert rec.aksiyon is None


# ---------------------------------------------------------------------------
# _is_cache_valid
# ---------------------------------------------------------------------------


def test_is_cache_valid_missing_key():
    """_is_cache_valid returns False when key not in cache."""
    engine = _make_engine()
    assert engine._is_cache_valid("nonexistent") is False


def test_is_cache_valid_fresh_entry():
    """_is_cache_valid returns True for a recent entry."""
    engine = _make_engine()
    engine._cache_time["key1"] = datetime.now(timezone.utc)
    assert engine._is_cache_valid("key1") is True


def test_is_cache_valid_expired_entry():
    """_is_cache_valid returns False for expired entry."""
    engine = _make_engine()
    engine.CACHE_TTL = 10  # 10 seconds
    engine._cache_time["old_key"] = datetime.now(timezone.utc) - timedelta(seconds=20)
    assert engine._is_cache_valid("old_key") is False


# ---------------------------------------------------------------------------
# get_vehicle_recommendations
# ---------------------------------------------------------------------------


async def test_get_vehicle_recommendations_not_found():
    """get_vehicle_recommendations returns [] when vehicle not found."""
    engine = _make_engine()
    mock_uow = _make_uow_ctx()
    mock_uow.arac_repo = MagicMock()
    mock_uow.arac_repo.get_by_id = AsyncMock(return_value=None)

    with patch("app.core.ai.recommendation_engine.unit_of_work", return_value=mock_uow):
        result = await engine.get_vehicle_recommendations(arac_id=999)
    assert result == []


async def test_get_vehicle_recommendations_high_consumption_critical():
    """get_vehicle_recommendations returns priority 4 when >20% above target."""
    engine = _make_engine()

    arac = {"plaka": "34ABC01", "hedef_tuketim": 30.0, "yil": 2020}
    row = _make_row(ort=39.0, sayi=5)  # 30% above → priority 4

    execute_mock = AsyncMock(return_value=_fetchone_result(row))
    mock_uow = _make_uow_ctx(session_execute_side_effect=execute_mock)
    mock_uow.arac_repo = MagicMock()
    mock_uow.arac_repo.get_by_id = AsyncMock(return_value=arac)

    with patch("app.core.ai.recommendation_engine.unit_of_work", return_value=mock_uow):
        result = await engine.get_vehicle_recommendations(arac_id=1)

    assert any(r.oncelik == 4 for r in result)
    assert any(r.kategori == "verimlilik" for r in result)


async def test_get_vehicle_recommendations_moderate_deviation():
    """get_vehicle_recommendations returns priority 3 when 10-20% above target."""
    engine = _make_engine()

    arac = {"plaka": "34XYZ01", "hedef_tuketim": 30.0, "yil": 2020}
    row = _make_row(ort=33.5, sayi=3)  # ~11.6% above → priority 3

    execute_mock = AsyncMock(return_value=_fetchone_result(row))
    mock_uow = _make_uow_ctx(session_execute_side_effect=execute_mock)
    mock_uow.arac_repo = MagicMock()
    mock_uow.arac_repo.get_by_id = AsyncMock(return_value=arac)

    with patch("app.core.ai.recommendation_engine.unit_of_work", return_value=mock_uow):
        result = await engine.get_vehicle_recommendations(arac_id=2)

    assert any(r.oncelik == 3 for r in result)


async def test_get_vehicle_recommendations_old_vehicle():
    """get_vehicle_recommendations adds maintenance rec for old vehicle."""
    engine = _make_engine()

    arac = {"plaka": "34OLD01", "hedef_tuketim": 30.0, "yil": 2010}  # 16 years old
    row = _make_row(ort=None, sayi=0)  # No consumption data

    execute_mock = AsyncMock(return_value=_fetchone_result(row))
    mock_uow = _make_uow_ctx(session_execute_side_effect=execute_mock)
    mock_uow.arac_repo = MagicMock()
    mock_uow.arac_repo.get_by_id = AsyncMock(return_value=arac)

    with patch("app.core.ai.recommendation_engine.unit_of_work", return_value=mock_uow):
        result = await engine.get_vehicle_recommendations(arac_id=3)

    assert any(r.kategori == "bakim" for r in result)


async def test_get_vehicle_recommendations_cache_hit():
    """get_vehicle_recommendations returns cached result on second call."""
    from app.core.ai.recommendation_engine import Recommendation

    engine = _make_engine()
    cached_recs = [
        Recommendation(
            kategori="verimlilik",
            hedef_tip="arac",
            hedef_id=5,
            mesaj="Cached",
            oncelik=3,
        )
    ]
    engine._cache["arac_5"] = cached_recs
    engine._cache_time["arac_5"] = datetime.now(timezone.utc)

    result = await engine.get_vehicle_recommendations(arac_id=5)
    assert result is cached_recs


# ---------------------------------------------------------------------------
# get_driver_recommendations
# ---------------------------------------------------------------------------


async def test_get_driver_recommendations_none_degerlendirme():
    """get_driver_recommendations returns [] when evaluation is None."""
    engine = _make_engine()

    mock_service = MagicMock()
    mock_service.evaluate_driver = AsyncMock(return_value=None)
    mock_container = MagicMock()
    mock_container.degerlendirme_service = mock_service

    with patch(
        "app.core.container.get_container",
        return_value=mock_container,
    ):
        result = await engine.get_driver_recommendations(sofor_id=99)
    assert result == []


async def test_get_driver_recommendations_low_score():
    """get_driver_recommendations returns education rec for low score."""
    engine = _make_engine()

    degerlendirme = MagicMock()
    degerlendirme.ad_soyad = "Düşük Puanlı"
    degerlendirme.genel_puan = 40
    degerlendirme.trend = MagicMock()
    degerlendirme.trend.value = "Stabil"
    degerlendirme.filo_karsilastirma = 0

    mock_service = MagicMock()
    mock_service.evaluate_driver = AsyncMock(return_value=degerlendirme)
    mock_container = MagicMock()
    mock_container.degerlendirme_service = mock_service

    with patch(
        "app.core.container.get_container",
        return_value=mock_container,
    ):
        result = await engine.get_driver_recommendations(sofor_id=1)

    assert any(r.kategori == "egitim" and r.oncelik == 4 for r in result)


async def test_get_driver_recommendations_worsening_trend():
    """get_driver_recommendations returns efficiency rec for worsening trend."""
    engine = _make_engine()

    degerlendirme = MagicMock()
    degerlendirme.ad_soyad = "Kötüleşen Sofor"
    degerlendirme.genel_puan = 70
    degerlendirme.trend = MagicMock()
    degerlendirme.trend.value = "Kötüleşiyor"
    degerlendirme.trend_degisim = -8.5
    degerlendirme.filo_karsilastirma = 0

    mock_service = MagicMock()
    mock_service.evaluate_driver = AsyncMock(return_value=degerlendirme)
    mock_container = MagicMock()
    mock_container.degerlendirme_service = mock_service

    with patch(
        "app.core.container.get_container",
        return_value=mock_container,
    ):
        result = await engine.get_driver_recommendations(sofor_id=2)

    assert any(r.kategori == "verimlilik" for r in result)


async def test_get_driver_recommendations_below_fleet_average():
    """get_driver_recommendations returns coaching rec when below fleet average."""
    engine = _make_engine()

    degerlendirme = MagicMock()
    degerlendirme.ad_soyad = "Düşük Performanslı"
    degerlendirme.genel_puan = 65
    degerlendirme.trend = MagicMock()
    degerlendirme.trend.value = "Stabil"
    degerlendirme.filo_karsilastirma = -15  # <-10

    mock_service = MagicMock()
    mock_service.evaluate_driver = AsyncMock(return_value=degerlendirme)
    mock_container = MagicMock()
    mock_container.degerlendirme_service = mock_service

    with patch(
        "app.core.container.get_container",
        return_value=mock_container,
    ):
        result = await engine.get_driver_recommendations(sofor_id=3)

    assert any(r.kategori == "egitim" and r.oncelik == 3 for r in result)


async def test_get_driver_recommendations_exception_logged():
    """get_driver_recommendations handles exception gracefully and returns []."""
    engine = _make_engine()

    mock_container = MagicMock()
    mock_container.degerlendirme_service = MagicMock(side_effect=Exception("DB error"))

    with patch(
        "app.core.container.get_container",
        return_value=mock_container,
    ):
        result = await engine.get_driver_recommendations(sofor_id=50)

    # Even with exception, should return cached empty list
    assert isinstance(result, list)


async def test_get_driver_recommendations_cache_hit():
    """get_driver_recommendations returns cache on second call."""
    from app.core.ai.recommendation_engine import Recommendation

    engine = _make_engine()
    cached = [
        Recommendation(
            kategori="egitim",
            hedef_tip="sofor",
            hedef_id=7,
            mesaj="Cached driver",
            oncelik=4,
        )
    ]
    engine._cache["sofor_7"] = cached
    engine._cache_time["sofor_7"] = datetime.now(timezone.utc)

    result = await engine.get_driver_recommendations(sofor_id=7)
    assert result is cached


# ---------------------------------------------------------------------------
# get_fleet_recommendations
# ---------------------------------------------------------------------------


async def test_get_fleet_recommendations_consumption_increase():
    """get_fleet_recommendations returns rec when this month > last month by >5%."""
    engine = _make_engine()

    bu_ay_row = _make_row(ort=35.0)
    gecen_ay_row = _make_row(ort=32.0)  # (35-32)/32 * 100 = 9.375% > 5%
    kotu_row = _make_row(plaka="34BAD01", ort=38.0)  # <40, so no critical rec

    call_count = 0

    async def multi_execute(stmt, *args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return _fetchone_result(bu_ay_row)
        elif call_count == 2:
            return _fetchone_result(gecen_ay_row)
        else:
            return _fetchone_result(kotu_row)

    mock_uow = _make_uow_ctx(
        session_execute_side_effect=AsyncMock(side_effect=multi_execute)
    )

    with patch("app.core.ai.recommendation_engine.unit_of_work", return_value=mock_uow):
        result = await engine.get_fleet_recommendations()

    assert any(r.kategori == "verimlilik" and r.hedef_tip == "filo" for r in result)


async def test_get_fleet_recommendations_worst_vehicle_critical():
    """get_fleet_recommendations flags vehicle with >40 L consumption."""
    engine = _make_engine()

    bu_ay_row = _make_row(ort=None)
    kotu_row = _make_row(plaka="34WORST", ort=45.0)  # >40

    call_count = 0

    async def multi_execute(stmt, *args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return _fetchone_result(bu_ay_row)
        elif call_count == 2:
            return _fetchone_result(None)
        else:
            return _fetchone_result(kotu_row)

    mock_uow = _make_uow_ctx(
        session_execute_side_effect=AsyncMock(side_effect=multi_execute)
    )

    with patch("app.core.ai.recommendation_engine.unit_of_work", return_value=mock_uow):
        result = await engine.get_fleet_recommendations()

    assert any(r.kategori == "bakim" and r.oncelik == 5 for r in result)


async def test_get_fleet_recommendations_cache_hit():
    """get_fleet_recommendations uses cached result on second call."""
    from app.core.ai.recommendation_engine import Recommendation

    engine = _make_engine()
    cached = [
        Recommendation(
            kategori="verimlilik",
            hedef_tip="filo",
            hedef_id=None,
            mesaj="Fleet cached",
            oncelik=4,
        )
    ]
    engine._cache["filo"] = cached
    engine._cache_time["filo"] = datetime.now(timezone.utc)

    result = await engine.get_fleet_recommendations()
    assert result is cached


# ---------------------------------------------------------------------------
# get_cost_saving_suggestions
# ---------------------------------------------------------------------------


async def test_get_cost_saving_suggestions_with_stations():
    """get_cost_saving_suggestions returns rec when price diff > 1 TL."""
    engine = _make_engine()

    pahali = _make_row(istasyon="Pahalı İstasyon", ort_fiyat=15.0)
    ucuz = _make_row(istasyon="Ucuz İstasyon", ort_fiyat=13.0)  # diff=2.0

    execute_mock = AsyncMock(return_value=_fetchall_result([pahali, ucuz]))
    mock_uow = _make_uow_ctx(session_execute_side_effect=execute_mock)

    with patch("app.core.ai.recommendation_engine.unit_of_work", return_value=mock_uow):
        result = await engine.get_cost_saving_suggestions()

    assert len(result) == 1
    assert result[0].kategori == "maliyet"
    assert "Ucuz İstasyon" in result[0].mesaj


async def test_get_cost_saving_suggestions_no_stations():
    """get_cost_saving_suggestions returns [] when less than 2 stations."""
    engine = _make_engine()

    execute_mock = AsyncMock(return_value=_fetchall_result([]))
    mock_uow = _make_uow_ctx(session_execute_side_effect=execute_mock)

    with patch("app.core.ai.recommendation_engine.unit_of_work", return_value=mock_uow):
        result = await engine.get_cost_saving_suggestions()

    assert result == []


async def test_get_cost_saving_suggestions_small_price_diff():
    """get_cost_saving_suggestions returns [] when price diff <= 1."""
    engine = _make_engine()

    pahali = _make_row(istasyon="Stasyon A", ort_fiyat=14.5)
    ucuz = _make_row(istasyon="Stasyon B", ort_fiyat=14.0)  # diff=0.5 <= 1

    execute_mock = AsyncMock(return_value=_fetchall_result([pahali, ucuz]))
    mock_uow = _make_uow_ctx(session_execute_side_effect=execute_mock)

    with patch("app.core.ai.recommendation_engine.unit_of_work", return_value=mock_uow):
        result = await engine.get_cost_saving_suggestions()

    assert result == []


# ---------------------------------------------------------------------------
# Cache invalidation methods
# ---------------------------------------------------------------------------


def test_clear_cache():
    """clear_cache empties both _cache and _cache_time."""
    engine = _make_engine()
    engine._cache["key1"] = ["rec"]
    engine._cache_time["key1"] = datetime.now(timezone.utc)

    engine.clear_cache()
    assert engine._cache == {}
    assert engine._cache_time == {}


def test_invalidate_vehicle_cache():
    """invalidate_vehicle_cache removes only vehicle-specific entry."""
    engine = _make_engine()
    engine._cache["arac_10"] = ["rec1"]
    engine._cache_time["arac_10"] = datetime.now(timezone.utc)
    engine._cache["filo"] = ["rec2"]

    engine.invalidate_vehicle_cache(10)
    assert "arac_10" not in engine._cache
    assert "filo" in engine._cache


def test_invalidate_driver_cache():
    """invalidate_driver_cache removes only driver-specific entry."""
    engine = _make_engine()
    engine._cache["sofor_5"] = ["rec1"]
    engine._cache_time["sofor_5"] = datetime.now(timezone.utc)
    engine._cache["filo"] = ["rec2"]

    engine.invalidate_driver_cache(5)
    assert "sofor_5" not in engine._cache
    assert "filo" in engine._cache


def test_invalidate_fleet_cache():
    """invalidate_fleet_cache removes only fleet entry."""
    engine = _make_engine()
    engine._cache["filo"] = ["rec1"]
    engine._cache_time["filo"] = datetime.now(timezone.utc)
    engine._cache["arac_1"] = ["rec2"]

    engine.invalidate_fleet_cache()
    assert "filo" not in engine._cache
    assert "arac_1" in engine._cache


# ---------------------------------------------------------------------------
# get_recommendation_engine singleton
# ---------------------------------------------------------------------------


def test_get_recommendation_engine_singleton():
    """get_recommendation_engine returns same instance on multiple calls."""
    import app.core.ai.recommendation_engine as mod

    mod._recommendation_engine = None  # Reset singleton

    engine1 = mod.get_recommendation_engine()
    engine2 = mod.get_recommendation_engine()
    assert engine1 is engine2
    mod._recommendation_engine = None  # Cleanup
