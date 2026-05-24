import asyncio
import inspect
import json
import logging
import time
from collections.abc import Awaitable, Callable
from contextvars import ContextVar
from typing import Any, TypeVar

from app.core.config import settings

T = TypeVar("T")

logger = logging.getLogger("app.dependency")
_current_trace_id: ContextVar[str | None] = ContextVar("dependency_trace_id", default=None)


class DependencyCallError(RuntimeError):
    pass


class DependencyCaller:
    async def call(
        self,
        *,
        name: str,
        dependency_type: str,
        func: Callable[[], T | Awaitable[T]],
        timeout_seconds: float,
        retry_count: int = 0,
        fallback: T | Callable[[], T | Awaitable[T]] | None = None,
        trace_id: str | None = None,
        metadata: dict[str, Any] | None = None,
        slow_call_threshold_ms: float | None = None,
    ) -> T:
        trace = trace_id or _current_trace_id.get()
        token = _current_trace_id.set(trace)
        attempts = max(1, retry_count + 1)
        threshold = slow_call_threshold_ms if slow_call_threshold_ms is not None else settings.slow_dependency_threshold_ms
        last_error: Exception | None = None
        call_started = time.perf_counter()
        try:
            for attempt in range(1, attempts + 1):
                attempt_started = time.perf_counter()
                self._log(
                    "external_dependency_call_start",
                    name=name,
                    dependency_type=dependency_type,
                    trace_id=trace,
                    attempt=attempt,
                    max_attempts=attempts,
                    timeout_seconds=timeout_seconds,
                    metadata=metadata,
                )
                try:
                    result = await asyncio.wait_for(self._invoke(func), timeout=timeout_seconds)
                    latency_ms = self._elapsed_ms(attempt_started)
                    level = logging.WARNING if latency_ms >= threshold else logging.INFO
                    self._log(
                        "external_dependency_call_success",
                        level=level,
                        name=name,
                        dependency_type=dependency_type,
                        trace_id=trace,
                        attempt=attempt,
                        max_attempts=attempts,
                        latency_ms=latency_ms,
                        slow=latency_ms >= threshold,
                        metadata=metadata,
                    )
                    return result
                except Exception as exc:
                    last_error = exc
                    latency_ms = self._elapsed_ms(attempt_started)
                    self._log(
                        "external_dependency_call_failed",
                        level=logging.WARNING if attempt < attempts else logging.ERROR,
                        name=name,
                        dependency_type=dependency_type,
                        trace_id=trace,
                        attempt=attempt,
                        max_attempts=attempts,
                        latency_ms=latency_ms,
                        error_type=exc.__class__.__name__,
                        error_message=self._error_summary(exc),
                        will_retry=attempt < attempts,
                        metadata=metadata,
                    )
                    if attempt < attempts:
                        await asyncio.sleep(min(0.1 * attempt, 1.0))

            if fallback is not None:
                fallback_started = time.perf_counter()
                result = await self._resolve_fallback(fallback)
                self._log(
                    "external_dependency_fallback_used",
                    level=logging.WARNING,
                    name=name,
                    dependency_type=dependency_type,
                    trace_id=trace,
                    latency_ms=self._elapsed_ms(fallback_started),
                    total_latency_ms=self._elapsed_ms(call_started),
                    error_type=last_error.__class__.__name__ if last_error else None,
                    error_message=self._error_summary(last_error) if last_error else None,
                    metadata=metadata,
                )
                return result
            raise DependencyCallError(
                f"{dependency_type} dependency {name} failed after {attempts} attempt(s): "
                f"{self._error_summary(last_error)}"
            ) from last_error
        finally:
            _current_trace_id.reset(token)

    async def _invoke(self, func: Callable[[], T | Awaitable[T]]) -> T:
        result = func()
        if inspect.isawaitable(result):
            return await result
        return result

    async def _resolve_fallback(self, fallback: T | Callable[[], T | Awaitable[T]]) -> T:
        if callable(fallback):
            return await self._invoke(fallback)
        return fallback

    def current_trace_id(self) -> str | None:
        return _current_trace_id.get()

    def _elapsed_ms(self, started: float) -> float:
        return round((time.perf_counter() - started) * 1000, 2)

    def _error_summary(self, exc: Exception | None) -> str:
        if exc is None:
            return "unknown error"
        message = str(exc).strip()
        return message if message else exc.__class__.__name__

    def _log(self, event: str, level: int = logging.INFO, **fields: Any) -> None:
        payload = {"event": event, **fields}
        logger.log(level, json.dumps(payload, ensure_ascii=False, default=str, sort_keys=True))


dependency_caller = DependencyCaller()
