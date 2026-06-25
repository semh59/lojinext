"""Feature A.2 — weekly_coaching_digest timeout regression testleri.

Geçmiş bug: weekly_coaching_digest task'ı global task_time_limit=90s'i
miras alıyordu. 500 şoför × ~2s Groq LLM ≈ 1000s — Pazartesi 09:00'da
~45 şoför işlendikten sonra SoftTimeLimitExceeded ile retry zinciri
hiç tamamlanamıyordu.

Bu testler:
1. Task decorator'da özel soft/hard limit'in tanımlı olduğunu doğrular
2. _run_digest SoftTimeLimitExceeded'i yakalayıp partial result döndürür
3. Partial result `timeout_partial=True` ve `processed < total` içerir
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from celery.exceptions import SoftTimeLimitExceeded

from app.database.models import Sofor


def test_weekly_digest_has_custom_time_limits():
    """Task decorator'ı soft_time_limit ve time_limit override etmeli."""
    from app.workers.tasks.coaching_tasks import (
        WEEKLY_DIGEST_HARD_LIMIT,
        WEEKLY_DIGEST_SOFT_LIMIT,
        weekly_coaching_digest,
    )

    # Sabitler makul aralıkta (1 saatlik batch için)
    assert WEEKLY_DIGEST_SOFT_LIMIT >= 1800, "1 saatten az soft limit yetmez"
    assert WEEKLY_DIGEST_HARD_LIMIT > WEEKLY_DIGEST_SOFT_LIMIT, (
        "Hard limit, soft'tan büyük olmalı"
    )

    # Celery task decorator field'ları
    task = weekly_coaching_digest
    assert task.soft_time_limit == WEEKLY_DIGEST_SOFT_LIMIT, (
        "Task soft_time_limit set edilmemiş (global 70s kullanılıyor)"
    )
    assert task.time_limit == WEEKLY_DIGEST_HARD_LIMIT, (
        "Task time_limit set edilmemiş (global 90s kullanılıyor)"
    )


@pytest.mark.asyncio
async def test_run_digest_partial_on_soft_time_limit(db_session):
    """SoftTimeLimitExceeded 3. şoförde fırlatıldığında: 2 işlenmiş,
    timeout_partial=True olmalı; exception caller'a propagasyon YOK (real DB)."""
    from app.workers.tasks import coaching_tasks as mod

    # Seed 5 real Sofor rows
    for i in range(1, 6):
        db_session.add(Sofor(ad_soyad=f"Koç Sofor D20 A{i}", aktif=True))
    await db_session.flush()

    # Engine: 3. çağrıda SoftTimeLimitExceeded fırlatsın
    call_count = {"n": 0}

    class _FakeInsights:
        priority = "low"
        insights: list = []
        headline = "h"

    fake_engine = AsyncMock()

    async def _fake_generate(sid):
        call_count["n"] += 1
        if call_count["n"] == 3:
            raise SoftTimeLimitExceeded()
        return _FakeInsights()

    fake_engine.generate_coaching = _fake_generate

    with patch(
        "app.core.ai.driver_coaching_engine.get_driver_coaching_engine",
        return_value=fake_engine,
    ):
        result = await mod._run_digest()

    # Partial: 2 başarılı (1+2), 3. timeout, 4+5 hiç çağrılmadı
    assert result["timeout_partial"] is True, "Partial bayrağı yok"
    assert result["processed"] == 2, f"2 başarılı olmalı, oldu={result['processed']}"
    assert result["total"] >= 5
    assert result["errors"] == 0, "SoftTimeLimit errors'a sayılmamalı"


@pytest.mark.asyncio
async def test_run_digest_normal_path_no_timeout_flag(db_session):
    """Tüm şoförler işlenirse timeout_partial=False ve processed==total (real DB)."""
    from app.workers.tasks import coaching_tasks as mod

    # Seed 3 real Sofor rows
    for i in range(1, 4):
        db_session.add(Sofor(ad_soyad=f"Koç Sofor D20 B{i}", aktif=True))
    await db_session.flush()

    class _FakeInsights:
        priority = "low"
        insights: list = []
        headline = "h"

    fake_engine = AsyncMock()
    fake_engine.generate_coaching = AsyncMock(return_value=_FakeInsights())

    with patch(
        "app.core.ai.driver_coaching_engine.get_driver_coaching_engine",
        return_value=fake_engine,
    ):
        result = await mod._run_digest()

    assert result["timeout_partial"] is False
    assert result["processed"] >= 3
    assert result["total"] >= 3
