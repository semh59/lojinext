"""
Unit tests for audit_log decorator, log_audit_event, and _mask_sensitive_data.

DB persist (_persist_audit_to_db) is always patched so no real DB connection
is needed.  JSON logging is verified by capturing the audit logger output.
"""

import json
from unittest.mock import AsyncMock, patch

import pytest

from v2.modules.platform_infra.audit.audit_logger import (
    _mask_sensitive_data,
    audit_log,
    log_audit_event,
)

pytestmark = pytest.mark.unit

# Patch target for DB persist — best-effort; always mock it in unit tests.
_PERSIST_PATCH = "v2.modules.platform_infra.audit.audit_logger._persist_audit_to_db"


class TestMaskSensitiveData:
    def test_basic_initialization(self):
        """_mask_sensitive_data is importable and callable."""
        assert callable(_mask_sensitive_data)

    def test_masks_password_key(self):
        """password key value is replaced with ***MASKED***."""
        data = {"user": "alice", "password": "s3cr3t"}  # pragma: allowlist secret
        result = _mask_sensitive_data(data)

        assert result["password"] == "***MASKED***"
        assert result["user"] == "alice"

    def test_masks_token_key(self):
        """token key is masked."""
        data = {"access_token": "jwt.abc.xyz"}  # pragma: allowlist secret
        result = _mask_sensitive_data(data)

        assert result["access_token"] == "***MASKED***"

    def test_masks_nested_sensitive_key(self):
        """Nested dicts are recursively masked."""
        data = {"outer": {"inner_secret": "hidden"}}  # pragma: allowlist secret
        result = _mask_sensitive_data(data)

        assert result["outer"]["inner_secret"] == "***MASKED***"

    def test_non_sensitive_keys_unchanged(self):
        """Non-sensitive keys pass through unchanged."""
        data = {"name": "Ahmet", "km": 500, "city": "Istanbul"}
        result = _mask_sensitive_data(data)

        assert result == data

    def test_list_is_processed(self):
        """Lists are recursively processed."""
        data = [{"api_key": "mykey"}, {"name": "ok"}]  # pragma: allowlist secret
        result = _mask_sensitive_data(data)

        assert result[0]["api_key"] == "***MASKED***"
        assert result[1]["name"] == "ok"

    def test_scalar_value_unchanged(self):
        """Scalar values (int, str, None) are returned as-is."""
        assert _mask_sensitive_data(42) == 42
        assert _mask_sensitive_data("hello") == "hello"
        assert _mask_sensitive_data(None) is None


class TestAuditLogDecorator:
    async def test_basic_initialization(self):
        """audit_log decorator is importable and returns a decorator."""
        decorator = audit_log(action="test_action")
        assert callable(decorator)

    async def test_happy_path(self):
        """Decorated async function succeeds; audit logger records 'success'."""
        log_entries = []

        with patch(_PERSIST_PATCH, new_callable=AsyncMock):
            with patch(
                "v2.modules.platform_infra.audit.audit_logger.audit_logger"
            ) as mock_logger:
                mock_logger.info.side_effect = lambda msg: log_entries.append(msg)

                @audit_log(action="CREATE_SEFER")
                async def create_sefer(sefer_id: int, user_id: int = 1):
                    return {"id": sefer_id}

                result = await create_sefer(sefer_id=42, user_id=5)

        assert result == {"id": 42}
        assert len(log_entries) == 1
        entry = json.loads(log_entries[0])
        assert entry["action"] == "CREATE_SEFER"
        assert entry["status"] == "success"

    async def test_error_handling(self):
        """Decorated async function that raises records 'failed' and re-raises."""
        log_entries = []

        with patch(_PERSIST_PATCH, new_callable=AsyncMock):
            with patch(
                "v2.modules.platform_infra.audit.audit_logger.audit_logger"
            ) as mock_logger:
                mock_logger.error.side_effect = lambda msg: log_entries.append(msg)

                @audit_log(action="FAIL_ACTION")
                async def always_fails():
                    raise ValueError("something went wrong")

                with pytest.raises(ValueError, match="something went wrong"):
                    await always_fails()

        assert len(log_entries) == 1
        entry = json.loads(log_entries[0])
        assert entry["status"] == "failed"
        assert "something went wrong" in entry["error"]

    async def test_edge_case_empty(self):
        """audit_log with empty action string still decorates correctly."""
        with patch(_PERSIST_PATCH, new_callable=AsyncMock):
            with patch("v2.modules.platform_infra.audit.audit_logger.audit_logger"):

                @audit_log(action="")
                async def no_op():
                    return None

                result = await no_op()

        assert result is None

    async def test_edge_case_none(self):
        """Sync function wrapped by audit_log does not require event loop."""
        log_entries = []

        with patch("v2.modules.platform_infra.audit.audit_logger.audit_logger") as mock_logger:
            mock_logger.info.side_effect = lambda msg: log_entries.append(msg)

            @audit_log(action="SYNC_ACTION")
            def sync_fn():
                return "sync_result"

            result = sync_fn()

        assert result == "sync_result"
        assert len(log_entries) == 1
        entry = json.loads(log_entries[0])
        assert entry["status"] == "success"

    async def test_integration_with_mock(self):
        """audit_log calls _persist_audit_to_db after successful execution."""
        with patch(_PERSIST_PATCH, new_callable=AsyncMock) as mock_persist:

            @audit_log(action="PERSIST_TEST", entity_type="seferler")
            async def my_service():
                return True

            await my_service()

        mock_persist.assert_awaited_once()
        call_kwargs = mock_persist.call_args.kwargs
        assert call_kwargs["action"] == "PERSIST_TEST"
        assert call_kwargs["entity"] == "seferler"
        assert call_kwargs["basarili"] is True

    async def test_return_type_validation(self):
        """audit_log preserves complex return types (list, dict, int)."""
        with patch(_PERSIST_PATCH, new_callable=AsyncMock):
            with patch("v2.modules.platform_infra.audit.audit_logger.audit_logger"):

                @audit_log(action="RETURN_TEST")
                async def returns_list():
                    return [1, 2, 3]

                result = await returns_list()

        assert result == [1, 2, 3]

    def test_service_exists(self):
        """audit_log is importable from the module."""
        from v2.modules.platform_infra.audit.audit_logger import audit_log  # noqa: F401

        assert callable(audit_log)

    async def test_persist_called_on_failure(self):
        """_persist_audit_to_db is called with basarili=False when function raises."""
        with patch(_PERSIST_PATCH, new_callable=AsyncMock) as mock_persist:

            @audit_log(action="FAIL_PERSIST")
            async def failing():
                raise RuntimeError("db error")

            with pytest.raises(RuntimeError):
                await failing()

        mock_persist.assert_awaited_once()
        call_kwargs = mock_persist.call_args.kwargs
        assert call_kwargs["basarili"] is False
        assert "db error" in call_kwargs["hata_mesaji"]

    async def test_duration_ms_present_in_log(self):
        """Log entry includes a duration_ms field."""
        log_entries = []

        with patch(_PERSIST_PATCH, new_callable=AsyncMock):
            with patch(
                "v2.modules.platform_infra.audit.audit_logger.audit_logger"
            ) as mock_logger:
                mock_logger.info.side_effect = lambda msg: log_entries.append(msg)

                @audit_log(action="DURATION_TEST")
                async def timed_fn():
                    return "done"

                await timed_fn()

        entry = json.loads(log_entries[0])
        assert "duration_ms" in entry
        assert isinstance(entry["duration_ms"], (int, float))


class TestLogAuditEvent:
    async def test_log_audit_event_writes_json(self):
        """log_audit_event logs a JSON entry with expected fields."""
        log_entries = []

        with patch(_PERSIST_PATCH, new_callable=AsyncMock):
            with patch(
                "v2.modules.platform_infra.audit.audit_logger.audit_logger"
            ) as mock_logger:
                mock_logger.info.side_effect = lambda msg: log_entries.append(msg)

                await log_audit_event(
                    action="DELETE_SEFER",
                    module="seferler",
                    entity_id="99",
                    user_id=7,
                )

        assert len(log_entries) == 1
        entry = json.loads(log_entries[0])
        assert entry["action"] == "DELETE_SEFER"
        assert entry["module"] == "seferler"
        assert entry["entity_id"] == "99"

    async def test_log_audit_event_masks_sensitive_new_value(self):
        """log_audit_event masks sensitive fields in new_value."""
        log_entries = []

        with patch(_PERSIST_PATCH, new_callable=AsyncMock):
            with patch(
                "v2.modules.platform_infra.audit.audit_logger.audit_logger"
            ) as mock_logger:
                mock_logger.info.side_effect = lambda msg: log_entries.append(msg)

                await log_audit_event(
                    action="UPDATE_USER",
                    module="kullanicilar",
                    new_value={
                        "name": "Bob",
                        "password": "secret123",  # pragma: allowlist secret
                    },
                )

        entry = json.loads(log_entries[0])
        assert entry["new_value"]["password"] == "***MASKED***"
        assert entry["new_value"]["name"] == "Bob"

    @pytest.mark.parametrize(
        "falsy_value",
        [0, False, "", {}, []],
        ids=["zero", "false", "empty_str", "empty_dict", "empty_list"],
    )
    async def test_log_audit_event_preserves_falsy_old_and_new_values(
        self, falsy_value
    ):
        """2026-07-02 prod-grade denetimi P2 (Tier A madde 5): eskiden
        `if old_value else None` Python truthiness kullanıyordu — old_value/
        new_value'nun KENDİSİ 0/False/""/{}/[] gibi GEÇERLİ-falsy bir değer
        olduğunda sessizce None'a düşüyordu (audit trail bu değişikliği hiç
        kaydetmiyordu). Artık `is not None` ile ayırt ediliyor."""
        log_entries = []

        with patch(_PERSIST_PATCH, new_callable=AsyncMock):
            with patch(
                "v2.modules.platform_infra.audit.audit_logger.audit_logger"
            ) as mock_logger:
                mock_logger.info.side_effect = lambda msg: log_entries.append(msg)

                await log_audit_event(
                    action="UPDATE_FIELD",
                    module="ayarlar",
                    old_value=falsy_value,
                    new_value=falsy_value,
                )

        entry = json.loads(log_entries[0])
        assert entry["old_value"] == falsy_value, (
            f"Falsy old_value ({falsy_value!r}) sessizce None'a düşürüldü: "
            f"{entry['old_value']!r}"
        )
        assert entry["new_value"] == falsy_value, (
            f"Falsy new_value ({falsy_value!r}) sessizce None'a düşürüldü: "
            f"{entry['new_value']!r}"
        )

    async def test_log_audit_event_none_stays_none(self):
        """`None` (gerçekten değer yok) hâlâ `None` olarak kalmalı — regresyon
        guard'ı, `is not None` geçişinin None-handling'i bozmadığını doğrular."""
        log_entries = []

        with patch(_PERSIST_PATCH, new_callable=AsyncMock):
            with patch(
                "v2.modules.platform_infra.audit.audit_logger.audit_logger"
            ) as mock_logger:
                mock_logger.info.side_effect = lambda msg: log_entries.append(msg)

                await log_audit_event(action="CREATE_SEFER", module="seferler")

        entry = json.loads(log_entries[0])
        assert entry["old_value"] is None
        assert entry["new_value"] is None

    async def test_log_audit_event_calls_persist_db(self):
        """log_audit_event calls _persist_audit_to_db."""
        with patch(_PERSIST_PATCH, new_callable=AsyncMock) as mock_persist:
            with patch("v2.modules.platform_infra.audit.audit_logger.audit_logger"):
                await log_audit_event(
                    action="IMPORT_EXCEL",
                    module="seferler",
                    entity_id="bulk",
                    user_id=3,
                )

        mock_persist.assert_awaited_once()

    async def test_log_audit_event_defaults_basarili_true(self):
        """Backward-compat: basarili not passed → True (unchanged default)."""
        with patch(_PERSIST_PATCH, new_callable=AsyncMock) as mock_persist:
            with patch("v2.modules.platform_infra.audit.audit_logger.audit_logger"):
                await log_audit_event(action="UPDATE_USER", module="kullanicilar")

        _, kwargs = mock_persist.await_args
        assert kwargs["basarili"] is True

    async def test_log_audit_event_propagates_basarili_false(self):
        """2026-07-01 prod-grade denetimi P1: `basarili=False` artık DB
        persist'e ve dosya logune doğru şekilde geçiyor — önceden
        `_persist_audit_to_db` her zaman sabit `basarili=True` ile
        çağrılıyordu, başarısız-giriş/403 kayıtları yanlışlıkla "başarılı"
        görünürdü."""
        log_entries = []

        with patch(_PERSIST_PATCH, new_callable=AsyncMock) as mock_persist:
            with patch(
                "v2.modules.platform_infra.audit.audit_logger.audit_logger"
            ) as mock_logger:
                mock_logger.info.side_effect = lambda msg: log_entries.append(msg)

                await log_audit_event(
                    action="auth.failed_login",
                    module="auth",
                    entity_id="attacker@evil.example",
                    basarili=False,
                )

        _, kwargs = mock_persist.await_args
        assert kwargs["basarili"] is False
        entry = json.loads(log_entries[0])
        assert entry["basarili"] is False
