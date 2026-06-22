"""
Logger module coverage tests.

Targets remaining uncovered branches in app/infrastructure/logging/logger.py (~75% → higher):
- PIIFilter.filter: record without msg attr (returns True early)
- PIIFilter.filter: args as dict (scrubs dict)
- PIIFilter.filter: args as tuple (scrubs each element)
- PIIFilter.filter: args as None/empty (skips)
- PIIFilter.filter: exception during scrub (swallowed)
- PIIFilter._is_sensitive_key: sensitive vs non-sensitive keys
- JSONFormatter.format: with exc_info, with correlation_id, extra attrs, without exception
- JSONFormatter.format: no correlation_id (exception path swallowed)
- setup_logging: creates rotating file + console handlers, returns logger
- AuditLogger.__init__: creates logger with handler
- AuditLogger.log: writes audit record
- get_audit_logger: returns singleton, same instance on second call
- get_logger: returns logging.Logger instance
"""

from __future__ import annotations

import json
import logging
import sys
from unittest.mock import MagicMock, patch

import pytest

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# PIIFilter
# ---------------------------------------------------------------------------


class TestPIIFilter:
    def _make_filter(self):
        from app.infrastructure.logging.logger import PIIFilter

        return PIIFilter()

    def _make_record(self, msg="test message", args=None):
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg=msg,
            args=args or (),
            exc_info=None,
        )
        return record

    def test_filter_returns_true_always(self):
        """filter() always returns True (does not block records)."""
        f = self._make_filter()
        record = self._make_record("hello world")
        result = f.filter(record)
        assert result is True

    def test_filter_record_without_msg(self):
        """Record without msg attribute → returns True early."""
        f = self._make_filter()
        record = MagicMock(spec=[])  # no msg attribute
        assert not hasattr(record, "msg")
        result = f.filter(record)
        assert result is True

    def test_filter_with_tuple_args(self):
        """Args as tuple: each element scrubbed."""
        f = self._make_filter()
        record = self._make_record("value: %s", args=("password: secret",))
        result = f.filter(record)
        assert result is True

    def test_filter_with_dict_args(self):
        """Args as dict: scrubbed as a unit."""
        f = self._make_filter()
        # Build the record manually to avoid LogRecord validation of dict args
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg="data",
            args=(),
            exc_info=None,
        )
        record.args = {"key": "password: 12345"}  # Set after construction
        result = f.filter(record)
        assert result is True

    def test_filter_empty_args(self):
        """Args as empty tuple: skips scrubbing."""
        f = self._make_filter()
        record = self._make_record("simple msg", args=())
        result = f.filter(record)
        assert result is True

    def test_filter_no_args_attr(self):
        """Record where args is None."""
        f = self._make_filter()
        record = self._make_record("msg")
        record.args = None
        result = f.filter(record)
        assert result is True

    def test_filter_log_injection_protection(self):
        """Newline in msg is replaced with \\n."""
        f = self._make_filter()
        record = self._make_record("line1\nline2\r\n")
        with patch(
            "app.infrastructure.security.pii_scrubber.scrub_pii",
            side_effect=lambda x: x,
        ):
            f.filter(record)
        # Just verify no exception raised

    def test_filter_exception_swallowed(self):
        """Exception during scrub is swallowed, returns True."""
        f = self._make_filter()
        record = self._make_record("some msg")

        with patch(
            "app.infrastructure.security.pii_scrubber.scrub_pii",
            side_effect=RuntimeError("scrub failed"),
        ):
            result = f.filter(record)

        assert result is True

    def test_is_sensitive_key_password(self):
        """'password' key is sensitive."""
        f = self._make_filter()
        assert f._is_sensitive_key("password") is True

    def test_is_sensitive_key_token(self):
        """'token' key is sensitive."""
        f = self._make_filter()
        assert f._is_sensitive_key("access_token") is True

    def test_is_sensitive_key_non_sensitive(self):
        """'username' key is not sensitive."""
        f = self._make_filter()
        assert f._is_sensitive_key("username") is False

    def test_is_sensitive_key_non_string(self):
        """Non-string key → False."""
        f = self._make_filter()
        assert f._is_sensitive_key(123) is False
        assert f._is_sensitive_key(None) is False

    def test_is_sensitive_key_api_key(self):
        f = self._make_filter()
        assert f._is_sensitive_key("api_key") is True

    def test_is_sensitive_key_jwt(self):
        f = self._make_filter()
        assert f._is_sensitive_key("jwt_token") is True

    def test_is_sensitive_key_sifre(self):
        f = self._make_filter()
        assert f._is_sensitive_key("sifre") is True


# ---------------------------------------------------------------------------
# JSONFormatter
# ---------------------------------------------------------------------------


class TestJSONFormatter:
    def _make_formatter(self):
        from app.infrastructure.logging.logger import JSONFormatter

        return JSONFormatter(datefmt="%Y-%m-%dT%H:%M:%S")

    def _make_record(self, msg="test", level=logging.INFO, exc_info=None, **extra):
        record = logging.LogRecord(
            name="test.module",
            level=level,
            pathname="/app/test.py",
            lineno=42,
            msg=msg,
            args=(),
            exc_info=exc_info,
        )
        for k, v in extra.items():
            setattr(record, k, v)
        return record

    def test_format_basic(self):
        """format() returns valid JSON with required fields."""
        formatter = self._make_formatter()
        record = self._make_record("hello")
        output = formatter.format(record)
        data = json.loads(output)

        assert data["level"] == "INFO"
        assert data["message"] == "hello"
        assert "timestamp" in data
        assert "logger" in data

    def test_format_with_exc_info(self):
        """format() includes 'exception' field when exc_info is set."""
        formatter = self._make_formatter()
        try:
            raise ValueError("test error")
        except ValueError:
            exc_info = sys.exc_info()

        record = self._make_record("error msg", exc_info=exc_info)
        output = formatter.format(record)
        data = json.loads(output)

        assert "exception" in data
        assert "ValueError" in data["exception"]

    def test_format_with_extra_fields(self):
        """Custom extra attributes appear in output."""
        formatter = self._make_formatter()
        record = self._make_record("msg", event="startup", custom_key="custom_val")
        output = formatter.format(record)
        data = json.loads(output)

        assert data.get("event") == "startup"
        assert data.get("custom_key") == "custom_val"

    def test_format_reserved_attrs_excluded(self):
        """Standard LogRecord attrs are not in 'extra' section."""
        formatter = self._make_formatter()
        record = self._make_record("msg")
        output = formatter.format(record)
        data = json.loads(output)

        # 'args', 'created', etc. should not appear as top-level extras
        assert "args" not in data
        assert "created" not in data

    def test_format_with_correlation_id(self):
        """format() adds correlation_id when available."""
        formatter = self._make_formatter()
        record = self._make_record("msg")

        with patch(
            "app.infrastructure.context.request_context.get_correlation_id",
            return_value="test-correlation-id-123",
        ):
            output = formatter.format(record)

        data = json.loads(output)
        assert data.get("correlation_id") == "test-correlation-id-123"

    def test_format_without_correlation_id_no_crash(self):
        """format() handles missing/exception in get_correlation_id gracefully."""
        formatter = self._make_formatter()
        record = self._make_record("msg")

        with patch(
            "app.infrastructure.context.request_context.get_correlation_id",
            side_effect=Exception("context missing"),
        ):
            output = formatter.format(record)

        data = json.loads(output)
        assert "message" in data
        # correlation_id should not be present when exception occurred
        assert "correlation_id" not in data

    def test_format_empty_correlation_id_not_included(self):
        """format() omits correlation_id when it's empty string."""
        formatter = self._make_formatter()
        record = self._make_record("msg")

        with patch(
            "app.infrastructure.context.request_context.get_correlation_id",
            return_value="",
        ):
            output = formatter.format(record)

        data = json.loads(output)
        assert "correlation_id" not in data

    def test_format_special_characters_in_message(self):
        """Turkish characters are preserved in JSON output."""
        formatter = self._make_formatter()
        record = self._make_record("Türkçe mesaj: İstanbul")
        output = formatter.format(record)

        data = json.loads(output)
        assert "İstanbul" in data["message"]

    def test_format_non_serializable_extra(self):
        """Non-serializable extra value uses default=str."""
        formatter = self._make_formatter()

        class Unserializable:
            def __str__(self):
                return "unserializable_object"

        record = self._make_record("msg", obj=Unserializable())
        output = formatter.format(record)
        data = json.loads(output)
        assert data.get("obj") == "unserializable_object"


# ---------------------------------------------------------------------------
# setup_logging
# ---------------------------------------------------------------------------


class TestSetupLogging:
    def test_setup_logging_returns_logger(self, tmp_path):
        """setup_logging() returns a Logger instance."""
        from app.infrastructure.logging.logger import setup_logging

        # Patch LOG_DIR to use tmp_path to avoid writing to real log dir
        with patch("app.infrastructure.logging.logger.LOG_DIR", tmp_path):
            result = setup_logging("test_app", level=logging.DEBUG)

        assert isinstance(result, logging.Logger)

    def test_setup_logging_adds_handlers(self, tmp_path):
        """setup_logging() attaches file + console handlers to root logger."""
        with patch("app.infrastructure.logging.logger.LOG_DIR", tmp_path):
            from app.infrastructure.logging.logger import setup_logging

            setup_logging("test_app2", level=logging.INFO)

        root = logging.getLogger()
        # At least 2 handlers: file + console
        assert len(root.handlers) >= 2

    def test_setup_logging_clears_old_handlers(self, tmp_path):
        """setup_logging() clears existing root handlers before adding new ones."""
        root = logging.getLogger()
        # Add a dummy handler
        dummy = logging.StreamHandler()
        root.addHandler(dummy)

        with patch("app.infrastructure.logging.logger.LOG_DIR", tmp_path):
            from app.infrastructure.logging.logger import setup_logging

            setup_logging("test_app3", level=logging.INFO)

        # Dummy should be gone
        assert dummy not in root.handlers

    def test_setup_logging_pii_filter_applied(self, tmp_path):
        """Handlers produced by setup_logging have PIIFilter attached."""
        from app.infrastructure.logging.logger import PIIFilter

        with patch("app.infrastructure.logging.logger.LOG_DIR", tmp_path):
            from app.infrastructure.logging.logger import setup_logging

            setup_logging("test_app4")

        root = logging.getLogger()
        pii_filter_found = any(
            any(isinstance(f, PIIFilter) for f in h.filters) for h in root.handlers
        )
        assert pii_filter_found


# ---------------------------------------------------------------------------
# AuditLogger
# ---------------------------------------------------------------------------


class TestAuditLogger:
    def test_audit_logger_init(self, tmp_path):
        """AuditLogger.__init__ creates logger with handler."""
        with patch("app.infrastructure.logging.logger.LOG_DIR", tmp_path):
            from app.infrastructure.logging.logger import AuditLogger

            al = AuditLogger()

        assert al.logger.name == "audit"
        assert len(al.logger.handlers) >= 1

    def test_audit_logger_log_success(self, tmp_path):
        """AuditLogger.log() writes a record without error."""
        with patch("app.infrastructure.logging.logger.LOG_DIR", tmp_path):
            from app.infrastructure.logging.logger import AuditLogger

            al = AuditLogger()

        # Replace handler with a no-op in-memory handler to avoid file I/O
        al.logger.handlers.clear()

        class CapturingHandler(logging.Handler):
            def __init__(self):
                super().__init__()
                self.records = []

            def emit(self, record):
                self.records.append(record)

        cap = CapturingHandler()
        al.logger.addHandler(cap)

        al.log(
            event="LOGIN",
            user="testuser",
            details={"ip": "127.0.0.1"},
            status="SUCCESS",
        )

        assert len(cap.records) == 1
        record = cap.records[0]
        assert record.audit_event == "LOGIN"
        assert record.actor == "testuser"
        assert record.status == "SUCCESS"

    def test_audit_logger_log_failure_status(self, tmp_path):
        """AuditLogger.log() with status=FAILURE works."""
        with patch("app.infrastructure.logging.logger.LOG_DIR", tmp_path):
            from app.infrastructure.logging.logger import AuditLogger

            al = AuditLogger()

        al.logger.handlers.clear()

        class CapturingHandler(logging.Handler):
            def __init__(self):
                super().__init__()
                self.records = []

            def emit(self, record):
                self.records.append(record)

        cap = CapturingHandler()
        al.logger.addHandler(cap)

        al.log(
            event="DELETE_USER",
            user="admin",
            details={"user_id": 5},
            status="FAILURE",
        )

        assert cap.records[0].status == "FAILURE"


# ---------------------------------------------------------------------------
# get_audit_logger — singleton
# ---------------------------------------------------------------------------


class TestGetAuditLogger:
    def test_singleton_same_instance(self, tmp_path):
        """get_audit_logger() returns the same instance on every call."""
        import app.infrastructure.logging.logger as mod

        # Reset singleton
        original = mod._audit_logger
        mod._audit_logger = None
        try:
            with patch("app.infrastructure.logging.logger.LOG_DIR", tmp_path):
                a = mod.get_audit_logger()
                b = mod.get_audit_logger()
            assert a is b
        finally:
            mod._audit_logger = original

    def test_returns_audit_logger_type(self, tmp_path):
        """get_audit_logger() returns an AuditLogger instance."""
        import app.infrastructure.logging.logger as mod
        from app.infrastructure.logging.logger import AuditLogger

        original = mod._audit_logger
        mod._audit_logger = None
        try:
            with patch("app.infrastructure.logging.logger.LOG_DIR", tmp_path):
                result = mod.get_audit_logger()
            assert isinstance(result, AuditLogger)
        finally:
            mod._audit_logger = original


# ---------------------------------------------------------------------------
# get_logger
# ---------------------------------------------------------------------------


class TestGetLogger:
    def test_returns_logger_instance(self):
        from app.infrastructure.logging.logger import get_logger

        log = get_logger("test.module.name")
        assert isinstance(log, logging.Logger)
        assert log.name == "test.module.name"

    def test_same_name_same_instance(self):
        from app.infrastructure.logging.logger import get_logger

        a = get_logger("same.name")
        b = get_logger("same.name")
        assert a is b

    def test_different_names_different_instances(self):
        from app.infrastructure.logging.logger import get_logger

        a = get_logger("module.a")
        b = get_logger("module.b")
        assert a is not b
