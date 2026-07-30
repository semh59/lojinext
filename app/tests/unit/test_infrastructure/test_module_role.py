import pytest

from v2.modules.platform_infra.database.module_role import (
    MODULE_ROLE_MAP,
    TASK_NAME_TO_MODULE,
    get_module_role,
    module_role_scope,
    require_module_role,
    setup_celery_module_role_signals,
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


class _FakeCeleryTask:
    def __init__(self, name: str) -> None:
        self.name = name


def test_celery_signal_wiring_scopes_role_for_mapped_task():
    """setup_celery_module_role_signals() only ever runs for real at real
    Celery worker startup (@worker_process_init.connect) -- pytest never
    spawns one, so its body was 100% uncovered, tanking the combined
    coverage gate below 92% (found via a real CI failure, 2026-07-30).
    Exercise it directly by sending the real celery signals it connects
    to, instead of needing an actual worker process."""
    from celery.signals import task_postrun, task_prerun

    setup_celery_module_role_signals()

    task_name = next(iter(TASK_NAME_TO_MODULE))
    expected_role = MODULE_ROLE_MAP[TASK_NAME_TO_MODULE[task_name]]
    task = _FakeCeleryTask(task_name)

    assert get_module_role() is None
    task_prerun.send(sender=task, task_id="test-task-mapped", task=task)
    assert get_module_role() == expected_role
    task_postrun.send(sender=task, task_id="test-task-mapped", task=task)
    assert get_module_role() is None


def test_celery_signal_wiring_ignores_unmapped_task():
    from celery.signals import task_postrun, task_prerun

    setup_celery_module_role_signals()

    task = _FakeCeleryTask(
        "infrastructure.relay_outbox_events"
    )  # deliberately unmapped

    assert get_module_role() is None
    task_prerun.send(sender=task, task_id="test-task-unmapped", task=task)
    assert get_module_role() is None
    task_postrun.send(sender=task, task_id="test-task-unmapped", task=task)
    assert get_module_role() is None
