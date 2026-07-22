from v2.modules.platform_infra.monitoring.db_probe import (
    _CRITICAL_PG_CODES,
    _PG_CODE_MAP,
    _sql_fingerprint,
)


def test_sql_fingerprint_normalizes_literals():
    s1 = _sql_fingerprint("SELECT * FROM users WHERE id = 42 AND name = 'alice'")
    s2 = _sql_fingerprint("SELECT * FROM users WHERE id = 99 AND name = 'bob'")
    assert s1 == s2


def test_sql_fingerprint_differs_by_table():
    s1 = _sql_fingerprint("SELECT * FROM users WHERE id = 1")
    s2 = _sql_fingerprint("SELECT * FROM orders WHERE id = 1")
    assert s1 != s2


def test_pg_code_deadlock_is_critical():
    assert "40P01" in _CRITICAL_PG_CODES
    assert _PG_CODE_MAP["40P01"] == "deadlock"


def test_pg_code_unique_violation():
    assert _PG_CODE_MAP["23505"] == "unique_violation"


def test_pg_code_unknown_returns_db_error():
    assert _PG_CODE_MAP.get("99999", "db_error") == "db_error"
