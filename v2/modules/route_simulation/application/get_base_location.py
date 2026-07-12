"""Use-case: return the system's configured base location."""

from app.database.unit_of_work import unit_of_work as get_uow


async def get_base_location() -> str:
    """Return the system base location."""
    async with get_uow() as uow:
        return await uow.config_repo.get_value("default_base_location", "FABRIKA")


__all__ = ["get_base_location"]
