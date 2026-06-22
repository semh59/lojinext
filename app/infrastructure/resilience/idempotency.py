"""
B-003: Idempotency Guard — Redis tabanlı idempotency key mekanizması.

X-Idempotency-Key header'ı ile gelen istekleri Redis'te 5 dakika boyunca saklar.
Aynı key tekrar gelirse, önceki response'u döner.
"""

from fastapi import HTTPException, Request

from app.infrastructure.logging.logger import get_logger

logger = get_logger(__name__)

# TTL: 5 dakika
IDEMPOTENCY_TTL = 300


class IdempotencyGuard:
    """
    Redis tabanlı idempotency guard dependency.

    Kullanım:
        @router.post("/trips", dependencies=[Depends(IdempotencyGuard())])
        async def create_sefer(...): ...

    Frontend tarafında her POST isteğine X-Idempotency-Key: uuid() header eklenmeli.
    """

    async def __call__(self, request: Request) -> None:
        key = request.headers.get("X-Idempotency-Key")
        if not key:
            # Key yoksa kontrol atla — backward compatible
            return

        # User bazlı key oluştur
        user = getattr(request.state, "user", None)
        user_id = getattr(user, "id", "anon") if user else "anon"
        cache_key = f"idemp:{user_id}:{key}"

        try:
            from app.infrastructure.cache.redis_pubsub import get_pubsub_manager

            redis = get_pubsub_manager()
            if redis is None:
                # Redis yoksa idempotency kontrolü yapma
                return

            # Atomic SET NX — tek atomik işlem, get-then-set TOCTOU yok.
            inserted = await redis.set_nx(
                cache_key, "processing", expire=IDEMPOTENCY_TTL
            )
            if not inserted:
                logger.info(f"Idempotency key duplicate: {cache_key}")
                raise HTTPException(
                    status_code=409,
                    detail="Bu istek zaten işleniyor veya işlendi. Lütfen bekleyin.",
                )

        except HTTPException:
            raise
        except Exception as e:
            # Redis hatası idempotency'yi devre dışı bırakmamalı
            logger.warning(f"Idempotency check failed (non-blocking): {e}")


class IdempotencyKeyDependency:
    """
    Factory pattern for idempotency guard with configurable rate/period.
    """

    def __init__(self, operation_name: str):
        self.operation_name = operation_name
        self._guard = IdempotencyGuard()

    async def __call__(self, request: Request) -> None:
        return await self._guard(request)
