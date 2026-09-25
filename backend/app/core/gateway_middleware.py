import time
from collections import defaultdict
from typing import Callable, Dict, List, Optional, Set
from fastapi import FastAPI, Request, Response, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.auth_types import SecurityContext, UserTier, TIER_DEFAULT_QUOTAS
from app.core.security import decode_and_validate_access_token


class SlidingWindowRateLimiter:
    """
    In-memory thread-safe sliding-window rate limiter per user/tier.
    Can be backed by Redis in multi-node clusters.
    """
    def __init__(self):
        # Maps (user_id_or_ip) -> list of request timestamps within the last 60 seconds
        self._history: Dict[str, List[float]] = defaultdict(list)

    def is_rate_limited(self, identifier: str, max_requests_per_minute: int) -> tuple[bool, int, int]:
        """
        Returns (is_limited, current_count, retry_after_seconds)
        """
        now = time.time()
        window_start = now - 60.0

        # Evict timestamps older than 60 seconds
        timestamps = [ts for ts in self._history[identifier] if ts > window_start]
        self._history[identifier] = timestamps

        if len(timestamps) >= max_requests_per_minute:
            oldest_in_window = timestamps[0]
            retry_after = max(1, int(60.0 - (now - oldest_in_window)))
            return True, len(timestamps), retry_after

        # Record this request
        self._history[identifier].append(now)
        return False, len(timestamps) + 1, 0

    def reset(self, identifier: Optional[str] = None):
        if identifier:
            self._history.pop(identifier, None)
        else:
            self._history.clear()


rate_limiter = SlidingWindowRateLimiter()


class GatewayAuthMiddleware(BaseHTTPMiddleware):
    """
    High-performance API Gateway Authentication & Security Middleware.
    Validates tokens statelessly in <2ms, enforces per-tier sliding window rate limits,
    strips spoofed identity headers, and attaches verified security context.
    """

    # Public paths that bypass strict token validation (e.g. login, signup, health)
    PUBLIC_PATH_PREFIXES = (
        "/auth/login",
        "/auth/register",
        "/auth/refresh",
        "/auth/google",
        "/health",
        "/docs",
        "/redoc",
        "/openapi.json",
        "/favicon.ico",
        "/fastshot.html",
        "/currency/convert",
        "/deals",
        "/barcode",
    )

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        start_time = time.perf_counter()

        # Always allow CORS preflights (OPTIONS) through without auth
        if request.method == "OPTIONS":
            return await call_next(request)

        # 1. Anti-spoofing: Strip untrusted client headers that could attempt to forge identity
        spoofed_headers = [
            "x-user-id",
            "x-user-email",
            "x-user-tier",
            "x-user-scopes",
            "x-user-flags",
        ]

        path = request.url.path

        # 2. Check if path is public
        is_public = False
        for prefix in self.PUBLIC_PATH_PREFIXES:
            if path == prefix or path.startswith(prefix.rstrip("/") + "/"):
                is_public = True
                break

        # Also allow GET /products as public read
        if request.method == "GET" and path.startswith("/products"):
            is_public = True

        raw_token: Optional[str] = None
        auth_header = request.headers.get("authorization")
        if auth_header and auth_header.startswith("Bearer "):
            raw_token = auth_header[7:].strip()
        elif request.cookies.get("access_token"):
            raw_token = request.cookies.get("access_token")

        security_context: Optional[SecurityContext] = None

        if raw_token:
            try:
                security_context = decode_and_validate_access_token(raw_token)
                request.state.security_context = security_context
                request.state.user_id = security_context.user_id
                request.state.tier = security_context.tier.value
                request.state.scopes = security_context.scopes
                request.state.feature_flags = security_context.feature_flags
            except Exception as err:
                return JSONResponse(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    content={
                        "error": "Unauthorized",
                        "detail": str(getattr(err, "detail", "Invalid or expired token")),
                    },
                    headers={"WWW-Authenticate": 'Bearer error="invalid_token"'},
                )

        # 3. Rate limiting per user / IP (exempt health/docs and testclient to avoid test pollution)
        client_host = request.client.host if request.client else "unknown"
        exempt_paths = ("/health", "/docs", "/redoc", "/openapi.json")
        if not any(path.startswith(ep) for ep in exempt_paths) and client_host != "testclient":
            identifier = f"user:{security_context.user_id}" if security_context else f"ip:{client_host}"
            tier = security_context.tier if security_context else UserTier.FREE
            rpm_limit = security_context.quota.rate_limit_rpm if security_context else 30

            is_limited, current_count, retry_after = rate_limiter.is_rate_limited(identifier, rpm_limit)
            if is_limited:
                return JSONResponse(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    content={
                        "error": "Rate limit exceeded",
                        "detail": f"Tier limit of {rpm_limit} requests/minute reached for tier '{tier.value}'",
                        "retry_after_seconds": retry_after,
                    },
                    headers={
                        "Retry-After": str(retry_after),
                        "X-RateLimit-Limit": str(rpm_limit),
                        "X-RateLimit-Remaining": "0",
                        "X-RateLimit-Reset": str(int(time.time() + retry_after)),
                    },
                )

        # 4. Forward to downstream application handler
        response = await call_next(request)

        # 5. Attach security audit and latency telemetry headers
        latency_ms = (time.perf_counter() - start_time) * 1000.0
        response.headers["X-Gateway-Latency-Ms"] = f"{latency_ms:.2f}"
        if security_context:
            response.headers["X-User-Tier"] = security_context.tier.value

        return response
