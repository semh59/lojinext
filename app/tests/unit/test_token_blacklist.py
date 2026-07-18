"""Unit tests for TokenBlacklist fail-secure behavior (SEC-004).

Note: the autouse ``bypass_token_blacklist`` conftest fixture replaces the
singleton's ``is_blacklisted`` with a stub. To exercise the *real*
implementation we call the class-level function directly (bypassing the
instance-attribute shadow).
"""

from unittest.mock import AsyncMock, patch

import pytest

import v2.modules.auth_rbac.infrastructure.token_blacklist as tb

pytestmark = pytest.mark.asyncio

# Real implementation, unaffected by the conftest instance-level stub.
_real_is_blacklisted = tb.TokenBlacklist.is_blacklisted


async def test_is_blacklisted_true_when_present():
    bl = tb.TokenBlacklist()
    with patch.object(tb, "get_redis_val", new=AsyncMock(return_value="1")):
        assert await _real_is_blacklisted(bl, "tok") is True


async def test_is_blacklisted_false_when_absent():
    bl = tb.TokenBlacklist()
    with patch.object(tb, "get_redis_val", new=AsyncMock(return_value=None)):
        assert await _real_is_blacklisted(bl, "tok") is False


async def test_is_blacklisted_fails_secure_on_redis_error():
    """SEC-004: Redis erişilemezse token revoked sayılır (True), bypass DEĞİL."""
    bl = tb.TokenBlacklist()
    with patch.object(
        tb, "get_redis_val", new=AsyncMock(side_effect=Exception("Redis down"))
    ):
        assert await _real_is_blacklisted(bl, "tok") is True
