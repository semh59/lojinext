"""with_async_retry — Phase 2.4 unit tests.

asyncio.sleep'i monkeypatch ile bypass ediyoruz; backoff zamanlamasını
gözlemliyoruz.
"""

from __future__ import annotations

import asyncio

import httpx
import pytest

from v2.modules.route_simulation.infrastructure.retry import with_async_retry


async def test_first_attempt_success_returns_result():
    async def fn():
        return 42

    result = await with_async_retry(fn, max_attempts=3)
    assert result == 42


async def test_retries_on_request_error_and_eventually_succeeds(monkeypatch):
    sleeps: list[float] = []

    async def fake_sleep(s):
        sleeps.append(s)

    monkeypatch.setattr("v2.modules.route_simulation.infrastructure.retry.asyncio.sleep", fake_sleep)

    attempts = {"count": 0}

    async def flaky():
        attempts["count"] += 1
        if attempts["count"] < 3:
            raise httpx.ConnectError("transient")
        return "ok"

    result = await with_async_retry(flaky, max_attempts=3, base_delay_s=0.5)
    assert result == "ok"
    assert attempts["count"] == 3
    # 2 retry sleep: 0.5s, 1.0s (base × 2^attempt için 0.5×1, 0.5×2)
    assert sleeps == [pytest.approx(0.5), pytest.approx(1.0)]


async def test_exhausts_attempts_raises_last_exception(monkeypatch):
    async def fake_sleep(_s):
        pass

    monkeypatch.setattr("v2.modules.route_simulation.infrastructure.retry.asyncio.sleep", fake_sleep)

    async def always_fail():
        raise httpx.ReadError("oops")

    with pytest.raises(httpx.ReadError):
        await with_async_retry(always_fail, max_attempts=3)


async def test_non_retryable_exception_propagates_immediately(monkeypatch):
    sleeps: list[float] = []

    async def fake_sleep(s):
        sleeps.append(s)

    monkeypatch.setattr("v2.modules.route_simulation.infrastructure.retry.asyncio.sleep", fake_sleep)

    async def fn():
        raise ValueError("not retryable")

    with pytest.raises(ValueError):
        await with_async_retry(fn, max_attempts=3)
    # ValueError default retry_on listesinde değil → sleep çağrılmamalı
    assert sleeps == []


async def test_zero_max_attempts_raises_value_error():
    async def fn():
        return 1

    with pytest.raises(ValueError):
        await with_async_retry(fn, max_attempts=0)


async def test_custom_retry_on_classes(monkeypatch):
    async def fake_sleep(_s):
        pass

    monkeypatch.setattr("v2.modules.route_simulation.infrastructure.retry.asyncio.sleep", fake_sleep)

    attempts = {"n": 0}

    async def fn():
        attempts["n"] += 1
        if attempts["n"] < 2:
            raise RuntimeError("transient")
        return "done"

    result = await with_async_retry(fn, max_attempts=3, retry_on=(RuntimeError,))
    assert result == "done"
    assert attempts["n"] == 2


async def test_args_kwargs_forwarded(monkeypatch):
    captured = []

    async def fn(a, b, c=None):
        captured.append((a, b, c))
        return a + b

    result = await with_async_retry(fn, 1, 2, c="hello")
    assert result == 3
    assert captured == [(1, 2, "hello")]


async def test_timeout_error_is_retryable_by_default(monkeypatch):
    sleeps: list[float] = []

    async def fake_sleep(s):
        sleeps.append(s)

    monkeypatch.setattr("v2.modules.route_simulation.infrastructure.retry.asyncio.sleep", fake_sleep)

    attempts = {"n": 0}

    async def fn():
        attempts["n"] += 1
        if attempts["n"] < 2:
            raise asyncio.TimeoutError()
        return "ok"

    result = await with_async_retry(fn, max_attempts=3)
    assert result == "ok"
    assert sleeps == [pytest.approx(0.5)]
