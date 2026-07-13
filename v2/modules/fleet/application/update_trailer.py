"""Use-case: update/delete a trailer record."""

from v2.modules.fleet.infrastructure.trailer_repository import DorseRepository


async def update_trailer(repo: DorseRepository, dorse_id: int, **data) -> bool:
    """Update trailer record."""
    return await repo.update(dorse_id, **data)


async def delete_trailer(repo: DorseRepository, dorse_id: int) -> bool:
    """Delete trailer record (Internal repo handles soft/hard)."""
    return await repo.delete(dorse_id)
