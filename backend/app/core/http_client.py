"""Shared synchronous HTTP clients with bounded keep-alive pools.

Use a timeout-keyed client for independent outbound calls, passing credentials and
request-specific headers at call time. SSRF-sensitive redirect validation intentionally
keeps its own short-lived client so each redirect target is revalidated before fetching.
"""
from __future__ import annotations

import atexit
import threading

import httpx

_CLIENTS: dict[float, httpx.Client] = {}
_CLIENT_LOCK = threading.RLock()


def get_http_client(timeout: float = 10.0) -> httpx.Client:
    """Return a reusable client with explicit connection and keep-alive limits."""
    normalized_timeout = max(0.1, float(timeout))
    with _CLIENT_LOCK:
        client = _CLIENTS.get(normalized_timeout)
        if client is None or client.is_closed:
            client = httpx.Client(
                timeout=normalized_timeout,
                limits=httpx.Limits(
                    max_connections=30,
                    max_keepalive_connections=12,
                    keepalive_expiry=30.0,
                ),
            )
            _CLIENTS[normalized_timeout] = client
        return client


def close_http_clients() -> None:
    """Close shared clients during application shutdown and process exit."""
    with _CLIENT_LOCK:
        clients = list(_CLIENTS.values())
        _CLIENTS.clear()
    for client in clients:
        try:
            client.close()
        except Exception:
            # Cleanup must not interrupt application shutdown.
            pass


atexit.register(close_http_clients)
