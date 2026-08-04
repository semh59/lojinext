"""Internal endpoints -- only reachable within the Docker network.

Added 2026-08-04 for the prediction_ml_service extraction (see
docs/superpowers/plans/2026-07-31-prediction-ml-service-extraction.md,
Task 5 Step 2b Option B): the standalone prediction_ml_service can no
longer import v2.modules.fleet.public directly (different container), so
it reaches vehicle/trailer data over HTTP against these routes instead.
Same X-Internal-Token pattern as admin_platform/api/internal_routes.py.
"""

from typing import Annotated, Optional

from fastapi import APIRouter, Depends, Header, HTTPException

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
    prefix="/internal/fleet",
    dependencies=[Depends(_require_internal_token)],
)


@router.get("/araclar/{arac_id}")
async def get_vehicle(arac_id: int) -> dict:
    async with UnitOfWork() as uow:
        arac = await uow.arac_repo.get_by_id(arac_id)
    if arac is None:
        raise HTTPException(status_code=404, detail="Arac not found")
    return arac


@router.get("/dorseler/{dorse_id}")
async def get_trailer(dorse_id: int) -> dict:
    async with UnitOfWork() as uow:
        dorse = await uow.dorse_repo.get_by_id(dorse_id)
    if dorse is None:
        raise HTTPException(status_code=404, detail="Dorse not found")
    return dorse
