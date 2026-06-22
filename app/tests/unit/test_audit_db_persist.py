"""Audit log DB persist testleri.

`audit_logger.py` JSON dosya log + admin_audit_log INSERT iki kanallı:
1. JSON log her zaman atılır (existing behavior)
2. DB INSERT best-effort — fail asıl iş akışını bozmamalı

Bu test'ler her iki kanalın çalıştığını, DB hatası sessizce yutulduğunu,
ve trace_id (correlation_id) → istek_id eşlemesinin doğru olduğunu
doğrular.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from app.infrastructure.audit.audit_logger import (
    _persist_audit_to_db,
    audit_log,
    log_audit_event,
)


@pytest.mark.asyncio
async def test_persist_audit_to_db_writes_to_admin_audit_log(monkeypatch):
    """``_persist_audit_to_db`` INSERT SQL'i admin_audit_log'a doğru
    parametrelerle çalıştırmalı (Türkçe kolon mapping)."""
    captured: list = []

    class FakeSession:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *_):
            return None

        async def execute(self, stmt, params=None):
            captured.append({"stmt": str(stmt), "params": params})
            return MagicMock()

        async def commit(self):
            captured.append({"commit": True})

        def in_transaction(self):
            # Production path: fresh session, no outer transaction → commit branch
            return False

    def _fake_session_factory():
        return FakeSession()

    monkeypatch.setattr(
        "app.database.connection.AsyncSessionLocal",
        _fake_session_factory,
    )

    await _persist_audit_to_db(
        action="DELETE",
        entity="sefer",
        entity_id="42",
        user_id=7,
        new_value={"durum": "İptal"},
        basarili=True,
        sure_ms=123.4,
        correlation_id="abc-123-trace",
    )

    # SQL çalıştırıldı + parametre türkçe kolonlara mapping
    sql_call = captured[0]
    assert "INSERT INTO admin_audit_log" in sql_call["stmt"]
    p = sql_call["params"]
    assert p["aksiyon_tipi"] == "DELETE"
    assert p["hedef_tablo"] == "sefer"
    assert p["hedef_id"] == "42"
    assert p["kullanici_id"] == 7
    assert p["basarili"] is True
    assert p["sure_ms"] == 123  # float → int round
    assert p["istek_id"] == "abc-123-trace"
    # yeni_deger JSON string olarak gönderilmeli (asyncpg JSONB cast için)
    assert isinstance(p["yeni_deger"], str)
    # json.dumps default ensure_ascii=True → İ → İ; payload aynı, encoding farklı
    assert "durum" in p["yeni_deger"]
    assert "0130" in p["yeni_deger"] or "İptal" in p["yeni_deger"]

    # commit çağrıldı
    assert any("commit" in c for c in captured)


@pytest.mark.asyncio
async def test_persist_audit_swallows_db_errors(monkeypatch, caplog):
    """DB hatası asıl iş akışını bozmamalı — sessiz yutup warning loglar."""

    def _broken_factory():
        raise RuntimeError("DB down")

    monkeypatch.setattr(
        "app.database.connection.AsyncSessionLocal",
        _broken_factory,
    )

    # raise etmemeli
    await _persist_audit_to_db(
        action="CREATE",
        entity="arac",
        correlation_id="trace-xyz",
    )


@pytest.mark.asyncio
async def test_audit_log_decorator_persists_success_to_db(monkeypatch):
    """``@audit_log`` decorator başarı durumunda DB'ye basarili=True yazmalı."""
    persisted: list = []

    async def _spy(**kwargs):
        persisted.append(kwargs)

    monkeypatch.setattr(
        "app.infrastructure.audit.audit_logger._persist_audit_to_db",
        _spy,
    )
    monkeypatch.setattr(
        "app.infrastructure.audit.audit_logger.get_correlation_id",
        lambda: "trace-success-1",
    )

    @audit_log("CREATE", "sefer")
    async def create_sefer(user_id: int = 0):
        return {"id": 42}

    result = await create_sefer(user_id=99)
    assert result == {"id": 42}

    assert len(persisted) == 1
    call = persisted[0]
    assert call["action"] == "CREATE"
    assert call["entity"] == "sefer"
    assert call["user_id"] == 99
    assert call["basarili"] is True
    assert call["correlation_id"] == "trace-success-1"
    assert "sure_ms" in call


@pytest.mark.asyncio
async def test_audit_log_decorator_persists_failure_to_db(monkeypatch):
    """Decorator wrapped exception → DB'ye basarili=False + hata_mesaji."""
    persisted: list = []

    async def _spy(**kwargs):
        persisted.append(kwargs)

    monkeypatch.setattr(
        "app.infrastructure.audit.audit_logger._persist_audit_to_db",
        _spy,
    )
    monkeypatch.setattr(
        "app.infrastructure.audit.audit_logger.get_correlation_id",
        lambda: "trace-fail-1",
    )

    @audit_log("DELETE", "sefer")
    async def delete_sefer(user_id: int = 0):
        raise ValueError("not found")

    with pytest.raises(ValueError, match="not found"):
        await delete_sefer(user_id=5)

    assert len(persisted) == 1
    call = persisted[0]
    assert call["action"] == "DELETE"
    assert call["basarili"] is False
    assert "not found" in call["hata_mesaji"]


@pytest.mark.asyncio
async def test_log_audit_event_persists_to_db(monkeypatch):
    """Imperative ``log_audit_event`` helper de DB'ye yazmalı —
    endpoint handler'lardan trace UI'a kayıt akışı için kritik."""
    persisted: list = []

    async def _spy(**kwargs):
        persisted.append(kwargs)

    monkeypatch.setattr(
        "app.infrastructure.audit.audit_logger._persist_audit_to_db",
        _spy,
    )
    monkeypatch.setattr(
        "app.infrastructure.audit.audit_logger.get_correlation_id",
        lambda: "trace-imp-1",
    )

    await log_audit_event(
        action="APPROVE",
        module="executive",
        entity_id="exec-1",
        new_value={"approved": True},
        user_id=42,
    )

    assert len(persisted) == 1
    call = persisted[0]
    assert call["action"] == "APPROVE"
    assert call["entity"] == "executive"
    assert call["entity_id"] == "exec-1"
    assert call["user_id"] == 42
    assert call["correlation_id"] == "trace-imp-1"
    assert call["new_value"] == {"approved": True}


@pytest.mark.asyncio
async def test_persist_sanitizes_synthetic_superadmin_id(monkeypatch):
    """Süper admin synthetic user_id=0 → kullanicilar tablosunda yok, FK
    violation olur. NULL'a düşürülmeli."""
    captured: list = []

    class FakeSession:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *_):
            return None

        async def execute(self, stmt, params=None):
            captured.append(params)
            return MagicMock()

        async def commit(self):
            pass

        def in_transaction(self):
            return False

    monkeypatch.setattr(
        "app.database.connection.AsyncSessionLocal",
        lambda: FakeSession(),
    )

    await _persist_audit_to_db(
        action="LOGIN",
        user_id=0,  # synthetic super admin
        correlation_id="trace-super-1",
    )
    assert captured[0]["kullanici_id"] is None

    # Negatif IDs de NULL'a düşmeli (sanity)
    await _persist_audit_to_db(action="LOGIN", user_id=-1)
    assert captured[1]["kullanici_id"] is None

    # Pozitif user_id korunmalı
    await _persist_audit_to_db(action="LOGIN", user_id=42)
    assert captured[2]["kullanici_id"] == 42


@pytest.mark.asyncio
async def test_persist_uses_savepoint_when_in_transaction(monkeypatch):
    """Integration test'lerde AsyncSessionLocal monkeypatch'le ortak session
    döndürebiliyor; outer transaction varsa savepoint izolasyonu gerek."""
    calls: list = []

    class FakeSavepointCtx:
        async def __aenter__(self):
            calls.append("begin_nested")
            return self

        async def __aexit__(self, *_):
            calls.append("savepoint_exit")
            return None

    class FakeSharedSession:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *_):
            return None

        async def execute(self, stmt, params=None):
            calls.append("execute")
            return MagicMock()

        async def commit(self):
            calls.append("commit")

        def in_transaction(self):
            return True

        def begin_nested(self):
            return FakeSavepointCtx()

    monkeypatch.setattr(
        "app.database.connection.AsyncSessionLocal",
        lambda: FakeSharedSession(),
    )

    await _persist_audit_to_db(action="TEST", correlation_id="t")

    # SAVEPOINT açıldı, execute içinde çalıştı, commit ÇAĞRILMADI
    # (outer transaction'a karışmamalı)
    assert "begin_nested" in calls
    assert "execute" in calls
    assert "commit" not in calls


@pytest.mark.asyncio
async def test_persist_handles_none_and_empty_gracefully(monkeypatch):
    """None / empty değerler kolonlara NULL/None gönderilmeli, crash yok."""
    captured: list = []

    class FakeSession:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *_):
            return None

        async def execute(self, stmt, params=None):
            captured.append(params)
            return MagicMock()

        async def commit(self):
            pass

        def in_transaction(self):
            return False

    monkeypatch.setattr(
        "app.database.connection.AsyncSessionLocal",
        lambda: FakeSession(),
    )

    await _persist_audit_to_db(
        action="CREATE",
        entity=None,
        entity_id=None,
        user_id=None,
        new_value=None,
        basarili=True,
        correlation_id=None,
    )

    p = captured[0]
    assert p["hedef_tablo"] is None
    assert p["hedef_id"] is None
    assert p["kullanici_id"] is None
    assert p["yeni_deger"] is None
    assert p["istek_id"] is None
