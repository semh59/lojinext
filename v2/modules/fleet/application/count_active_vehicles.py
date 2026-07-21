"""Use-case: count active (non-deleted) vehicles — used by auth_rbac's license limit check."""

from v2.modules.shared_kernel.infrastructure.unit_of_work import UnitOfWork


async def count_active_vehicles() -> int:
    async with UnitOfWork() as uow:
        return await uow.arac_repo.count_active()
