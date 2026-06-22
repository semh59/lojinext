from unittest.mock import patch

import pytest

from app.infrastructure.cache.redis_pubsub import RedisPubSubManager
from app.infrastructure.resilience.circuit_breaker import (
    CircuitBreaker,
)


@pytest.mark.asyncio
async def test_distributed_circuit_breaker_tripping():
    """Verify that multiple breakers share state via Redis."""
    cb_name = "test_shared_service"

    # Mock RedisPubSubManager.incr to simulate shared counter
    shared_count = {"val": 0}

    async def mock_incr(key):
        shared_count["val"] += 1
        return shared_count["val"]

    async def mock_get(key):
        return shared_count["val"]

    with (
        patch.object(RedisPubSubManager, "incr", side_effect=mock_incr),
        patch.object(RedisPubSubManager, "get", side_effect=mock_get),
    ):
        # Instance 1 fails 3 times
        cb1 = CircuitBreaker(name=cb_name, max_failures=5)
        for _ in range(3):
            try:
                async with cb1:
                    raise RuntimeError("Fail 1")
            except RuntimeError:
                pass

        # Instance 2 fails 2 times
        cb2 = CircuitBreaker(name=cb_name, max_failures=5)
        for _ in range(2):
            try:
                async with cb2:
                    raise RuntimeError("Fail 2")
            except RuntimeError:
                pass

        # Now total count is 5. Both should be OPEN.
        assert await cb1._get_state() == "OPEN"
        assert await cb2._get_state() == "OPEN"

        # Verify that instance 3 (new) is also OPEN immediately
        cb3 = CircuitBreaker(name=cb_name, max_failures=5)
        assert await cb3._get_state() == "OPEN"
