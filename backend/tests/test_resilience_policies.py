import httpx

from app.core.resilience import CircuitBreaker, is_transient_upstream_failure, retry_delay_seconds, should_try_model_fallback
from app.services import live_search


def test_retry_delay_is_jittered_capped_and_respects_deadline():
    delay = retry_delay_seconds(
        4,
        retry_after=8,
        max_seconds=10,
        remaining_seconds=3,
        random_uniform=lambda low, high: high,
    )
    assert delay == 3

    capped = retry_delay_seconds(8, max_seconds=2, random_uniform=lambda low, high: high)
    assert capped == 2


def test_permanent_provider_errors_do_not_trigger_model_fallback():
    assert should_try_model_fallback(type("Unauthorized", (), {"status_code": 401})()) is False
    assert should_try_model_fallback(type("BadRequest", (), {"status_code": 400, "message": "invalid JSON payload"})()) is False
    assert should_try_model_fallback(type("MissingModel", (), {"status_code": 404})()) is True
    assert should_try_model_fallback(type("RateLimited", (), {"status_code": 429})()) is True
    assert is_transient_upstream_failure(type("ServerError", (), {"status_code": 503})())


def test_circuit_breaker_opens_then_allows_only_one_half_open_probe():
    now = {"value": 100.0}
    breaker = CircuitBreaker(
        failure_threshold=2,
        reset_timeout_seconds=10,
        clock=lambda: now["value"],
    )
    assert breaker.allow_request() is True
    breaker.record_failure()
    assert breaker.allow_request() is True
    breaker.record_failure()
    assert breaker.snapshot()["state"] == "open"
    assert breaker.allow_request() is False

    now["value"] += 10
    assert breaker.allow_request() is True
    assert breaker.snapshot()["state"] == "half_open"
    assert breaker.allow_request() is False
    breaker.record_success()
    assert breaker.snapshot()["state"] == "closed"
    assert breaker.allow_request() is True


def test_serpapi_circuit_short_circuits_repeated_transient_failures(monkeypatch):
    live_search.clear_live_search_cache()
    live_search._SERPAPI_BREAKER.reset()
    monkeypatch.setattr(
        live_search,
        "get_settings",
        lambda: type("Settings", (), {
            "serpapi_api_key": "test-only-key",
            "serpapi_location": "Mumbai, Maharashtra, India",
            "live_search_cache_ttl_seconds": 1,
            "live_search_cache_max_entries": 16,
        })(),
    )
    upstream_calls = []
    fallback_calls = []

    class BrokenClient:
        def get(self, url, params, timeout):
            upstream_calls.append(url)
            raise httpx.ConnectError("test connection failure")

    monkeypatch.setattr(live_search, "get_http_client", lambda timeout: BrokenClient())
    monkeypatch.setattr(
        live_search, "_search_ddg",
        lambda query, limit: fallback_calls.append(query) or [],
    )

    for _ in range(6):
        live_search.search_live_deals("headphones latest price", force=True)

    assert len(upstream_calls) == 5
    assert len(fallback_calls) == 6
    assert live_search.serpapi_breaker_stats()["state"] == "open"

    live_search._SERPAPI_BREAKER.reset()
    live_search.clear_live_search_cache()
