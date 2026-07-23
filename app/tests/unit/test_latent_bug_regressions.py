"""Regression tests for latent bugs found during the 2026-06-04 prod-readiness audit.

These bugs were discovered as a side-effect of coverage work and fixed in the
GO operation. Each test pins the corrected behavior so the bug cannot silently
return.
"""

from unittest.mock import MagicMock

import pytest

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# Bug 1: fuel.py async upload imported a non-existent factory
#   `get_background_job_manager` (module only exports `get_job_manager`),
#   so the async upload path crashed with ImportError before doing any work.
# ---------------------------------------------------------------------------


def test_job_manager_factory_name_exists():
    """The factory fuel.py imports must actually exist in the module."""
    from v2.modules.platform_infra.background import job_manager

    assert hasattr(job_manager, "get_job_manager")
    # The buggy name must NOT be what the endpoint relies on.
    assert not hasattr(job_manager, "get_background_job_manager")


def test_fuel_async_upload_imports_resolve():
    """The async-upload import block in fuel.py must import cleanly.

    Reproduces the exact import the endpoint performs at request time.
    """
    from v2.modules.platform_infra.background.job_manager import (  # noqa: F401
        get_job_manager,
    )

    mgr = get_job_manager()
    assert hasattr(mgr, "submit")


# ---------------------------------------------------------------------------
# Bug 2: redis_cache.RedisCache.get_stats() referenced `self._fallback_cache`
#   which never exists (the real attribute is `self._fallback`, a
#   CacheManager). On the memory backend path this raised AttributeError.
#   A dead `_evict_fallback_if_needed` referencing the same phantom attrs
#   was also removed.
# ---------------------------------------------------------------------------


def test_redis_cache_get_stats_memory_backend_no_crash():
    """get_stats() on the memory backend must not raise AttributeError."""
    from v2.modules.platform_infra.cache.redis_cache import RedisCache

    rc = RedisCache()
    rc._redis_client = None  # force memory/fallback path

    stats = rc.get_stats()

    assert stats["backend"] == "memory"
    # The fallback CacheManager's own stats are surfaced (not a phantom attr).
    assert "fallback" in stats
    assert isinstance(stats["fallback"], dict)


def test_redis_cache_no_phantom_fallback_attr_references():
    """The removed phantom attributes must not reappear in the class."""
    import inspect

    from v2.modules.platform_infra.cache import redis_cache

    src = inspect.getsource(redis_cache)
    assert "_fallback_cache" not in src
    assert "_fallback_expiry" not in src


def test_redis_cache_get_stats_redis_backend():
    """get_stats() on the redis backend reports redis info without touching fallback."""
    from v2.modules.platform_infra.cache.redis_cache import RedisCache

    rc = RedisCache()
    mock_client = MagicMock()
    mock_client.info.return_value = {"used_memory_human": "1.2M"}
    mock_client.dbsize.return_value = 42
    rc._redis_client = mock_client

    stats = rc.get_stats()

    assert stats["backend"] == "redis"
    assert stats["keys"] == 42
    assert stats["used_memory"] == "1.2M"
