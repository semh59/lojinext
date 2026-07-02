"""Central Sentinel-aware Redis client factory (Tier E madde 31).

Redis is a single point of failure shared by cache, Celery broker/backend,
rate-limiting, event dedup, idempotency, and the JWT blacklist. All
production Redis client construction should go through this module instead
of calling ``redis.Redis(...)``/``redis.from_url(...)``/
``redis.asyncio.from_url(...)`` directly — that way a single
``REDIS_USE_SENTINEL`` flag switches the whole app from one Redis instance
to Sentinel-discovered HA (auto-failover to a promoted replica) without
touching call sites.

When ``REDIS_USE_SENTINEL`` is False (the dev/test default), behaviour is
unchanged: a direct connection built from REDIS_HOST/PORT/DB/PASSWORD/SSL.
"""

from __future__ import annotations

from typing import Any, List, Tuple
from urllib.parse import quote as _urlquote

from app.config import settings


def _sentinel_hosts() -> List[Tuple[str, int]]:
    hosts: List[Tuple[str, int]] = []
    for entry in filter(
        None, (h.strip() for h in settings.REDIS_SENTINEL_HOSTS.split(","))
    ):
        host, _, port = entry.partition(":")
        hosts.append((host, int(port) if port else 26379))
    return hosts


def _redis_url() -> str:
    scheme = "rediss" if settings.REDIS_SSL else "redis"
    auth = (
        f":{_urlquote(settings.REDIS_PASSWORD, safe='')}@"
        if settings.REDIS_PASSWORD
        else ""
    )
    return f"{scheme}://{auth}{settings.REDIS_HOST}:{settings.REDIS_PORT}/{settings.REDIS_DB}"


def get_sync_redis_client(**kwargs: Any) -> Any:
    """Build a sync ``redis.Redis`` — Sentinel-discovered master when
    ``REDIS_USE_SENTINEL`` is set, otherwise a direct single-instance
    connection (unchanged legacy behaviour)."""
    import redis

    kwargs.setdefault("decode_responses", True)
    kwargs.setdefault("socket_connect_timeout", 2.0)
    kwargs.setdefault("socket_timeout", 2.0)
    if settings.REDIS_PASSWORD and "password" not in kwargs:
        kwargs["password"] = settings.REDIS_PASSWORD
    url = kwargs.pop("url", None)

    if settings.REDIS_USE_SENTINEL:
        from redis.sentinel import Sentinel

        sentinel = Sentinel(
            _sentinel_hosts(),
            socket_connect_timeout=kwargs["socket_connect_timeout"],
            socket_timeout=kwargs["socket_timeout"],
        )
        return sentinel.master_for(
            settings.REDIS_SENTINEL_MASTER_NAME, db=settings.REDIS_DB, **kwargs
        )

    return redis.Redis.from_url(url or _redis_url(), **kwargs)


def get_async_redis_client(**kwargs: Any) -> Any:
    """Async-client counterpart of :func:`get_sync_redis_client`.

    Not itself a coroutine — both ``aioredis.from_url`` and
    ``AsyncSentinel.master_for`` build a lazily-connecting client
    synchronously; the network connection only happens on the first awaited
    command against the returned client.
    """
    import redis.asyncio as aioredis

    kwargs.setdefault("decode_responses", True)
    kwargs.setdefault("socket_connect_timeout", 2.0)
    kwargs.setdefault("socket_timeout", 2.0)
    if settings.REDIS_PASSWORD and "password" not in kwargs:
        kwargs["password"] = settings.REDIS_PASSWORD
    url = kwargs.pop("url", None)

    if settings.REDIS_USE_SENTINEL:
        from redis.asyncio.sentinel import Sentinel as AsyncSentinel

        sentinel = AsyncSentinel(
            _sentinel_hosts(),
            socket_connect_timeout=kwargs["socket_connect_timeout"],
            socket_timeout=kwargs["socket_timeout"],
        )
        return sentinel.master_for(
            settings.REDIS_SENTINEL_MASTER_NAME, db=settings.REDIS_DB, **kwargs
        )

    return aioredis.from_url(url or _redis_url(), **kwargs)


def get_celery_broker_url() -> str:
    """Broker URL for Celery — ``sentinel://`` scheme when Sentinel is
    enabled (kombu's redis transport auto-discovers the master), otherwise
    the plain ``settings.CELERY_BROKER_URL``.

    kombu's ``SentinelChannel`` expects EACH sentinel prefixed with its own
    ``sentinel://`` scheme, joined by ``;`` — e.g.
    ``sentinel://h1:26379;sentinel://h2:26379;sentinel://h3:26379/0``
    (see ``kombu.transport.redis.SentinelChannel`` docstring).
    """
    if not settings.REDIS_USE_SENTINEL:
        return settings.CELERY_BROKER_URL

    auth = (
        f":{_urlquote(settings.REDIS_PASSWORD, safe='')}@"
        if settings.REDIS_PASSWORD
        else ""
    )
    hosts = ";".join(
        f"sentinel://{auth}{host}:{port}" for host, port in _sentinel_hosts()
    )
    return f"{hosts}/0"


def get_celery_result_backend_url() -> str:
    """Result backend URL — same Sentinel group, DB 1 (mirrors the plain
    ``CELERY_RESULT_BACKEND`` default of DB 1 vs broker's DB 0)."""
    if not settings.REDIS_USE_SENTINEL:
        return settings.CELERY_RESULT_BACKEND

    auth = (
        f":{_urlquote(settings.REDIS_PASSWORD, safe='')}@"
        if settings.REDIS_PASSWORD
        else ""
    )
    hosts = ";".join(
        f"sentinel://{auth}{host}:{port}" for host, port in _sentinel_hosts()
    )
    return f"{hosts}/1"


def get_celery_broker_transport_options() -> dict:
    if not settings.REDIS_USE_SENTINEL:
        return {}
    return {"master_name": settings.REDIS_SENTINEL_MASTER_NAME}
