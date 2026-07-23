from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from v2.modules.admin_platform.application.konfig_service import (
    get_config_value,
    update_config,
)


@pytest.mark.asyncio
async def test_konfig_get_value_cache_hit_miss():
    """Test standard cache hit/miss behavior for konfig_service.get_config_value."""

    # Mocking RedisCache
    mock_cache = MagicMock()
    # First call returns None (miss), second returns value (hit)
    mock_cache.get.side_effect = [None, 9.81]

    # Mocking Repository
    mock_repo = AsyncMock()
    mock_repo.get_value.return_value = 9.81

    with (
        patch(
            "v2.modules.admin_platform.application.konfig_service.get_redis_cache", return_value=mock_cache
        ),
        patch(
            "v2.modules.admin_platform.application.konfig_service.get_admin_config_repo",
            return_value=mock_repo,
        ),
    ):
        # 1. First Call (Miss)
        val1 = await get_config_value(None, "physics.gravity")
        assert val1 == 9.81
        mock_repo.get_value.assert_called_once_with("physics.gravity", None)
        mock_cache.set.assert_called_once()  # Should cache the result

        # 2. Second Call (Hit)
        val2 = await get_config_value(None, "physics.gravity")
        assert val2 == 9.81
        # Repo should NOT be called again
        assert mock_repo.get_value.call_count == 1


@pytest.mark.asyncio
async def test_konfig_update_invalidates_cache():
    """Verifies that updating a config deletes related cache keys."""

    mock_cache = MagicMock()
    mock_pubsub = AsyncMock()

    mock_repo = AsyncMock()
    mock_repo.get_config.return_value = {
        "anahtar": "physics.gravity",
        "tip": "number",
        "min_deger": 0,
        "max_deger": 20,
        "grup": "physics",
        "yeniden_baslat": False,
    }
    mock_repo.update_value.return_value = {
        "anahtar": "physics.gravity",
        "deger": 10.0,
        "yeniden_baslat": False,
    }

    with (
        patch(
            "v2.modules.admin_platform.application.konfig_service.get_redis_cache", return_value=mock_cache
        ),
        patch(
            "v2.modules.admin_platform.application.konfig_service.get_pubsub_manager",
            return_value=mock_pubsub,
        ),
        patch(
            "v2.modules.admin_platform.application.konfig_service.get_admin_config_repo",
            return_value=mock_repo,
        ),
    ):
        await update_config(None, "physics.gravity", 10.0, user_id=1, reason="Test")

        # Check invalidation
        # Should delete individual key and group key
        delete_calls = [c[0][0] for c in mock_cache.delete.call_args_list]
        assert "config:val:physics.gravity" in delete_calls
        assert "configs:group:physics" in delete_calls

        # Check event propagation
        mock_pubsub.publish.assert_called_once()
        args = mock_pubsub.publish.call_args[0]
        assert args[0] == "config_updates"
        assert args[1]["key"] == "physics.gravity"


@pytest.mark.asyncio
async def test_konfig_validation_bounds():
    """Verify numeric bounds validation in konfig_service.update_config."""

    mock_repo = AsyncMock()
    mock_repo.get_config.return_value = {
        "anahtar": "physics.gravity",
        "tip": "number",
        "min_deger": 0.0,
        "max_deger": 15.0,
        "grup": "physics",
    }

    with patch(
        "v2.modules.admin_platform.application.konfig_service.get_admin_config_repo", return_value=mock_repo
    ):
        # Test lower bound - loosen regex to avoid encoding issues etc
        with pytest.raises(ValueError, match="0.0"):
            await update_config(None, "physics.gravity", -1.0)

        # Test upper bound
        with pytest.raises(ValueError, match="15.0"):
            await update_config(None, "physics.gravity", 20.0)

        # Test type validation
        with pytest.raises(ValueError, match="sayısal"):
            await update_config(None, "physics.gravity", "not-a-number")
