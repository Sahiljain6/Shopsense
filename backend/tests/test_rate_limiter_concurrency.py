from concurrent.futures import ThreadPoolExecutor

from app.core.gateway_middleware import SlidingWindowRateLimiter


def test_sliding_window_rate_limit_is_atomic_under_concurrency():
    limiter = SlidingWindowRateLimiter()
    request_count = 100
    allowed_count = 20

    def submit(_):
        limited, _count, _retry_after = limiter.is_rate_limited(
            "user:concurrent-test",
            max_requests_per_minute=allowed_count,
        )
        return not limited

    with ThreadPoolExecutor(max_workers=20) as executor:
        allowed = list(executor.map(submit, range(request_count)))

    assert sum(allowed) == allowed_count
    assert len(limiter._history["user:concurrent-test"]) == allowed_count


def test_sliding_window_rate_limit_bounds_new_identifiers():
    limiter = SlidingWindowRateLimiter(max_identifiers=100)

    first_results = [
        limiter.is_rate_limited(f"ip:192.0.2.{index}", max_requests_per_minute=30)
        for index in range(100)
    ]
    assert all(not item[0] for item in first_results)

    limited, count, retry_after = limiter.is_rate_limited("ip:198.51.100.1", max_requests_per_minute=30)
    assert limited is True
    assert count == 0
    assert retry_after == 60
    assert len(limiter._history) == 100
