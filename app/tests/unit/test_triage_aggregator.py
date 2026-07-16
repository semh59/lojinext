"""Reports v2 RV2.1 — Triage aggregator tests."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, List, Optional

import pytest


# ── Fake DB session (substring routing) ───────────────────────────────
class _FakeMappings:
    def __init__(self, rows) -> None:
        self._rows = rows

    def all(self):
        return self._rows

    def one(self):
        return self._rows[0] if self._rows else {}


class _FakeResult:
    def __init__(self, rows) -> None:
        self._rows = rows

    def mappings(self):
        return _FakeMappings(self._rows)


class _FakeSession:
    """SQL substring'e bakıp uygun rows döner."""

    def __init__(
        self,
        *,
        anomaly_rows: Optional[List[dict]] = None,
        investigation_rows: Optional[List[dict]] = None,
        counts_row: Optional[dict] = None,
    ) -> None:
        self._anomaly = anomaly_rows or []
        self._inv = investigation_rows or []
        self._counts = counts_row or {"active": 0, "completed_today": 0}

    async def execute(self, sql_obj: Any, params: Optional[dict] = None):
        sql_text = str(sql_obj)
        if "fuel_investigations" in sql_text:
            return _FakeResult(self._inv)
        if "FROM anomalies" in sql_text and "resolved_at IS NULL" in sql_text:
            return _FakeResult(self._anomaly)
        if "FILTER (WHERE durum = 'Planned')" in sql_text:
            return _FakeResult([self._counts])
        return _FakeResult([])


class _FakeUoW:
    def __init__(self, **kw) -> None:
        self.session = _FakeSession(**kw)

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return None


# ── _map_anomaly_severity ─────────────────────────────────────────────
@pytest.mark.parametrize(
    "raw, expected",
    [
        (None, "low"),
        ("", "low"),
        ("CRITICAL", "critical"),
        ("high", "high"),
        ("medium", "medium"),
        ("low", "low"),
        ("unknown_value", "low"),
    ],
)
def test_map_anomaly_severity(raw, expected):
    from v2.modules.reports.application.aggregate_today_triage import (
        _map_anomaly_severity,
    )

    assert _map_anomaly_severity(raw) == expected


# ── _map_maintenance_risk ─────────────────────────────────────────────
@pytest.mark.parametrize(
    "risk, expected",
    [
        ("overdue", "critical"),
        ("soon", "high"),
        ("normal", "medium"),
        ("low", "low"),
        (None, "low"),
        ("unknown", "low"),
    ],
)
def test_map_maintenance_risk(risk, expected):
    from v2.modules.reports.application.aggregate_today_triage import (
        _map_maintenance_risk,
    )

    assert _map_maintenance_risk(risk) == expected


# ── _sort_items ───────────────────────────────────────────────────────
def test_sort_items_critical_first():
    from v2.modules.reports.application.aggregate_today_triage import (
        TriageItem,
        _sort_items,
    )

    now = datetime.now(timezone.utc)
    items = [
        TriageItem(
            id="a",
            category="anomaly",
            severity="low",
            title="x",
            subtitle="",
            timestamp=now,
        ),
        TriageItem(
            id="b",
            category="anomaly",
            severity="critical",
            title="y",
            subtitle="",
            timestamp=now,
        ),
        TriageItem(
            id="c",
            category="anomaly",
            severity="medium",
            title="z",
            subtitle="",
            timestamp=now,
        ),
    ]
    sorted_items = _sort_items(items)
    assert [i.severity for i in sorted_items] == ["critical", "medium", "low"]


def test_sort_items_same_severity_newer_first():
    from v2.modules.reports.application.aggregate_today_triage import (
        TriageItem,
        _sort_items,
    )

    older = datetime.now(timezone.utc) - timedelta(hours=2)
    newer = datetime.now(timezone.utc) - timedelta(minutes=10)
    items = [
        TriageItem(
            id="old",
            category="anomaly",
            severity="critical",
            title="x",
            subtitle="",
            timestamp=older,
        ),
        TriageItem(
            id="new",
            category="anomaly",
            severity="critical",
            title="y",
            subtitle="",
            timestamp=newer,
        ),
    ]
    sorted_items = _sort_items(items)
    assert sorted_items[0].id == "new"


# ── aggregate_today_triage ────────────────────────────────────────────
@pytest.mark.asyncio
async def test_aggregate_empty_returns_zero_counts(monkeypatch):
    """Hiç veri yok → 0 counts, empty items list."""
    import v2.modules.reports.application.aggregate_today_triage as triage_aggregator

    # D.1 MaintenancePredictor.predict_all → empty
    class _EmptyPredictor:
        async def predict_all(self):
            return []

    monkeypatch.setattr(
        "v2.modules.fleet.domain.maintenance_prediction.MaintenancePredictor",
        _EmptyPredictor,
    )

    uow = _FakeUoW()
    result = await triage_aggregator.aggregate_today_triage(uow)
    assert result.critical_count == 0
    assert result.pending_count == 0
    assert result.items == []
    assert result.active_trips_count == 0
    assert result.completed_today_count == 0


@pytest.mark.asyncio
async def test_aggregate_anomaly_critical_first(monkeypatch):
    """1 critical + 1 low anomaly → critical önce sıralı."""
    import v2.modules.reports.application.aggregate_today_triage as triage_aggregator

    class _EmptyPredictor:
        async def predict_all(self):
            return []

    monkeypatch.setattr(
        "v2.modules.fleet.domain.maintenance_prediction.MaintenancePredictor",
        _EmptyPredictor,
    )

    now = datetime.now(timezone.utc)
    anomaly_rows = [
        {
            "id": 1,
            "severity": "low",
            "tip": "tuketim",
            "sapma_yuzde": 5.0,
            "tarih": now.date(),
            "created_at": now - timedelta(hours=1),
            "aciklama": "düşük sapma",
            "plaka": "34 ABC 1",
        },
        {
            "id": 2,
            "severity": "critical",
            "tip": "tuketim",
            "sapma_yuzde": 45.0,
            "tarih": now.date(),
            "created_at": now,
            "aciklama": "yüksek sapma",
            "plaka": "34 ABC 2",
        },
    ]
    uow = _FakeUoW(anomaly_rows=anomaly_rows)
    result = await triage_aggregator.aggregate_today_triage(uow, limit=10)
    assert result.critical_count == 1
    assert result.pending_count == 1
    assert result.items[0].id == "anomaly:2"
    assert result.items[0].severity == "critical"


@pytest.mark.asyncio
async def test_aggregate_maintenance_filters_far_future(monkeypatch):
    """30 gün sonraki bakım triage'a girmemeli (>7 gün)."""
    from datetime import date

    import v2.modules.reports.application.aggregate_today_triage as triage_aggregator

    class _Pred:
        def __init__(self, predicted_date, predictable=True, risk_level="normal"):
            self.predictable = predictable
            self.predicted_date = predicted_date
            self.risk_level = risk_level
            self.confidence = 0.8
            self.arac_id = 1
            self.plaka = "34 X 1"
            self.bakim_tipi = "PERIYODIK"

    class _PredictorWith2:
        async def predict_all(self):
            return [
                _Pred(date.today() + timedelta(days=3)),  # dahil (3 gün)
                _Pred(date.today() + timedelta(days=30)),  # dışlanır (30 gün)
                _Pred(date.today() - timedelta(days=5)),  # dahil (gecikti)
            ]

    monkeypatch.setattr(
        "v2.modules.fleet.domain.maintenance_prediction.MaintenancePredictor",
        _PredictorWith2,
    )

    uow = _FakeUoW()
    result = await triage_aggregator.aggregate_today_triage(uow, limit=20)
    assert len(result.items) == 2  # sadece 3g + gecikme


@pytest.mark.asyncio
async def test_aggregate_investigation_severity_mapping(monkeypatch):
    """high suspicion → critical (B kanalı en kritik)."""
    import v2.modules.reports.application.aggregate_today_triage as triage_aggregator

    class _EmptyPredictor:
        async def predict_all(self):
            return []

    monkeypatch.setattr(
        "v2.modules.fleet.domain.maintenance_prediction.MaintenancePredictor",
        _EmptyPredictor,
    )

    inv_rows = [
        {
            "id": 42,
            "suspicion_level": "high",
            "suspicion_score": 0.85,
            "created_at": datetime.now(timezone.utc),
            "plaka": "34 SUS 99",
            "sapma_yuzde": 35.0,
        },
    ]
    uow = _FakeUoW(investigation_rows=inv_rows)
    result = await triage_aggregator.aggregate_today_triage(uow)
    inv_items = [i for i in result.items if i.category == "investigation"]
    assert len(inv_items) == 1
    assert inv_items[0].severity == "critical"
    assert inv_items[0].id == "investigation:42"


@pytest.mark.asyncio
async def test_aggregate_active_trips_counter(monkeypatch):
    """Counter sayıları ayrı SQL'den geliyor — sıralamayı etkilemez."""
    import v2.modules.reports.application.aggregate_today_triage as triage_aggregator

    class _EmptyPredictor:
        async def predict_all(self):
            return []

    monkeypatch.setattr(
        "v2.modules.fleet.domain.maintenance_prediction.MaintenancePredictor",
        _EmptyPredictor,
    )

    uow = _FakeUoW(counts_row={"active": 23, "completed_today": 12})
    result = await triage_aggregator.aggregate_today_triage(uow)
    assert result.active_trips_count == 23
    assert result.completed_today_count == 12


@pytest.mark.asyncio
async def test_aggregate_limit_respected(monkeypatch):
    """limit=5 → max 5 item döner."""
    import v2.modules.reports.application.aggregate_today_triage as triage_aggregator

    class _EmptyPredictor:
        async def predict_all(self):
            return []

    monkeypatch.setattr(
        "v2.modules.fleet.domain.maintenance_prediction.MaintenancePredictor",
        _EmptyPredictor,
    )

    now = datetime.now(timezone.utc)
    anomaly_rows = [
        {
            "id": i,
            "severity": "medium",
            "tip": "tuketim",
            "sapma_yuzde": 10.0 + i,
            "tarih": now.date(),
            "created_at": now - timedelta(minutes=i),
            "aciklama": f"a{i}",
            "plaka": f"34 X {i}",
        }
        for i in range(20)
    ]
    uow = _FakeUoW(anomaly_rows=anomaly_rows)
    result = await triage_aggregator.aggregate_today_triage(uow, limit=5)
    assert len(result.items) == 5
