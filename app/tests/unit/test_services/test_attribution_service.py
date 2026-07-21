"""override_attribution/bulk_override_attribution tests — real DB, no mocked UoW.

Previously these mocked the UnitOfWork/sefer_repo and asserted inner calls
(sefer_repo.update.assert_awaited_once(), commit.assert_awaited_once()). Here the
free functions run against the real test DB (db_session monkeypatches
AsyncSessionLocal, so `async with UnitOfWork():` uses the test session) and we
assert the real seferler row (arac_id/sofor_id/is_corrected actually changed).
Only the event bus (external Redis pub/sub) is stubbed.

B.1: eski ``AttributionService`` sınıfı dalga 8'de kaldırıldı — testler artık
``v2.modules.anomaly.application.attribute_loss.override_attribution``/
``bulk_override_attribution`` free function'larını doğrudan çağırır.
"""

from datetime import date
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import HTTPException
from sqlalchemy import insert, select

from v2.modules.anomaly.application.attribute_loss import (
    bulk_override_attribution,
    override_attribution,
)
from v2.modules.driver.public import Sofor
from v2.modules.fleet.public import AracORM as Arac
from v2.modules.shared_kernel.infrastructure.unit_of_work import UnitOfWork
from v2.modules.trip.public import SeferORM as Sefer

pytestmark = pytest.mark.integration


async def _seed_arac(db_session, plaka: str) -> int:
    return (
        await db_session.execute(insert(Arac).values(plaka=plaka, marka="M"))
    ).inserted_primary_key[0]


async def _seed_sofor(db_session, ad: str) -> int:
    # ORM constructor (not Core insert()) — Sofor.ad_soyad_bidx is derived via
    # @validates on attribute assignment, which a Core insert() bypasses.
    sofor = Sofor(ad_soyad=ad)
    db_session.add(sofor)
    await db_session.flush()
    return sofor.id


async def _seed_sefer(db_session, arac_id: int, sofor_id: int) -> int:
    sid = (
        await db_session.execute(
            insert(Sefer).values(
                arac_id=arac_id,
                sofor_id=sofor_id,
                cikis_yeri="A",
                varis_yeri="B",
                mesafe_km=100.0,
                bos_agirlik_kg=8000,
                dolu_agirlik_kg=20000,
                net_kg=12000,
                durum="Planned",
                tarih=date.today(),
            )
        )
    ).inserted_primary_key[0]
    await db_session.commit()
    return sid


async def _get_sefer(db_session, sid):
    return (
        await db_session.execute(select(Sefer).where(Sefer.id == sid))
    ).scalar_one_or_none()


def _patch_event_bus():
    # The event bus is external infra → stub it; the UoW/DB is real.
    mock_bus = AsyncMock()
    mock_bus.publish_async = AsyncMock()
    return patch(
        "v2.modules.anomaly.application.attribute_loss.get_event_bus",
        return_value=mock_bus,
    )


class TestOverrideAttribution:
    async def test_happy_path_override_arac(self, db_session):
        a1 = await _seed_arac(db_session, "34 AAA 111")
        a2 = await _seed_arac(db_session, "34 BBB 222")
        s = await _seed_sofor(db_session, "Sofor A")
        sefer_id = await _seed_sefer(db_session, a1, s)

        with _patch_event_bus():
            result = await override_attribution(
                sefer_id=sefer_id, arac_id=a2, reason="Test", uow=UnitOfWork()
            )

        assert result is True
        row = await _get_sefer(db_session, sefer_id)
        assert row.arac_id == a2
        assert row.is_corrected is True

    async def test_happy_path_override_sofor(self, db_session):
        a1 = await _seed_arac(db_session, "34 AAA 333")
        s1 = await _seed_sofor(db_session, "Sofor B")
        s2 = await _seed_sofor(db_session, "Sofor C")
        sefer_id = await _seed_sefer(db_session, a1, s1)

        with _patch_event_bus():
            result = await override_attribution(
                sefer_id=sefer_id,
                sofor_id=s2,
                reason="Sürücü değişti",
                uow=UnitOfWork(),
            )

        assert result is True
        row = await _get_sefer(db_session, sefer_id)
        assert row.sofor_id == s2

    async def test_error_handling_sefer_not_found(self, db_session):
        with _patch_event_bus():
            with pytest.raises(HTTPException) as exc_info:
                await override_attribution(sefer_id=999999, uow=UnitOfWork())
        assert exc_info.value.status_code == 404

    async def test_edge_case_update_returns_false(self, db_session):
        """Defensive branch: if repo.update reports failure, return False, no commit.

        A real UPDATE on an existing row always succeeds, so this otherwise-unreachable
        guard is exercised by forcing the repo method's return value (error-path only)."""
        from v2.modules.trip.infrastructure.repository import SeferRepository

        a1 = await _seed_arac(db_session, "34 AAA 444")
        s1 = await _seed_sofor(db_session, "Sofor D")
        sefer_id = await _seed_sefer(db_session, a1, s1)

        with (
            _patch_event_bus(),
            patch.object(SeferRepository, "update", AsyncMock(return_value=False)),
        ):
            result = await override_attribution(
                sefer_id=sefer_id, arac_id=a1, uow=UnitOfWork()
            )

        assert result is False
        # No correction was committed.
        row = await _get_sefer(db_session, sefer_id)
        assert row.is_corrected in (False, None)

    async def test_event_published_on_success(self, db_session):
        a1 = await _seed_arac(db_session, "34 AAA 555")
        a2 = await _seed_arac(db_session, "34 BBB 666")
        s1 = await _seed_sofor(db_session, "Sofor E")
        sefer_id = await _seed_sefer(db_session, a1, s1)

        mock_bus = AsyncMock()
        mock_bus.publish_async = AsyncMock()
        with patch(
            "v2.modules.anomaly.application.attribute_loss.get_event_bus",
            return_value=mock_bus,
        ):
            await override_attribution(
                sefer_id=sefer_id, arac_id=a2, reason="Nakil", uow=UnitOfWork()
            )

        mock_bus.publish_async.assert_awaited_once()
        published_event = mock_bus.publish_async.call_args[0][0]
        assert published_event.data["sefer_id"] == sefer_id
        assert published_event.data["new_arac_id"] == a2

    async def test_override_both_arac_and_sofor(self, db_session):
        a1 = await _seed_arac(db_session, "34 AAA 999")
        a2 = await _seed_arac(db_session, "34 BBB 000")
        s1 = await _seed_sofor(db_session, "Sofor H")
        s2 = await _seed_sofor(db_session, "Sofor I")
        sefer_id = await _seed_sefer(db_session, a1, s1)

        with _patch_event_bus():
            result = await override_attribution(
                sefer_id=sefer_id,
                arac_id=a2,
                sofor_id=s2,
                reason="Full override",
                uow=UnitOfWork(),
            )

        assert result is True
        row = await _get_sefer(db_session, sefer_id)
        assert row.is_corrected is True
        assert row.arac_id == a2 and row.sofor_id == s2

    async def test_return_type_validation(self, db_session):
        a1 = await _seed_arac(db_session, "34 AAA 121")
        s1 = await _seed_sofor(db_session, "Sofor J")
        sefer_id = await _seed_sefer(db_session, a1, s1)

        with _patch_event_bus():
            result = await override_attribution(
                sefer_id=sefer_id, arac_id=a1, uow=UnitOfWork()
            )
        assert isinstance(result, bool)
        assert result is True

    async def test_default_uow_opens_own(self, db_session):
        """uow=None → override_attribution opens its own UnitOfWork()."""
        a1 = await _seed_arac(db_session, "34 AAA 131")
        a2 = await _seed_arac(db_session, "34 BBB 141")
        s1 = await _seed_sofor(db_session, "Sofor K")
        sefer_id = await _seed_sefer(db_session, a1, s1)

        with _patch_event_bus():
            result = await override_attribution(sefer_id=sefer_id, arac_id=a2)

        assert result is True
        row = await _get_sefer(db_session, sefer_id)
        assert row.arac_id == a2


class TestBulkOverrideAttribution:
    async def test_bulk_override_returns_count(self, db_session):
        a1 = await _seed_arac(db_session, "34 AAA 777")
        a2 = await _seed_arac(db_session, "34 BBB 888")
        s1 = await _seed_sofor(db_session, "Sofor F")
        s2 = await _seed_sofor(db_session, "Sofor G")
        sefer_id = await _seed_sefer(db_session, a1, s1)

        with _patch_event_bus():
            count = await bulk_override_attribution(
                [
                    {"sefer_id": sefer_id, "arac_id": a2, "reason": "r1"},
                    {"sefer_id": sefer_id, "sofor_id": s2, "reason": "r2"},
                ]
            )

        assert count == 2
        row = await _get_sefer(db_session, sefer_id)
        assert row.arac_id == a2
        assert row.sofor_id == s2

    async def test_bulk_override_partial_failure(self, db_session):
        """Bulk swallows individual errors (missing sefer) and counts only successes."""
        with _patch_event_bus():
            count = await bulk_override_attribution(
                [
                    {"sefer_id": 999999, "arac_id": 1},
                    {"sefer_id": 999998, "sofor_id": 2},
                ]
            )
        assert count == 0
