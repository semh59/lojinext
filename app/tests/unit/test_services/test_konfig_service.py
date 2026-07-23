from contextlib import ExitStack, contextmanager
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from v2.modules.admin_platform.application import konfig_service

pytestmark = pytest.mark.unit


def _make_mocks():
    """Build mocked repo/cache/pubsub for konfig_service's free functions."""
    mock_repo = AsyncMock()
    mock_repo.session.commit = AsyncMock()
    mock_cache = MagicMock()
    mock_cache.get = MagicMock(return_value=None)
    mock_cache.set = MagicMock()
    mock_cache.delete = MagicMock()
    mock_pubsub = AsyncMock()
    mock_pubsub.publish = AsyncMock()
    return mock_repo, mock_cache, mock_pubsub


@contextmanager
def _patched(mock_repo=None, mock_cache=None, mock_pubsub=None):
    patches = []
    if mock_repo is not None:
        patches.append(
            patch(
                "v2.modules.admin_platform.application.konfig_service.get_admin_config_repo",
                return_value=mock_repo,
            )
        )
    if mock_cache is not None:
        patches.append(
            patch(
                "v2.modules.admin_platform.application.konfig_service.get_redis_cache",
                return_value=mock_cache,
            )
        )
    if mock_pubsub is not None:
        patches.append(
            patch(
                "v2.modules.admin_platform.application.konfig_service.get_pubsub_manager",
                return_value=mock_pubsub,
            )
        )
    with ExitStack() as stack:
        for p in patches:
            stack.enter_context(p)
        yield


class TestKonfigService:
    def test_module_exists(self):
        assert konfig_service is not None

    async def test_get_all_by_group_hits_repo_on_cache_miss(self):
        mock_repo, mock_cache, _ = _make_mocks()
        mock_cache.get.return_value = None
        mock_repo.get_by_group = AsyncMock(
            return_value=[{"anahtar": "k1", "deger": "v1"}]
        )

        with _patched(mock_repo=mock_repo, mock_cache=mock_cache):
            result = await konfig_service.get_all_by_group(None, "physics")

        mock_repo.get_by_group.assert_awaited_once_with("physics")
        assert result == [{"anahtar": "k1", "deger": "v1"}]

    async def test_get_all_by_group_cache_hit(self):
        mock_repo, mock_cache, _ = _make_mocks()
        cached = [{"anahtar": "k2", "deger": "v2"}]
        mock_cache.get.return_value = cached
        mock_repo.get_by_group = AsyncMock()

        with _patched(mock_repo=mock_repo, mock_cache=mock_cache):
            result = await konfig_service.get_all_by_group(None, "physics")

        mock_repo.get_by_group.assert_not_awaited()
        assert result == cached

    async def test_get_value_returns_default_when_none(self):
        mock_repo, mock_cache, _ = _make_mocks()
        mock_cache.get.return_value = None
        mock_repo.get_value = AsyncMock(return_value=None)

        with _patched(mock_repo=mock_repo, mock_cache=mock_cache):
            result = await konfig_service.get_config_value(
                None, "MISSING_KEY", default="fallback"
            )

        assert result == "fallback"

    async def test_get_value_returns_repo_value(self):
        mock_repo, mock_cache, _ = _make_mocks()
        mock_cache.get.return_value = None
        mock_repo.get_value = AsyncMock(return_value="42")

        with _patched(mock_repo=mock_repo, mock_cache=mock_cache):
            result = await konfig_service.get_config_value(
                None, "SOME_KEY", default=None
            )

        assert result == "42"

    async def test_update_config_raises_for_unknown_key(self):
        mock_repo, _, _ = _make_mocks()
        mock_repo.get_config = AsyncMock(return_value=None)

        with _patched(mock_repo=mock_repo):
            with pytest.raises(ValueError, match="Konfigrasyon bulunamadı"):
                await konfig_service.update_config(None, "UNKNOWN_KEY", "value")

    async def test_update_config_validates_number_type(self):
        mock_repo, mock_cache, mock_pubsub = _make_mocks()
        mock_repo.get_config = AsyncMock(
            return_value={
                "tip": "number",
                "min_deger": None,
                "max_deger": None,
                "grup": "g",
            }
        )
        mock_repo.update_value = AsyncMock(
            return_value={"yeniden_baslat": False, "grup": "g"}
        )

        with _patched(mock_repo=mock_repo, mock_cache=mock_cache, mock_pubsub=mock_pubsub):
            with pytest.raises(ValueError):
                await konfig_service.update_config(None, "NUM_KEY", "not_a_number")

    async def test_update_config_number_min_validation(self):
        mock_repo, _, _ = _make_mocks()
        mock_repo.get_config = AsyncMock(
            return_value={
                "tip": "number",
                "min_deger": 10.0,
                "max_deger": None,
                "grup": "g",
            }
        )

        with _patched(mock_repo=mock_repo):
            with pytest.raises(ValueError, match="minimum"):
                await konfig_service.update_config(None, "NUM_KEY", 5)

    async def test_update_config_success_invalidates_cache(self):
        mock_repo, mock_cache, mock_pubsub = _make_mocks()
        mock_repo.get_config = AsyncMock(
            return_value={
                "tip": "string",
                "min_deger": None,
                "max_deger": None,
                "grup": "general",
            }
        )
        mock_repo.update_value = AsyncMock(
            return_value={"yeniden_baslat": False, "grup": "general"}
        )

        with _patched(mock_repo=mock_repo, mock_cache=mock_cache, mock_pubsub=mock_pubsub):
            await konfig_service.update_config(
                None, "STR_KEY", "new_val", user_id=1
            )

        assert mock_cache.delete.call_count >= 1

    async def test_get_history_delegates_to_repo(self):
        mock_repo, _, _ = _make_mocks()
        history = [{"changed_at": "2024-01-01", "old": "a", "new": "b"}]
        mock_repo.get_history = AsyncMock(return_value=history)

        with _patched(mock_repo=mock_repo):
            result = await konfig_service.get_config_history(
                None, "SOME_KEY", limit=5
            )

        mock_repo.get_history.assert_awaited_once_with("SOME_KEY", 5)
        assert result == history

    async def test_edge_case_boolean_coercion_true(self):
        mock_repo, mock_cache, mock_pubsub = _make_mocks()
        mock_repo.get_config = AsyncMock(
            return_value={
                "tip": "boolean",
                "min_deger": None,
                "max_deger": None,
                "grup": "g",
            }
        )
        mock_repo.update_value = AsyncMock(
            return_value={"yeniden_baslat": False, "grup": "g"}
        )

        with _patched(mock_repo=mock_repo, mock_cache=mock_cache, mock_pubsub=mock_pubsub):
            await konfig_service.update_config(
                None, "BOOL_KEY", "true", user_id=1
            )

        call_kwargs = mock_repo.update_value.call_args.kwargs
        assert call_kwargs["new_value"] is True

    async def test_return_type_validation(self):
        mock_repo, _, _ = _make_mocks()
        history = []
        mock_repo.get_history = AsyncMock(return_value=history)

        with _patched(mock_repo=mock_repo):
            result = await konfig_service.get_config_history(None, "KEY")
        assert isinstance(result, list)
