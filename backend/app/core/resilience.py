"""Bounded retry helpers and process-local circuit breakers for upstream calls."""
from __future__ import annotations

import random
import threading
import time
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from collections.abc import Callable
from typing import Any


def _status_code(error: BaseException | Any) -> int | None:
    status = getattr(error, "status_code", None)
    if status is None:
        response = getattr(error, "response", None)
        status = getattr(response, "status_code", None)
    try:
        return int(status) if status is not None else None
    except (TypeError, ValueError):
        return None


def is_transient_upstream_failure(error: BaseException | Any) -> bool:
    """Classify retryable transport/upstream failures without treating auth/input errors as transient."""
    status = _status_code(error)
    if status is not None:
        return status in {408, 409, 425, 429} or status >= 500
    name = type(error).__name__.lower()
    return any(token in name for token in ("timeout", "connection", "network", "temporarilyunavailable"))


def should_try_model_fallback(error: BaseException | Any) -> bool:
    """Allow next configured model for transient errors or explicit model-not-found responses only."""
    status = _status_code(error)
    if is_transient_upstream_failure(error):
        return True
    if status == 404:
        return True
    code = str(getattr(error, "code", "") or "").lower()
    message = str(getattr(error, "message", "") or "").lower()
    response = getattr(error, "response", None)
    if not message and response is not None:
        try:
            message = str(response.json()).lower()
        except Exception:
            message = ""
    model_miss = "model" in (code + " " + message) and any(
        word in (code + " " + message)
        for word in ("not found", "not_found", "unknown model", "invalid model", "does not exist")
    )
    return status == 400 and model_miss


def retry_after_from_error(error: BaseException | Any) -> str | None:
    """Extract Retry-After from an upstream response without logging its contents."""
    response = getattr(error, "response", None)
    headers = getattr(response, "headers", None)
    if headers is None:
        return None
    try:
        return headers.get("Retry-After") or headers.get("retry-after")
    except Exception:
        return None


def retry_delay_seconds(
    attempt: int,
    *,
    retry_after: str | int | float | None = None,
    base_seconds: float = 0.25,
    max_seconds: float = 2.0,
    remaining_seconds: float | None = None,
    random_uniform: Callable[[float, float], float] = random.uniform,
) -> float:
    """Return capped exponential backoff with jitter, bounded by Retry-After and deadline."""
    attempt = max(0, int(attempt))
    cap = min(max(0.0, max_seconds), max(0.0, base_seconds) * (2 ** min(attempt, 20)))
    delay = random_uniform(0.0, cap) if cap > 0 else 0.0
    if retry_after is not None:
        try:
            retry_after_seconds = max(0.0, float(retry_after))
        except (TypeError, ValueError):
            try:
                retry_at = parsedate_to_datetime(str(retry_after))
                if retry_at.tzinfo is None:
                    retry_at = retry_at.replace(tzinfo=timezone.utc)
                retry_after_seconds = max(0.0, (retry_at - datetime.now(timezone.utc)).total_seconds())
            except (TypeError, ValueError, OverflowError):
                retry_after_seconds = 0.0
        delay = max(delay, retry_after_seconds)
    delay = min(delay, max(0.0, max_seconds))
    if remaining_seconds is not None:
        delay = min(delay, max(0.0, remaining_seconds))
    return delay


class CircuitBreaker:
    """Thread-safe process-local closed/open/half-open breaker with one half-open probe."""

    def __init__(
        self,
        *,
        failure_threshold: int = 5,
        reset_timeout_seconds: float = 30.0,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.failure_threshold = max(1, int(failure_threshold))
        self.reset_timeout_seconds = max(0.1, float(reset_timeout_seconds))
        self._clock = clock
        self._lock = threading.RLock()
        self._state = "closed"
        self._failures = 0
        self._opened_at = 0.0
        self._probe_in_flight = False

    def allow_request(self) -> bool:
        with self._lock:
            if self._state == "closed":
                return True
            if self._state == "open":
                if self._clock() - self._opened_at < self.reset_timeout_seconds:
                    return False
                self._state = "half_open"
                self._probe_in_flight = False
            if self._state == "half_open":
                if self._probe_in_flight:
                    return False
                self._probe_in_flight = True
                return True
            return False

    def record_success(self) -> None:
        with self._lock:
            self._state = "closed"
            self._failures = 0
            self._opened_at = 0.0
            self._probe_in_flight = False

    def record_failure(self) -> None:
        with self._lock:
            if self._state == "half_open":
                self._state = "open"
                self._opened_at = self._clock()
                self._probe_in_flight = False
                return
            self._failures += 1
            if self._failures >= self.failure_threshold:
                self._state = "open"
                self._opened_at = self._clock()
                self._probe_in_flight = False

    def reset(self) -> None:
        """Reset breaker state, primarily for isolated tests and controlled operations."""
        with self._lock:
            self._state = "closed"
            self._failures = 0
            self._opened_at = 0.0
            self._probe_in_flight = False

    def snapshot(self) -> dict[str, int | float | str]:
        with self._lock:
            return {
                "state": self._state,
                "consecutive_failures": self._failures,
                "failure_threshold": self.failure_threshold,
                "reset_timeout_seconds": self.reset_timeout_seconds,
            }


_PROVIDER_BREAKERS: dict[str, CircuitBreaker] = {}
_PROVIDER_BREAKERS_LOCK = threading.RLock()
_SUPPORTED_PROVIDERS = {"openai", "groq", "gemini", "ollama", "huggingface"}


def get_provider_breaker(provider: str) -> CircuitBreaker:
    """Return a process-local breaker from a fixed provider allow-list."""
    key = str(provider or "").lower()
    if key not in _SUPPORTED_PROVIDERS:
        raise ValueError("Unsupported AI provider breaker.")
    with _PROVIDER_BREAKERS_LOCK:
        breaker = _PROVIDER_BREAKERS.get(key)
        if breaker is None:
            breaker = CircuitBreaker(failure_threshold=5, reset_timeout_seconds=30.0)
            _PROVIDER_BREAKERS[key] = breaker
        return breaker


def reset_provider_breakers() -> None:
    """Reset local provider breaker state for isolated test/application harnesses."""
    with _PROVIDER_BREAKERS_LOCK:
        for breaker in _PROVIDER_BREAKERS.values():
            breaker.reset()


def provider_breaker_stats() -> dict[str, dict[str, int | float | str]]:
    """Return non-sensitive local provider circuit status."""
    with _PROVIDER_BREAKERS_LOCK:
        return {name: breaker.snapshot() for name, breaker in _PROVIDER_BREAKERS.items()}
