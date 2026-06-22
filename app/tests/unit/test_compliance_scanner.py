"""Feature E.4 — Compliance scanner tests (plan §7.3 uyumlu)."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any, List, Optional

import pytest


# ── _risk_for_days: 4 sınır (plan §7.3) ────────────────────────────────
@pytest.mark.parametrize(
    "days, expected",
    [
        (-30, "overdue"),
        (-1, "overdue"),
        (0, "soon"),
        (14, "soon"),
        (15, "normal"),
        (60, "normal"),
        (61, "low"),
        (365, "low"),
    ],
)
def test_risk_for_days_boundaries(days, expected):
    from app.core.services.compliance_scanner import _risk_for_days

    assert _risk_for_days(days) == expected


# ── Fake DB session (paylaşılan stub pattern) ──────────────────────────
class _FakeMappings:
    def __init__(self, rows: List[dict]) -> None:
        self._rows = rows

    def all(self):
        return self._rows


class _FakeResult:
    def __init__(self, rows: List[dict]) -> None:
        self._rows = rows

    def mappings(self):
        return _FakeMappings(self._rows)


class _FakeSession:
    """SQL string'de "araclar" vs "dorseler" görerek farklı rows döner."""

    def __init__(
        self,
        arac_rows: List[dict],
        dorse_rows: List[dict],
    ) -> None:
        self._arac = arac_rows
        self._dorse = dorse_rows

    async def execute(self, sql_obj: Any, params: Optional[dict] = None):
        sql_text = str(sql_obj)
        if "araclar" in sql_text:
            return _FakeResult(self._arac)
        if "dorseler" in sql_text:
            return _FakeResult(self._dorse)
        return _FakeResult([])


class _FakeUoW:
    def __init__(self, arac_rows: List[dict], dorse_rows: List[dict]) -> None:
        self.session = _FakeSession(arac_rows, dorse_rows)

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return None


# ── scan_compliance (plan §7.3 integration: 2 araç + 1 dorse → 3 item) ─
@pytest.mark.asyncio
async def test_scan_compliance_2_arac_1_dorse():
    """Plan §7.3 zorunlu test: 2 araç + 1 dorse → 3 item, days_until ASC sıralı."""
    from app.core.services.compliance_scanner import scan_compliance

    today = date.today()
    arac_rows = [
        {
            "id": 1,
            "plaka": "34 ABC 001",
            "muayene_tarihi": today + timedelta(days=5),
        },  # soon
        {
            "id": 2,
            "plaka": "34 ABC 002",
            "muayene_tarihi": today - timedelta(days=10),
        },  # overdue
    ]
    dorse_rows = [
        {
            "id": 99,
            "plaka": "TRL 999",
            "muayene_tarihi": today + timedelta(days=30),
        },  # normal
    ]
    uow = _FakeUoW(arac_rows, dorse_rows)
    items = await scan_compliance(uow, days_horizon=90)

    assert len(items) == 3
    # Sıralama: days_until ASC → önce overdue (-10), sonra +5, sonra +30
    assert items[0].entity_id == 2
    assert items[0].risk_level == "overdue"
    assert items[0].days_until == -10
    assert items[1].entity_id == 1
    assert items[1].risk_level == "soon"
    assert items[1].days_until == 5
    assert items[2].entity_id == 99
    assert items[2].entity_type == "dorse"
    assert items[2].risk_level == "normal"


@pytest.mark.asyncio
async def test_scan_compliance_empty_fleet():
    """Hiç araç yok → boş liste."""
    from app.core.services.compliance_scanner import scan_compliance

    uow = _FakeUoW([], [])
    items = await scan_compliance(uow, days_horizon=90)
    assert items == []


@pytest.mark.asyncio
async def test_scan_compliance_arac_only_no_dorse():
    """Sadece araç verisi → dorse hiç eklenmez."""
    from app.core.services.compliance_scanner import scan_compliance

    today = date.today()
    arac_rows = [
        {"id": 1, "plaka": "X", "muayene_tarihi": today + timedelta(days=20)},
    ]
    uow = _FakeUoW(arac_rows, [])
    items = await scan_compliance(uow, days_horizon=90)
    assert len(items) == 1
    assert items[0].entity_type == "arac"


@pytest.mark.asyncio
async def test_scan_compliance_days_until_calculation():
    """expiry_date korunmalı; days_until = (expiry - today).days."""
    from app.core.services.compliance_scanner import scan_compliance

    today = date.today()
    expiry = today + timedelta(days=45)
    uow = _FakeUoW(
        [{"id": 1, "plaka": "Y", "muayene_tarihi": expiry}],
        [],
    )
    items = await scan_compliance(uow, days_horizon=90)
    assert items[0].expiry_date == expiry
    assert items[0].days_until == 45
    assert items[0].risk_level == "normal"


@pytest.mark.asyncio
async def test_scan_compliance_field_value():
    """v1'de field her zaman 'muayene' (plan §7.2)."""
    from app.core.services.compliance_scanner import scan_compliance

    today = date.today()
    arac = [{"id": 1, "plaka": "X", "muayene_tarihi": today}]
    dorse = [{"id": 2, "plaka": "Y", "muayene_tarihi": today}]
    uow = _FakeUoW(arac, dorse)
    items = await scan_compliance(uow, days_horizon=90)
    assert all(item.field == "muayene" for item in items)
