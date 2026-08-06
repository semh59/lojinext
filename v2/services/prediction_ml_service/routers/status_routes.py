"""Ensemble/time-series status + forecast endpoints."""

from typing import Optional

from fastapi import APIRouter, Depends

from prediction_ml_service.application.time_series_service import (
    get_time_series_service,
)
from prediction_ml_service.domain.ensemble_core import (
    LIGHTGBM_AVAILABLE,
    SKLEARN_AVAILABLE,
    XGBOOST_AVAILABLE,
    EnsembleFuelPredictor,
)
from prediction_ml_service.main import check_internal_auth

router = APIRouter(dependencies=[Depends(check_internal_auth)])


@router.get("/ensemble/status")
async def ensemble_status() -> dict:
    predictor = EnsembleFuelPredictor()
    return {
        "models": {
            "physics": True,
            "lightgbm": LIGHTGBM_AVAILABLE,
            "xgboost": XGBOOST_AVAILABLE,
            "gradient_boosting": SKLEARN_AVAILABLE,
            "random_forest": SKLEARN_AVAILABLE,
        },
        "weights": predictor.weights,
        "sklearn_available": SKLEARN_AVAILABLE,
        "lightgbm_available": LIGHTGBM_AVAILABLE,
        "xgboost_available": XGBOOST_AVAILABLE,
        "total_models": sum(
            [
                1,
                1 if LIGHTGBM_AVAILABLE else 0,
                1 if XGBOOST_AVAILABLE else 0,
                1 if SKLEARN_AVAILABLE else 0,
                1 if SKLEARN_AVAILABLE else 0,
            ]
        ),
    }


@router.post("/time-series/forecast")
async def time_series_forecast(arac_id: Optional[int] = None, days: int = 7) -> dict:
    service = get_time_series_service()
    return await service.predict_weekly(arac_id)


@router.get("/time-series/trend")
async def time_series_trend(arac_id: Optional[int] = None, days: int = 30) -> dict:
    service = get_time_series_service()
    return await service.get_trend_analysis(arac_id, days)


@router.get("/time-series/status")
async def time_series_status() -> dict:
    service = get_time_series_service()
    return service.get_model_status()
