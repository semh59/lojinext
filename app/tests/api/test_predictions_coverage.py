"""
Predictions endpoint coverage tests.

Targets lines missed in app/api/v1/endpoints/predictions.py (28% → ≥70%).
All service / Celery calls are mocked — no real DB needed.
"""

from contextlib import contextmanager
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

pytestmark = pytest.mark.unit

# ---------------------------------------------------------------------------
# Minimal valid PredictionRequest payload
# ---------------------------------------------------------------------------
PRED_PAYLOAD = {
    "arac_id": 1,
    "mesafe_km": 450.0,
    "ton": 10.0,
    "ascent_m": 200.0,
    "descent_m": 150.0,
}

PRED_SUCCESS = {
    "status": "success",
    "tahmini_tuketim": 31.5,
    "tahmini_litre": 141.75,
    "model_used": "ensemble",
    "model_version": "v1",
    "confidence_score": 0.85,
    "confidence_low": 29.0,
    "confidence_high": 34.0,
    "warning_level": "GREEN",
    "fallback_triggered": False,
    "faktorler": None,
    "explanation_summary": "Test",
    "prediction_liters": None,
}


# ---------------------------------------------------------------------------
# Helper: override PredictionService constructor
# ---------------------------------------------------------------------------


@contextmanager
def _mock_prediction_service(**overrides):
    """Patch the PredictionService class so endpoints get a mock instance."""
    svc = MagicMock()
    svc.predict_consumption = AsyncMock(return_value={**PRED_SUCCESS, **overrides})
    # Tier E madde 33: shape matches ensemble_core.explain_prediction's real
    # return dict — endpoint now has response_model=ExplainPredictionResponse.
    svc.explain_consumption = AsyncMock(
        return_value={
            "prediction": 32.5,
            "unit": "L/100km",
            "contributions": {"mesafe_km": 0.4, "ML Düzeltmesi": 0.1},
            "confidence": 0.85,
        }
    )
    svc.train_xgboost_model = AsyncMock(
        return_value={
            "status": "success",
            "model_type": "ensemble",
            "r2_score": 0.91,
            "sample_count": 120,
            "metrics": {"mae": 1.2},
        }
    )

    with patch("v2.modules.prediction_ml.api.predictions.PredictionService", return_value=svc):
        yield svc


# ---------------------------------------------------------------------------
# POST /api/v1/predictions/predict
# ---------------------------------------------------------------------------


class TestPredictFuel:
    async def test_happy_path_returns_200(self, async_client, admin_auth_headers):
        with _mock_prediction_service():
            resp = await async_client.post(
                "/api/v1/predictions/predict",
                json=PRED_PAYLOAD,
                headers=admin_auth_headers,
            )
        assert resp.status_code == 200
        data = resp.json()
        assert data["tahmini_tuketim"] == 31.5

    async def test_requires_auth(self, async_client):
        resp = await async_client.post("/api/v1/predictions/predict", json=PRED_PAYLOAD)
        assert resp.status_code == 401

    async def test_invalid_sofor_score_returns_400(
        self, async_client, admin_auth_headers
    ):
        payload = {**PRED_PAYLOAD, "sofor_score": 5.0}  # > 2.0
        with _mock_prediction_service():
            resp = await async_client.post(
                "/api/v1/predictions/predict",
                json=payload,
                headers=admin_auth_headers,
            )
        # Pydantic validates ≤2.0, so 422 is also acceptable
        assert resp.status_code in (400, 422)

    async def test_sofor_score_valid_range_accepted(
        self, async_client, admin_auth_headers
    ):
        payload = {**PRED_PAYLOAD, "sofor_score": 1.2}
        with _mock_prediction_service():
            resp = await async_client.post(
                "/api/v1/predictions/predict",
                json=payload,
                headers=admin_auth_headers,
            )
        assert resp.status_code == 200

    async def test_model_not_trained_returns_422(
        self, async_client, admin_auth_headers
    ):
        err_result = {
            "status": "error",
            "code": "model_not_trained",
            "message": "Not trained",
        }
        with _mock_prediction_service() as svc:
            svc.predict_consumption = AsyncMock(return_value=err_result)
            resp = await async_client.post(
                "/api/v1/predictions/predict",
                json=PRED_PAYLOAD,
                headers=admin_auth_headers,
            )
        assert resp.status_code == 422

    async def test_service_unavailable_returns_503(
        self, async_client, admin_auth_headers
    ):
        err_result = {
            "status": "error",
            "code": "service_unavailable",
            "message": "Down",
        }
        with _mock_prediction_service() as svc:
            svc.predict_consumption = AsyncMock(return_value=err_result)
            resp = await async_client.post(
                "/api/v1/predictions/predict",
                json=PRED_PAYLOAD,
                headers=admin_auth_headers,
            )
        assert resp.status_code == 503

    async def test_generic_error_returns_500(self, async_client, admin_auth_headers):
        err_result = {"status": "error", "code": "unknown", "message": "Oops"}
        with _mock_prediction_service() as svc:
            svc.predict_consumption = AsyncMock(return_value=err_result)
            resp = await async_client.post(
                "/api/v1/predictions/predict",
                json=PRED_PAYLOAD,
                headers=admin_auth_headers,
            )
        assert resp.status_code == 500

    async def test_missing_required_field_returns_422(
        self, async_client, admin_auth_headers
    ):
        resp = await async_client.post(
            "/api/v1/predictions/predict",
            json={"mesafe_km": 450.0},  # no arac_id
            headers=admin_auth_headers,
        )
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# POST /api/v1/predictions/explain
# ---------------------------------------------------------------------------


class TestExplainPrediction:
    async def test_explain_returns_200(self, async_client, admin_auth_headers):
        with _mock_prediction_service():
            resp = await async_client.post(
                "/api/v1/predictions/explain",
                json=PRED_PAYLOAD,
                headers=admin_auth_headers,
            )
        assert resp.status_code == 200
        data = resp.json()
        # Tier E madde 33: real ExplainPredictionResponse shape — endpoint
        # returns prediction/unit/contributions/confidence, not "features".
        assert "contributions" in data
        assert "prediction" in data

    async def test_explain_requires_auth(self, async_client):
        resp = await async_client.post("/api/v1/predictions/explain", json=PRED_PAYLOAD)
        assert resp.status_code == 401

    async def test_explain_with_sofor_id(self, async_client, admin_auth_headers):
        payload = {**PRED_PAYLOAD, "sofor_id": None, "sofor_score": 1.1}
        with _mock_prediction_service():
            resp = await async_client.post(
                "/api/v1/predictions/explain",
                json=payload,
                headers=admin_auth_headers,
            )
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# POST /api/v1/predictions  (enqueue)
# ---------------------------------------------------------------------------


class TestEnqueuePrediction:
    async def test_enqueue_returns_202(self, async_client, admin_auth_headers):
        fake_task = MagicMock()
        fake_task.id = "test-task-uuid-1234"

        with patch("v2.modules.prediction_ml.api.predictions.celery_app") as mock_celery:
            mock_celery.send_task.return_value = fake_task
            resp = await async_client.post(
                "/api/v1/predictions",
                json={"question": "Sefer yakıt tahmini?", "context": "fleet"},
                headers=admin_auth_headers,
            )

        assert resp.status_code == 202
        assert resp.json()["task_id"] == "test-task-uuid-1234"

    async def test_enqueue_requires_auth(self, async_client):
        resp = await async_client.post(
            "/api/v1/predictions",
            json={"question": "test"},
        )
        assert resp.status_code == 401


# ---------------------------------------------------------------------------
# GET /api/v1/predictions/{task_id}  (status polling)
# ---------------------------------------------------------------------------


class TestPredictionStatus:
    async def test_pending_task_returns_pending_status(
        self, async_client, admin_auth_headers
    ):
        fake_result = MagicMock()
        fake_result.state = "PENDING"
        fake_result.result = None

        with patch(
            "v2.modules.prediction_ml.api.predictions.AsyncResult", return_value=fake_result
        ):
            resp = await async_client.get(
                "/api/v1/predictions/abc-123",
                headers=admin_auth_headers,
            )

        assert resp.status_code == 200
        assert resp.json()["status"] == "pending"

    async def test_success_task_returns_answer(self, async_client, admin_auth_headers):
        fake_result = MagicMock()
        fake_result.state = "SUCCESS"
        fake_result.result = {
            "answer": "31.5 L/100km",
            "finished_at": "2026-06-01T10:00:00Z",
        }

        with patch(
            "v2.modules.prediction_ml.api.predictions.AsyncResult", return_value=fake_result
        ):
            resp = await async_client.get(
                "/api/v1/predictions/abc-success",
                headers=admin_auth_headers,
            )

        data = resp.json()
        assert resp.status_code == 200
        assert data["answer"] == "31.5 L/100km"

    async def test_status_requires_auth(self, async_client):
        resp = await async_client.get("/api/v1/predictions/some-task-id")
        assert resp.status_code == 401


# ---------------------------------------------------------------------------
# POST /api/v1/predictions/train/{arac_id}
# ---------------------------------------------------------------------------


class TestTrainVehicleModel:
    async def test_train_success_returns_200(self, async_client, admin_auth_headers):
        with _mock_prediction_service():
            resp = await async_client.post(
                "/api/v1/predictions/train/1",
                headers=admin_auth_headers,
            )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "success"
        assert data["r2_score"] == 0.91

    async def test_train_failure_returns_500(self, async_client, admin_auth_headers):
        with _mock_prediction_service() as svc:
            svc.train_xgboost_model = AsyncMock(
                return_value={"status": "error", "message": "Not enough data"}
            )
            resp = await async_client.post(
                "/api/v1/predictions/train/1",
                headers=admin_auth_headers,
            )
        assert resp.status_code == 500

    async def test_train_requires_admin(self, async_client, normal_auth_headers):
        with _mock_prediction_service():
            resp = await async_client.post(
                "/api/v1/predictions/train/1",
                headers=normal_auth_headers,
            )
        assert resp.status_code == 403


# ---------------------------------------------------------------------------
# GET /api/v1/predictions/comparison
# ---------------------------------------------------------------------------


class TestPredictionComparison:
    async def test_comparison_empty_db_returns_zero_metrics(
        self, async_client, admin_auth_headers
    ):
        # No seferler in DB → should return 0 metrics
        resp = await async_client.get(
            "/api/v1/predictions/comparison",
            headers=admin_auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_compared"] == 0
        assert data["mae"] == 0.0

    async def test_comparison_requires_auth(self, async_client):
        resp = await async_client.get("/api/v1/predictions/comparison")
        assert resp.status_code == 401

    async def test_comparison_days_param_validation(
        self, async_client, admin_auth_headers
    ):
        resp = await async_client.get(
            "/api/v1/predictions/comparison?days=0",
            headers=admin_auth_headers,
        )
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# GET /api/v1/predictions/ensemble/status
# ---------------------------------------------------------------------------


class TestEnsembleStatus:
    async def test_ensemble_status_returns_200(self, async_client, admin_auth_headers):
        fake_predictor = MagicMock()
        fake_predictor.weights = {"physics": 0.8, "xgboost": 0.05}

        with patch(
            "app.core.ml.ensemble_predictor.EnsembleFuelPredictor",
            return_value=fake_predictor,
        ):
            resp = await async_client.get(
                "/api/v1/predictions/ensemble/status",
                headers=admin_auth_headers,
            )

        assert resp.status_code == 200
        data = resp.json()
        assert "models" in data
        assert "weights" in data

    async def test_ensemble_status_requires_auth(self, async_client):
        resp = await async_client.get("/api/v1/predictions/ensemble/status")
        assert resp.status_code == 401


# ---------------------------------------------------------------------------
# GET /api/v1/predictions/time-series/status
# ---------------------------------------------------------------------------


class TestTimeSeriesStatus:
    async def test_time_series_status_returns_200(
        self, async_client, admin_auth_headers
    ):
        # Tier E madde 33: shape matches AdvancedLSTM.status()'s real return
        # dict — endpoint now has response_model=TimeSeriesStatusResponse.
        fake_ts_service = MagicMock()
        fake_ts_service.get_model_status.return_value = {
            "is_trained": False,
            "training_epochs": 0,
            "last_loss": None,
            "n_training_samples": 0,
            "train_time_s": 0.0,
            "bilstm_mae": None,
            "tcn_mae": None,
            "torch_available": False,
            "deep_learning_active": False,
            "min_days_for_deep": 30,
        }

        # get_time_series_service is imported inside the endpoint function body,
        # so patch at the source module level.
        with patch(
            "v2.modules.prediction_ml.application.time_series_service.get_time_series_service",
            return_value=fake_ts_service,
        ):
            resp = await async_client.get(
                "/api/v1/predictions/time-series/status",
                headers=admin_auth_headers,
            )

        assert resp.status_code == 200

    async def test_time_series_status_requires_auth(self, async_client):
        resp = await async_client.get("/api/v1/predictions/time-series/status")
        assert resp.status_code == 401


# ---------------------------------------------------------------------------
# GET /api/v1/predictions/time-series/forecast
# ---------------------------------------------------------------------------


class TestTimeSeriesForecast:
    async def test_forecast_success_returns_200(self, async_client, admin_auth_headers):
        fake_ts_service = MagicMock()
        fake_ts_service.predict_weekly = AsyncMock(
            return_value={
                "success": True,
                "forecast_dates": ["2026-06-04", "2026-06-05"],
                "forecast": [31.5, 32.0],
                "confidence_low": [29.0, 29.5],
                "confidence_high": [34.0, 34.5],
                "trend": "stable",
                "method": "ARIMA",
            }
        )

        with patch(
            "v2.modules.prediction_ml.application.time_series_service.get_time_series_service",
            return_value=fake_ts_service,
        ):
            resp = await async_client.post(
                "/api/v1/predictions/time-series/forecast",
                headers=admin_auth_headers,
            )

        assert resp.status_code == 200
        data = resp.json()
        assert "series" in data
        assert data["trend"] == "stable"

    async def test_forecast_failure_returns_error_body(
        self, async_client, admin_auth_headers
    ):
        fake_ts_service = MagicMock()
        fake_ts_service.predict_weekly = AsyncMock(
            return_value={
                "success": False,
                "error": "Not enough data",
                "error_code": "INSUFFICIENT_DATA",
                "status_code": 503,
            }
        )

        with patch(
            "v2.modules.prediction_ml.application.time_series_service.get_time_series_service",
            return_value=fake_ts_service,
        ):
            resp = await async_client.post(
                "/api/v1/predictions/time-series/forecast",
                headers=admin_auth_headers,
            )

        assert resp.status_code == 503
        data = resp.json()
        assert data["success"] is False

    async def test_forecast_requires_auth(self, async_client):
        resp = await async_client.post("/api/v1/predictions/time-series/forecast")
        assert resp.status_code == 401


# ---------------------------------------------------------------------------
# GET /api/v1/predictions/time-series/trend
# ---------------------------------------------------------------------------


class TestTimeSeriesTrend:
    async def test_trend_success_returns_200(self, async_client, admin_auth_headers):
        # Tier E madde 33: shape matches TimeSeriesService.get_trend_analysis's
        # real success return dict — endpoint now has
        # response_model=TrendAnalysisResponse.
        fake_ts_service = MagicMock()
        fake_ts_service.get_trend_analysis = AsyncMock(
            return_value={
                "success": True,
                "trend": "increasing",
                "trend_tr": "Artıyor",
                "slope": 0.15,
                "current_avg": 32.0,
                "previous_avg": 31.0,
                "moving_average_7": [31.5, 31.8, 32.0],
                "daily_values": [31.0, 32.0, 33.0],
                "daily_total_values": [100.0, 105.0, 110.0],
                "dates": ["2026-06-01", "2026-06-02", "2026-06-03"],
                "days_analyzed": 3,
            }
        )

        with patch(
            "v2.modules.prediction_ml.application.time_series_service.get_time_series_service",
            return_value=fake_ts_service,
        ):
            resp = await async_client.get(
                "/api/v1/predictions/time-series/trend",
                headers=admin_auth_headers,
            )

        # success=True: endpoint returns the dict directly (200)
        assert resp.status_code == 200

    async def test_trend_failure_returns_error_body(
        self, async_client, admin_auth_headers
    ):
        fake_ts_service = MagicMock()
        fake_ts_service.get_trend_analysis = AsyncMock(
            return_value={
                "success": False,
                "error": "No data",
                "error_code": "NO_DATA",
                "status_code": 503,
            }
        )

        with patch(
            "v2.modules.prediction_ml.application.time_series_service.get_time_series_service",
            return_value=fake_ts_service,
        ):
            resp = await async_client.get(
                "/api/v1/predictions/time-series/trend",
                headers=admin_auth_headers,
            )

        assert resp.status_code == 503

    async def test_trend_requires_auth(self, async_client):
        resp = await async_client.get("/api/v1/predictions/time-series/trend")
        assert resp.status_code == 401


# ---------------------------------------------------------------------------
# _build_time_series_error_response helper
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# GET /api/v1/predictions/{task_id}/stream  (SSE)
# ---------------------------------------------------------------------------


class TestPredictionStream:
    async def test_stream_terminates_on_success_state(
        self, async_client, admin_auth_headers
    ):
        fake_result = MagicMock()
        fake_result.state = "SUCCESS"
        fake_result.result = {"answer": "done", "finished_at": "2026-06-01T10:00:00Z"}

        with patch(
            "v2.modules.prediction_ml.api.predictions.AsyncResult", return_value=fake_result
        ):
            resp = await async_client.get(
                "/api/v1/predictions/stream-task/stream",
                headers=admin_auth_headers,
            )

        assert resp.status_code == 200
        # SSE media type
        assert "text/event-stream" in resp.headers.get("content-type", "")

    async def test_stream_requires_auth(self, async_client):
        resp = await async_client.get("/api/v1/predictions/some-id/stream")
        assert resp.status_code == 401


# ---------------------------------------------------------------------------
# POST /api/v1/predictions/predict — sofor_id DB lookup paths
# (needs actual DB session, marked integration so CI can skip if no DB)
# ---------------------------------------------------------------------------


class TestPredictFuelDriverDBLookup:
    @pytest.mark.integration
    async def test_sofor_id_found_uses_score(
        self, async_client, admin_auth_headers, db_session
    ):
        """When sofor_id is provided and exists, use sofor.score."""
        from app.database.models import Sofor

        sofor = Sofor(
            ad_soyad="Test Sofor",
            ehliyet_sinifi="E",
            score=1.3,
            aktif=True,
        )
        db_session.add(sofor)
        await db_session.flush()

        payload = {**PRED_PAYLOAD, "sofor_id": sofor.id}
        with _mock_prediction_service():
            resp = await async_client.post(
                "/api/v1/predictions/predict",
                json=payload,
                headers=admin_auth_headers,
            )
        assert resp.status_code == 200

    @pytest.mark.integration
    async def test_sofor_id_not_found_returns_404(
        self, async_client, admin_auth_headers
    ):
        payload = {**PRED_PAYLOAD, "sofor_id": 999999}
        with _mock_prediction_service():
            resp = await async_client.post(
                "/api/v1/predictions/predict",
                json=payload,
                headers=admin_auth_headers,
            )
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# GET /api/v1/predictions/comparison — with arac_id filter
# ---------------------------------------------------------------------------


class TestPredictionComparisonWithAracId:
    async def test_comparison_with_arac_id_filter_returns_200(
        self, async_client, admin_auth_headers
    ):
        resp = await async_client.get(
            "/api/v1/predictions/comparison?arac_id=1",
            headers=admin_auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_compared"] == 0  # no matching data in test DB


class TestBuildTimeSeriesErrorResponse:
    def test_builds_correct_body(self):
        from v2.modules.prediction_ml.api.predictions import (
            _build_time_series_error_response,
        )

        result = {
            "error": "Not enough data",
            "error_code": "INSUFFICIENT_DATA",
            "status_code": 503,
        }
        resp = _build_time_series_error_response(result, "fallback message")
        import json

        body = json.loads(resp.body)
        assert resp.status_code == 503
        assert body["success"] is False
        assert body["error_code"] == "INSUFFICIENT_DATA"
        assert "request_id" in body
        assert "timestamp" in body

    def test_uses_default_message_when_no_error_key(self):
        from v2.modules.prediction_ml.api.predictions import (
            _build_time_series_error_response,
        )

        resp = _build_time_series_error_response({}, "default msg")
        import json

        body = json.loads(resp.body)
        assert body["error_message"] == "default msg"
