from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException

from app.api.deps import UOWDep, get_sefer_service, require_permissions
from app.infrastructure.audit.audit_logger import log_audit_event
from v2.modules.admin_platform.public import (
    IdempotencyKeyConflictError,
    IdempotencyKeyInProgressError,
    finalize_response,
    release_reservation,
    reserve_or_get_cached,
)
from v2.modules.auth_rbac.public import Kullanici
from v2.modules.platform_infra.logging.logger import get_logger
from v2.modules.platform_infra.resilience.rate_limiter import RateLimiterDependency
from v2.modules.shared_kernel.exceptions import DomainError
from v2.modules.trip.public import SeferCreate, SeferResponse, SeferService, SeferUpdate

logger = get_logger(__name__)

router = APIRouter()


@router.post(
    "/",
    response_model=SeferResponse,
    status_code=201,
)
async def create_sefer(
    _: Annotated[
        None, Depends(RateLimiterDependency("create_trip", rate=2.0, period=1.0))
    ],
    sefer: SeferCreate,
    current_admin: Annotated[Kullanici, Depends(require_permissions("sefer:write"))],
    uow: UOWDep,
    service: SeferService = Depends(get_sefer_service),
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
):
    """Yeni sefer oluştur (Service Layer).

    2026-07-01 prod-grade denetimi P1 (Dalga 4 madde 19): client timeout+retry
    ile çift kayıt oluşmasını önlemek için opsiyonel `Idempotency-Key` header'ı
    desteklenir — aynı key + aynı gövde tekrar POST edilirse önbelleklenen
    yanıt aynen dönülür, gerçek bir ikinci kayıt oluşturulmaz.
    """
    _ENDPOINT = "POST /trips"
    request_body = sefer.model_dump(mode="json")
    if idempotency_key:
        try:
            reservation = await reserve_or_get_cached(
                key=idempotency_key,
                endpoint=_ENDPOINT,
                request_body=request_body,
            )
        except IdempotencyKeyConflictError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        except IdempotencyKeyInProgressError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        if not reservation.reserved:
            _status_code, cached_body = reservation.cached
            return cached_body

    try:
        # Capture the actor id BEFORE the service commits — after commit the
        # ORM attribute is expired and re-reading it would trigger a sync lazy
        # load (MissingGreenlet) inside the later audit call.
        actor_id = current_admin.id
        logger.info(
            f"API: Creating trip with sefer_no: {sefer.sefer_no}, round_trip: {sefer.is_round_trip}"
        )
        sefer_id = await service.add_sefer(sefer, user_id=actor_id)
        logger.info(f"API: Service returned sefer_id: {sefer_id}")

        # Use service to get detailed object
        created_dict = await service.get_sefer_by_id(sefer_id)
        if not created_dict:
            logger.error(
                f"API: Created trip ID {sefer_id} could not be retrieved after creation"
            )
            raise HTTPException(
                status_code=500, detail="Oluşturulan kayıt geri okunamadı"
            )

        logger.info(f"API: Retrieved created trip dict for ID {sefer_id}")

        await log_audit_event(
            module="sefer",
            action="create",
            entity_id=str(sefer_id),
            new_value={"sefer_no": sefer.sefer_no},
            user_id=actor_id,
        )

        # Manually validate to SeferResponse to catch serialization errors
        from pydantic import ValidationError

        try:
            validated = SeferResponse.model_validate(created_dict)
            if idempotency_key:
                await finalize_response(
                    key=idempotency_key,
                    endpoint=_ENDPOINT,
                    status_code=201,
                    response_body=validated.model_dump(mode="json"),
                )
            return validated
        except ValidationError as ve:
            logger.error(
                f"API: Serialization error to SeferResponse for ID {sefer_id}: {ve}"
            )
            raise HTTPException(
                status_code=500,
                detail=f"Veri şema uyumsuzluğu (ID:{sefer_id}): {str(ve.errors()[0].get('msg'))}",
            )

    except HTTPException:
        if idempotency_key:
            await release_reservation(key=idempotency_key, endpoint=_ENDPOINT)
        raise
    except ValueError as e:
        if idempotency_key:
            await release_reservation(key=idempotency_key, endpoint=_ENDPOINT)
        logger.warning(f"API: Validation error: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except DomainError:
        if idempotency_key:
            await release_reservation(key=idempotency_key, endpoint=_ENDPOINT)
        raise
    except HTTPException:
        if idempotency_key:
            await release_reservation(key=idempotency_key, endpoint=_ENDPOINT)
        raise
    except Exception as e:
        import traceback

        from sqlalchemy.exc import IntegrityError

        # NOT NULL / FK constraint violations → unprocessable input (422)
        if isinstance(e, IntegrityError) and (
            "NotNullViolationError" in str(type(e.__cause__))
            or "ForeignKeyViolationError" in str(type(e.__cause__))
            or "not-null constraint" in str(e).lower()
            or "foreign key" in str(e).lower()
        ):
            if idempotency_key:
                await release_reservation(key=idempotency_key, endpoint=_ENDPOINT)
            logger.warning("API: DB constraint violation (422): %s", e)
            raise HTTPException(
                status_code=422,
                detail="Eksik veya geçersiz alan: " + str(e).split("DETAIL")[0][:200],
            )

        if idempotency_key:
            await release_reservation(key=idempotency_key, endpoint=_ENDPOINT)
        logger.error(
            f"API: Unexpected error creating trip: {str(e)}\n{traceback.format_exc()}"
        )
        raise HTTPException(
            status_code=500, detail="Sefer oluşturulurken bir hata oluştu"
        )


@router.post("/{sefer_id}/return", response_model=SeferResponse, status_code=201)
async def create_return_trip(
    sefer_id: int,
    current_admin: Annotated[Kullanici, Depends(require_permissions("sefer:write"))],
    service: SeferService = Depends(get_sefer_service),
):
    """Mevcut bir sefer baz alınarak dönüş seferi oluştur (Backend mantığı)."""
    try:
        actor_id = current_admin.id  # capture pre-commit (see create_sefer)
        new_sefer_id = await service.create_return_trip(sefer_id, user_id=actor_id)

        # Oku ve döndür
        created_dict = await service.get_sefer_by_id(new_sefer_id)
        if not created_dict:
            raise HTTPException(
                status_code=500, detail="Dönüş seferi oluşturuldu ancak okunamadı"
            )

        await log_audit_event(
            module="sefer",
            action="create_return",
            entity_id=str(new_sefer_id),
            new_value={"source_sefer_id": sefer_id},
            user_id=actor_id,
        )

        from pydantic import ValidationError

        try:
            return SeferResponse.model_validate(created_dict)
        except ValidationError as ve:
            logger.error(f"API: Serialization error to SeferResponse: {ve}")
            raise HTTPException(status_code=500, detail=f"Veri dönüşüm hatası: {ve}")

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except DomainError:
        raise
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Return trip creation error: {e}", exc_info=True)
        raise HTTPException(
            status_code=500, detail="Dönüş seferi oluşturulurken hata meydana geldi"
        )


@router.patch("/{sefer_id}", response_model=SeferResponse)
async def update_sefer(
    sefer_id: int,
    sefer_in: SeferUpdate,
    current_admin: Annotated[Kullanici, Depends(require_permissions("sefer:write"))],
    service: SeferService = Depends(get_sefer_service),
):
    """Sefer güncelle (Service Layer)."""
    try:
        actor_id = current_admin.id  # capture pre-commit (see create_sefer)
        success = await service.update_sefer(sefer_id, sefer_in, user_id=actor_id)
        if not success:
            raise HTTPException(status_code=404, detail="Sefer bulunamadi")

        # Guncel veriyi getir (cache invalidation sonrasinda taze veri)
        updated = await service.get_sefer_by_id(sefer_id)
        if not updated:
            raise HTTPException(status_code=404, detail="Guncellenen sefer bulunamadi")
        await log_audit_event(
            module="sefer",
            action="update",
            entity_id=str(sefer_id),
            new_value=sefer_in.model_dump(exclude_unset=True),
            user_id=actor_id,
        )
        return updated

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except DomainError:
        raise
    except Exception as e:
        logger.error(f"Update error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Guncelleme sirasinda hata olustu")


@router.delete("/{sefer_id}", response_model=dict)
async def delete_sefer(
    sefer_id: int,
    current_admin: Annotated[Kullanici, Depends(require_permissions("sefer:write"))],
    service: SeferService = Depends(get_sefer_service),
):
    """Seferi soft-delete olarak iptal eder."""

    try:
        actor_id = current_admin.id  # capture pre-commit (see create_sefer)
        success = await service.delete_sefer(sefer_id)
        if not success:
            raise HTTPException(
                status_code=404, detail="Sefer bulunamadi veya silinemedi"
            )

        await log_audit_event(
            module="sefer",
            action="delete",
            entity_id=str(sefer_id),
            user_id=actor_id,
        )
        return {
            "status": "success",
            "message": "Sefer soft-delete olarak iptal edildi",
            "soft_deleted": True,
        }

    except DomainError:
        raise
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting trip: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Silme hatasi")
