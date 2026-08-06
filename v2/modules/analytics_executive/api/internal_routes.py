"""Internal endpoints -- only reachable within the Docker network.

Added 2026-08-04 for the prediction_ml_service extraction (see
docs/superpowers/plans/2026-07-31-prediction-ml-service-extraction.md,
Task 5 Step 2b Option B). Same X-Internal-Token pattern as
admin_platform/api/internal_routes.py.
"""

from typing import Annotated, Any, Optional

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
    prefix="/internal/analytics",
    dependencies=[Depends(_require_internal_token)],
)


class ModelParamsBody(BaseModel):
    arac_id: int
    result: dict[str, Any]


@router.post("/model-params")
async def save_model_params(body: ModelParamsBody) -> dict:
    async with UnitOfWork() as uow:
        await uow.analiz_repo.save_model_params(body.arac_id, body.result)
        await uow.commit()
    return {"ok": True}


@router.get("/daily-summary")
async def daily_summary(days: int = 60, arac_id: Optional[int] = None) -> list:
    async with UnitOfWork() as uow:
        return await uow.analiz_repo.get_daily_summary_for_ml(
            days=days, arac_id=arac_id
        )
