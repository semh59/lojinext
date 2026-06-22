from __future__ import annotations

import asyncio
import functools
import traceback as _tb
from contextvars import ContextVar
from typing import Any, Callable, TypeVar

from app.infrastructure.logging.logger import get_logger
from app.infrastructure.monitoring import aemit, emit
from app.infrastructure.monitoring.models import ErrorEvent, ErrorLayer, ErrorSeverity

logger = get_logger(__name__)

F = TypeVar("F", bound=Callable)

_call_chain: ContextVar[list[str] | None] = ContextVar(
    "service_call_chain", default=None
)


def monitor_errors(
    category: str = "service_error",
    severity: str = "error",
    reraise: bool = True,
    capture_result: bool = False,
) -> Callable[[F], F]:
    """
    Decorator for service methods. Emits ErrorEvent on any non-DomainError exception.
    DomainError is intentionally skipped — main.py exception handlers cover it.

    capture_result: if True, emit WARNING when function returns None.
                    Only use on methods where None is never a valid return value
                    (e.g. "get by id" lookups, not mutations/deletes).
    """

    def decorator(fn: F) -> F:
        if asyncio.iscoroutinefunction(fn):

            @functools.wraps(fn)
            async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
                chain = (_call_chain.get(None) or []).copy()
                chain.append(fn.__qualname__)
                token = _call_chain.set(chain)
                try:
                    result = await fn(*args, **kwargs)
                    if capture_result and result is None:
                        await aemit(
                            ErrorEvent(
                                layer=ErrorLayer.SERVICE,
                                category=f"{category}:null_result",
                                severity=ErrorSeverity.WARNING,
                                message=f"{fn.__qualname__} returned None unexpectedly",
                                metadata={"fn": fn.__qualname__, "call_chain": chain},
                            )
                        )
                    return result
                except Exception as exc:
                    from fastapi import HTTPException

                    from app.core.exceptions import DomainError

                    if isinstance(exc, (DomainError, HTTPException)):
                        raise
                    await aemit(
                        ErrorEvent(
                            layer=ErrorLayer.SERVICE,
                            category=category,
                            severity=ErrorSeverity(severity),
                            message=(
                                f"{fn.__qualname__}: {type(exc).__name__}: {str(exc)[:300]}"
                            ),
                            stack_trace=_tb.format_exc()[:2000],
                            metadata={
                                "fn": fn.__qualname__,
                                "exception_type": type(exc).__name__,
                                "call_chain": chain,
                            },
                        )
                    )
                    if reraise:
                        raise
                    return None
                finally:
                    _call_chain.reset(token)

            return async_wrapper  # type: ignore[return-value]
        else:

            @functools.wraps(fn)
            def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
                chain = (_call_chain.get(None) or []).copy()
                chain.append(fn.__qualname__)
                token = _call_chain.set(chain)
                try:
                    result = fn(*args, **kwargs)
                    return result
                except Exception as exc:
                    from fastapi import HTTPException

                    from app.core.exceptions import DomainError

                    if isinstance(exc, (DomainError, HTTPException)):
                        raise
                    emit(
                        ErrorEvent(
                            layer=ErrorLayer.SERVICE,
                            category=category,
                            severity=ErrorSeverity(severity),
                            message=f"{fn.__qualname__}: {type(exc).__name__}: {str(exc)[:300]}",
                            metadata={
                                "fn": fn.__qualname__,
                                "exception_type": type(exc).__name__,
                                "call_chain": chain,
                            },
                        )
                    )
                    if reraise:
                        raise
                    return None
                finally:
                    _call_chain.reset(token)

            return sync_wrapper  # type: ignore[return-value]

    return decorator


def intentional_fallback(reason: str) -> Callable[[F], F]:
    """
    Marks a function as having an intentional silent fallback.
    Emits WARNING (not ERROR) — distinguishes bugs from handled degradation.
    """

    def decorator(fn: F) -> F:
        @functools.wraps(fn)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            try:
                return await fn(*args, **kwargs)
            except Exception as exc:
                await aemit(
                    ErrorEvent(
                        layer=ErrorLayer.SERVICE,
                        category="intentional_fallback",
                        severity=ErrorSeverity.WARNING,
                        message=(
                            f"[INTENTIONAL] {fn.__qualname__}: {reason}"
                            f" — {type(exc).__name__}: {str(exc)[:200]}"
                        ),
                        metadata={
                            "fn": fn.__qualname__,
                            "reason": reason,
                            "exception_type": type(exc).__name__,
                        },
                    )
                )
                return None

        return wrapper  # type: ignore[return-value]

    return decorator


def assert_invariant(
    invariant_holds: bool,
    message: str,
    severity: str = "error",
    metadata: dict | None = None,
) -> None:
    """
    Emit ErrorEvent if a business invariant is violated.
    Does NOT raise — use when wrong value is detected but processing can continue.
    """
    if invariant_holds:
        return
    emit(
        ErrorEvent(
            layer=ErrorLayer.SERVICE,
            category="invariant_violation",
            severity=ErrorSeverity(severity),
            message=message,
            metadata=metadata or {},
        )
    )


def setup_asyncio_exception_handler() -> None:
    """Capture unhandled asyncio coroutine exceptions (dangling tasks)."""

    def _handler(loop: asyncio.AbstractEventLoop, context: dict) -> None:
        msg = context.get("message", "")
        exc = context.get("exception")
        future = context.get("future")
        emit(
            ErrorEvent(
                layer=ErrorLayer.SERVICE,
                category="async_context_leak",
                severity=ErrorSeverity.ERROR,
                message=f"Asyncio unhandled: {msg}",
                metadata={
                    "exception": str(exc) if exc else None,
                    "exception_type": type(exc).__name__
                    if isinstance(exc, BaseException)
                    else None,
                    "source": str(future)[:200] if future else None,
                },
            )
        )
        logger.error("Asyncio unhandled exception: %s", msg, exc_info=exc)

    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        logger.debug("setup_asyncio_exception_handler: no running loop at call time")
        return
    loop.set_exception_handler(_handler)
    logger.info("Asyncio exception handler probe activated")
