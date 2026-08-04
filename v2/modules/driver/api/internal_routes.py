"""Internal endpoints -- only reachable within the Docker network.

Added 2026-08-04 for the prediction_ml_service extraction (see
docs/superpowers/plans/2026-07-31-prediction-ml-service-extraction.md,
Task 5 Step 2b Option B). Same X-Internal-Token pattern as
admin_platform/api/internal_routes.py.
"""

from typing import Annotated, Optional

from fastapi import APIRouter, Depends, Header, HTTPException

from app.config import settings
from v2.modules.driver.application.driver_stats import get_driver_stats
from v2.modules.driver.application.list_sofor import get_by_id


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
    prefix="/internal/driver",
    dependencies=[Depends(_require_internal_token)],
)


@router.get("/stats")
async def driver_stats(
    sofor_id: Optional[int] = None,
    include_elite_score: bool = True,
) -> list:
    return await get_driver_stats(
        sofor_id=sofor_id, include_elite_score=include_elite_score
    )


@router.get("/{sofor_id}")
async def driver_by_id(sofor_id: int) -> dict:
    sofor = await get_by_id(sofor_id)
    if sofor is None:
        raise HTTPException(status_code=404, detail="Sofor not found")
    return sofor
