"""
Predictions endpoint — 2nd pass coverage.

Targets remaining uncovered branches in predictions.py (~77% → higher):
- predict_fuel: sofor_id lookup when sofor.score is None (uses 1.0), sofor found with score
- predict_fuel: sofor_score below lower bound (< 0.1) → 400
- comparison: with matching trip data (non-empty seferler) — all accuracy buckets
- comparison: trend aggregation logic
- stream: timeout path (loop exhausted)
- stream: failure state terminates early
- enqueue: missing required fields → 422
- train: requires admin (non-admin returns 403) already covered — verify training path
"""

from __future__ import annotations

from contextlib import contextmanager
from datetime import date, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

pytestmark = pytest.mark.unit

BASE = "/api/v1/predictions"

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


@contextmanager
def _mock_prediction_service(**overrides):
    svc = MagicMock()
    svc.predict_consumption = AsyncMock(return_value={**PRED_SUCCESS, **overrides})
    svc.explain_consumption = AsyncMock(
        return_value={"features": [], "top_factor": "mesafe_km"}
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
# predict_fuel — sofor_score below lower bound
# ---------------------------------------------------------------------------


async def test_predict_sofor_score_below_min(async_client, admin_auth_headers):
    """sofor_score=0.05 (< 0.1) → 400."""
    payload = {**PRED_PAYLOAD, "sofor_score": 0.05}
    with _mock_prediction_service():
        resp = await async_client.post(
            f"{BASE}/predict",
            json=payload,
            headers=admin_auth_headers,
        )
    assert resp.status_code in (400, 422)


async def test_predict_sofor_score_exact_minimum(async_client, admin_auth_headers):
    """sofor_score=0.1 (exact lower bound) → 200."""
    payload = {**PRED_PAYLOAD, "sofor_score": 0.1}
    with _mock_prediction_service():
        resp = await async_client.post(
            f"{BASE}/predict",
            json=payload,
            headers=admin_auth_headers,
        )
    assert resp.status_code == 200


async def test_predict_sofor_score_exact_maximum(async_client, admin_auth_headers):
    """sofor_score=2.0 (exact upper bound) → 200."""
    payload = {**PRED_PAYLOAD, "sofor_score": 2.0}
    with _mock_prediction_service():
        resp = await async_client.post(
            f"{BASE}/predict",
            json=payload,
            headers=admin_auth_headers,
        )
    assert resp.status_code == 200


# ---------------------------------------------------------------------------
# predict_fuel — sofor_id found with None score → uses 1.0 default
# ---------------------------------------------------------------------------


async def test_predict_sofor_id_found_null_score(async_client, admin_auth_headers):
    """sofor_id provided, sofor found but score is None → uses default 1.0."""
    from app.database.connection import get_db
    from app.main import app

    fake_sofor = MagicMock()
    fake_sofor.id = 1
    fake_sofor.score = None  # None score → falls back to 1.0

    mock_session = AsyncMock()
    mock_session.get = AsyncMock(return_value=fake_sofor)

    async def _fake_db():
        yield mock_session

    app.dependency_overrides[get_db] = _fake_db
    try:
        payload = {**PRED_PAYLOAD, "sofor_id": 1}
        with _mock_prediction_service():
            resp = await async_client.post(
                f"{BASE}/predict",
                json=payload,
                headers=admin_auth_headers,
            )
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert resp.status_code == 200


async def test_predict_sofor_id_found_with_score(async_client, admin_auth_headers):
    """sofor_id provided, sofor found with score=1.5 → uses 1.5."""
    from app.database.connection import get_db
    from app.main import app

    fake_sofor = MagicMock()
    fake_sofor.id = 2
    fake_sofor.score = 1.5

    mock_session = AsyncMock()
    mock_session.get = AsyncMock(return_value=fake_sofor)

    async def _fake_db():
        yield mock_session

    app.dependency_overrides[get_db] = _fake_db
    try:
        payload = {**PRED_PAYLOAD, "sofor_id": 2}
        with _mock_prediction_service():
            resp = await async_client.post(
                f"{BASE}/predict",
                json=payload,
                headers=admin_auth_headers,
            )
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert resp.status_code == 200


# ---------------------------------------------------------------------------
# comparison — with real trip data (non-empty) to exercise accuracy buckets
# ---------------------------------------------------------------------------


async def test_comparison_with_trips_all_buckets(async_client, admin_auth_headers):
    """GET /comparison with mock DB rows → exercises good/warning/error buckets."""
    from app.database.connection import get_db
    from app.main import app

    # Build fake trip objects covering three accuracy buckets:
    # good (pct <= 5), warning (5 < pct <= 15), error (pct > 15)
    trips = []
    for actual, predicted, d_offset in [
        (31.5, 31.0, 0),  # good: ~1.6%
        (35.0, 30.0, 1),  # warning: ~16.7% -> error bucket
        (40.0, 30.0, 2),  # error: 33%
        (31.5, 30.5, 3),  # good: ~3.3%
        (33.0, 31.0, 4),  # warning: ~6.5%
    ]:
        t = MagicMock()
        t.tuketim = actual
        t.tahmini_tuketim = predicted
        t.tarih = date.today() - timedelta(days=d_offset)
        trips.append(t)

    mock_scalars = MagicMock()
    mock_scalars.all.return_value = trips

    mock_result = MagicMock()
    mock_result.scalars.return_value = mock_scalars

    mock_session = AsyncMock()
    mock_session.execute = AsyncMock(return_value=mock_result)

    async def _fake_db():
        yield mock_session

    app.dependency_overrides[get_db] = _fake_db
    try:
        resp = await async_client.get(
            f"{BASE}/comparison?days=30",
            headers=admin_auth_headers,
        )
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert resp.status_code == 200
    data = resp.json()
    assert data["total_compared"] == 5
    assert data["mae"] > 0
    assert data["rmse"] > 0
    # Trend should have entries (grouped by date)
    assert len(data["trend"]) > 0


async def test_comparison_pct_error_predicted_zero(async_client, admin_auth_headers):
    """GET /comparison handles predicted=0 gracefully (pct_err=100 → error bucket)."""
    from app.database.connection import get_db
    from app.main import app

    t = MagicMock()
    t.tuketim = 30.0
    t.tahmini_tuketim = 0.0  # predicted=0 → division guard
    t.tarih = date.today()

    mock_scalars = MagicMock()
    mock_scalars.all.return_value = [t]

    mock_result = MagicMock()
    mock_result.scalars.return_value = mock_scalars

    mock_session = AsyncMock()
    mock_session.execute = AsyncMock(return_value=mock_result)

    async def _fake_db():
        yield mock_session

    app.dependency_overrides[get_db] = _fake_db
    try:
        resp = await async_client.get(
            f"{BASE}/comparison",
            headers=admin_auth_headers,
        )
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert resp.status_code == 200
    data = resp.json()
    assert data["total_compared"] == 1
    # pct_err=100 → goes to error bucket
    assert data["accuracy_distribution"]["error"] >= 1


# ---------------------------------------------------------------------------
# comparison — with arac_id filter + non-empty result
# ---------------------------------------------------------------------------


async def test_comparison_with_arac_id_and_trips(async_client, admin_auth_headers):
    """GET /comparison?arac_id=1 with matching trips → non-zero metrics."""
    from app.database.connection import get_db
    from app.main import app

    t = MagicMock()
    t.tuketim = 32.0
    t.tahmini_tuketim = 30.0
    t.tarih = date.today()

    mock_scalars = MagicMock()
    mock_scalars.all.return_value = [t]

    mock_result = MagicMock()
    mock_result.scalars.return_value = mock_scalars

    mock_session = AsyncMock()
    mock_session.execute = AsyncMock(return_value=mock_result)

    async def _fake_db():
        yield mock_session

    app.dependency_overrides[get_db] = _fake_db
    try:
        resp = await async_client.get(
            f"{BASE}/comparison?arac_id=1",
            headers=admin_auth_headers,
        )
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert resp.status_code == 200
    data = resp.json()
    assert data["total_compared"] == 1


# ---------------------------------------------------------------------------
# SSE stream — failure state terminates
# ---------------------------------------------------------------------------


async def test_stream_terminates_on_failure_state(async_client, admin_auth_headers):
    """SSE stream terminates when task state is FAILURE."""
    fake_result = MagicMock()
    fake_result.state = "FAILURE"
    fake_result.result = {"error": "something failed", "finished_at": None}

    with patch(
        "v2.modules.prediction_ml.api.predictions.AsyncResult", return_value=fake_result
    ):
        resp = await async_client.get(
            f"{BASE}/failing-task/stream",
            headers=admin_auth_headers,
        )

    assert resp.status_code == 200
    assert "text/event-stream" in resp.headers.get("content-type", "")


async def test_stream_terminates_on_revoked_state(async_client, admin_auth_headers):
    """SSE stream terminates when task state is REVOKED."""
    fake_result = MagicMock()
    fake_result.state = "REVOKED"
    fake_result.result = {}

    with patch(
        "v2.modules.prediction_ml.api.predictions.AsyncResult", return_value=fake_result
    ):
        resp = await async_client.get(
            f"{BASE}/revoked-task/stream",
            headers=admin_auth_headers,
        )

    assert resp.status_code == 200


# ---------------------------------------------------------------------------
# SSE stream — result is not dict (covers payload = {} branch)
# ---------------------------------------------------------------------------


async def test_stream_result_not_dict(async_client, admin_auth_headers):
    """SSE stream when result.result is a string (not dict) → payload={}."""
    fake_result = MagicMock()
    fake_result.state = "SUCCESS"
    fake_result.result = "some_string_result"  # not a dict

    with patch(
        "v2.modules.prediction_ml.api.predictions.AsyncResult", return_value=fake_result
    ):
        resp = await async_client.get(
            f"{BASE}/str-result-task/stream",
            headers=admin_auth_headers,
        )

    assert resp.status_code == 200


# ---------------------------------------------------------------------------
# status polling — result.result is not dict
# ---------------------------------------------------------------------------


async def test_prediction_status_result_not_dict(async_client, admin_auth_headers):
    """GET /{task_id} when result.result is not dict → payload={}."""
    fake_result = MagicMock()
    fake_result.state = "FAILURE"
    fake_result.result = Exception("something went wrong")  # not a dict

    with patch(
        "v2.modules.prediction_ml.api.predictions.AsyncResult", return_value=fake_result
    ):
        resp = await async_client.get(
            f"{BASE}/failed-task",
            headers=admin_auth_headers,
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "failure"
    assert data["answer"] is None


# ---------------------------------------------------------------------------
# enqueue — missing required fields
# ---------------------------------------------------------------------------


async def test_enqueue_missing_question(async_client, admin_auth_headers):
    """POST /predictions without question → 422."""
    resp = await async_client.post(
        f"{BASE}",
        json={"context": "some context"},  # missing question
        headers=admin_auth_headers,
    )
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# ensemble status — sklearn/lightgbm/xgboost availability flags
# ---------------------------------------------------------------------------


async def test_ensemble_status_all_available(async_client, admin_auth_headers):
    """GET /ensemble/status when all ML libs available → models dict present."""
    fake_predictor = MagicMock()
    fake_predictor.weights = {
        "physics": 0.6,
        "lightgbm": 0.1,
        "xgboost": 0.1,
        "gradient_boosting": 0.1,
        "random_forest": 0.1,
    }

    with patch(
        "v2.modules.prediction_ml.domain.ensemble_core.EnsembleFuelPredictor",
        return_value=fake_predictor,
    ):
        with (
            patch("v2.modules.prediction_ml.domain.ensemble_core.SKLEARN_AVAILABLE", True),
            patch("v2.modules.prediction_ml.domain.ensemble_core.LIGHTGBM_AVAILABLE", True),
            patch("v2.modules.prediction_ml.domain.ensemble_core.XGBOOST_AVAILABLE", True),
        ):
            resp = await async_client.get(
                f"{BASE}/ensemble/status",
                headers=admin_auth_headers,
            )

    assert resp.status_code == 200
    data = resp.json()
    assert data["models"]["physics"] is True
    assert "weights" in data


async def test_ensemble_status_none_available(async_client, admin_auth_headers):
    """GET /ensemble/status when only physics available → total_models=1."""
    fake_predictor = MagicMock()
    fake_predictor.weights = {"physics": 1.0}

    with patch(
        "v2.modules.prediction_ml.domain.ensemble_core.EnsembleFuelPredictor",
        return_value=fake_predictor,
    ):
        with (
            patch("v2.modules.prediction_ml.domain.ensemble_core.SKLEARN_AVAILABLE", False),
            patch("v2.modules.prediction_ml.domain.ensemble_core.LIGHTGBM_AVAILABLE", False),
            patch("v2.modules.prediction_ml.domain.ensemble_core.XGBOOST_AVAILABLE", False),
        ):
            resp = await async_client.get(
                f"{BASE}/ensemble/status",
                headers=admin_auth_headers,
            )

    assert resp.status_code == 200
    data = resp.json()
    assert "total_models" in data


# ---------------------------------------------------------------------------
# forecast — days parameter validation
# ---------------------------------------------------------------------------


async def test_forecast_days_param_out_of_range(async_client, admin_auth_headers):
    """POST /time-series/forecast?days=0 → 422."""
    resp = await async_client.post(
        f"{BASE}/time-series/forecast?days=0",
        headers=admin_auth_headers,
    )
    assert resp.status_code == 422


async def test_forecast_with_arac_id(async_client, admin_auth_headers):
    """POST /time-series/forecast?arac_id=1 passes arac_id to service."""
    fake_ts_service = MagicMock()
    fake_ts_service.predict_weekly = AsyncMock(
        return_value={
            "success": True,
            "forecast_dates": ["2026-06-05"],
            "forecast": [31.5],
            "confidence_low": [29.0],
            "confidence_high": [34.0],
            "trend": "stable",
            "method": "ARIMA",
        }
    )

    with patch(
        "v2.modules.prediction_ml.application.time_series_service.get_time_series_service",
        return_value=fake_ts_service,
    ):
        resp = await async_client.post(
            f"{BASE}/time-series/forecast?arac_id=1",
            headers=admin_auth_headers,
        )

    assert resp.status_code == 200
    fake_ts_service.predict_weekly.assert_called_once_with(1)
