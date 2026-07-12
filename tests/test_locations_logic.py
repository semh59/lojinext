from unittest.mock import AsyncMock

import pytest

from v2.modules.location.application.create_location import create_location
from v2.modules.location.application.delete_location import delete_location
from v2.modules.location.application.list_locations import list_locations
from v2.modules.location.schemas import LokasyonCreate


@pytest.mark.asyncio
async def test_locations_logic():
    repo = AsyncMock()
    repo.get_all.return_value = [
        {
            "id": 1,
            "cikis_yeri": "Istanbul",
            "varis_yeri": "Ankara",
            "mesafe_km": 450.0,
            "tahmini_sure_saat": 6.5,
            "zorluk": "Normal",
            "aktif": True,
            "flat_distance_km": 200.0,
        }
    ]
    repo.count.return_value = 1
    repo.get_by_route.side_effect = [None, {"id": 5, "aktif": True}]
    repo.add.return_value = 5
    repo.get_by_id.side_effect = [{"id": 5, "aktif": True}, {"id": 5, "aktif": False}]
    repo.update.return_value = True
    repo.hard_delete.return_value = True

    page = await list_locations(repo, limit=5)
    assert page["total"] == 1
    assert page["items"][0].cikis_yeri == "Istanbul"

    lokasyon_id = await create_location(
        repo,
        LokasyonCreate(
            cikis_yeri="istanbul",
            varis_yeri="ankara",
            mesafe_km=450,
            zorluk="Normal",
        ),
    )
    assert lokasyon_id == 5

    with pytest.raises(ValueError, match="zaten mevcut"):
        await create_location(
            repo,
            LokasyonCreate(
                cikis_yeri="istanbul",
                varis_yeri="ankara",
                mesafe_km=450,
                zorluk="Normal",
            ),
        )

    assert await delete_location(repo, 5) is True
    assert await delete_location(repo, 5) is True
    repo.hard_delete.assert_awaited_once_with(5)
