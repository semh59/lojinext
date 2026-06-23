"""
Real integration tests for the prediction_service contract seams.

These tests call the actual service chain without mocks so contract
mismatches (wrong dict key names, missing keys) surface immediately.

Seams tested:
  1. ensemble_service → prediction_service  (confidence_score key present)
  2. prediction_service → anomaly_detector  (tahmini_tuketim key read correctly)
  3. prediction_service → sofor_analiz_service  (tahmini_tuketim key read correctly)
"""

from datetime import date, timedelta

import pytest
from sqlalchemy import insert

from app.database.models import Arac, Sefer, Sofor

pytestmark = pytest.mark.integration

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _create_arac(db_session) -> int:
    result = await db_session.execute(
        insert(Arac).values(
            plaka="88 CONTRACT 01",
            marka="Contract",
            model="Test",
            yil=2021,
            aktif=True,
            bos_agirlik_kg=8000.0,
            euro_sinifi="EURO6",
        )
    )
    await db_session.commit()
    return result.inserted_primary_key[0]


async def _create_sofor(db_session) -> int:
    result = await db_session.execute(
        insert(Sofor).values(
            ad_soyad="Contract Driver",
            telefon="0532 888 88 88",
            ise_baslama=date(2019, 1, 1),
            ehliyet_sinifi="E",
            aktif=True,
        )
    )
    await db_session.commit()
    return result.inserted_primary_key[0]


# ---------------------------------------------------------------------------
# Seam 1: ensemble_service → prediction_service
# ---------------------------------------------------------------------------


async def test_prediction_service_returns_tahmini_tuketim(db_session):
    """
    prediction_service.predict_consumption must return a dict with
    'tahmini_tuketim' as the primary L/100km key (not 'prediction_l_100km').
    Also asserts 'confidence_score' is present (fixed in ensemble_service).
    """
    from app.services.prediction_service import get_prediction_service

    arac_id = await _create_arac(db_session)
    svc = get_prediction_service()

    result = await svc.predict_consumption(
        arac_id=arac_id,
        mesafe_km=300.0,
        ton=18.0,
        ascent_m=500.0,
        descent_m=500.0,
    )

    # Primary contract: key name must be tahmini_tuketim
    assert "tahmini_tuketim" in result, (
        f"'tahmini_tuketim' missing from prediction response. Got keys: {list(result)}"
    )
    assert result["tahmini_tuketim"] > 0, "Expected a positive L/100km estimate"

    # confidence_score must be present and valid (fixed P0 bug)
    assert "confidence_score" in result, (
        f"'confidence_score' missing — ensemble_service bug not fixed. Keys: {list(result)}"
    )
    assert 0.0 <= result["confidence_score"] <= 1.0, (
        f"confidence_score out of [0,1]: {result['confidence_score']}"
    )

    # fallback_triggered must be False when physics works (not always True)
    # Note: may be True if no ML model trained — acceptable, but key must exist
    assert "fallback_triggered" in result


# ---------------------------------------------------------------------------
# Seam 2: prediction_service → anomaly_detector
# ---------------------------------------------------------------------------


async def test_anomaly_detector_reads_tahmini_tuketim_key(db_session):
    """
    AnomalyDetector.detect_trip_anomaly_elite must correctly read 'tahmini_tuketim'
    from prediction_service response. If it reads 'prediction_l_100km' it would
    raise KeyError (silently caught → always returns None).

    We inject a trip with a deliberately extreme consumption (3× the predicted)
    so the test is independent of the exact physics estimate.
    """
    from app.core.services.anomaly_detector import AnomalyDetector

    arac_id = await _create_arac(db_session)
    sofor_id = await _create_sofor(db_session)

    # First get the real prediction to know what the model returns
    from app.services.prediction_service import get_prediction_service

    pred = await get_prediction_service().predict_consumption(
        arac_id=arac_id,
        mesafe_km=500.0,
        ton=18.0,
    )
    predicted_l100 = pred["tahmini_tuketim"]

    # Craft a consumption 3× the prediction → guaranteed >20% deviation
    extreme_consumption = predicted_l100 * 3.0

    detector = AnomalyDetector()
    trip_data = {
        "id": 9901,
        "arac_id": arac_id,
        "sofor_id": sofor_id,
        "mesafe_km": 500.0,
        "ton": 18.0,
        "tuketim": extreme_consumption,
        "tarih": date.today(),
    }

    result = await detector.detect_trip_anomaly_elite(trip_data)

    assert result is not None, (
        "AnomalyDetector returned None for a 200%+ deviation — "
        "likely still reading wrong key name from prediction response"
    )
    assert result.sapma_yuzde > 20.0, (
        f"Expected >20% deviation, got {result.sapma_yuzde}"
    )


async def test_anomaly_detector_hybrid_reads_tahmini_tuketim_key(db_session):
    """Same contract check for detect_anomaly_hybrid (the ML-assisted path)."""
    from app.core.services.anomaly_detector import AnomalyDetector
    from app.services.prediction_service import get_prediction_service

    arac_id = await _create_arac(db_session)
    sofor_id = await _create_sofor(db_session)

    pred = await get_prediction_service().predict_consumption(
        arac_id=arac_id,
        mesafe_km=400.0,
        ton=15.0,
    )
    extreme_consumption = pred["tahmini_tuketim"] * 3.0

    detector = AnomalyDetector()
    trip_data = {
        "id": 9902,
        "arac_id": arac_id,
        "sofor_id": sofor_id,
        "mesafe_km": 400.0,
        "ton": 15.0,
        "tuketim": extreme_consumption,
        "tarih": date.today(),
    }

    result = await detector.detect_anomaly_hybrid(trip_data, use_ml=False)

    assert result is not None, (
        "detect_anomaly_hybrid returned None for a 200%+ deviation — "
        "likely still reading wrong key name from prediction response"
    )


# ---------------------------------------------------------------------------
# Seam 3: prediction_service → sofor_analiz_service
# ---------------------------------------------------------------------------


async def test_sofor_elite_score_not_none_with_real_prediction(db_session):
    """
    sofor_analiz_service._calculate_elite_score must read 'tahmini_tuketim'
    from the prediction response (not 'prediction_l_100km' which doesn't exist).

    If the key bug is present, pred.get("prediction_l_100km", 0) → 0 → expected<=0
    → returns None for every trip → final score is None even with valid data.
    """
    from app.core.services.sofor_analiz_service import SoforAnalizService
    from app.database.unit_of_work import UnitOfWork

    arac_id = await _create_arac(db_session)
    sofor_id = await _create_sofor(db_session)

    # Insert real sefer rows so the service has data to work with
    async with UnitOfWork() as uow:
        for i in range(3):
            await uow.session.execute(
                insert(Sefer).values(
                    arac_id=arac_id,
                    sofor_id=sofor_id,
                    baslangic_lokasyon="Ankara",
                    bitis_lokasyon="Istanbul",
                    mesafe_km=450.0,
                    gercek_tuketim=28.0,
                    net_kg=18000,
                    dolu_agirlik_kg=26000,
                    bos_agirlik_kg=8000,
                    tarih=date.today() - timedelta(days=i + 1),
                    durum="tamamlandi",
                    aktif=True,
                )
            )

    service = SoforAnalizService()
    score = await service._calculate_elite_score(sofor_id=sofor_id, arac_id=arac_id)

    assert score is not None, (
        "Elite score is None — sofor_analiz_service is reading wrong key "
        "'prediction_l_100km' (always 0) instead of 'tahmini_tuketim'"
    )
    assert 0.0 <= score <= 100.0, f"Score out of bounds: {score}"


async def test_sofor_calculate_elite_performance_score_real(db_session):
    """
    Full calculate_elite_performance_score path using real DB data and real
    prediction_service — no mocks anywhere in the call chain.
    """
    from app.core.services.sofor_analiz_service import SoforAnalizService
    from app.database.unit_of_work import UnitOfWork

    arac_id = await _create_arac(db_session)
    sofor_id = await _create_sofor(db_session)

    async with UnitOfWork() as uow:
        for i in range(5):
            await uow.session.execute(
                insert(Sefer).values(
                    arac_id=arac_id,
                    sofor_id=sofor_id,
                    baslangic_lokasyon="Konya",
                    bitis_lokasyon="Bursa",
                    mesafe_km=380.0,
                    gercek_tuketim=26.0,
                    net_kg=16000,
                    dolu_agirlik_kg=24000,
                    bos_agirlik_kg=8000,
                    tarih=date.today() - timedelta(days=i + 1),
                    durum="tamamlandi",
                    aktif=True,
                )
            )

    service = SoforAnalizService()
    score = await service.calculate_elite_performance_score(sofor_id=sofor_id)

    assert score is not None, (
        "calculate_elite_performance_score returned None with real trip data — "
        "prediction key contract mismatch still present"
    )
    assert 0.0 <= score <= 100.0
