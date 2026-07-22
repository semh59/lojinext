"""Toplu sefer durum güncelleme/iptal/silme use-case'leri."""

from typing import Any, Dict, List, Optional, cast

from v2.modules.platform_infra.public import get_logger
from v2.modules.shared_kernel.infrastructure.unit_of_work import UnitOfWork
from v2.modules.trip.application.delete_trip import delete_sefer_uow
from v2.modules.trip.application.stats_refresh import refresh_stats
from v2.modules.trip.application.update_trip import update_sefer_uow
from v2.modules.trip.schemas import SeferUpdate
from v2.modules.trip.sefer_status import (
    SEFER_STATUS_IPTAL,
    ensure_canonical_sefer_status,
)

logger = get_logger(__name__)


async def bulk_update_status(
    sefer_ids: List[int], new_status: str, user_id: Optional[int] = None
) -> Dict[str, Any]:
    """
    Birden fazla seferin durumunu toplu güncelle.
    N+1 Transaction sorunu giderildi (Tek UoW).
    """
    normalized_status = ensure_canonical_sefer_status(
        new_status, field_name="new_status", allow_none=False
    )
    if normalized_status == SEFER_STATUS_IPTAL:
        raise ValueError(
            "Toplu durum güncelleme iptal kabul etmez. İptal için bulk_cancel kullanın."
        )

    success_count = 0
    failed = []

    async with UnitOfWork() as uow:
        for sid in sefer_ids:
            try:
                success = await update_sefer_uow(
                    uow,
                    sid,
                    # SeferUpdate alanları tümü optional; pydantic.mypy plugin
                    # olmadığı için mypy Field() default'larını görmez (call-arg
                    # false-positive) ve str->TripStatus runtime coercion'ını
                    # bilmez (arg-type). ARCH-005 partial-update kontratı.
                    SeferUpdate(durum=normalized_status),  # type: ignore[call-arg, arg-type]
                    user_id=user_id,
                )
                if success:
                    success_count += 1
                else:
                    failed.append({"id": sid, "reason": "Bulunamadı veya güncellenemedi"})
            except Exception as e:
                logger.error(f"Bulk status update error for sid {sid}: {e}")
                failed.append({"id": sid, "reason": str(e)})

        if success_count > 0:
            await uow.commit()
            await refresh_stats(uow)

    return {
        "success_count": success_count,
        "failed_count": len(failed),
        "failed": failed,
    }


async def bulk_cancel(
    sefer_ids: List[int],
    iptal_nedeni: str,
    user_id: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Birden fazla seferi toplu iptal et.
    N+1 Transaction sorunu giderildi.
    """
    success_count = 0
    failed = []

    async with UnitOfWork() as uow:
        for sid in sefer_ids:
            try:
                success = await update_sefer_uow(
                    uow,
                    sid,
                    # Bkz. bulk_update_status: pydantic.mypy plugin yok (ARCH-005).
                    SeferUpdate(  # type: ignore[call-arg]
                        durum=cast(Any, SEFER_STATUS_IPTAL),
                        iptal_nedeni=iptal_nedeni,
                    ),
                    user_id=user_id,
                )
                if success:
                    success_count += 1
                else:
                    failed.append({"id": sid, "reason": "Bulunamadı veya iptal edilemedi"})
            except Exception as e:
                logger.error(f"Bulk cancel error for sid {sid}: {e}")
                failed.append({"id": sid, "reason": str(e)})

        if success_count > 0:
            await uow.commit()
            await refresh_stats(uow)

    return {
        "success_count": success_count,
        "failed_count": len(failed),
        "failed": failed,
    }


async def bulk_delete(sefer_ids: List[int]) -> Dict[str, Any]:
    """
    Birden fazla seferi toplu sil.
    N+1 Transaction sorunu giderildi (Tek UoW).
    """
    success_count = 0
    failed = []

    async with UnitOfWork() as uow:
        for sid in sefer_ids:
            try:
                success = await delete_sefer_uow(uow, sid)
                if success:
                    success_count += 1
                else:
                    failed.append({"id": sid, "reason": "Bulunamadı veya silinemedi"})
            except Exception as e:
                logger.error(f"Bulk delete error for sid {sid}: {e}")
                failed.append({"id": sid, "reason": str(e)})

        if success_count > 0:
            await uow.commit()
            await refresh_stats(uow)

    return {
        "success_count": success_count,
        "failed_count": len(failed),
        "failed": failed,
    }
