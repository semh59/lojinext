from app.infrastructure.monitoring.celery_probe import _record_heartbeat_key


def test_heartbeat_key_format():
    key = _record_heartbeat_key("my.task.name")
    assert key == "beat:last_run:my.task.name"
