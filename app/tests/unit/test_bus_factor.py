"""Feature E.7 — Bus factor tests (plan §10 uyumlu)."""

from __future__ import annotations

from typing import Any, Optional

import pytest


# ── Fake DB ────────────────────────────────────────────────────────────
class _FakeMappings:
    def __init__(self, rows) -> None:
        self._rows = rows

    def all(self):
        return self._rows


class _FakeResult:
    def __init__(self, rows) -> None:
        self._rows = rows

    def mappings(self):
        return _FakeMappings(self._rows)


class _FakeSession:
    def __init__(self, rows) -> None:
        self._rows = rows

    async def execute(self, sql_obj: Any, params: Optional[dict] = None):
        return _FakeResult(self._rows)


class _FakeUoW:
    def __init__(self, rows) -> None:
        self.session = _FakeSession(rows)

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return None


# ── _risk_level_for_loss ───────────────────────────────────────────────
@pytest.mark.parametrize(
    "loss, expected",
    [
        (0, "low"),
        (50_000, "low"),  # threshold (>50K → medium)
        (50_001, "medium"),
        (200_000, "medium"),  # threshold (>200K → high)
        (200_001, "high"),
        (1_000_000, "high"),
    ],
)
def test_risk_level_for_loss_boundaries(loss, expected):
    from v2.modules.analytics_executive.domain.bus_factor_scoring import (
        risk_level_for_loss,
    )

    assert risk_level_for_loss(loss) == expected


# ── _median_score ──────────────────────────────────────────────────────
def test_median_score_empty_rest_uses_fallback():
    from v2.modules.analytics_executive.domain.bus_factor_scoring import (
        MEDIAN_FALLBACK,
        median_score,
    )

    assert median_score([]) == MEDIAN_FALLBACK


def test_median_score_odd_count():
    from v2.modules.analytics_executive.domain.bus_factor_scoring import median_score

    rows = [{"score": 0.8}, {"score": 1.2}, {"score": 1.5}]
    assert median_score(rows) == 1.2


def test_median_score_even_count():
    """Median = sorted'in mid (len//2) eleman; plan §10.1 sorted_scores[len//2]."""
    from v2.modules.analytics_executive.domain.bus_factor_scoring import median_score

    rows = [{"score": 0.5}, {"score": 1.0}, {"score": 1.5}, {"score": 2.0}]
    # len=4, mid=2 → sorted[2] = 1.5 (upper of mid)
    assert median_score(rows) == 1.5


# ── _compute_loss_tl ──────────────────────────────────────────────────
def test_compute_loss_tl_no_gap_returns_zero():
    """Top-N skoru medyandan düşük/eşit → loss=0 (max(0, gap))."""
    from v2.modules.analytics_executive.domain.bus_factor_scoring import compute_loss_tl

    top = [{"score": 1.0, "yearly_km": 50_000}]
    assert compute_loss_tl(top, 1.5, 50.0) == 0.0


def test_compute_loss_tl_positive_gap():
    """Top-N skoru medyandan yüksek → loss > 0."""
    from v2.modules.analytics_executive.domain.bus_factor_scoring import (
        LOSS_L_PER_KM,
        compute_loss_tl,
    )

    top = [{"score": 1.5, "yearly_km": 100_000}]
    # gap = 1.5 - 1.0 = 0.5; loss_l = 100k × 0.5 × 0.5/100 = 250; ×50 = 12500
    expected = 100_000 * 0.5 * LOSS_L_PER_KM / 100.0 * 50.0
    assert compute_loss_tl(top, 1.0, 50.0) == expected


# ── compute_bus_factor e2e ────────────────────────────────────────────
@pytest.mark.asyncio
async def test_compute_bus_factor_empty_fleet():
    """Hiç şoför yok → 0 kayıp, risk_level=low."""
    from v2.modules.analytics_executive.application.get_bus_factor import (
        compute_bus_factor,
    )

    uow = _FakeUoW([])
    report = await compute_bus_factor(uow, n=3, diesel_price_tl=50.0)
    assert report.top_n_drivers_loss_tl == 0.0
    assert report.top_n_drivers == []
    assert report.bottlenecked_routes == []
    assert report.risk_level == "low"
    assert report.n == 3


@pytest.mark.asyncio
async def test_compute_bus_factor_returns_pii_safe_top_n():
    """Plan §15: top_n_drivers'da yalnız score + yearly_km; ad/id yok."""
    from v2.modules.analytics_executive.application.get_bus_factor import (
        compute_bus_factor,
    )

    rows = [
        {"id": 1, "score": 1.8, "yearly_km": 100_000},
        {"id": 2, "score": 1.5, "yearly_km": 80_000},
        {"id": 3, "score": 1.0, "yearly_km": 60_000},
        {"id": 4, "score": 0.9, "yearly_km": 50_000},
    ]
    uow = _FakeUoW(rows)
    report = await compute_bus_factor(uow, n=2, diesel_price_tl=50.0)
    assert len(report.top_n_drivers) == 2
    for d in report.top_n_drivers:
        assert set(d.keys()) == {"score", "yearly_km"}  # PII koruma
        assert "ad" not in d and "id" not in d and "name" not in d


@pytest.mark.asyncio
async def test_compute_bus_factor_high_risk_triggers_threshold():
    """Çok yüksek kayıp → risk_level='high'."""
    from v2.modules.analytics_executive.application.get_bus_factor import (
        compute_bus_factor,
    )

    # gap=0.5 × yearly_km=10_000_000 × 0.005 × 50 = 1_250_000 TL → high
    rows = [
        {"id": 1, "score": 1.5, "yearly_km": 10_000_000},
        {"id": 2, "score": 1.0, "yearly_km": 500_000},
        {"id": 3, "score": 1.0, "yearly_km": 500_000},
    ]
    uow = _FakeUoW(rows)
    report = await compute_bus_factor(uow, n=1, diesel_price_tl=50.0)
    assert report.top_n_drivers_loss_tl > 200_000
    assert report.risk_level == "high"


@pytest.mark.asyncio
async def test_compute_bus_factor_medium_risk():
    """Orta seviye kayıp → risk_level='medium'."""
    from v2.modules.analytics_executive.application.get_bus_factor import (
        compute_bus_factor,
    )

    # gap=0.5 × yearly_km=1_000_000 × 0.005 × 50 = 125_000 TL → medium
    rows = [
        {"id": 1, "score": 1.5, "yearly_km": 1_000_000},
        {"id": 2, "score": 1.0, "yearly_km": 100_000},
        {"id": 3, "score": 1.0, "yearly_km": 100_000},
    ]
    uow = _FakeUoW(rows)
    report = await compute_bus_factor(uow, n=1, diesel_price_tl=50.0)
    assert 50_000 < report.top_n_drivers_loss_tl <= 200_000
    assert report.risk_level == "medium"


@pytest.mark.asyncio
async def test_compute_bus_factor_no_rest_uses_fallback_median():
    """n >= rows sayısı → rest boş → median fallback 1.0."""
    from v2.modules.analytics_executive.application.get_bus_factor import (
        compute_bus_factor,
    )

    rows = [
        {"id": 1, "score": 1.3, "yearly_km": 100_000},
        {"id": 2, "score": 1.2, "yearly_km": 80_000},
    ]
    uow = _FakeUoW(rows)
    report = await compute_bus_factor(uow, n=5, diesel_price_tl=50.0)
    # 2 şoför var ama n=5 → top_n=2, rest=0 → median fallback 1.0
    assert len(report.top_n_drivers) == 2
    # gap[0] = 0.3, gap[1] = 0.2 → loss > 0 (medyandan yüksek)
    assert report.top_n_drivers_loss_tl > 0


@pytest.mark.asyncio
async def test_compute_bus_factor_all_same_score_no_loss():
    """Tüm şoförlerin skoru eşit → gap=0 → loss=0."""
    from v2.modules.analytics_executive.application.get_bus_factor import (
        compute_bus_factor,
    )

    rows = [{"id": i, "score": 1.0, "yearly_km": 100_000} for i in range(5)]
    uow = _FakeUoW(rows)
    report = await compute_bus_factor(uow, n=3, diesel_price_tl=50.0)
    assert report.top_n_drivers_loss_tl == 0
    assert report.risk_level == "low"


@pytest.mark.asyncio
async def test_compute_bus_factor_top_n_loss_value_correct():
    """Plan §10.1 formül doğrulama (sayısal)."""
    from v2.modules.analytics_executive.application.get_bus_factor import (
        compute_bus_factor,
    )
    from v2.modules.analytics_executive.domain.bus_factor_scoring import (
        LOSS_L_PER_KM,
    )

    rows = [
        # Top 1: gap=0.5, yearly_km=200k → loss_l = 500 → 25k TL
        {"id": 1, "score": 1.5, "yearly_km": 200_000},
        # Rest medyan 1.0
        {"id": 2, "score": 1.0, "yearly_km": 100_000},
        {"id": 3, "score": 1.0, "yearly_km": 100_000},
        {"id": 4, "score": 1.0, "yearly_km": 100_000},
    ]
    uow = _FakeUoW(rows)
    report = await compute_bus_factor(uow, n=1, diesel_price_tl=50.0)
    # gap=0.5, loss_l = 200000 × 0.5 × 0.5/100 = 500 L; ×50 = 25_000 TL
    expected_l = 200_000 * 0.5 * LOSS_L_PER_KM / 100.0
    expected_tl = expected_l * 50.0
    assert report.top_n_drivers_loss_tl == round(expected_tl, 0)


@pytest.mark.asyncio
async def test_compute_bus_factor_bottlenecked_routes_empty_v1():
    """v1'de bottlenecked_routes her zaman boş liste (plan §10.1)."""
    from v2.modules.analytics_executive.application.get_bus_factor import (
        compute_bus_factor,
    )

    rows = [
        {"id": 1, "score": 1.2, "yearly_km": 50_000},
    ]
    uow = _FakeUoW(rows)
    report = await compute_bus_factor(uow, n=1)
    assert report.bottlenecked_routes == []
