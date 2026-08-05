"""
Real integration tests for the prediction_service contract seams.

Seam 1 (ensemble_service -> prediction_service response shape) moved to
v2/services/prediction_ml_service/tests/test_prediction_contract_integration.py
with the Task 5 extraction (2026-08-04): it exercised the real physics
engine end-to-end, which now only lives in that service's own process --
v2.modules.prediction_ml.public.get_prediction_service on the main
backend is an HTTP-client facade that would make a real network call to a
service not running in this test environment.

Seams 2 and 3 stay here (anomaly_detector / driver_stats are main-backend
modules) but the prediction_service boundary is now mocked at the
cross-process HTTP-client-facade seam -- the contract under test is
"does this consumer read the 'tahmini_tuketim' key correctly", which is
still exercised for real; only the (now cross-process) physics
computation itself is faked, with a shape matching what the real service
actually returns (verified against prediction_ml_service's own response
schema).

Seams tested:
  2. prediction_service → anomaly_detector  (tahmini_tuketim key read correctly)
  3. prediction_service → sofor_analiz_service  (tahmini_tuketim key read correctly)
"""

from datetime import date, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy import insert

from v2.modules.driver.public import Sofor
from v2.modules.fleet.public import AracORM as Arac
from v2.modules.platform_infra.security.pii_encryption import blind_index
from v2.modules.trip.public import SeferORM as Sefer

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
        )
    )
    await db_session.commit()
    return result.inserted_primary_key[0]


async def _create_sofor(db_session) -> int:
    result = await db_session.execute(
        insert(Sofor).values(
            ad_soyad="Contract Driver",
            ad_soyad_bidx=blind_index("Contract Driver"),
            telefon="0532 888 88 88",
            ise_baslama=date(2019, 1, 1),
            ehliyet_sinifi="E",
            aktif=True,
        )
    )
    await db_session.commit()
    return result.inserted_primary_key[0]


def _mock_prediction_service(tahmini_tuketim: float):
    """Fake the cross-process HTTP-client-facade boundary, not the
    consumer under test -- shape matches the real service's response
    (see prediction_ml_service's own response_builder.build_prediction_response)."""
    svc = MagicMock()
    svc.predict_consumption = AsyncMock(
        return_value={
            "status": "success",
            "tahmini_tuketim": tahmini_tuketim,
            "tahmini_litre": None,
            "model_used": "physics",
            "model_version": "physics-v2.0",
            "confidence_score": 0.72,
            "confidence_low": tahmini_tuketim * 0.9,
            "confidence_high": tahmini_tuketim * 1.1,
            "warning_level": "YELLOW",
            "fallback_triggered": False,
            "faktorler": {},
            "explanation_summary": "test",
        }
    )
    return svc


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
    from v2.modules.anomaly.application.detect_anomaly import AnomalyDetector

    arac_id = await _create_arac(db_session)
    sofor_id = await _create_sofor(db_session)

    predicted_l100 = 30.0

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

    with patch(
        "v2.modules.anomaly.application.detect_anomaly.get_prediction_service",
        return_value=_mock_prediction_service(predicted_l100),
    ):
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
    from v2.modules.anomaly.application.detect_anomaly import AnomalyDetector

    arac_id = await _create_arac(db_session)
    sofor_id = await _create_sofor(db_session)

    predicted_l100 = 28.0
    extreme_consumption = predicted_l100 * 3.0

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

    with patch(
        "v2.modules.anomaly.application.detect_anomaly.get_prediction_service",
        return_value=_mock_prediction_service(predicted_l100),
    ):
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
    from v2.modules.driver.application.driver_stats import _calc_elite_from_trips
    from v2.modules.shared_kernel.infrastructure.unit_of_work import UnitOfWork

    arac_id = await _create_arac(db_session)
    sofor_id = await _create_sofor(db_session)

    # Insert real sefer rows so the use-case has data to work with
    for i in range(3):
        await db_session.execute(
            insert(Sefer).values(
                arac_id=arac_id,
                sofor_id=sofor_id,
                cikis_yeri="Ankara",
                varis_yeri="Istanbul",
                mesafe_km=450.0,
                tuketim=28.0,
                net_kg=18000,
                dolu_agirlik_kg=26000,
                bos_agirlik_kg=8000,
                tarih=date.today() - timedelta(days=i + 1),
                durum="Completed",
            )
        )
    await db_session.commit()

    with patch(
        "v2.modules.driver.application.driver_stats.get_prediction_service",
        return_value=_mock_prediction_service(30.0),
    ):
        async with UnitOfWork() as uow:
            seferler = await uow.sefer_repo.get_all(
                filters={"sofor_id": sofor_id}, limit=50
            )
            score = await _calc_elite_from_trips(seferler)

    assert score is not None, (
        "Elite score is None — driver_stats is reading wrong key "
        "'prediction_l_100km' (always 0) instead of 'tahmini_tuketim'"
    )
    assert 0.0 <= score <= 100.0, f"Score out of bounds: {score}"


async def test_sofor_calculate_elite_performance_score_real(db_session):
    """
    Full calculate_elite_performance_score path using real DB data; the
    cross-process prediction_service call is mocked at the HTTP-client
    facade boundary (see module docstring), everything else is real.
    """
    from v2.modules.driver.application.driver_stats import (
        calculate_elite_performance_score,
    )
    from v2.modules.shared_kernel.infrastructure.unit_of_work import UnitOfWork

    arac_id = await _create_arac(db_session)
    sofor_id = await _create_sofor(db_session)

    for i in range(5):
        await db_session.execute(
            insert(Sefer).values(
                arac_id=arac_id,
                sofor_id=sofor_id,
                cikis_yeri="Konya",
                varis_yeri="Bursa",
                mesafe_km=380.0,
                tuketim=26.0,
                net_kg=16000,
                dolu_agirlik_kg=24000,
                bos_agirlik_kg=8000,
                tarih=date.today() - timedelta(days=i + 1),
                durum="Completed",
            )
        )
    await db_session.commit()

    with patch(
        "v2.modules.driver.application.driver_stats.get_prediction_service",
        return_value=_mock_prediction_service(27.0),
    ):
        async with UnitOfWork() as uow:
            score = await calculate_elite_performance_score(sofor_id=sofor_id, uow=uow)

    assert score is not None, (
        "calculate_elite_performance_score returned None with real trip data — "
        "prediction key contract mismatch still present"
    )
    assert 0.0 <= score <= 100.0
