"""Internal endpoints -- only reachable within the Docker network.

Added 2026-08-04 for the prediction_ml_service extraction (see
docs/superpowers/plans/2026-07-31-prediction-ml-service-extraction.md,
Task 5 Step 2b Option B): ensemble_service.py's train_for_vehicle/
train_general_model need sefer training data, but the moved code no
longer has an in-process UnitOfWork with fleet/trip access -- it reaches
this over HTTP instead. Same X-Internal-Token pattern as
admin_platform/api/internal_routes.py.
"""

from typing import Annotated, Optional

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel

from app.config import settings
from v2.modules.shared_kernel.infrastructure.unit_of_work import UnitOfWork


async def _require_internal_token(
    x_internal_token: Annotated[Optional[str], Header()] = None,
) -> None:
    secret = settings.INTERNAL_API_SECRET
    if not secret:
        if settings.ENVIRONMENT == "prod":
            raise HTTPException(
                status_code=503, detail="Internal API secret not configured"
            )
        return
    if x_internal_token != secret:
        raise HTTPException(status_code=401, detail="Invalid internal token")


router = APIRouter(
    prefix="/internal/trip",
    dependencies=[Depends(_require_internal_token)],
)


@router.get("/training-data/{arac_id}")
async def training_data(arac_id: int, limit: int = 500) -> list:
    async with UnitOfWork() as uow:
        return await uow.sefer_repo.get_for_training(arac_id, limit=limit)


@router.get("/training-data-all")
async def training_data_all(limit: int = 2000) -> list:
    async with UnitOfWork() as uow:
        return await uow.sefer_repo.get_all_for_training(limit=limit)


@router.get("/seferler/{sefer_id}")
async def get_sefer(sefer_id: int) -> dict:
    async with UnitOfWork() as uow:
        sefer = await uow.sefer_repo.get_by_id(sefer_id)
    if sefer is None:
        raise HTTPException(status_code=404, detail="Sefer not found")
    return sefer


class TahminiTuketimBody(BaseModel):
    tahmini_tuketim: float


@router.patch("/seferler/{sefer_id}/tahmini-tuketim")
async def update_tahmini_tuketim(sefer_id: int, body: TahminiTuketimBody) -> dict:
    async with UnitOfWork() as uow:
        await uow.sefer_repo.update(sefer_id, tahmini_tuketim=body.tahmini_tuketim)
        await uow.commit()
    return {"ok": True}
