"""SeferRepository stats methods unit tests — session mocked."""

from datetime import date
from unittest.mock import AsyncMock, MagicMock

import pytest

pytestmark = pytest.mark.unit


def _make_repo_with_session():
    """Return a SeferRepository instance with a mocked async session."""
    from app.database.repositories.sefer_repo import SeferRepository

    repo = SeferRepository.__new__(SeferRepository)
    repo.session = AsyncMock()
    return repo


def _make_stats_row(
    total=10,
    completed=6,
    cancelled=1,
    planned=2,
    in_progress=1,
    distance=4500.0,
    avg=32.0,
):
    row = MagicMock()
    row.total_count = total
    row.completed_count = completed
    row.cancelled_count = cancelled
    row.planned_count = planned
    row.in_progress_count = in_progress
    row.total_distance_km = distance
    row.avg_consumption = avg
    return row


class TestSeferRepoStats:
    def test_service_exists(self):
        """SeferRepository is importable and has get_trip_stats."""
        from app.database.repositories.sefer_repo import SeferRepository

        assert SeferRepository is not None
        assert hasattr(SeferRepository, "get_trip_stats")

    async def test_basic_initialization(self):
        """SeferRepository can be constructed with a mock session."""
        repo = _make_repo_with_session()
        assert repo is not None
        assert repo.session is not None

    async def test_happy_path_get_trip_stats_no_filters(self):
        """get_trip_stats returns expected keys when no filters applied."""
        repo = _make_repo_with_session()
        row = _make_stats_row()
        mock_result = MagicMock()
        mock_result.one = MagicMock(return_value=row)
        repo.session.execute = AsyncMock(return_value=mock_result)

        result = await repo.get_trip_stats()

        assert isinstance(result, dict)
        assert result["total_count"] == 10
        assert result["completed_count"] == 6
        assert result["cancelled_count"] == 1
        assert result["planned_count"] == 2
        assert result["in_progress_count"] == 1
        assert result["total_distance_km"] == 4500.0
        assert result["avg_consumption"] == 32.0

    async def test_get_trip_stats_with_durum_filter(self):
        """get_trip_stats accepts valid durum filter."""
        repo = _make_repo_with_session()
        row = _make_stats_row(total=6, completed=6)
        mock_result = MagicMock()
        mock_result.one = MagicMock(return_value=row)
        repo.session.execute = AsyncMock(return_value=mock_result)

        result = await repo.get_trip_stats(durum="Tamamlandı")

        assert result["total_count"] == 6

    async def test_get_trip_stats_raises_for_invalid_durum(self):
        """get_trip_stats raises ValueError for unknown durum."""
        repo = _make_repo_with_session()

        with pytest.raises(ValueError, match="Geçersiz durum"):
            await repo.get_trip_stats(durum="GecersizDurum")

    async def test_get_trip_stats_with_date_range(self):
        """get_trip_stats accepts baslangic_tarih and bitis_tarih filters."""
        repo = _make_repo_with_session()
        row = _make_stats_row(total=3)
        mock_result = MagicMock()
        mock_result.one = MagicMock(return_value=row)
        repo.session.execute = AsyncMock(return_value=mock_result)

        result = await repo.get_trip_stats(
            baslangic_tarih=date(2024, 1, 1),
            bitis_tarih=date(2024, 1, 31),
        )

        assert result["total_count"] == 3
        repo.session.execute.assert_called_once()

    async def test_get_trip_stats_nulls_default_to_zero(self):
        """get_trip_stats coerces NULL fields to 0."""
        repo = _make_repo_with_session()
        row = _make_stats_row(
            total=0,
            completed=0,
            cancelled=0,
            planned=0,
            in_progress=0,
            distance=0,
            avg=0,
        )
        row.total_count = None
        row.total_distance_km = None
        row.avg_consumption = None
        mock_result = MagicMock()
        mock_result.one = MagicMock(return_value=row)
        repo.session.execute = AsyncMock(return_value=mock_result)

        result = await repo.get_trip_stats()

        assert result["total_count"] == 0
        assert result["total_distance_km"] == 0.0
        assert result["avg_consumption"] == 0.0

    async def test_count_all_returns_int(self):
        """count_all returns an integer count."""
        repo = _make_repo_with_session()
        mock_result = MagicMock()
        mock_result.scalar = MagicMock(return_value=7)
        repo.session.execute = AsyncMock(return_value=mock_result)

        result = await repo.count_all()
        assert result == 7

    async def test_count_today_returns_int(self):
        """count_today returns an integer count for today's trips."""
        repo = _make_repo_with_session()
        mock_result = MagicMock()
        mock_result.scalar = MagicMock(return_value=3)
        repo.session.execute = AsyncMock(return_value=mock_result)

        result = await repo.count_today()
        assert result == 3

    async def test_integration_with_mock_all_valid_durum_values(self):
        """All valid durum strings are accepted without ValueError.

        Canonical English values plus legacy Türkçe aliases that normalize to
        the canonical set (Planned/Completed/Cancelled).
        """
        valid_durum = [
            "Planned",
            "Completed",
            "Cancelled",
            "Tamamlandı",
            "İptal",
            "Planlandı",
            "Yolda",
        ]
        repo = _make_repo_with_session()
        row = _make_stats_row()
        mock_result = MagicMock()
        mock_result.one = MagicMock(return_value=row)
        repo.session.execute = AsyncMock(return_value=mock_result)

        for durum in valid_durum:
            result = await repo.get_trip_stats(durum=durum)
            assert isinstance(result, dict)
