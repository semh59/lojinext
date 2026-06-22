"""Feature B.3 — theft pattern scan PII regression testi.

Geçmiş bug: logger.warning satırı `sofor_adi` ve `plaka` (PII) basıyordu;
KVKK kapsamında kişisel veri Sentry/Loki backend'ine sızıyordu. Düzeltme
sonrası sadece `sofor_id` ve `arac_id` log'a basılır.

Bu test düzeltmenin korunması için (gelecek regression engelle).
"""

from __future__ import annotations

import logging
from typing import Any, List
from unittest.mock import patch

import pytest


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
    def __init__(self, rows: List[dict]) -> None:
        self._rows = rows

    async def execute(self, query: Any, params: Any = None):
        return _FakeResult(self._rows)


class _FakeUoW:
    def __init__(self, rows: List[dict]) -> None:
        self.session = _FakeSession(rows)

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_a):
        return False


@pytest.mark.asyncio
async def test_theft_pattern_scan_logs_ids_not_pii(caplog):
    """logger.warning'de ad_soyad/plaka YOK, sofor_id/arac_id VAR."""
    from app.workers.tasks import theft_tasks

    fake_rows = [
        {
            "sofor_id": 42,
            "arac_id": 7,
            "sofor_adi": "Ali Veli",  # SQL döndürür ama log'a girmemeli
            "plaka": "34 ABC 123",  # SQL döndürür ama log'a girmemeli
            "occurrence_count": 5,
            "avg_suspicion_score": 0.81,
            "last_seen": "2026-05-20T10:00:00Z",
        },
    ]

    with (
        patch(
            "app.database.unit_of_work.UnitOfWork",
            lambda *a, **kw: _FakeUoW(fake_rows),
        ),
        caplog.at_level(logging.WARNING, logger=theft_tasks.logger.name),
    ):
        result = await theft_tasks._run_pattern_scan(days=30, min_count=3, limit=50)

    assert result["patterns_found"] == 1

    # Tek bir THEFT_PATTERN log kaydı olmalı
    pattern_logs = [r for r in caplog.records if "THEFT_PATTERN" in r.getMessage()]
    assert len(pattern_logs) == 1, "Tek bir pattern log bekleniyor"

    log_msg = pattern_logs[0].getMessage()

    # PII regression: ad_soyad ve plaka log'da OLMAMALI
    assert "Ali Veli" not in log_msg, "PII (ad_soyad) log'a sızdı"
    assert "34 ABC 123" not in log_msg, "PII (plaka) log'a sızdı"
    assert "sofor=" not in log_msg, "Eski PII format string hâlâ var"

    # Bekleneninin doğru olduğunu da assert et
    assert "sofor_id=42" in log_msg
    assert "arac_id=7" in log_msg
    assert "count=5" in log_msg
