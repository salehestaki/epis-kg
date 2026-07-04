"""Tracing helpers with graceful degradation.

If ``opentelemetry`` is installed and ``OTEL_EXPORTER_OTLP_ENDPOINT`` is set,
:func:`traced` emits real spans. Otherwise it falls back to structured log
lines so services never hard-depend on a collector being present.
"""

from __future__ import annotations

import functools
import os
import time
from collections.abc import Awaitable, Callable
from typing import Any, TypeVar

from observability.logging import get_logger

_log = get_logger("observability.tracing")

F = TypeVar("F", bound=Callable[..., Any])

try:  # pragma: no cover - exercised only when the extra is installed
    from opentelemetry import trace as _otel_trace

    _TRACER = _otel_trace.get_tracer("epis-kg")
    _OTEL_AVAILABLE = bool(os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT"))
except Exception:  # noqa: BLE001
    _TRACER = None
    _OTEL_AVAILABLE = False


def langsmith_enabled() -> bool:
    """Whether LangSmith tracing should be turned on for LangGraph runs."""
    return os.getenv("LANGSMITH_TRACING", "false").lower() in ("1", "true", "yes")


def _log_span(name: str, duration_ms: float, error: BaseException | None) -> None:
    if error is None:
        _log.info("span", span=name, duration_ms=round(duration_ms, 2))
    else:
        _log.error(
            "span_error",
            span=name,
            duration_ms=round(duration_ms, 2),
            error=str(error),
            error_type=type(error).__name__,
        )


def traced(name: str | None = None) -> Callable[[F], F]:
    """Decorator emitting a span around a sync or async callable."""

    def decorator(func: F) -> F:
        span_name = name or f"{func.__module__}.{func.__qualname__}"

        if _is_coroutine(func):

            @functools.wraps(func)
            async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
                start = time.perf_counter()
                error: BaseException | None = None
                if _OTEL_AVAILABLE and _TRACER is not None:
                    with _TRACER.start_as_current_span(span_name):
                        return await func(*args, **kwargs)
                try:
                    return await func(*args, **kwargs)
                except BaseException as exc:  # noqa: BLE001
                    error = exc
                    raise
                finally:
                    _log_span(span_name, (time.perf_counter() - start) * 1000, error)

            return async_wrapper  # type: ignore[return-value]

        @functools.wraps(func)
        def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
            start = time.perf_counter()
            error: BaseException | None = None
            if _OTEL_AVAILABLE and _TRACER is not None:
                with _TRACER.start_as_current_span(span_name):
                    return func(*args, **kwargs)
            try:
                return func(*args, **kwargs)
            except BaseException as exc:  # noqa: BLE001
                error = exc
                raise
            finally:
                _log_span(span_name, (time.perf_counter() - start) * 1000, error)

        return sync_wrapper  # type: ignore[return-value]

    return decorator


def _is_coroutine(func: Callable[..., Any]) -> bool:
    import inspect

    return inspect.iscoroutinefunction(func)


# Re-exported for typing convenience.
AsyncCallable = Callable[..., Awaitable[Any]]
