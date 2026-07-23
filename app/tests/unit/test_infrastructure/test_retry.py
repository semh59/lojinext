"""
Unit tests for with_async_retry and DEFAULT_RETRYABLE_EXCEPTIONS.
asyncio.sleep is patched to avoid real delays.
"""

import asyncio
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from v2.modules.route_simulation.infrastructure.retry import (
    DEFAULT_RETRYABLE_EXCEPTIONS,
    with_async_retry,
)

pytestmark = pytest.mark.unit


class TestRetry:
    async def test_basic_initialization(self):
        """DEFAULT_RETRYABLE_EXCEPTIONS contains expected exception types."""
        assert httpx.RequestError in DEFAULT_RETRYABLE_EXCEPTIONS
        assert asyncio.TimeoutError in DEFAULT_RETRYABLE_EXCEPTIONS
        assert ConnectionError in DEFAULT_RETRYABLE_EXCEPTIONS

    async def test_happy_path(self):
        """Successful function returns its value on first attempt."""
        call_count = 0

        async def always_succeeds():
            nonlocal call_count
            call_count += 1
            return "result"

        result = await with_async_retry(always_succeeds, max_attempts=3)

        assert result == "result"
        assert call_count == 1

    async def test_error_handling_exhausts_attempts(self):
        """Raises last exception after max_attempts exhausted."""
        call_count = 0

        async def always_fails():
            nonlocal call_count
            call_count += 1
            raise ConnectionError("network error")

        with patch("asyncio.sleep", AsyncMock()):
            with pytest.raises(ConnectionError, match="network error"):
                await with_async_retry(always_fails, max_attempts=3, base_delay_s=0.0)

        assert call_count == 3

    async def test_edge_case_empty(self):
        """max_attempts=1 makes a single attempt; no retry on failure."""
        call_count = 0

        async def fails_once():
            nonlocal call_count
            call_count += 1
            raise ConnectionError("one try")

        with pytest.raises(ConnectionError):
            await with_async_retry(fails_once, max_attempts=1)

        assert call_count == 1

    async def test_edge_case_none(self):
        """max_attempts < 1 raises ValueError immediately (no attempt)."""

        async def never_called():
            return "should not run"

        with pytest.raises(ValueError, match="max_attempts must be >= 1"):
            await with_async_retry(never_called, max_attempts=0)

    async def test_integration_with_mock(self):
        """Function that fails twice then succeeds retries correctly."""
        attempt = 0

        async def flaky():
            nonlocal attempt
            attempt += 1
            if attempt < 3:
                raise ConnectionError(f"fail {attempt}")
            return "success_on_third"

        with patch("asyncio.sleep", AsyncMock()):
            result = await with_async_retry(flaky, max_attempts=3, base_delay_s=0.0)

        assert result == "success_on_third"
        assert attempt == 3

    async def test_return_type_validation(self):
        """Return value preserves type from the wrapped coroutine."""

        async def returns_dict():
            return {"key": "value", "count": 42}

        result = await with_async_retry(returns_dict, max_attempts=1)

        assert isinstance(result, dict)
        assert result["key"] == "value"

    def test_service_exists(self):
        """with_async_retry is importable from the module."""
        from v2.modules.route_simulation.infrastructure.retry import (
            with_async_retry,  # noqa: F401
        )

        assert callable(with_async_retry)

    async def test_non_retryable_exception_propagates_immediately(self):
        """ValueError (not in retry_on) propagates without retry."""
        call_count = 0

        async def bad_value():
            nonlocal call_count
            call_count += 1
            raise ValueError("not retryable")

        with pytest.raises(ValueError, match="not retryable"):
            await with_async_retry(
                bad_value,
                max_attempts=5,
                retry_on=(ConnectionError,),
            )

        assert call_count == 1

    async def test_backoff_sleep_called_between_retries(self):
        """asyncio.sleep is called with exponential backoff delays."""
        attempt = 0
        sleep_calls = []

        async def side_effect_sleep(delay):
            sleep_calls.append(delay)

        async def fail_twice():
            nonlocal attempt
            attempt += 1
            if attempt <= 2:
                raise ConnectionError("retry me")
            return "done"

        with patch("asyncio.sleep", side_effect=side_effect_sleep):
            result = await with_async_retry(
                fail_twice,
                max_attempts=3,
                base_delay_s=0.5,
                backoff_factor=2.0,
            )

        assert result == "done"
        # First retry delay: 0.5 * 2^0 = 0.5; second retry delay: 0.5 * 2^1 = 1.0
        assert len(sleep_calls) == 2
        assert sleep_calls[0] == pytest.approx(0.5)
        assert sleep_calls[1] == pytest.approx(1.0)

    async def test_args_kwargs_forwarded(self):
        """Positional and keyword args are forwarded to the coroutine."""

        async def echo(x, y, z=0):
            return x + y + z

        result = await with_async_retry(echo, 10, 20, z=5, max_attempts=1)

        assert result == 35

    async def test_httpx_request_error_is_retried(self):
        """httpx.RequestError triggers retry behaviour."""
        attempt = 0

        async def httpx_fails():
            nonlocal attempt
            attempt += 1
            if attempt < 3:
                raise httpx.RequestError("timeout")
            return "http_ok"

        with patch("asyncio.sleep", AsyncMock()):
            result = await with_async_retry(
                httpx_fails, max_attempts=3, base_delay_s=0.0
            )

        assert result == "http_ok"
        assert attempt == 3
