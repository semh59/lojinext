"""MaintenanceService existence-gate tests — real DB, no mocked UoW.

2026-07-01 prod-grade denetiminde bulunan bug: `create_maintenance_record` ve
`create_breakdown`, araç/dorse "var mı" kontrolünü `arac_repo.get_by_id`/
`dorse_repo.get_by_id` ile yapıyordu; bu metod soft-delete filtresi
uygulamadığı için pasif (aktif=False) bir araç/dorseye yeni bakım/arıza kaydı
sessizce açılabiliyordu. Kök neden `BaseRepository.get_by_id`'ye eklenen
otomatik soft-delete filtresiyle (include_inactive=False varsayılanı)
düzeltildi — bu dosya sonucu doğrular.
"""

from datetime import datetime, timezone

import pytest
from fastapi import HTTPException
from sqlalchemy import insert

from app.database.models import Arac, BakimTipi, Dorse
from v2.modules.fleet.application.create_maintenance_record import (
    create_breakdown,
    create_maintenance_record,
)

pytestmark = pytest.mark.integration


async def _seed_arac(db_session, plaka: str, *, aktif: bool = True) -> int:
    res = await db_session.execute(
        insert(Arac).values(plaka=plaka, marka="Mercedes", model="Actros", aktif=aktif)
    )
    await db_session.commit()
    return res.inserted_primary_key[0]


async def _seed_dorse(db_session, plaka: str, *, aktif: bool = True) -> int:
    res = await db_session.execute(insert(Dorse).values(plaka=plaka, aktif=aktif))
    await db_session.commit()
    return res.inserted_primary_key[0]


class TestMaintenanceServiceSoftDeleteGate:
    async def test_create_maintenance_record_rejects_passive_vehicle(self, db_session):
        arac_id = await _seed_arac(db_session, "34 MNT 001", aktif=False)

        with pytest.raises(HTTPException) as exc_info:
            await create_maintenance_record(
                arac_id=arac_id,
                bakim_tipi=BakimTipi.PERIYODIK,
                km_bilgisi=100000,
                bakim_tarihi=datetime.now(timezone.utc),
            )
        assert exc_info.value.status_code == 404

    async def test_create_maintenance_record_active_vehicle_succeeds(self, db_session):
        arac_id = await _seed_arac(db_session, "34 MNT 002", aktif=True)

        result = await create_maintenance_record(
            arac_id=arac_id,
            bakim_tipi=BakimTipi.PERIYODIK,
            km_bilgisi=100000,
            bakim_tarihi=datetime.now(timezone.utc),
        )
        assert result.arac_id == arac_id

    async def test_create_breakdown_rejects_passive_vehicle(self, db_session):
        arac_id = await _seed_arac(db_session, "34 MNT 003", aktif=False)

        with pytest.raises(HTTPException) as exc_info:
            await create_breakdown(bakim_tipi=BakimTipi.ARIZA, arac_id=arac_id)
        assert exc_info.value.status_code == 404

    async def test_create_breakdown_rejects_passive_dorse(self, db_session):
        dorse_id = await _seed_dorse(db_session, "34 MNT 004", aktif=False)

        with pytest.raises(HTTPException) as exc_info:
            await create_breakdown(bakim_tipi=BakimTipi.ARIZA, dorse_id=dorse_id)
        assert exc_info.value.status_code == 404

    async def test_create_breakdown_active_dorse_succeeds(self, db_session):
        dorse_id = await _seed_dorse(db_session, "34 MNT 005", aktif=True)

        result = await create_breakdown(bakim_tipi=BakimTipi.ARIZA, dorse_id=dorse_id)
        assert result.dorse_id == dorse_id
