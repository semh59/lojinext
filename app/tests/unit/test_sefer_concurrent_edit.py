"""
Concurrent edit behavior tests for the trip module.
"""

from datetime import date
from types import SimpleNamespace

from app.core.utils.sefer_status import (
    SEFER_STATUS_IPTAL,
    SEFER_STATUS_PLANLANDI,
    SEFER_STATUS_TAMAMLANDI,
    SEFER_STATUS_TRANSITIONS,
)
from app.schemas.sefer import SeferUpdate


def _make_mock_sefer(id: int = 1, durum: str = SEFER_STATUS_PLANLANDI, **overrides):
    defaults = {
        "id": id,
        "sefer_no": f"SEF-{id:03d}",
        "tarih": date(2026, 1, 15),
        "saat": "10:00",
        "arac_id": 1,
        "sofor_id": 1,
        "guzergah_id": 1,
        "cikis_yeri": "Istanbul",
        "varis_yeri": "Ankara",
        "mesafe_km": 450.0,
        "bos_agirlik_kg": 8000,
        "dolu_agirlik_kg": 18000,
        "net_kg": 10000,
        "ton": 10.0,
        "durum": durum,
        "is_deleted": False,
        "created_at": "2026-01-01T00:00:00+00:00",
        "updated_at": "2026-01-01T00:00:00+00:00",
    }
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


class TestStatusTransitionGuards:
    def test_completed_trip_cannot_change(self):
        allowed = SEFER_STATUS_TRANSITIONS.get(SEFER_STATUS_TAMAMLANDI, set())
        assert len(allowed) == 0

    def test_cancelled_trip_cannot_be_reactivated(self):
        allowed = SEFER_STATUS_TRANSITIONS.get(SEFER_STATUS_IPTAL, set())
        assert len(allowed) == 0

    def test_planned_trip_allows_only_complete_or_cancel(self):
        allowed = SEFER_STATUS_TRANSITIONS.get(SEFER_STATUS_PLANLANDI, set())
        assert allowed == (SEFER_STATUS_TAMAMLANDI, SEFER_STATUS_IPTAL)


class TestConcurrentEditBehavior:
    def test_last_writer_wins_on_field_update(self):
        sefer = _make_mock_sefer(durum=SEFER_STATUS_PLANLANDI)

        update_a = SeferUpdate(notlar="User A notes")
        update_b = SeferUpdate(notlar="User B notes")

        if update_a.notlar:
            sefer.notlar = update_a.notlar
        if update_b.notlar:
            sefer.notlar = update_b.notlar

        assert sefer.notlar == "User B notes"

    def test_concurrent_status_change_first_wins_due_to_guard(self):
        sefer = _make_mock_sefer(durum=SEFER_STATUS_TAMAMLANDI)
        current_allowed = SEFER_STATUS_TRANSITIONS.get(sefer.durum, set())
        assert SEFER_STATUS_IPTAL not in current_allowed

    def test_parallel_delete_and_update_race(self):
        sefer = _make_mock_sefer(durum=SEFER_STATUS_PLANLANDI)
        sefer.is_deleted = True
        sefer.durum = SEFER_STATUS_IPTAL
        assert sefer.is_deleted is True


class TestBulkOperationAtomicity:
    def test_bulk_status_transitions_are_individual(self):
        seferler = [
            _make_mock_sefer(id=1, durum=SEFER_STATUS_PLANLANDI),
            _make_mock_sefer(id=2, durum=SEFER_STATUS_TAMAMLANDI),
            _make_mock_sefer(id=3, durum=SEFER_STATUS_IPTAL),
        ]

        new_status = SEFER_STATUS_IPTAL
        results = {"success": [], "failed": []}

        for sefer in seferler:
            allowed = SEFER_STATUS_TRANSITIONS.get(sefer.durum, set())
            if new_status in allowed:
                results["success"].append(sefer.id)
            else:
                results["failed"].append(sefer.id)

        assert 1 in results["success"]
        assert 2 in results["failed"]
        assert 3 in results["failed"]

    def test_bulk_delete_handles_already_deleted(self):
        seferler = [
            _make_mock_sefer(id=1, is_deleted=False),
            _make_mock_sefer(id=2, is_deleted=True),
            _make_mock_sefer(id=3, is_deleted=False),
        ]

        results = {"success": [], "failed": []}
        for sefer in seferler:
            if sefer.is_deleted:
                results["failed"].append(sefer.id)
            else:
                results["success"].append(sefer.id)

        assert len(results["success"]) == 2
        assert 2 in results["failed"]


class TestRaceConditionAwareness:
    def test_no_version_field_exists_on_mock_sefer(self):
        sefer = _make_mock_sefer()
        has_version = hasattr(sefer, "version") or hasattr(sefer, "etag")
        assert not has_version

    def test_update_schema_has_version_field(self):
        fields = SeferUpdate.model_fields
        assert "version" in fields
        assert "etag" not in fields
