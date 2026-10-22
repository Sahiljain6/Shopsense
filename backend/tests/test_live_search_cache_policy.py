from types import SimpleNamespace

from app.services import live_search


def settings(api_key="test-cache-key", location="Mumbai, Maharashtra, India", ttl=900, max_entries=256):
    return SimpleNamespace(
        serpapi_api_key=api_key,
        serpapi_location=location,
        live_search_cache_ttl_seconds=ttl,
        live_search_cache_max_entries=max_entries,
    )


def test_cache_key_tracks_location_provider_configuration_and_result_limit(monkeypatch):
    live_search.clear_live_search_cache()
    monkeypatch.setenv("SERPAPI_API_KEY", "")
    active = {"settings": settings()}
    monkeypatch.setattr(live_search, "get_settings", lambda: active["settings"])
    calls = []

    def fake_search(query, max_results):
        calls.append((query, max_results))
        return True, [{
            "title": "Headphones",
            "retrieved_at": "2026-10-22T00:00:00Z",
            "price": 100,
        }]

    monkeypatch.setattr(live_search, "_search_serpapi", fake_search)

    live_search.search_live_deals("headphones latest price", max_results=2, force=True)
    live_search.search_live_deals("headphones latest price", max_results=2, force=True)
    active["settings"] = settings(location="Delhi, India")
    live_search.search_live_deals("headphones latest price", max_results=2, force=True)
    active["settings"] = settings(api_key="rotated-test-key", location="Delhi, India")
    live_search.search_live_deals("headphones latest price", max_results=2, force=True)
    live_search.search_live_deals("headphones latest price", max_results=3, force=True)

    assert len(calls) == 4
    assert calls[0][1] == 2
    assert calls[-1][1] == 3
    assert live_search.live_search_cache_stats()["hits"] == 1
    live_search.clear_live_search_cache()


def test_cache_hit_returns_copy_and_preserves_snapshot_timestamp(monkeypatch):
    live_search.clear_live_search_cache()
    monkeypatch.setenv("SERPAPI_API_KEY", "")
    monkeypatch.setattr(live_search, "get_settings", lambda: settings())
    calls = []

    def fake_search(query, max_results):
        calls.append(query)
        return True, [{"title": "Original", "retrieved_at": "2026-10-22T00:00:00Z"}]

    monkeypatch.setattr(live_search, "_search_serpapi", fake_search)
    first = live_search.search_live_deals("headphones latest price", force=True)
    first[0]["title"] = "Caller mutation"
    second = live_search.search_live_deals("headphones latest price", force=True)

    assert len(calls) == 1
    assert second[0]["title"] == "Original"
    assert second[0]["retrieved_at"] == "2026-10-22T00:00:00Z"
    live_search.clear_live_search_cache()


def test_expired_cache_entry_is_refetched(monkeypatch):
    live_search.clear_live_search_cache()
    monkeypatch.setenv("SERPAPI_API_KEY", "")
    monkeypatch.setattr(live_search, "get_settings", lambda: settings(ttl=1))
    clock = {"now": 10.0}
    monkeypatch.setattr(live_search.time, "monotonic", lambda: clock["now"])
    calls = []

    def fake_search(query, max_results):
        calls.append(query)
        return True, [{"title": f"Result {len(calls)}", "retrieved_at": "2026-10-22T00:00:00Z"}]

    monkeypatch.setattr(live_search, "_search_serpapi", fake_search)
    first = live_search.search_live_deals("headphones latest price", force=True)
    clock["now"] += 2
    second = live_search.search_live_deals("headphones latest price", force=True)

    assert first[0]["title"] == "Result 1"
    assert second[0]["title"] == "Result 2"
    assert len(calls) == 2
    assert live_search.live_search_cache_stats()["expirations"] >= 1
    live_search.clear_live_search_cache()


def test_failed_serpapi_fallback_is_not_cached_as_fresh(monkeypatch):
    live_search.clear_live_search_cache()
    monkeypatch.setenv("SERPAPI_API_KEY", "")
    monkeypatch.setattr(live_search, "get_settings", lambda: settings())
    serp_calls = []
    fallback_calls = []

    def failed_search(query, max_results):
        serp_calls.append(query)
        return False, []

    monkeypatch.setattr(live_search, "_search_serpapi", failed_search)
    monkeypatch.setattr(live_search, "_search_ddg", lambda query, limit: fallback_calls.append(query) or [])

    assert live_search.search_live_deals("headphones latest price", force=True) == []
    assert live_search.search_live_deals("headphones latest price", force=True) == []
    assert len(serp_calls) == 2
    assert len(fallback_calls) == 2
    assert live_search.live_search_cache_stats()["entries"] == 0
    live_search.clear_live_search_cache()


def test_cache_entry_count_is_bounded(monkeypatch):
    live_search.clear_live_search_cache()
    monkeypatch.setenv("SERPAPI_API_KEY", "")
    monkeypatch.setattr(live_search, "get_settings", lambda: settings(max_entries=16))
    monkeypatch.setattr(
        live_search,
        "_search_serpapi",
        lambda query, max_results: (True, [{"title": query, "retrieved_at": "2026-10-22T00:00:00Z"}]),
    )

    for index in range(17):
        live_search.search_live_deals(f"headphones model {index} latest price", force=True)

    stats = live_search.live_search_cache_stats()
    assert stats["entries"] == 16
    assert stats["max_entries"] == 16
    assert stats["evictions"] >= 1
    assert stats["scope"] == "process-local"
    live_search.clear_live_search_cache()
