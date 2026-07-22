"""2026-07-01 prod-grade denetimi P1 (Dalga 4 madde 19) — idempotency key desteği.

Client `Idempotency-Key` header'ı gönderirse, aynı (key, endpoint) çifti için
aynı istek gövdesiyle tekrar POST edilirse önbelleklenen yanıt aynen dönülür
(yeni kayıt oluşturulmaz); farklı bir gövdeyle tekrar edilirse
`IdempotencyKeyConflictError` fırlatılır (çağıran 409'a çevirir).

2026-07-01 derin kontrol bulgusu #1: ilk implementasyon `get_cached_response()`
(SELECT) + ayrı bir `store_response()` (INSERT, commit sonradan) kullanıyordu —
aynı YENİ key ile gerçek eşzamanlı iki istek gelirse, ikisi de SELECT'te "yok"
bulup ikisi de gerçek işlemi yapıyor, sonra ikinci commit `UniqueViolationError`
ile yakalanmamış şekilde patlıyordu (500). Fix: "reserve-then-create" deseni
(bkz. `reserve_or_get_cached()` docstring'i).

2026-07-01 derin kontrol bulgusu #2: "reserve-then-create" ilk hâli, rezervasyon
INSERT'ini çağıranın PAYLAŞILAN request-UoW session'ında (`uow.session`) aynı
transaction içinde yapıyordu — "aynı transaction = atomik" varsayımıyla. Ancak
`POST /trips/` özelinde bu varsayım YANLIŞ çıktı: `SeferWriteService.add_sefer`
→ `_predict_outbound`, ML tahminine 2.5s `asyncio.wait_for` timeout'u uyguluyor
(bkz CLAUDE.md "Sefer yakıt tahmini"); tahmin genellikle bunu aşıyor (RAG/HF
network çağrıları). `asyncio.wait_for` timeout'ta iç task'ı `CancelledError` ile
iptal ediyor — bu iptal, tahmin pipeline'ının kendi (non-owning, paylaşılan
session'a bağlı) `async with UnitOfWork()` bloğu İÇİNDEYKEN gerçekleşirse,
`UnitOfWork.__aexit__` bunu "hata oluştu" sayıp `rollback()` çağırıyor —
`rollback()` `_owns` kontrolü YAPMIYOR (bilinen, ayrı bir bulgu — bkz rapor),
yani PAYLAŞILAN session'ın TÜMÜNÜ (benim henüz commit edilmemiş rezervasyon
satırım dahil) geri alıyor. Sefer kaydı yine de başarıyla oluşuyor çünkü ondan
SONRAKİ INSERT'ler session'ın otomatik açtığı YENİ transaction'a düşüyor — ama
rezervasyonum o yeni transaction'da YOK, sessizce kayboluyor. Sonuç: aynı key
ile ikinci istek `reserve_or_get_cached`'i BOŞ bulup tekrar "reserved=True"
dönüyor → GERÇEK bir ikinci sefer oluşuyor (item 19'un önlemeye çalıştığı tam
senaryo, sessizce geri geliyor). Empirik kanıt: `test_trip_create_same_idempotency_key_does_not_duplicate`
kırmızıydı — rezervasyon satırı ilk isteğin sonunda DB'de HİÇ yoktu.

Fix: idempotency defteri artık çağıranın UoW'undan TAMAMEN BAĞIMSIZ, kendi
kısa ömürlü session'ında anında commit ediyor (`v2.modules.platform_infra.database.connection`
üzerinden, modül attribute erişimiyle — test fixture'ının monkeypatch'i hâlâ
geçerli oluyor). Böylece ana iş-transaction'ında (add_sefer içinde) her ne
olursa olsun (cancel/rollback/retry), rezervasyon kaydı ETKİLENMİYOR. Bu,
Stripe'ın gerçek idempotency-key implementasyonlarının da kullandığı desen —
idempotency defteri iş transaction'ından kasıtlı olarak AYRI tutulur. Bedeli:
gerçek iş BAŞARISIZ olursa rezervasyon "pending" kalıp gelecek retry'ları
kilitleyebilir — bu yüzden `release_reservation()` eklendi, çağıran (fuel.py/
trips.py) her hata yolunda bunu çağırıp rezervasyonu serbest bırakmalı.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any, Optional

from sqlalchemy import delete, select, update
from sqlalchemy.exc import IntegrityError

import v2.modules.platform_infra.database.connection as db_connection
from v2.modules.admin_platform.infrastructure.models import IdempotencyKey

# Reservation sentinel — finalize_response() overwrites this before commit.
# A real HTTP status code is always >= 100, so 0 can never collide.
_PENDING_STATUS = 0


class IdempotencyKeyConflictError(Exception):
    """Aynı idempotency key farklı bir istek gövdesiyle daha önce kullanılmış."""


class IdempotencyKeyInProgressError(Exception):
    """Aynı key için başka bir istek şu an işleniyor (nadir, dar bir yarış penceresi)."""


@dataclass
class ReservationResult:
    reserved: bool
    cached: Optional[tuple[int, Any]] = None


def _hash_request_body(body: dict[str, Any]) -> str:
    canonical = json.dumps(body, sort_keys=True, default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


async def _select_existing(
    session, *, key: str, endpoint: str
) -> Optional[IdempotencyKey]:
    result = await session.execute(
        select(IdempotencyKey).where(
            IdempotencyKey.key == key, IdempotencyKey.endpoint == endpoint
        )
    )
    return result.scalar_one_or_none()


async def reserve_or_get_cached(
    *, key: str, endpoint: str, request_body: dict[str, Any]
) -> ReservationResult:
    """Bu (key, endpoint) için işlemeyi dener veya mevcut yanıtı döner.

    Kasıtlı olarak çağıranın UoW/session'ından BAĞIMSIZ, kendi kısa ömürlü
    session'ında çalışır ve anında commit eder — bkz. modül docstring'i
    (derin kontrol bulgusu #2): ana iş-transaction'ı içeride her ne olursa
    olsun (unrelated cancel/rollback), rezervasyon kaydı etkilenmemeli.

    Returns:
        ReservationResult(reserved=True) — anahtar başarıyla rezerve edildi;
            çağıran gerçek işi yapmalı, başarılıysa `finalize_response()`,
            başarısızsa `release_reservation()` çağırmalı.
        ReservationResult(reserved=False, cached=(status_code, body)) —
            aynı istek daha önce (veya bu anda eşzamanlı olarak) başarıyla
            işlendi; bu yanıt aynen dönülmeli, hiçbir gerçek iş yapılmamalı.

    Raises:
        IdempotencyKeyConflictError — key farklı bir gövdeyle kullanılmış.
        IdempotencyKeyInProgressError — key için başka bir istek hâlâ
            işleniyor (rezerve edilmiş ama henüz finalize edilmemiş).
    """
    request_hash = _hash_request_body(request_body)

    async with db_connection.AsyncSessionLocal() as session:
        existing = await _select_existing(session, key=key, endpoint=endpoint)
        if existing is not None:
            return _resolve_existing(existing, request_hash)

        try:
            session.add(
                IdempotencyKey(
                    key=key,
                    endpoint=endpoint,
                    request_hash=request_hash,
                    response_status_code=_PENDING_STATUS,
                    response_body={},
                )
            )
            await session.commit()
        except IntegrityError:
            await session.rollback()
            # Gerçek eşzamanlı ilk-kullanım yarışı — rakip satır artık commit
            # edilmiş olmalı (Postgres unique-index insert, çakışan satırın
            # transaction'ı bitene kadar bloklar). Güvenle yeniden oku.
            existing = await _select_existing(session, key=key, endpoint=endpoint)
            if existing is None:
                raise
            return _resolve_existing(existing, request_hash)

        return ReservationResult(reserved=True)


def _resolve_existing(existing: IdempotencyKey, request_hash: str) -> ReservationResult:
    if existing.request_hash != request_hash:
        raise IdempotencyKeyConflictError(
            "Idempotency-Key daha önce farklı bir istek gövdesiyle kullanılmış"
        )
    if existing.response_status_code == _PENDING_STATUS:
        raise IdempotencyKeyInProgressError(
            "Bu Idempotency-Key için başka bir istek şu an işleniyor"
        )
    return ReservationResult(
        reserved=False,
        cached=(existing.response_status_code, existing.response_body),
    )


async def finalize_response(
    *,
    key: str,
    endpoint: str,
    status_code: int,
    response_body: Any,
) -> None:
    """Rezervasyonu gerçek yanıtla günceller — kendi bağımsız session'ında
    anında commit eder (bkz. `reserve_or_get_cached` docstring'i)."""
    async with db_connection.AsyncSessionLocal() as session:
        await session.execute(
            update(IdempotencyKey)
            .where(IdempotencyKey.key == key, IdempotencyKey.endpoint == endpoint)
            .values(response_status_code=status_code, response_body=response_body)
        )
        await session.commit()


async def release_reservation(*, key: str, endpoint: str) -> None:
    """Gerçek iş başarısız olduğunda rezervasyonu siler — aksi halde
    `_PENDING_STATUS`'ta kalır ve gelecekteki tüm retry'ları kalıcı olarak
    `IdempotencyKeyInProgressError`'a kilitler. Yalnızca hâlâ pending
    olan (henüz finalize edilmemiş) satırı siler — zaten finalize edilmiş
    bir satırı asla silmez (nadir bir geç-hata senaryosunda önbelleklenmiş
    başarılı yanıtı bozmamak için)."""
    async with db_connection.AsyncSessionLocal() as session:
        await session.execute(
            delete(IdempotencyKey).where(
                IdempotencyKey.key == key,
                IdempotencyKey.endpoint == endpoint,
                IdempotencyKey.response_status_code == _PENDING_STATUS,
            )
        )
        await session.commit()
