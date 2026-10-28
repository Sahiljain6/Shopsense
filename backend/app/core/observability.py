"""Privacy-safe, bounded request timing metrics and request-ID middleware."""
from __future__ import annotations

import logging
import time
from contextvars import ContextVar
import uuid
from collections import deque
from threading import RLock
from typing import Any

from starlette.types import ASGIApp, Message, Receive, Scope, Send

logger = logging.getLogger("shopsense.http")

request_id_context: ContextVar[str] = ContextVar("shopsense_request_id", default="-")


def current_request_id() -> str:
    """Return the current server-generated request ID, or '-' outside an HTTP request."""
    return request_id_context.get()


class RequestMetrics:
    """Bounded process-local HTTP metrics keyed only by method and route template."""

    def __init__(self, *, max_routes: int = 250, samples_per_route: int = 256) -> None:
        self.max_routes = max(10, int(max_routes))
        self.samples_per_route = max(10, int(samples_per_route))
        self._lock = RLock()
        self._routes: dict[str, dict[str, Any]] = {}
        self._total = 0
        self._errors = 0

    def record(self, method: str, route: str, status_code: int, duration_ms: float) -> None:
        key = f"{method.upper()} {route}"[:256]
        with self._lock:
            self._total += 1
            if status_code >= 500:
                self._errors += 1
            overflow_key = "OTHER /bounded-route-cardinality"
            # Reserve one slot for the overflow bucket so route cardinality never
            # exceeds max_routes, even on the first unseen route after the cap.
            if key not in self._routes and key != overflow_key and len(self._routes) >= self.max_routes - 1:
                key = overflow_key
            row = self._routes.setdefault(key, {
                "count": 0,
                "errors_4xx": 0,
                "errors_5xx": 0,
                "duration_ms_samples": deque(maxlen=self.samples_per_route),
                "last_status": 0,
            })
            row["count"] += 1
            row["errors_4xx"] += int(400 <= status_code < 500)
            row["errors_5xx"] += int(status_code >= 500)
            row["last_status"] = int(status_code)
            row["duration_ms_samples"].append(max(0.0, float(duration_ms)))

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            routes: dict[str, Any] = {}
            for key, row in self._routes.items():
                samples = sorted(row["duration_ms_samples"])
                if samples:
                    p50 = samples[int((len(samples) - 1) * 0.50)]
                    p95 = samples[int((len(samples) - 1) * 0.95)]
                else:
                    p50 = p95 = 0.0
                routes[key] = {
                    "count": row["count"],
                    "errors_4xx": row["errors_4xx"],
                    "errors_5xx": row["errors_5xx"],
                    "last_status": row["last_status"],
                    "sample_count": len(samples),
                    "p50_duration_ms": round(p50, 2),
                    "p95_duration_ms": round(p95, 2),
                }
            return {
                "scope": "process-local",
                "request_count": self._total,
                "server_error_count": self._errors,
                "max_route_keys": self.max_routes,
                "samples_per_route": self.samples_per_route,
                "routes": routes,
            }


request_metrics = RequestMetrics()


class RequestObservabilityMiddleware:
    """Pure ASGI middleware: request ID plus complete-response timing, including SSE streams."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        # Always generate a server-owned ID: never copy arbitrary client header
        # values (which could accidentally contain secrets) into logs.
        request_id = uuid.uuid4().hex
        scope.setdefault("state", {})["request_id"] = request_id
        context_token = request_id_context.set(request_id)
        started = time.perf_counter()
        status_code = 500
        response_started = False
        finalized = False
        method = str(scope.get("method", "GET")).upper()

        async def finalize() -> None:
            nonlocal finalized
            if finalized:
                return
            finalized = True
            elapsed_ms = (time.perf_counter() - started) * 1000.0
            route_obj = scope.get("route")
            route = getattr(route_obj, "path", None) or "/unmatched"
            request_metrics.record(method, route, status_code, elapsed_ms)
            logger.info(
                "http_request request_id=%s method=%s route=%s status_code=%d duration_ms=%.2f",
                request_id, method, route, status_code, elapsed_ms,
            )

        async def send_with_context(message: Message) -> None:
            nonlocal status_code, response_started
            if message["type"] == "http.response.start":
                response_started = True
                status_code = int(message.get("status", 500))
                headers = list(message.get("headers", []))
                headers = [(name, value) for name, value in headers if name.lower() != b"x-request-id"]
                headers.append((b"x-request-id", request_id.encode("ascii")))
                message = {**message, "headers": headers}
            await send(message)
            if message["type"] == "http.response.body" and not message.get("more_body", False):
                await finalize()

        try:
            await self.app(scope, receive, send_with_context)
        except Exception as exc:
            logger.warning(
                "http_request_failed request_id=%s method=%s status_code=%d error_type=%s",
                request_id, method, status_code, type(exc).__name__,
            )
            raise
        finally:
            try:
                if not finalized:
                    if not response_started:
                        status_code = 500
                    await finalize()
            finally:
                request_id_context.reset(context_token)


class RequestBodyLimitMiddleware:
    """Reject oversized declared request bodies before multipart/JSON parsing."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        from app.core.config import get_settings
        max_bytes = int(get_settings().max_request_body_bytes)
        declared_length: int | None = None
        for name, value in scope.get("headers", []):
            if name.lower() == b"content-length":
                try:
                    declared_length = int(value.decode("ascii"))
                except (ValueError, UnicodeDecodeError):
                    declared_length = None
                break

        if declared_length is not None and declared_length > max_bytes:
            body = b'{"detail":"Request body exceeds the configured size limit."}'
            await send({
                "type": "http.response.start",
                "status": 413,
                "headers": [
                    (b"content-type", b"application/json"),
                    (b"content-length", str(len(body)).encode("ascii")),
                ],
            })
            await send({"type": "http.response.body", "body": body, "more_body": False})
            return

        await self.app(scope, receive, send)
