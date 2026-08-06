"""Prediction endpoints -- thin pass-throughs to PredictionService/EnsemblePredictorService."""

from fastapi import APIRouter, Depends

from prediction_ml_service.application.ensemble_service import get_ensemble_service
from prediction_ml_service.application.prediction_service import (
    get_prediction_service,
)
from prediction_ml_service.main import check_internal_auth

router = APIRouter(dependencies=[Depends(check_internal_auth)])


@router.post("/predict")
async def predict(payload: dict) -> dict:
    service = get_prediction_service()
    return await service.predict_consumption(**payload)


@router.post("/predict/explain")
async def predict_explain(payload: dict) -> dict:
    service = get_prediction_service()
    return await service.explain_consumption(**payload)


@router.post("/predict/batch")
async def predict_batch(payload: dict) -> list:
    service = get_ensemble_service()
    return await service.predict_batch(payload["requests"])
