from __future__ import annotations

import time
from typing import Callable
from urllib.parse import urlparse, urlunparse

import httpx

from app.infrastructure.logging.logger import get_logger
from app.infrastructure.monitoring.models import ErrorEvent, ErrorLayer, ErrorSeverity

logger = get_logger(__name__)

_THRESHOLDS: dict[str, float] = {
    "ors": 3000,
    "groq": 10000,
    "telegram": 2000,
    "mapbox": 5000,
}
_DEFAULT_THRESHOLD = 5000


def _identify_service(url: str) -> str:
    try:
        host = urlparse(url).hostname or ""
    except Exception:
        host = url.lower()
    if "openrouteservice" in host or host.startswith("ors."):
        return "ors"
    if "groq" in host:
        return "groq"
    if "telegram" in host:
        return "telegram"
    if "mapbox" in host:
        return "mapbox"
    return "external"


def _sanitize_url(url: str) -> str:
    try:
        p = urlparse(url)
        netloc = p.hostname or ""
        if p.port:
            netloc = f"{netloc}:{p.port}"
        return urlunparse(p._replace(netloc=netloc, query="", fragment=""))[:200]
    except Exception:
        return url[:200]


async def _on_request(request: httpx.Request) -> None:
    # Use object id as key to avoid cross-redirect contamination
    request.extensions["_probe_start_" + str(id(request))] = time.monotonic()


async def _on_response(response: httpx.Response) -> None:
    key = "_probe_start_" + str(id(response.request))
    start = response.request.extensions.get(key)
    elapsed_ms = (time.monotonic() - start) * 1000 if start else None
    service = _identify_service(str(response.url))
    threshold = _THRESHOLDS.get(service, _DEFAULT_THRESHOLD)
    safe_url = _sanitize_url(str(response.url))

    from app.infrastructure.monitoring import aemit

    if response.status_code >= 500:
        await aemit(
            ErrorEvent(
                layer=ErrorLayer.EXTERNAL,
                category="api_5xx",
                severity=ErrorSeverity.ERROR,
                message=f"{service} HTTP {response.status_code}: {safe_url}",
                metadata={
                    "service": service,
                    "status": response.status_code,
                    "url": safe_url,
                },
            )
        )
    elif response.status_code == 429:
        await aemit(
            ErrorEvent(
                layer=ErrorLayer.EXTERNAL,
                category="api_rate_limited",
                severity=ErrorSeverity.WARNING,
                message=f"{service} rate limited (429)",
                metadata={"service": service, "url": safe_url},
            )
        )

    if elapsed_ms is not None and elapsed_ms > threshold:
        severity = (
            ErrorSeverity.ERROR if elapsed_ms > threshold * 2 else ErrorSeverity.WARNING
        )
        await aemit(
            ErrorEvent(
                layer=ErrorLayer.EXTERNAL,
                category="api_slow",
                severity=severity,
                message=f"{service} slow: {elapsed_ms:.0f}ms (threshold {threshold}ms)",
                metadata={
                    "service": service,
                    "ms": round(elapsed_ms),
                    "threshold_ms": threshold,
                    "url": safe_url,
                },
            )
        )


async def emit_network_error(exc: Exception, url: str) -> None:
    """Call from except httpx.RequestError blocks to capture network failures.

    httpx does not have a request_error hook slot, so callers must catch
    ``httpx.RequestError`` themselves and invoke this helper.

    Usage::

        try:
            resp = await client.get(url)
        except httpx.RequestError as exc:
            await emit_network_error(exc, url)
            raise
    """
    from app.infrastructure.monitoring import aemit

    service = _identify_service(url)
    await aemit(
        ErrorEvent(
            layer=ErrorLayer.EXTERNAL,
            category="api_unreachable",
            severity=ErrorSeverity.CRITICAL,
            message=f"{service} unreachable: {type(exc).__name__}: {str(exc)[:200]}",
            metadata={
                "service": service,
                "url": _sanitize_url(url),
                "exception_type": type(exc).__name__,
            },
        )
    )


def get_monitored_client(**kwargs) -> httpx.AsyncClient:
    """
    Return an httpx.AsyncClient with monitoring event_hooks wired.

    Usage (replace existing httpx.AsyncClient() calls):
        async with get_monitored_client(timeout=5.0) as client:
            resp = await client.get(url)

    Note: httpx does not expose a request_error hook slot. To capture network
    errors (e.g. connection refused, DNS failure), wrap your call in a
    ``try/except httpx.RequestError`` block and call ``emit_network_error(exc, url)``.
    """
    event_hooks: dict[str, list[Callable]] = kwargs.pop("event_hooks", {})
    event_hooks.setdefault("request", []).insert(0, _on_request)
    event_hooks.setdefault("response", []).insert(0, _on_response)
    return httpx.AsyncClient(event_hooks=event_hooks, **kwargs)
