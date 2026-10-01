from __future__ import annotations

import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from threading import Lock
from typing import Any


class ContractError(ValueError):
    """Raised when a tool input or output violates its contract."""


class CircuitOpenError(RuntimeError):
    """Raised when a tool is temporarily unhealthy."""


def _validate(value: Any, schema: Mapping[str, type], label: str) -> None:
    if not isinstance(value, Mapping):
        raise ContractError(f"{label} must be an object")
    missing = [key for key in schema if key not in value]
    if missing:
        raise ContractError(f"{label} missing required fields: {', '.join(missing)}")
    wrong = [f"{key} ({type(value[key]).__name__})" for key, expected in schema.items() if key in value and not isinstance(value[key], expected)]
    if wrong:
        raise ContractError(f"{label} has invalid fields: {', '.join(wrong)}")


@dataclass(frozen=True)
class RetryPolicy:
    max_attempts: int = 3
    backoff_seconds: float = 0.1
    max_backoff_seconds: float = 2.0

    def delay(self, attempt: int) -> float:
        return min(self.max_backoff_seconds, self.backoff_seconds * (2 ** max(0, attempt - 1)))


@dataclass
class Tool:
    name: str
    input_schema: Mapping[str, type]
    output_schema: Mapping[str, type]
    handler: Callable[..., Mapping[str, Any]]
    failure_threshold: int = 3
    _failures: int = field(default=0, init=False, repr=False)
    _opened_at: float | None = field(default=None, init=False, repr=False)
    _lock: Lock = field(default_factory=Lock, init=False, repr=False)

    def available(self) -> bool:
        with self._lock:
            return self._opened_at is None

    def record_failure(self) -> None:
        with self._lock:
            self._failures += 1
            if self._failures >= self.failure_threshold:
                self._opened_at = time.monotonic()

    def record_success(self) -> None:
        with self._lock:
            self._failures = 0
            self._opened_at = None


@dataclass(frozen=True)
class ToolResult:
    tool: str
    output: Mapping[str, Any]
    attempts: int
    duration_ms: float
    events: tuple[Mapping[str, Any], ...]


class ToolRunner:
    def __init__(self, retry_policy: RetryPolicy | None = None, sleep: Callable[[float], None] = time.sleep):
        self.retry_policy = retry_policy or RetryPolicy()
        self._sleep = sleep

    def run(self, tool: Tool, inputs: Mapping[str, Any], timeout_seconds: float | None = None) -> ToolResult:
        if not tool.available():
            raise CircuitOpenError(f"tool {tool.name!r} circuit is open")
        _validate(inputs, tool.input_schema, "input")
        events: list[Mapping[str, Any]] = []
        started = time.perf_counter()
        last_error: Exception | None = None
        for attempt in range(1, self.retry_policy.max_attempts + 1):
            events.append({"event": "tool_attempt", "tool": tool.name, "attempt": attempt})
            try:
                output = tool.handler(**dict(inputs))
                _validate(output, tool.output_schema, "output")
                elapsed = time.perf_counter() - started
                if timeout_seconds is not None and elapsed > timeout_seconds:
                    raise TimeoutError(f"tool {tool.name!r} exceeded timeout")
                tool.record_success()
                events.append({"event": "tool_succeeded", "tool": tool.name, "attempt": attempt})
                return ToolResult(tool.name, dict(output), attempt, elapsed * 1000, tuple(events))
            except Exception as error:  # noqa: BLE001 - provider failures are intentionally retryable
                last_error = error
                tool.record_failure()
                events.append({"event": "tool_failed", "tool": tool.name, "attempt": attempt, "error": type(error).__name__})
                if attempt < self.retry_policy.max_attempts:
                    self._sleep(self.retry_policy.delay(attempt))
        assert last_error is not None
        raise last_error
