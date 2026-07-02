"""
Canonical audit logging decorator and helpers.

İki kanal:
  1. JSON dosya log (her zaman, mevcut davranış)
  2. ``admin_audit_log`` tablosu (best-effort async INSERT — Trace UI
     audit chain'i için. DB fail asıl iş akışını bozmaz.)

Sync wrapper'lar yalnız JSON log atar (event loop garanti değil); async
wrapper ve ``log_audit_event`` DB'ye de yazar.
"""

import asyncio
import functools
import json
from datetime import datetime, timezone
from typing import Any, Callable, Optional

from app.infrastructure.context.request_context import (
    get_correlation_id,
    set_correlation_id,
)
from app.infrastructure.logging.logger import get_logger

audit_logger = get_logger("audit")


async def _persist_audit_to_db(
    *,
    action: str,
    entity: Optional[str] = None,
    entity_id: Optional[str] = None,
    user_id: Optional[int] = None,
    new_value: Any = None,
    old_value: Any = None,
    basarili: bool = True,
    hata_mesaji: Optional[str] = None,
    sure_ms: Optional[int] = None,
    correlation_id: Optional[str] = None,
    aciklama: Optional[str] = None,
) -> None:
    """Best-effort INSERT to ``admin_audit_log`` — never raises.

    Türkçe kolon mapping'i ``app/api/v1/endpoints/system.py`` trace
    endpoint sorgusuyla bire bir uyumlu (istek_id, aksiyon_tipi, hedef_tablo,
    hedef_id, kullanici_id, yeni_deger, basarili, sure_ms, zaman, ...).

    DB hatası asıl iş akışını bozmaz — sadece warning log atar.
    """
    try:
        from sqlalchemy import text

        from app.database.connection import AsyncSessionLocal

        # JSONB kolonlarına insert için Python objesini JSON string'e çevir;
        # `CAST(:x AS JSONB)` ile asyncpg adaptasyonu güvenli.
        new_value_json = (
            json.dumps(new_value, default=str) if new_value is not None else None
        )
        old_value_json = (
            json.dumps(old_value, default=str) if old_value is not None else None
        )

        # sure_ms INTEGER — float'tan dönüştür
        sure_ms_int: Optional[int] = (
            int(round(sure_ms)) if sure_ms is not None else None
        )

        # user_id INTEGER veya None — string gelirse atla. Süper admin
        # synthetic id=0 (app/api/deps.py:156,163) kullanıyor; kullanicilar
        # tablosunda karşılığı yok → FK violation. <=0 olanları NULL'a
        # düşürüp insert'i geçirelim.
        user_id_int: Optional[int]
        if user_id is None:
            user_id_int = None
        else:
            try:
                user_id_int = int(user_id)
            except (TypeError, ValueError):
                user_id_int = None
        if user_id_int is not None and user_id_int <= 0:
            user_id_int = None

        # entity_id TEXT — herhangi bir scalar string'e çevrilir
        entity_id_text = (
            str(entity_id) if entity_id is not None and entity_id != "" else None
        )

        # Integration test'lerde AsyncSessionLocal monkeypatch'le ortak bir
        # session döndürebiliyor (app/tests/conftest.py NonClosingSession).
        # SAVEPOINT olmadan burada bir IntegrityError olursa testin dış
        # transaction'ı poison'lanır → sonraki sorgular
        # InFailedSQLTransactionError. begin_nested() ile inner block
        # rollback edilir, dış transaction etkilenmez.
        async with AsyncSessionLocal() as session:
            insert_sql = text(
                """
                INSERT INTO admin_audit_log (
                    kullanici_id, aksiyon_tipi, hedef_tablo, hedef_id,
                    aciklama, eski_deger, yeni_deger,
                    basarili, hata_mesaji, sure_ms, istek_id
                ) VALUES (
                    :kullanici_id, :aksiyon_tipi, :hedef_tablo, :hedef_id,
                    :aciklama,
                    CAST(:eski_deger AS JSONB), CAST(:yeni_deger AS JSONB),
                    :basarili, :hata_mesaji, :sure_ms, :istek_id
                )
                """
            )
            params = {
                "kullanici_id": user_id_int,
                "aksiyon_tipi": action[:100],
                "hedef_tablo": (entity[:100] if entity else None),
                "hedef_id": entity_id_text,
                "aciklama": aciklama,
                "eski_deger": old_value_json,
                "yeni_deger": new_value_json,
                "basarili": basarili,
                "hata_mesaji": (hata_mesaji[:500] if hata_mesaji else None),
                "sure_ms": sure_ms_int,
                "istek_id": (correlation_id[:36] if correlation_id else None),
            }
            if session.in_transaction():
                # Shared/test session: savepoint izolasyonu
                async with session.begin_nested():
                    await session.execute(insert_sql, params)
            else:
                # Production: fresh session, normal commit
                await session.execute(insert_sql, params)
                await session.commit()
    except Exception as exc:
        # Asıl iş zaten JSON log'a gitti — DB persist düşmesi sessiz olmasın
        # ama exception'ı yutalım (audit_log decorator caller'ın akışını
        # bozmamalı).
        audit_logger.warning(
            "audit DB persist failed (action=%s, trace=%s): %s",
            action,
            correlation_id,
            exc,
        )


def _mask_sensitive_data(data: Any) -> Any:
    sensitive_keys = {
        "password",
        "token",
        "api_key",
        "secret",
        "credit_card",
        "sifre",
        "auth",
        # PII fields
        "telefon",
        "phone",
        "email",
        "tc_no",
        "tc_kimlik",
        "kimlik_no",
        "dogum_tarihi",
        "adres",
        "address",
    }

    if isinstance(data, dict):
        return {
            key: (
                "***MASKED***"
                if any(token in key.lower() for token in sensitive_keys)
                else _mask_sensitive_data(value)
            )
            for key, value in data.items()
        }
    if isinstance(data, list):
        return [_mask_sensitive_data(item) for item in data]
    return data


def audit_log(action: str, entity_type: str = None, log_params: bool = False):
    """Audit decorator for service and compatibility callers."""

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            start = datetime.now(timezone.utc)
            user_id = kwargs.get("user_id")
            if not user_id and args:
                user_id = getattr(args[0], "_current_user_id", None)

            audit_entry = {
                "timestamp": start.isoformat(),
                "action": action,
                "entity": entity_type or func.__name__,
                "user_id": user_id,
                "function": func.__name__,
                "correlation_id": get_correlation_id(),
                "status": "started",
            }

            if log_params and kwargs:
                from app.infrastructure.security.pii_scrubber import scrub_pii

                safe_params = _mask_sensitive_data(scrub_pii(kwargs))
                audit_entry["params"] = str(safe_params)[:500]

            try:
                result = await func(*args, **kwargs)
                audit_entry["status"] = "success"
                audit_entry["duration_ms"] = round(
                    (datetime.now(timezone.utc) - start).total_seconds() * 1000, 2
                )
                audit_logger.info(json.dumps(audit_entry, default=str))
                # DB persist — best-effort, JSON log'dan sonra
                await _persist_audit_to_db(
                    action=action,
                    entity=entity_type or func.__name__,
                    user_id=user_id,
                    basarili=True,
                    sure_ms=audit_entry["duration_ms"],
                    correlation_id=audit_entry["correlation_id"],
                )
                return result
            except Exception as exc:
                audit_entry["status"] = "failed"
                audit_entry["error"] = str(exc)[:200]
                audit_entry["duration_ms"] = round(
                    (datetime.now(timezone.utc) - start).total_seconds() * 1000, 2
                )
                audit_logger.error(json.dumps(audit_entry, default=str))
                # Fail durumu da DB'ye yazılmalı — trace UI'da failure
                # action görünsün (rollback'ten önce log)
                await _persist_audit_to_db(
                    action=action,
                    entity=entity_type or func.__name__,
                    user_id=user_id,
                    basarili=False,
                    hata_mesaji=str(exc)[:500],
                    sure_ms=audit_entry["duration_ms"],
                    correlation_id=audit_entry["correlation_id"],
                )
                raise

        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            start = datetime.now(timezone.utc)
            audit_entry = {
                "timestamp": start.isoformat(),
                "action": action,
                "entity": entity_type or func.__name__,
                "function": func.__name__,
                "correlation_id": get_correlation_id(),
                "status": "started",
            }

            if log_params and kwargs:
                from app.infrastructure.security.pii_scrubber import scrub_pii

                safe_params = _mask_sensitive_data(scrub_pii(kwargs))
                audit_entry["params"] = str(safe_params)[:500]

            try:
                result = func(*args, **kwargs)
                audit_entry["status"] = "success"
                audit_entry["duration_ms"] = round(
                    (datetime.now(timezone.utc) - start).total_seconds() * 1000, 2
                )
                audit_logger.info(json.dumps(audit_entry, default=str))
                return result
            except Exception as exc:
                audit_entry["status"] = "failed"
                audit_entry["error"] = str(exc)[:200]
                audit_entry["duration_ms"] = round(
                    (datetime.now(timezone.utc) - start).total_seconds() * 1000, 2
                )
                audit_logger.error(json.dumps(audit_entry, default=str))
                raise

        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper

    return decorator


async def log_audit_event(
    action: str,
    module: str = "",
    entity_id: str = "",
    old_value: Any = None,
    new_value: Any = None,
    user_id: Any = None,
    basarili: bool = True,
    **extra: Any,
) -> None:
    """Imperative audit logging helper for use inside endpoint handlers.

    ``basarili`` (2026-07-01 prod-grade denetimi P1 eki): önceden bu parametre
    yoktu — ``_persist_audit_to_db`` her zaman ``basarili=True`` ile
    çağrılıyordu, yani bu helper üzerinden bir başarısız-giriş/403 denemesi
    kaydedilse bile DB'de "başarılı" görünürdü. Artık çağıran taraf açıkça
    ``basarili=False`` geçebilir (ör. `auth.failed_login`, `authz.forbidden`).
    """
    correlation_id = get_correlation_id()
    # 2026-07-02 prod-grade denetimi P2 (Tier A madde 5): `if old_value else None`
    # Python truthiness kullanıyordu — 0/False/""/{}/[] gibi geçerli-falsy
    # değerler sessizce audit trail'den düşüyordu (audit "değer yok" sanıyordu,
    # oysa GERÇEK bir 0/False/boş değere set edildiğini kaydetmesi gerekiyordu).
    masked_old = _mask_sensitive_data(old_value) if old_value is not None else None
    masked_new = _mask_sensitive_data(new_value) if new_value is not None else None

    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "action": action,
        "module": module,
        "entity_id": entity_id,
        "user_id": user_id,
        "correlation_id": correlation_id,
        "old_value": masked_old,
        "new_value": masked_new,
        "basarili": basarili,
    }
    entry.update(extra)
    audit_logger.info(json.dumps(entry, default=str))

    # DB persist — endpoint handler tipik async context'tedir; trace UI
    # için bu satır olmadan audit chain hep boş kalır.
    await _persist_audit_to_db(
        action=action,
        entity=module or None,
        entity_id=str(entity_id) if entity_id else None,
        user_id=user_id,
        old_value=masked_old,
        new_value=masked_new,
        basarili=basarili,
        correlation_id=correlation_id,
        aciklama=extra.get("aciklama") or extra.get("description"),
    )


__all__ = [
    "audit_log",
    "log_audit_event",
    "_mask_sensitive_data",
    "get_correlation_id",
    "set_correlation_id",
]
