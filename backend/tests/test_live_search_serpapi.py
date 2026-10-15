from types import SimpleNamespace

from app.services import live_search


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self.payload


def test_serpapi_results_include_price_image_and_timestamp(monkeypatch):
    live_search._DEAL_CACHE.clear()
    monkeypatch.setattr(
        live_search,
        "get_settings",
        lambda: SimpleNamespace(
            serpapi_api_key="test-serpapi-secret",
            serpapi_location="Mumbai, Maharashtra, India",
        ),
    )
    calls = []

    def fake_get(url, params, timeout):
        calls.append({"url": url, "params": params, "timeout": timeout})
        return FakeResponse({
            "shopping_results": [{
                "title": "Sony Wireless Headphones",
                "link": "https://www.amazon.in/dp/B012345678",
                "source": "Amazon.in",
                "price": "₹8,999",
                "extracted_price": 8999,
                "old_price": "₹9,999",
                "extracted_old_price": 9999,
                "thumbnail": "https://serpapi.com/images/sony-headphones.jpg",
                "rating": 4.5,
                "reviews": 1204,
                "snippet": "Wireless noise cancelling headphones",
            }]
        })

    monkeypatch.setattr(live_search.httpx, "get", fake_get)

    first = live_search.search_live_deals("Sony headphones latest price", force=True)
    second = live_search.search_live_deals("Sony headphones latest price", force=True)

    assert len(first) == 1
    item = first[0]
    assert item["title"] == "Sony Wireless Headphones"
    assert item["price"] == 8999
    assert item["old_price"] == 9999
    assert item["discount_percentage"] == 10.0
    assert item["image_url"] == "https://serpapi.com/images/sony-headphones.jpg"
    assert item["url"] == "https://www.amazon.in/dp/B012345678"
    assert item["source"] == "Amazon.in"
    assert item["rating"] == 4.5
    assert item["reviews"] == 1204
    assert item["provider"] == "SerpApi Google Shopping"
    assert item["retrieved_at"].endswith("Z")
    assert len(second) == 1
    assert len(calls) == 1, "a cache hit should not spend another SerpApi request"
    assert calls[0]["params"]["api_key"] == "test-serpapi-secret"
    live_search._DEAL_CACHE.clear()


def test_serpapi_normalizer_rejects_local_product_links():
    result = live_search._normalise_serpapi_result(
        {
            "title": "Local-only result",
            "link": "http://127.0.0.1/admin",
            "price": "₹500",
            "extracted_price": 500,
        },
        "2026-10-15T00:00:00Z",
    )

    assert result is None


def test_missing_serpapi_key_returns_empty_when_no_fallback_available(monkeypatch):
    live_search._DEAL_CACHE.clear()
    monkeypatch.setattr(
        live_search,
        "get_settings",
        lambda: SimpleNamespace(serpapi_api_key="", serpapi_location="Mumbai, Maharashtra, India"),
    )
    monkeypatch.setattr(live_search, "HAS_DDG", False)

    results = live_search.search_live_deals("rare headphones latest price", force=True)

    assert results == []
    live_search._DEAL_CACHE.clear()
