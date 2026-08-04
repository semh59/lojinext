"""Training endpoints -- thin pass-throughs to MLService/EnsemblePredictorService."""

from typing import List

from fastapi import APIRouter, Depends, HTTPException

from prediction_ml_service.application.ensemble_service import get_ensemble_service
from prediction_ml_service.application.ml_service import MLService
from prediction_ml_service.application.prediction_service import (
    get_prediction_service,
)
from prediction_ml_service.infrastructure.service_uow import ServiceUnitOfWork
from prediction_ml_service.main import check_internal_auth
from prediction_ml_service.schemas import MLTaskRead, ModelVersionRead

router = APIRouter(dependencies=[Depends(check_internal_auth)])


@router.post("/train/{arac_id}")
async def train_vehicle(arac_id: int, payload: dict) -> dict:
    """Synchronous ensemble training + audit log (same shape as before Task 5's move)."""
    service = get_prediction_service()
    return await service.train_xgboost_model(arac_id, user_id=payload.get("user_id"))


@router.post("/train/general")
async def train_general() -> dict:
    service = get_ensemble_service()
    return await service.train_general_model()


@router.post("/train/{arac_id}/schedule", response_model=MLTaskRead)
async def schedule_training(arac_id: int, payload: dict) -> object:
    async with ServiceUnitOfWork() as uow:
        ml_service = MLService(uow)
        try:
            return await ml_service.schedule_training(
                arac_id=arac_id, user_id=payload.get("user_id")
            )
        except HTTPException:
            raise


@router.get("/queue", response_model=List[MLTaskRead])
async def training_queue(limit: int = 50) -> list:
    async with ServiceUnitOfWork() as uow:
        ml_service = MLService(uow)
        return await ml_service.get_training_queue(limit=limit)


@router.get("/versions/{arac_id}", response_model=List[ModelVersionRead])
async def model_versions(arac_id: int) -> list:
    async with ServiceUnitOfWork() as uow:
        return await uow.model_versiyon_repo.get_all_for_vehicle(arac_id)
