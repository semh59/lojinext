import pytest

from v2.modules.platform_infra.database.module_role import (
    MODULE_ROLE_MAP,
    get_module_role,
    module_role_scope,
    require_module_role,
)


def test_module_role_scope_sets_and_resets_contextvar():
    assert get_module_role() is None
    with module_role_scope("m_trip"):
        assert get_module_role() == "m_trip"
    assert get_module_role() is None


def test_module_role_scope_rejects_unknown_role():
    with pytest.raises(ValueError, match="Unknown PostgreSQL module role"):
        with module_role_scope("m_does_not_exist"):
            pass
    assert get_module_role() is None


async def test_require_module_role_dependency_scopes_the_generator_body():
    dependency = require_module_role("trip")
    agen = dependency()
    assert get_module_role() is None
    await agen.__anext__()
    assert get_module_role() == MODULE_ROLE_MAP["trip"]
    with pytest.raises(StopAsyncIteration):
        await agen.__anext__()
    assert get_module_role() is None
