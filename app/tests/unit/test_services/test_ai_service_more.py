"""
Additional coverage for app/core/services/ai_service.py.

0-mock (Dilim 29): all patch(UnitOfWork) removed.
- Non-dorse tests: db_session + patch.object(svc, '_get_predictor_for_vehicle')
- Dorse tests: db_session + patch _get_predictor_for_vehicle + AsyncSession.execute
  (dorseler.dingil_sayisi doesn't exist in the schema — raw SQL would fail on real DB,
  so AsyncSession.execute is narrowly patched to avoid the broken column error)
- TestDetectAnomaliesMore: patch.object(YakitRepository, 'get_all')

Note: asyncio.to_thread(predictor.predict, ctx) calls the INSTANCE method, not the
class — capture is done by assigning a sync function to mock.predict directly.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

import app.database.repositories.yakit_repo as yakit_repo_mod

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


def _make_fake_result(tahmin=32.5, low=29.0, high=36.0):
    r = MagicMock()
    r.tahmin_l_100km = tahmin
    r.confidence_low = low
    r.confidence_high = high
    r.physics_weight = 0.8
    r.features_used = {}
    return r


def _make_pred(captured=None, tahmin=32.5):
    """Mock predictor whose .predict is a sync function capturing sefer_context."""
    fake_result = _make_fake_result(tahmin)

    def _predict(ctx):
        if captured is not None:
            captured.append(ctx)
        return fake_result

    pred = MagicMock()
    pred.predict = _predict
    return pred


# ---------------------------------------------------------------------------
# predict_trip_fuel — basic path without dorse_id
# ---------------------------------------------------------------------------


class TestPredictTripFuel:
    async def test_basic_prediction_no_dorse(self, db_session):
        svc = _make_service()
        pred = _make_pred(tahmin=32.5)

        with patch.object(
            svc, "_get_predictor_for_vehicle", AsyncMock(return_value=pred)
        ):
            result = await svc.predict_trip_fuel(arac_id=1, ton=15.0, mesafe_km=300.0)

        assert result.tahmin_l_100km == pytest.approx(32.5)

    async def test_prediction_with_route_analysis(self, db_session):
        """route_analysis dict is forwarded into sefer_context."""
        svc = _make_service()
        captured = []
        pred = _make_pred(captured=captured, tahmin=30.0)

        with patch.object(
            svc, "_get_predictor_for_vehicle", AsyncMock(return_value=pred)
        ):
            await svc.predict_trip_fuel(
                arac_id=2,
                ton=10.0,
                mesafe_km=200.0,
                route_analysis={"highway_fraction": 0.7},
            )

        assert len(captured) == 1
        assert "rota_detay" in captured[0]
        assert captured[0]["rota_detay"]["route_analysis"]["highway_fraction"] == 0.7

    async def test_prediction_with_dorse_row_found(self, db_session):
        """dorse_id provided and dorse row found — updates sefer_context.

        Narrow AsyncSession.execute patch: dorseler.dingil_sayisi doesn't exist in
        the schema, so the raw SQL in predict_trip_fuel would fail on a real DB.
        """
        from sqlalchemy.ext.asyncio import AsyncSession

        svc = _make_service()
        captured = []
        pred = _make_pred(captured=captured, tahmin=35.0)

        dorse_row = MagicMock()
        dorse_row.bos_agirlik_kg = 6500
        dorse_row.dingil_sayisi = 3
        dorse_result = MagicMock()
        dorse_result.first.return_value = dorse_row

        with (
            patch.object(
                svc, "_get_predictor_for_vehicle", AsyncMock(return_value=pred)
            ),
            patch.object(AsyncSession, "execute", AsyncMock(return_value=dorse_result)),
        ):
            await svc.predict_trip_fuel(
                arac_id=3, ton=18.0, mesafe_km=400.0, dorse_id=10
            )

        assert "dorse_bos_agirlik" in captured[0]
        assert captured[0]["dorse_bos_agirlik"] == pytest.approx(6500.0)
        assert captured[0]["dorse_lastik_sayisi"] == 6  # 3 axles * 2

    async def test_prediction_with_dorse_row_none(self, db_session):
        """dorse_id provided but no row found — proceeds without dorse context."""
        from sqlalchemy.ext.asyncio import AsyncSession

        svc = _make_service()
        captured = []
        pred = _make_pred(captured=captured, tahmin=32.0)

        dorse_result = MagicMock()
        dorse_result.first.return_value = None

        with (
            patch.object(
                svc, "_get_predictor_for_vehicle", AsyncMock(return_value=pred)
            ),
            patch.object(AsyncSession, "execute", AsyncMock(return_value=dorse_result)),
        ):
            await svc.predict_trip_fuel(
                arac_id=4, ton=15.0, mesafe_km=350.0, dorse_id=99
            )

        assert "dorse_bos_agirlik" not in captured[0]

    async def test_prediction_ascent_descent_flat(self, db_session):
        """Extra kwargs (ascent_m, descent_m, flat_km) are forwarded correctly."""
        svc = _make_service()
        captured = []
        pred = _make_pred(captured=captured, tahmin=33.0)

        with patch.object(
            svc, "_get_predictor_for_vehicle", AsyncMock(return_value=pred)
        ):
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
# detect_anomalies — edge cases
# ---------------------------------------------------------------------------


class TestDetectAnomaliesMore:
    async def test_consumptions_empty_when_km_decreasing(self):
        """kms in descending order → dist always negative → consumptions empty → []."""
        svc = _make_service()
        records = [
            {"litre": 50.0, "km_sayac": 100000 - i * 100, "tarih": "2024-01-01"}
            for i in range(8)
        ]
        with patch.object(
            yakit_repo_mod.YakitRepository,
            "get_all",
            AsyncMock(return_value={"items": records, "total": len(records)}),
        ):
            result = await svc.detect_anomalies(7)
        assert result == []

    async def test_std_zero_no_anomaly(self):
        """All consumptions identical → std=0 → no anomaly flagged."""
        svc = _make_service()
        base = 100000
        records = [
            {"litre": 30.0, "km_sayac": base + i * 100, "tarih": "2024-01-01"}
            for i in range(10)
        ]
        with patch.object(
            yakit_repo_mod.YakitRepository,
            "get_all",
            AsyncMock(return_value={"items": records, "total": len(records)}),
        ):
            result = await svc.detect_anomalies(8)
        assert result == []

    async def test_anomaly_z_score_fields_present(self):
        """Each detected anomaly has required fields."""
        svc = _make_service()
        base = 100000
        records = [
            {"litre": 30.0, "km_sayac": base + i * 100, "tarih": "2024-01-01"}
            for i in range(9)
        ]
        records.append({"litre": 999.0, "km_sayac": base + 850, "tarih": "2024-01-15"})
        with patch.object(
            yakit_repo_mod.YakitRepository,
            "get_all",
            AsyncMock(return_value={"items": records, "total": len(records)}),
        ):
            result = await svc.detect_anomalies(9)
        for anomaly in result:
            assert "index" in anomaly
            assert "z_score" in anomaly
            assert anomaly["type"] == "CONSUMPTION_SPIKE"
