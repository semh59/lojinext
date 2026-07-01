from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api import deps
from app.api.middleware.rate_limiter import limiter
from app.core.exceptions import DomainError
from app.core.services.ml_service import MLService
from app.database.models import Kullanici
from app.database.unit_of_work import UnitOfWork
from app.infrastructure.audit.audit_logger import log_audit_event
from app.infrastructure.logging.logger import get_logger
from app.infrastructure.security.permission_checker import require_yetki
from app.schemas.ml_schemas import MLTaskRead, ModelVersionRead

logger = get_logger(__name__)

router = APIRouter()


@router.post(
    "/train/{arac_id}",
    response_model=MLTaskRead,
    dependencies=[Depends(require_yetki(["model_egit", "all", "*"]))],
)
@limiter.limit("3/hour")
async def trigger_training(
    arac_id: int,
    request: Request,
    current_user: Kullanici = Depends(deps.get_current_active_user),
    db: AsyncSession = Depends(deps.get_db),
):
    """
    Manually trigger model training for a specific vehicle.
    Calculates next version automatically.
    """
    try:
        async with UnitOfWork(db) as uow:
            ml_service = MLService(uow)
            task = await ml_service.schedule_training(
                arac_id=arac_id, user_id=current_user.id
            )
        user_id = current_user.id if current_user.id and current_user.id > 0 else None
        try:
            await log_audit_event(
                action="ml.train_triggered",
                module="ml",
                entity_id=str(arac_id),
                user_id=user_id,
                new_value={"arac_id": arac_id},
            )
        except Exception as exc:  # pragma: no cover
            logger.warning("Audit log failed: %s", exc)
        return task
    except HTTPException as e:
        raise e
    except DomainError:
        raise
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Eğitim başlatılamadı: {str(e)}",
        )


@router.get(
    "/queue",
    response_model=List[MLTaskRead],
    dependencies=[Depends(require_yetki("model_goruntule"))],
)
async def get_training_queue(
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(deps.get_db),
):
    """Get recent and pending training tasks."""
    async with UnitOfWork(db) as uow:
        ml_service = MLService(uow)
        return await ml_service.get_training_queue(limit=limit)


@router.get(
    "/versions/{arac_id}",
    response_model=List[ModelVersionRead],
    dependencies=[Depends(require_yetki("model_goruntule"))],
)
async def get_model_versions(
    arac_id: int,
    db: AsyncSession = Depends(deps.get_db),
):
    """Get all model versions for a vehicle."""
    async with UnitOfWork(db) as uow:
        return await uow.model_versiyon_repo.get_all_for_vehicle(arac_id)
