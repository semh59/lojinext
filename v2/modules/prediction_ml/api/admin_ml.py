from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api import deps
from app.api.middleware.rate_limiter import limiter
from app.infrastructure.audit.audit_logger import log_audit_event
from v2.modules.auth_rbac.public import Kullanici, require_yetki
from v2.modules.platform_infra.logging.logger import get_logger
from v2.modules.prediction_ml.application.ml_service import MLService
from v2.modules.prediction_ml.schemas import MLTaskRead, ModelVersionRead
from v2.modules.shared_kernel.exceptions import DomainError
from v2.modules.shared_kernel.infrastructure.unit_of_work import UnitOfWork

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
):
    """
    Manually trigger model training for a specific vehicle.
    Calculates next version automatically.
    """
    try:
        # UnitOfWork(db) with an externally-injected session makes
        # uow.commit() a deliberate no-op (nested/non-owning UoW — the
        # OUTER caller is supposed to control the commit boundary). But
        # `deps.get_db()` never commits on the success path either, so the
        # previous `UnitOfWork(db)` here silently never persisted the new
        # training task at all — the endpoint appeared to "succeed" (past
        # the ResponseValidationError this same call also had) while the
        # row never survived past the request. `UnitOfWork()` (no injected
        # session) owns its session so `schedule_training`'s internal
        # `await self.uow.commit()` actually commits. Verified via curl:
        # POST /admin/ml/train/{id} then GET /admin/ml/queue now shows the
        # persisted row.
        # Synthetic super-admin has id<=0 and no row in `kullanicilar` —
        # passing it straight through as tetikleyen_kullanici_id violates
        # egitim_kuyrugu_tetikleyen_kullanici_id_fkey (confirmed via curl:
        # POST as the super-admin 500'd with ForeignKeyViolationError).
        # Same pattern already used for the audit-log call below and in
        # the push/subscribe fix (commit b2351f9).
        user_id = current_user.id if current_user.id and current_user.id > 0 else None
        async with UnitOfWork() as uow:
            ml_service = MLService(uow)
            task = await ml_service.schedule_training(arac_id=arac_id, user_id=user_id)
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
