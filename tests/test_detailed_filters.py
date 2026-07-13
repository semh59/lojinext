from unittest.mock import AsyncMock, patch

import pytest

from app.core.services.sofor_service import SoforService
from v2.modules.fleet.application.list_vehicles import get_all_vehicles_paged


@pytest.mark.asyncio
async def test_filters():
    sofor_uow = AsyncMock()
    sofor_uow.__aenter__.return_value = sofor_uow
    sofor_uow.__aexit__.return_value = None
    sofor_uow.sofor_repo.get_all.return_value = [
        {"id": 1, "ad_soyad": "Ahmet Sofor", "score": 1.6, "ehliyet_sinifi": "E"}
    ]
    sofor_uow.sofor_repo.count_all.return_value = 1

    arac_uow = AsyncMock()
    arac_uow.__aenter__.return_value = arac_uow
    arac_uow.__aexit__.return_value = None
    arac_uow.arac_repo.get_all.return_value = [
        {
            "id": 1,
            "plaka": "34 ABC 123",
            "marka": "SCANIA",
            "model": "R450",
            "yil": 2023,
            "tank_kapasitesi": 700,
            "hedef_tuketim": 31.5,
            "aktif": True,
        }
    ]
    arac_uow.arac_repo.count_all.return_value = 1

    with (
        patch("app.core.services.sofor_service.UnitOfWork", return_value=sofor_uow),
        patch(
            "v2.modules.fleet.application.list_vehicles.UnitOfWork",
            return_value=arac_uow,
        ),
    ):
        sofor_service = SoforService(repo=AsyncMock(), event_bus=AsyncMock())

        high_score = await sofor_service.get_all_paged(
            min_score=1.5, ehliyet_sinifi="E"
        )
        modern_arac = await get_all_vehicles_paged(
            search="34", marka="SCANIA", min_yil=2022
        )

    assert high_score["total"] == 1
    assert high_score["items"][0]["ad_soyad"] == "Ahmet Sofor"
    sofor_uow.sofor_repo.get_all.assert_awaited_once_with(
        offset=0,
        limit=100,
        sadece_aktif=True,
        search=None,
        filters={"ehliyet_sinifi": "E", "score_ge": 1.5},
    )

    assert modern_arac["total"] == 1
    assert modern_arac["items"][0].plaka == "34 ABC 123"
    arac_uow.arac_repo.get_all.assert_awaited_once_with(
        offset=0,
        limit=100,
        sadece_aktif=True,
        search="34",
        filters={"marka": "SCANIA", "yil_ge": 2022},
    )
