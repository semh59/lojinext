from datetime import datetime, timedelta, timezone

import pytest

from app.database.models import AracBakim, BakimTipi
from app.tests._helpers.seed import seed_arac
from v2.modules.fleet.application.create_maintenance_record import (
    create_maintenance_record,
)
from v2.modules.fleet.application.get_vehicle_maintenance_history import (
    get_upcoming_maintenance_alerts,
    get_vehicle_maintenance_history,
    mark_maintenance_completed,
)


@pytest.mark.asyncio
async def test_create_maintenance_record(db_session):
    """Verify maintenance record creation persists to the real DB."""
    arac = await seed_arac(db_session, plaka="34ABC123")
    await db_session.commit()

    result = await create_maintenance_record(
        arac_id=arac.id,
        bakim_tipi=BakimTipi.PERIYODIK,
        km_bilgisi=50000,
        bakim_tarihi=datetime.now(timezone.utc),
    )

    assert result.id is not None
    assert result.tamamlandi is False

    # Re-read through a fresh session-independent query to prove the row was
    # actually committed by create_maintenance_record's own UnitOfWork, not
    # just returned in-memory.
    history = await get_vehicle_maintenance_history(arac.id)
    assert any(h.id == result.id for h in history)


@pytest.mark.asyncio
async def test_get_upcoming_alerts(db_session):
    """Verify enrichment of maintenance alerts with vehicle plates."""
    arac = await seed_arac(db_session, plaka="34PLK099")
    bakim = AracBakim(
        arac_id=arac.id,
        bakim_tipi=BakimTipi.PERIYODIK,
        km_bilgisi=1000,
        bakim_tarihi=datetime.now(timezone.utc) + timedelta(days=7),
        tamamlandi=False,
    )
    db_session.add(bakim)
    await db_session.commit()

    alerts = await get_upcoming_maintenance_alerts()

    matching = [a for a in alerts if a["arac_id"] == arac.id]
    assert len(matching) == 1
    assert matching[0]["plaka"] == "34PLK099"
    assert matching[0]["vade_durumu"] == "UPCOMING"


@pytest.mark.asyncio
async def test_mark_as_completed(db_session):
    """Verify that marking maintenance completed persists to the real DB."""
    arac = await seed_arac(db_session, plaka="34CMP001")
    bakim = AracBakim(
        arac_id=arac.id,
        bakim_tipi=BakimTipi.PERIYODIK,
        km_bilgisi=2000,
        bakim_tarihi=datetime.now(timezone.utc),
        tamamlandi=False,
    )
    db_session.add(bakim)
    await db_session.commit()
    await db_session.refresh(bakim)

    success = await mark_maintenance_completed(bakim.id)
    assert success is True

    history = await get_vehicle_maintenance_history(arac.id)
    updated = next(h for h in history if h.id == bakim.id)
    assert updated.tamamlandi is True


@pytest.mark.asyncio
async def test_get_vehicle_maintenance_history(db_session):
    """Verify history retrieval for a specific vehicle."""
    arac = await seed_arac(db_session, plaka="34HIS001")
    other_arac = await seed_arac(db_session, plaka="34HIS002")
    db_session.add_all(
        [
            AracBakim(
                arac_id=arac.id,
                bakim_tipi=BakimTipi.PERIYODIK,
                km_bilgisi=3000,
                bakim_tarihi=datetime.now(timezone.utc),
                tamamlandi=False,
            ),
            AracBakim(
                arac_id=other_arac.id,
                bakim_tipi=BakimTipi.ARIZA,
                km_bilgisi=4000,
                bakim_tarihi=datetime.now(timezone.utc),
                tamamlandi=False,
            ),
        ]
    )
    await db_session.commit()

    history = await get_vehicle_maintenance_history(arac.id)
    assert len(history) == 1
    assert history[0].arac_id == arac.id
