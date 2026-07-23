"""HATA 5 (LOJINEXT_v7) — get_recent_anomalies sofor_id filtresi.

Geçmiş bug: driver_coaching_engine TÜM filo anomalilerini çekiyordu;
Şoför A için coaching üretirken Şoför B'nin yüksek tüketim anomalisi
Şoför A'nın önerisine sızıyordu.

Bu testler:
1. AnomalyDetector.get_recent_anomalies signature'ında sofor_id
   parametresi var
2. SQL'e gerçekten WHERE sf.sofor_id = :sofor_id filter eklendi
3. Coaching engine sofor_id'yi geçiriyor
"""

from __future__ import annotations

import inspect
from typing import Any, Dict, List
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from v2.modules.shared_kernel.infrastructure.unit_of_work import UnitOfWork


class _FakeResult:
    def __init__(self, rows: List[Dict[str, Any]]):
        self._rows = rows

    def fetchall(self):
        return [type("Row", (), {"_mapping": r})() for r in self._rows]


class _FakeSession:
    def __init__(self, rows: List[Dict[str, Any]]):
        self.rows = rows
        self.last_sql = ""
        self.last_params: Dict[str, Any] = {}

    async def execute(self, query: Any, params: Dict[str, Any] = None):
        self.last_sql = str(query)
        self.last_params = params or {}
        return _FakeResult(self.rows)


class _FakeUoW:
    def __init__(self, rows: List[Dict[str, Any]]):
        from v2.modules.anomaly.infrastructure.anomaly_repository import (
            AnomalyRepository,
        )

        self.session = _FakeSession(rows)
        self.anomaly_repo = AnomalyRepository(self.session)

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_a):
        return False


def test_get_recent_anomalies_signature_has_sofor_id():
    """API signature regression — sofor_id parametresi olmalı."""
    from v2.modules.anomaly.application.detect_anomaly import AnomalyDetector

    sig = inspect.signature(AnomalyDetector.get_recent_anomalies)
    assert "sofor_id" in sig.parameters, (
        "get_recent_anomalies(sofor_id=...) parametresi yok — "
        "coaching engine tüm filo anomalilerine erişiyor (HATA 5)"
    )
    # Optional[int] = None
    assert sig.parameters["sofor_id"].default is None


@pytest.mark.asyncio
async def test_get_recent_anomalies_applies_sofor_filter():
    """sofor_id verildiğinde SQL'e WHERE sf.sofor_id = :sofor_id eklenmeli."""
    from v2.modules.anomaly.application import detect_anomaly as mod

    fake_uow = _FakeUoW(rows=[])
    with (
        patch.object(UnitOfWork, "__aenter__", AsyncMock(return_value=fake_uow)),
        patch.object(UnitOfWork, "__aexit__", AsyncMock(return_value=False)),
    ):
        detector = mod.AnomalyDetector()
        await detector.get_recent_anomalies(days=30, status="open", sofor_id=42)

    assert "sf.sofor_id = :sofor_id" in fake_uow.session.last_sql, (
        "SQL'de sofor_id filtresi yok"
    )
    assert fake_uow.session.last_params.get("sofor_id") == 42


@pytest.mark.asyncio
async def test_get_recent_anomalies_no_filter_when_sofor_id_none():
    """sofor_id=None ise filtre eklenmemeli (tüm filo davranışı korunur)."""
    from v2.modules.anomaly.application import detect_anomaly as mod

    fake_uow = _FakeUoW(rows=[])
    with (
        patch.object(UnitOfWork, "__aenter__", AsyncMock(return_value=fake_uow)),
        patch.object(UnitOfWork, "__aexit__", AsyncMock(return_value=False)),
    ):
        detector = mod.AnomalyDetector()
        await detector.get_recent_anomalies(days=30, status="open")

    assert "sf.sofor_id = :sofor_id" not in fake_uow.session.last_sql
    assert "sofor_id" not in fake_uow.session.last_params


@pytest.mark.asyncio
async def test_coaching_engine_passes_sofor_id_to_detector():
    """driver_coaching_engine sofor_id'yi detector'a iletmeli."""
    from v2.modules.driver.application import generate_coaching as mod

    # Engine ve detector mock'la
    engine = mod.DriverCoachingEngine.__new__(mod.DriverCoachingEngine)
    engine.detector = MagicMock()
    engine.detector.get_recent_anomalies = AsyncMock(return_value=[])
    engine.groq = MagicMock()
    engine.groq.chat = AsyncMock(return_value="{}")

    # UoW + sofor + score + route_profile
    class _FakeSoforRepo:
        async def get_by_id(self, sid):
            return {"id": sid, "ad_soyad": "Test", "aktif": True}

    class _FakeUoWLocal:
        def __init__(self):
            self.sofor_repo = _FakeSoforRepo()

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_a):
            return False

    fake_uow_local = _FakeUoWLocal()
    with (
        patch.object(UnitOfWork, "__aenter__", AsyncMock(return_value=fake_uow_local)),
        patch.object(UnitOfWork, "__aexit__", AsyncMock(return_value=False)),
        patch(
            "v2.modules.driver.application.generate_coaching.get_score_breakdown_sofor",
            AsyncMock(return_value={"trip_count": 1}),
        ),
        patch(
            "v2.modules.driver.application.generate_coaching.get_route_profile_sofor",
            AsyncMock(return_value={}),
        ),
    ):
        await engine.generate_coaching(sofor_id=99)

    # detector.get_recent_anomalies sofor_id=99 ile çağrılmalı
    engine.detector.get_recent_anomalies.assert_called_once()
    call_kwargs = engine.detector.get_recent_anomalies.call_args.kwargs
    assert call_kwargs.get("sofor_id") == 99, (
        f"Coaching engine sofor_id=99 geçirmedi: {call_kwargs}"
    )
