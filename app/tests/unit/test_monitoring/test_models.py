from v2.modules.platform_infra.monitoring.models import (
    ErrorEvent,
    ErrorLayer,
    ErrorSeverity,
    make_fingerprint,
)


def test_fingerprint_normalizes_numbers():
    fp1 = make_fingerprint("db", "slow_query", "Query took 150ms on table users")
    fp2 = make_fingerprint("db", "slow_query", "Query took 3200ms on table users")
    assert fp1 == fp2


def test_fingerprint_normalizes_strings():
    fp1 = make_fingerprint("service", "invariant_violation", "user 'alice' not found")
    fp2 = make_fingerprint("service", "invariant_violation", "user 'bob' not found")
    assert fp1 == fp2


def test_fingerprint_differs_by_category():
    fp1 = make_fingerprint("db", "slow_query", "timeout")
    fp2 = make_fingerprint("db", "deadlock", "timeout")
    assert fp1 != fp2


def test_error_event_auto_fingerprint():
    ev = ErrorEvent(
        layer=ErrorLayer.DB,
        category="slow_query",
        severity=ErrorSeverity.WARNING,
        message="took 200ms",
    )
    assert len(ev.fingerprint) == 16
    assert ev.fingerprint == make_fingerprint("db", "slow_query", "took 200ms")


def test_error_event_to_dict():
    ev = ErrorEvent(
        layer=ErrorLayer.CELERY,
        category="task_failure",
        severity=ErrorSeverity.ERROR,
        message="boom",
        trace_id="abc123",
        metadata={"task": "foo"},
    )
    d = ev.to_dict()
    assert d["layer"] == "celery"
    assert d["severity"] == "error"
    assert d["metadata"]["task"] == "foo"
    assert "fingerprint" in d
    assert "occurred_at" in d


def test_error_event_accepts_string_layer_and_severity():
    ev = ErrorEvent(layer="db", category="test", severity="warning", message="msg")
    assert ev.layer == ErrorLayer.DB
    assert ev.severity == ErrorSeverity.WARNING


def test_fingerprint_normalizes_string_with_numbers():
    # Quoted string containing number should be treated as 'S', not 'N'
    fp1 = make_fingerprint("db", "error", "got 'user123' not found")
    fp2 = make_fingerprint("db", "error", "got 'admin456' not found")
    assert fp1 == fp2


def test_emit_noops_gracefully_without_event_bus():
    from v2.modules.platform_infra.monitoring import emit

    ev = ErrorEvent(
        layer=ErrorLayer.SERVICE,
        category="test",
        severity=ErrorSeverity.INFO,
        message="test",
    )
    # Should not raise even though event_bus doesn't exist yet
    emit(ev)
