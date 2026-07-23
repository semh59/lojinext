from v2.modules.platform_infra.monitoring.celery_probe import _record_heartbeat_key


def test_heartbeat_key_format():
    key = _record_heartbeat_key("my.task.name")
    assert key == "beat:last_run:my.task.name"
