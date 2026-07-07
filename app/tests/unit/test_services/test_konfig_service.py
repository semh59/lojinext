from unittest.mock import AsyncMock, MagicMock, patch

import pytest

pytestmark = pytest.mark.unit


def _make_service():
    """Construct KonfigService with all external deps mocked."""
    mock_repo = AsyncMock()
    mock_repo.session.commit = AsyncMock()
    mock_cache = MagicMock()
    mock_cache.get = MagicMock(return_value=None)
    mock_cache.set = MagicMock()
    mock_cache.delete = MagicMock()
    mock_pubsub = AsyncMock()
    mock_pubsub.publish = AsyncMock()

    with (
        patch(
            "app.core.services.konfig_service.get_admin_config_repo",
            return_value=mock_repo,
        ),
        patch(
            "app.core.services.konfig_service.get_redis_cache", return_value=mock_cache
        ),
        patch(
            "app.core.services.konfig_service.get_pubsub_manager",
            return_value=mock_pubsub,
        ),
    ):
        from app.core.services.konfig_service import KonfigService

        svc = KonfigService()
    svc.repo = mock_repo
    svc._mock_cache = mock_cache
    svc._mock_pubsub = mock_pubsub
    return svc


class TestKonfigService:
    def test_service_exists(self):
        from app.core.services.konfig_service import KonfigService

        assert KonfigService is not None

    async def test_basic_initialization(self):
        svc = _make_service()
        from app.core.services.konfig_service import KonfigService

        assert isinstance(svc, KonfigService)

    async def test_get_all_by_group_hits_repo_on_cache_miss(self):
        svc = _make_service()
        svc._mock_cache.get.return_value = None
        svc.repo.get_by_group = AsyncMock(
            return_value=[{"anahtar": "k1", "deger": "v1"}]
        )

        with (
            patch(
                "app.core.services.konfig_service.get_redis_cache",
                return_value=svc._mock_cache,
            ),
        ):
            result = await svc.get_all_by_group("physics")

        svc.repo.get_by_group.assert_awaited_once_with("physics")
        assert result == [{"anahtar": "k1", "deger": "v1"}]

    async def test_get_all_by_group_cache_hit(self):
        svc = _make_service()
        cached = [{"anahtar": "k2", "deger": "v2"}]
        svc._mock_cache.get.return_value = cached
        svc.repo.get_by_group = AsyncMock()

        with patch(
            "app.core.services.konfig_service.get_redis_cache",
            return_value=svc._mock_cache,
        ):
            result = await svc.get_all_by_group("physics")

        svc.repo.get_by_group.assert_not_awaited()
        assert result == cached

    async def test_get_value_returns_default_when_none(self):
        svc = _make_service()
        svc._mock_cache.get.return_value = None
        svc.repo.get_value = AsyncMock(return_value=None)

        with patch(
            "app.core.services.konfig_service.get_redis_cache",
            return_value=svc._mock_cache,
        ):
            result = await svc.get_value("MISSING_KEY", default="fallback")

        assert result == "fallback"

    async def test_get_value_returns_repo_value(self):
        svc = _make_service()
        svc._mock_cache.get.return_value = None
        svc.repo.get_value = AsyncMock(return_value="42")

        with patch(
            "app.core.services.konfig_service.get_redis_cache",
            return_value=svc._mock_cache,
        ):
            result = await svc.get_value("SOME_KEY", default=None)

        assert result == "42"

    async def test_update_config_raises_for_unknown_key(self):
        svc = _make_service()
        svc.repo.get_config = AsyncMock(return_value=None)

        with pytest.raises(ValueError, match="Konfigrasyon bulunamadı"):
            await svc.update_config("UNKNOWN_KEY", "value")

    async def test_update_config_validates_number_type(self):
        svc = _make_service()
        svc.repo.get_config = AsyncMock(
            return_value={
                "tip": "number",
                "min_deger": None,
                "max_deger": None,
                "grup": "g",
            }
        )
        svc.repo.update_value = AsyncMock(
            return_value={"yeniden_baslat": False, "grup": "g"}
        )

        with (
            patch(
                "app.core.services.konfig_service.get_redis_cache",
                return_value=svc._mock_cache,
            ),
            patch(
                "app.core.services.konfig_service.get_pubsub_manager",
                return_value=svc._mock_pubsub,
            ),
        ):
            with pytest.raises(ValueError):
                await svc.update_config("NUM_KEY", "not_a_number")

    async def test_update_config_number_min_validation(self):
        svc = _make_service()
        svc.repo.get_config = AsyncMock(
            return_value={
                "tip": "number",
                "min_deger": 10.0,
                "max_deger": None,
                "grup": "g",
            }
        )

        with pytest.raises(ValueError, match="minimum"):
            await svc.update_config("NUM_KEY", 5)

    async def test_update_config_success_invalidates_cache(self):
        svc = _make_service()
        svc.repo.get_config = AsyncMock(
            return_value={
                "tip": "string",
                "min_deger": None,
                "max_deger": None,
                "grup": "general",
            }
        )
        svc.repo.update_value = AsyncMock(
            return_value={"yeniden_baslat": False, "grup": "general"}
        )

        with (
            patch(
                "app.core.services.konfig_service.get_redis_cache",
                return_value=svc._mock_cache,
            ),
            patch(
                "app.core.services.konfig_service.get_pubsub_manager",
                return_value=svc._mock_pubsub,
            ),
        ):
            await svc.update_config("STR_KEY", "new_val", user_id=1)

        assert svc._mock_cache.delete.call_count >= 1

    async def test_get_history_delegates_to_repo(self):
        svc = _make_service()
        history = [{"changed_at": "2024-01-01", "old": "a", "new": "b"}]
        svc.repo.get_history = AsyncMock(return_value=history)

        result = await svc.get_history("SOME_KEY", limit=5)

        svc.repo.get_history.assert_awaited_once_with("SOME_KEY", 5)
        assert result == history

    async def test_edge_case_boolean_coercion_true(self):
        svc = _make_service()
        svc.repo.get_config = AsyncMock(
            return_value={
                "tip": "boolean",
                "min_deger": None,
                "max_deger": None,
                "grup": "g",
            }
        )
        svc.repo.update_value = AsyncMock(
            return_value={"yeniden_baslat": False, "grup": "g"}
        )

        with (
            patch(
                "app.core.services.konfig_service.get_redis_cache",
                return_value=svc._mock_cache,
            ),
            patch(
                "app.core.services.konfig_service.get_pubsub_manager",
                return_value=svc._mock_pubsub,
            ),
        ):
            await svc.update_config("BOOL_KEY", "true", user_id=1)

        call_kwargs = svc.repo.update_value.call_args.kwargs
        assert call_kwargs["new_value"] is True

    async def test_return_type_validation(self):
        svc = _make_service()
        history = []
        svc.repo.get_history = AsyncMock(return_value=history)

        result = await svc.get_history("KEY")
        assert isinstance(result, list)
