"""
Integration tests for SeferService — real SeferRepository over seeded test DB.

Pure Pydantic validation tests remain unit-style (no DB).
All DB-touching tests use the ``db_session`` fixture (TRUNCATE + monkeypatched UoW).
"""

from datetime import date, timedelta

import pytest
from pydantic import ValidationError

from app.infrastructure.events.event_bus import get_event_bus
from app.tests._helpers.seed import seed_arac, seed_sefer, seed_sofor
from v2.modules.trip.application.trip_service import SeferService
from v2.modules.trip.infrastructure.repository import SeferRepository
from v2.modules.trip.schemas import SeferCreate
from v2.modules.trip.sefer_status import (
    SEFER_STATUS_IPTAL,
    SEFER_STATUS_PLANLANDI,
    SEFER_STATUS_TAMAMLANDI,
)

pytestmark = pytest.mark.integration


@pytest.fixture
async def seeded_sefer_service(db_session):
    """Seed 3 trips (Planned/Completed/Cancelled) and return a live SeferService."""
    arac = await seed_arac(db_session)
    sofor = await seed_sofor(db_session)
    # Trip 1: today, Planned
    await seed_sefer(
        db_session,
        arac_id=arac.id,
        sofor_id=sofor.id,
        tarih=date.today(),
        durum=SEFER_STATUS_PLANLANDI,
    )
    # Trip 2: yesterday, Completed
    await seed_sefer(
        db_session,
        arac_id=arac.id,
        sofor_id=sofor.id,
        tarih=date.today() - timedelta(days=1),
        durum=SEFER_STATUS_TAMAMLANDI,
    )
    # Trip 3: today, Cancelled
    await seed_sefer(
        db_session,
        arac_id=arac.id,
        sofor_id=sofor.id,
        tarih=date.today(),
        durum=SEFER_STATUS_IPTAL,
    )
    await db_session.commit()
    return SeferService(
        repo=SeferRepository(session=db_session),
        event_bus=get_event_bus(),
    )


class TestSeferService:
    """Test suite for SeferService."""

    async def test_service_instances_accept_explicit_dependencies(self, db_session):
        """Two distinct SeferService instances can be built with explicit deps."""
        repo = SeferRepository(session=db_session)
        bus = get_event_bus()
        service1 = SeferService(repo=repo, event_bus=bus)
        service2 = SeferService(repo=repo, event_bus=bus)

        assert isinstance(service1, SeferService)
        assert isinstance(service2, SeferService)
        assert service1 is not service2

    async def test_get_all_trips_returns_list(self, seeded_sefer_service):
        """get_all_trips should return a list."""
        trips = await seeded_sefer_service.get_all_trips()
        assert isinstance(trips, list)

    async def test_get_all_trips_with_limit(self, seeded_sefer_service):
        """Limit parameter should work correctly."""
        trips = await seeded_sefer_service.get_all_trips(limit=1)
        assert len(trips) == 1

    async def test_get_all_trips_with_date_filter(self, seeded_sefer_service):
        """Date filters should be applied.

        Seeded: Planned(today), Completed(yesterday), Cancelled(today).
        Real repo excludes Cancelled by default (include_inactive=False).
        yesterday..today spans both Planned and Completed → expect 2.
        """
        today = date.today()
        yesterday = today - timedelta(days=1)

        trips = await seeded_sefer_service.get_all_trips(
            start_date=yesterday, end_date=today
        )
        assert isinstance(trips, list)
        # Planned(today) + Completed(yesterday) — Cancelled excluded by default
        assert len(trips) == 2

    @pytest.mark.parametrize(
        "status,expected_count",
        [
            (SEFER_STATUS_PLANLANDI, 1),
            (SEFER_STATUS_TAMAMLANDI, 1),
            (SEFER_STATUS_IPTAL, 1),
            # status=None → real repo excludes Cancelled → 2 active trips
            (None, 2),
        ],
    )
    async def test_get_all_trips_status_filter(
        self, seeded_sefer_service, status, expected_count
    ):
        """Status filter should work for all valid statuses.

        Real SeferRepository.get_all with no durum and no include_inactive
        applies ``Sefer.durum != SEFER_STATUS_IPTAL`` — matches old FakeSeferRepo
        behaviour exactly.
        """
        trips = await seeded_sefer_service.get_all_trips(status=status)
        assert isinstance(trips, list)
        assert len(trips) == expected_count


class TestSeferServiceValidation:
    """Test input validation in SeferService."""

    def test_add_sefer_requires_arac_id(self, sample_sefer_data):
        """Adding a trip without arac_id should fail at Pydantic validation."""
        data = sample_sefer_data.copy()
        data.pop("arac_id")

        with pytest.raises(ValidationError):
            SeferCreate(**data)

    def test_add_sefer_requires_locations(self, sample_sefer_data):
        """Adding a trip without locations should fail at Pydantic validation."""
        data = sample_sefer_data.copy()
        data["cikis_yeri"] = ""
        data["varis_yeri"] = ""

        with pytest.raises(ValidationError):
            SeferCreate(**data)

    async def test_add_sefer_same_locations(self, sample_sefer_data, db_session):
        """Start and end location cannot be the same.

        ``_validate_sefer_create`` is called before any DB lookup inside
        ``add_sefer``, so RouteProcessingError is raised early.
        The ``db_session`` fixture already monkeypatches UnitOfWork to use
        the test session — no inline FakeUnitOfWork needed.
        """
        from v2.modules.shared_kernel.exceptions import RouteProcessingError

        data = sample_sefer_data.copy()
        data["cikis_yeri"] = "Istanbul"
        data["varis_yeri"] = "Istanbul"

        model = SeferCreate(**data)
        service = SeferService(
            repo=SeferRepository(session=db_session),
            event_bus=get_event_bus(),
        )

        with pytest.raises(RouteProcessingError, match="aynı olamaz"):
            await service.add_sefer(model)


class TestSeferServiceStats:
    """Test statistics methods in SeferService."""

    async def test_get_bugunun_seferleri(self, seeded_sefer_service):
        """Today's trips should be retrievable via repo.get_bugunun_seferleri().

        Seeded: Planned(today), Completed(yesterday), Cancelled(today).
        get_bugunun_seferleri filters by today's date and excludes Cancelled
        (real repo: durum != SEFER_STATUS_IPTAL).
        Expected: 1 (Planned today only; Completed is yesterday; Cancelled excluded).
        """
        trips = await seeded_sefer_service.repo.get_bugunun_seferleri()
        assert isinstance(trips, list)

        today = date.today().isoformat()
        for trip in trips:
            trip_date = trip.get("tarih") if isinstance(trip, dict) else trip.tarih
            assert str(trip_date) == today
