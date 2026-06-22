"""
Additional coverage for app/core/services/ai_service.py.

Targets missing lines:
  178-215 — predict_trip_fuel (basic path, with dorse_id, dorse_row present, route_analysis)
  239     — detect_anomalies: consumptions empty (dist always 0)
  242-249 — detect_anomalies: std == 0 (no anomaly)
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

pytestmark = pytest.mark.unit


def _make_service():
    """Return an AIService with a stubbed GroqService."""
    with patch("app.core.ai.groq_service.GroqService.__init__", return_value=None):
        from app.core.services.ai_service import AIService

        svc = AIService.__new__(AIService)
        svc._predictor_cache = {}
        groq = MagicMock()
        groq.chat = AsyncMock(return_value="resp")
        groq.chat_stream = AsyncMock()
        svc.groq = groq
        return svc


def _make_mock_uow():
    uow = MagicMock()
    uow.__aenter__ = AsyncMock(return_value=uow)
    uow.__aexit__ = AsyncMock(return_value=False)
    uow.arac_repo = MagicMock()
    uow.sefer_repo = MagicMock()
    uow.yakit_repo = MagicMock()
    uow.session = MagicMock()
    return uow


def _make_uow_cls(uow):
    uow_cls = MagicMock()
    uow_cls.return_value.__aenter__ = AsyncMock(return_value=uow)
    uow_cls.return_value.__aexit__ = AsyncMock(return_value=False)
    return uow_cls


# ---------------------------------------------------------------------------
# predict_trip_fuel — basic path without dorse_id
# ---------------------------------------------------------------------------


class TestPredictTripFuel:
    async def test_basic_prediction_no_dorse(self):
        svc = _make_service()
        uow = _make_mock_uow()
        uow.arac_repo.get_by_id = AsyncMock(return_value=None)
        uow.sefer_repo.get_for_training = AsyncMock(return_value=[])

        from app.core.ml.ensemble_predictor import EnsembleFuelPredictor

        fake_result = MagicMock()
        fake_result.tahmin_l_100km = 32.5
        fake_result.confidence_low = 29.0
        fake_result.confidence_high = 36.0
        fake_result.physics_weight = 0.8
        fake_result.features_used = {}

        with patch("app.core.services.ai_service.UnitOfWork", _make_uow_cls(uow)):
            with patch.object(
                EnsembleFuelPredictor, "predict", return_value=fake_result
            ):
                result = await svc.predict_trip_fuel(
                    arac_id=1,
                    ton=15.0,
                    mesafe_km=300.0,
                )

        assert result.tahmin_l_100km == pytest.approx(32.5)

    async def test_prediction_with_route_analysis(self):
        """route_analysis dict is forwarded into sefer_context."""
        svc = _make_service()
        uow = _make_mock_uow()
        uow.arac_repo.get_by_id = AsyncMock(return_value=None)
        uow.sefer_repo.get_for_training = AsyncMock(return_value=[])

        from app.core.ml.ensemble_predictor import EnsembleFuelPredictor

        fake_result = MagicMock()
        fake_result.tahmin_l_100km = 30.0
        fake_result.confidence_low = 27.0
        fake_result.confidence_high = 33.0
        fake_result.physics_weight = 0.8
        fake_result.features_used = {}

        captured_contexts = []

        def _capture_predict(context):
            captured_contexts.append(context)
            return fake_result

        with patch("app.core.services.ai_service.UnitOfWork", _make_uow_cls(uow)):
            with patch.object(
                EnsembleFuelPredictor, "predict", side_effect=_capture_predict
            ):
                await svc.predict_trip_fuel(
                    arac_id=2,
                    ton=10.0,
                    mesafe_km=200.0,
                    route_analysis={"highway_fraction": 0.7},
                )

        assert len(captured_contexts) == 1
        assert "rota_detay" in captured_contexts[0]
        assert (
            captured_contexts[0]["rota_detay"]["route_analysis"]["highway_fraction"]
            == 0.7
        )

    async def test_prediction_with_dorse_row_found(self):
        """dorse_id provided and dorse row found — updates sefer_context."""
        svc = _make_service()
        uow = _make_mock_uow()
        uow.arac_repo.get_by_id = AsyncMock(return_value=None)
        uow.sefer_repo.get_for_training = AsyncMock(return_value=[])

        # Mock session.execute to return a row with dorse data
        dorse_row = MagicMock()
        dorse_row.bos_agirlik_kg = 6500
        dorse_row.dingil_sayisi = 3
        dorse_result = MagicMock()
        dorse_result.first.return_value = dorse_row
        uow.session.execute = AsyncMock(return_value=dorse_result)

        from app.core.ml.ensemble_predictor import EnsembleFuelPredictor

        fake_result = MagicMock()
        fake_result.tahmin_l_100km = 35.0
        fake_result.confidence_low = 31.0
        fake_result.confidence_high = 39.0
        fake_result.physics_weight = 0.8
        fake_result.features_used = {}

        captured = []

        def _capture_predict(context):
            captured.append(context)
            return fake_result

        with patch("app.core.services.ai_service.UnitOfWork", _make_uow_cls(uow)):
            with patch.object(
                EnsembleFuelPredictor, "predict", side_effect=_capture_predict
            ):
                await svc.predict_trip_fuel(
                    arac_id=3,
                    ton=18.0,
                    mesafe_km=400.0,
                    dorse_id=10,
                )

        # Dorse data should be forwarded
        assert "dorse_bos_agirlik" in captured[0]
        assert captured[0]["dorse_bos_agirlik"] == pytest.approx(6500.0)
        assert captured[0]["dorse_lastik_sayisi"] == 6  # 3 axles * 2

    async def test_prediction_with_dorse_row_none(self):
        """dorse_id provided but no row found — proceeds without dorse context."""
        svc = _make_service()
        uow = _make_mock_uow()
        uow.arac_repo.get_by_id = AsyncMock(return_value=None)
        uow.sefer_repo.get_for_training = AsyncMock(return_value=[])

        # dorse row not found
        dorse_result = MagicMock()
        dorse_result.first.return_value = None
        uow.session.execute = AsyncMock(return_value=dorse_result)

        from app.core.ml.ensemble_predictor import EnsembleFuelPredictor

        fake_result = MagicMock()
        fake_result.tahmin_l_100km = 32.0
        fake_result.confidence_low = 29.0
        fake_result.confidence_high = 35.0
        fake_result.physics_weight = 0.8
        fake_result.features_used = {}

        captured = []

        def _capture_predict(context):
            captured.append(context)
            return fake_result

        with patch("app.core.services.ai_service.UnitOfWork", _make_uow_cls(uow)):
            with patch.object(
                EnsembleFuelPredictor, "predict", side_effect=_capture_predict
            ):
                await svc.predict_trip_fuel(
                    arac_id=4,
                    ton=15.0,
                    mesafe_km=350.0,
                    dorse_id=99,
                )

        # No dorse keys in context
        assert "dorse_bos_agirlik" not in captured[0]

    async def test_prediction_ascent_descent_flat(self):
        """Extra kwargs (ascent_m, descent_m, flat_km) are forwarded correctly."""
        svc = _make_service()
        uow = _make_mock_uow()
        uow.arac_repo.get_by_id = AsyncMock(return_value=None)
        uow.sefer_repo.get_for_training = AsyncMock(return_value=[])

        from app.core.ml.ensemble_predictor import EnsembleFuelPredictor

        fake_result = MagicMock()
        fake_result.tahmin_l_100km = 33.0
        fake_result.confidence_low = 30.0
        fake_result.confidence_high = 36.0
        fake_result.physics_weight = 0.8
        fake_result.features_used = {}

        captured = []

        def _capture(context):
            captured.append(context)
            return fake_result

        with patch("app.core.services.ai_service.UnitOfWork", _make_uow_cls(uow)):
            with patch.object(EnsembleFuelPredictor, "predict", side_effect=_capture):
                await svc.predict_trip_fuel(
                    arac_id=5,
                    ton=12.0,
                    mesafe_km=250.0,
                    ascent_m=500,
                    descent_m=300,
                    flat_km=150.0,
                )

        ctx = captured[0]
        assert ctx["ascent_m"] == 500
        assert ctx["descent_m"] == 300
        assert ctx["flat_distance_km"] == 150.0


# ---------------------------------------------------------------------------
# detect_anomalies — edge case: consumptions list is empty (line 239)
# ---------------------------------------------------------------------------


class TestDetectAnomaliesMore:
    async def test_consumptions_empty_when_km_decreasing(self):
        """If kms[i] - kms[i+1] <= 0 for all, consumptions is empty → returns []."""
        svc = _make_service()
        # kms in descending order → dist is always negative
        records = []
        for i in range(8):
            records.append(
                {"litre": 50.0, "km_sayac": 100000 - i * 100, "tarih": "2024-01-01"}
            )
        uow = _make_mock_uow()
        uow.yakit_repo.get_all = AsyncMock(
            return_value={"items": records, "total": len(records)}
        )

        with patch("app.core.services.ai_service.UnitOfWork", _make_uow_cls(uow)):
            result = await svc.detect_anomalies(7)

        assert result == []

    async def test_std_zero_no_anomaly(self):
        """All consumptions identical → std=0 → no anomaly even at extreme values."""
        svc = _make_service()
        # Identical consumption (30L/100km) for all intervals
        records = []
        base = 100000
        for i in range(10):
            records.append(
                {"litre": 30.0, "km_sayac": base + i * 100, "tarih": "2024-01-01"}
            )
        uow = _make_mock_uow()
        uow.yakit_repo.get_all = AsyncMock(
            return_value={"items": records, "total": len(records)}
        )

        with patch("app.core.services.ai_service.UnitOfWork", _make_uow_cls(uow)):
            result = await svc.detect_anomalies(8)

        assert result == []

    async def test_anomaly_z_score_fields_present(self):
        """Each detected anomaly has required fields."""
        svc = _make_service()
        records = []
        base = 100000
        for i in range(9):
            records.append(
                {"litre": 30.0, "km_sayac": base + i * 100, "tarih": "2024-01-01"}
            )
        # Insert a massive spike
        records.append({"litre": 999.0, "km_sayac": base + 850, "tarih": "2024-01-15"})
        uow = _make_mock_uow()
        uow.yakit_repo.get_all = AsyncMock(
            return_value={"items": records, "total": len(records)}
        )

        with patch("app.core.services.ai_service.UnitOfWork", _make_uow_cls(uow)):
            result = await svc.detect_anomalies(9)

        for anomaly in result:
            assert "index" in anomaly
            assert "z_score" in anomaly
            assert anomaly["type"] == "CONSUMPTION_SPIKE"
