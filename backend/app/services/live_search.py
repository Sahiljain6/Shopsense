"""Live shopping search for ShopSense.

SerpApi's Google Shopping engine is preferred when SERPAPI_API_KEY is configured.
DuckDuckGo remains a no-key fallback. Prices are search snapshots, not checkout guarantees.
"""
import hashlib
import ipaddress
import json
import logging
import os
import re
import threading
import time
import warnings
from datetime import datetime, timezone
from urllib.parse import urlparse

import httpx

from app.core.config import get_settings
from app.core.http_client import get_http_client
from app.core.resilience import CircuitBreaker, is_transient_upstream_failure
from app.services.trust_engine import evaluate_store_trust, filter_and_rank_trustworthy_deals

logger = logging.getLogger("shopsense.live_search")

try:
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", category=RuntimeWarning)
        try:
            from ddgs import DDGS
        except ImportError:
            from duckduckgo_search import DDGS
    HAS_DDG = True
except ImportError:
    DDGS = None
    HAS_DDG = False

SERPAPI_ENDPOINT = "https://serpapi.com/search.json"
CACHE_TTL_SECONDS = 15 * 60
CACHE_MAX_ENTRIES = 256
CACHE_SCHEMA_VERSION = 2
_CACHE_LOCK = threading.RLock()
_DEAL_CACHE: dict[str, tuple[float, list[dict[str, object]]]] = {}
_CACHE_METRICS: dict[str, int] = {"hits": 0, "misses": 0, "expirations": 0, "evictions": 0}

_SERPAPI_BREAKER = CircuitBreaker(failure_threshold=5, reset_timeout_seconds=30.0)


def _cache_ttl_seconds(settings: object | None = None) -> int:
    configured = getattr(settings or get_settings(), "live_search_cache_ttl_seconds", CACHE_TTL_SECONDS)
    try:
        return max(1, min(int(configured), 86400))
    except (TypeError, ValueError):
        return CACHE_TTL_SECONDS


def _cache_max_entries(settings: object | None = None) -> int:
    configured = getattr(settings or get_settings(), "live_search_cache_max_entries", CACHE_MAX_ENTRIES)
    try:
        return max(16, min(int(configured), 5000))
    except (TypeError, ValueError):
        return CACHE_MAX_ENTRIES


def clear_live_search_cache(*, reset_metrics: bool = True) -> None:
    """Clear only derived live-search snapshots; persistent catalog/account data is untouched."""
    with _CACHE_LOCK:
        _DEAL_CACHE.clear()
        if reset_metrics:
            for name in _CACHE_METRICS:
                _CACHE_METRICS[name] = 0


def serpapi_breaker_stats() -> dict[str, int | float | str]:
    """Expose only local breaker state, never provider credentials or query content."""
    return _SERPAPI_BREAKER.snapshot()


def live_search_cache_stats() -> dict[str, int | str]:
    """Expose non-sensitive local cache diagnostics; never expose query/cache keys."""
    with _CACHE_LOCK:
        return {
            "scope": "process-local",
            "entries": len(_DEAL_CACHE),
            "max_entries": _cache_max_entries(),
            "ttl_seconds": _cache_ttl_seconds(),
            **_CACHE_METRICS,
        }


def _evict_expired_locked(now: float, ttl_seconds: int) -> None:
    expired = [
        key for key, (stored_at, _items) in _DEAL_CACHE.items()
        if now - stored_at >= ttl_seconds
    ]
    for key in expired:
        _DEAL_CACHE.pop(key, None)
    _CACHE_METRICS["expirations"] += len(expired)


def _build_cache_key(
    *,
    provider: str,
    api_key: str,
    location: str,
    query: str,
    max_results: int,
) -> str:
    """Version and hash every result-affecting input without storing a raw API key."""
    provider_fingerprint = (
        hashlib.sha256(api_key.encode("utf-8")).hexdigest()[:16]
        if api_key
        else ("ddg-available" if HAS_DDG else "ddg-unavailable")
    )
    key_payload = {
        "schema": CACHE_SCHEMA_VERSION,
        "provider": provider,
        "provider_config": provider_fingerprint,
        "market": "in",
        "language": "en",
        "location": re.sub(r"\s+", " ", location.strip().lower()),
        "query": re.sub(r"\s+", " ", query.strip().lower()),
        "max_results": max_results,
    }
    canonical = json.dumps(key_payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

ALLOWED_STORES = [
    "amazon.in", "amazon.com", "flipkart.com", "croma.com",
    "reliancedigital.in", "tatacliq.com", "myntra.com", "jiomart.com",
    "vijaysales.com", "shopclues.com", "snapdeal.com", "meesho.com",
    "oneplus.in", "samsung.com",
]
BLOCKED_DOMAINS = [
    "youtube.com", "netflix.com", "diffchecker.com", "text-compare.com",
    "draftable.com", "wikipedia.org", "facebook.com", "twitter.com",
    "reddit.com", "instagram.com",
]
LIVE_SEARCH_TRIGGER_KEYWORDS = [
    "price", "prices", "deal", "deals", "discount", "discounts", "offer", "offers",
    "coupon", "coupons", "sale", "amazon", "flipkart", "croma", "buy online",
    "how much", "rate", "cost", "available", "availability", "latest price",
    "latest", "current price", "current prices", "today's", "todays", "in stock",
    "live deal", "live price", "right now",
]


def should_use_live_search(query: str) -> bool:
    """Return True only for shopping queries that benefit from current retailer data."""
    if not query or len(query.strip()) < 3:
        return False
    lowered = query.lower()
    conversational_skip = [
        "hi", "hello", "hey", "what is", "explain", "how do", "which type of",
        "difference between", "who are you", "what can you do", "help me choose",
        "why should", "pros and cons", "guide",
    ]
    if any(s in lowered for s in conversational_skip) and not any(
        k in lowered for k in ["price", "deal", "offer", "amazon", "flipkart", "latest", "current"]
    ):
        return False
    return any(keyword in lowered for keyword in LIVE_SEARCH_TRIGGER_KEYWORDS)


def _safe_external_url(value: object) -> str | None:
    """Allow public HTTP(S) links only; never fetch local URLs."""
    if not isinstance(value, str) or not value.strip():
        return None
    raw = value.strip()
    try:
        parsed = urlparse(raw)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            return None
        if parsed.username or parsed.password:
            return None
        hostname = parsed.hostname.lower().rstrip(".")
        if hostname in {"localhost", "localhost.localdomain"} or hostname.endswith(".local"):
            return None
        try:
            address = ipaddress.ip_address(hostname)
            if not address.is_global:
                return None
        except ValueError:
            pass
        return raw[:2048]
    except (ValueError, TypeError):
        return None


def _as_number(value: object) -> float | None:
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, (float, int)):
        return float(value) if value >= 0 else None
    match = re.search(r"(\d[\d,]*(?:\.\d+)?)", str(value))
    if not match:
        return None
    try:
        return float(match.group(1).replace(",", ""))
    except ValueError:
        return None


def _retrieved_at() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _normalise_serpapi_result(item: dict[str, object], retrieved_at: str) -> dict[str, object] | None:
    title = str(item.get("title") or "").strip()[:180]
    if not title:
        return None
    url = _safe_external_url(item.get("link")) or _safe_external_url(item.get("product_link"))
    if not url:
        return None

    price = _as_number(item.get("extracted_price"))
    if price is None:
        price = _as_number(item.get("price"))
    old_price = _as_number(item.get("extracted_old_price"))
    if old_price is None:
        old_price = _as_number(item.get("old_price"))
    source = str(item.get("source") or "Google Shopping").strip()[:100]
    image_url = _safe_external_url(item.get("thumbnail")) or _safe_external_url(item.get("serpapi_thumbnail"))
    rating = _as_number(item.get("rating"))
    reviews = _as_number(item.get("reviews"))
    store_trust = evaluate_store_trust(source or url)
    discount = round((old_price - price) / old_price * 100, 1) if old_price and price is not None and old_price > price else None

    return {
        "title": title,
        "price": price,
        "price_str": str(item.get("price") or (f"₹{price:,.2f}" if price is not None else "")),
        "old_price": old_price,
        "currency": "INR",
        "source": source,
        "store": source,
        "url": url,
        "image_url": image_url,
        "rating": rating,
        "reviews": int(reviews) if reviews is not None else None,
        "discount_percentage": discount,
        "snippet": str(item.get("snippet") or item.get("description") or "")[:300],
        "retrieved_at": retrieved_at,
        "provider": "SerpApi Google Shopping",
        "is_live": True,
        "trust_score": int(store_trust["trust_score"]),
        "badge": str(store_trust["badge"]),
        "is_verified": bool(store_trust["is_verified"]),
        "warning": store_trust.get("warning"),
    }


def _search_serpapi(query: str, max_results: int) -> tuple[bool, list[dict[str, object]]]:
    """Return request status and results; never log a request URL containing the key."""
    settings = get_settings()
    api_key = (getattr(settings, "serpapi_api_key", "") or os.getenv("SERPAPI_API_KEY") or "").strip().strip("'").strip('"')
    if not api_key:
        return False, []
    if not _SERPAPI_BREAKER.allow_request():
        logger.warning("SerpApi circuit is open; using fallback search.")
        return False, []

    location = (
        getattr(settings, "serpapi_location", "")
        or os.getenv("SERPAPI_LOCATION")
        or "Mumbai, Maharashtra, India"
    ).strip()
    params = {
        "engine": "google_shopping",
        "q": query,
        "api_key": api_key,
        "gl": "in",
        "hl": "en",
        "location": location,
        "output": "json",
        "no_cache": "false",
    }
    try:
        response = get_http_client(timeout=9.0).get(SERPAPI_ENDPOINT, params=params, timeout=9.0)
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, dict) or payload.get("error"):
            logger.warning("SerpApi Google Shopping returned an API error; using fallback search.")
            return False, []
        shopping_results = payload.get("shopping_results")
        if shopping_results is not None and not isinstance(shopping_results, list):
            logger.warning("SerpApi Google Shopping returned malformed results; using fallback search.")
            return False, []
        if isinstance(shopping_results, list) and shopping_results and not any(
            isinstance(item, dict) for item in shopping_results
        ):
            logger.warning("SerpApi Google Shopping returned malformed result entries; using fallback search.")
            return False, []
        fetched_at = _retrieved_at()
        normalized: list[dict[str, object]] = []
        seen: set[str] = set()
        for item in shopping_results or []:
            if not isinstance(item, dict):
                continue
            result = _normalise_serpapi_result(item, fetched_at)
            if not result:
                continue
            dedupe_key = str(result.get("url") or result.get("title")).lower()
            if dedupe_key in seen:
                continue
            seen.add(dedupe_key)
            normalized.append(result)
            if len(normalized) >= max(1, min(max_results, 20)):
                break
        if shopping_results and not normalized:
            logger.warning("SerpApi Google Shopping results contained no usable listings; using fallback search.")
            return False, []
        _SERPAPI_BREAKER.record_success()
        return True, normalized
    except (httpx.HTTPError, ValueError, TypeError) as error:
        if is_transient_upstream_failure(error):
            _SERPAPI_BREAKER.record_failure()
        logger.warning(
            "SerpApi Google Shopping request failed (error_type=%s); trying fallback search.",
            type(error).__name__,
        )
        return False, []


def _search_ddg(query: str, max_results: int) -> list[dict[str, object]]:
    """No-key fallback search. This source may not provide product images."""
    if not HAS_DDG or DDGS is None:
        return []
    search_term = f"{query} price buy online india amazon flipkart croma"
    raw_deals: list[dict[str, object]] = []
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", category=RuntimeWarning)
            with DDGS() as ddgs:
                raw_results = list(ddgs.text(search_term, max_results=max_results * 4))
        fetched_at = _retrieved_at()
        for item in raw_results:
            url = _safe_external_url(item.get("href") or item.get("link"))
            title = str(item.get("title") or "").strip()
            snippet = str(item.get("body") or item.get("snippet") or "")
            if not url or not title:
                continue
            lowered_url = url.lower()
            if any(domain in lowered_url for domain in BLOCKED_DOMAINS):
                continue
            if not any(domain in lowered_url for domain in ALLOWED_STORES):
                continue
            match = re.search(r"(?:₹|Rs\.?|INR)\s*([\d,]+(?:\.\d+)?)", f"{title} {snippet}", re.IGNORECASE)
            price = _as_number(match.group(1)) if match else None
            store = (
                "Amazon India" if "amazon.in" in lowered_url else
                "Flipkart" if "flipkart.com" in lowered_url else
                "Croma" if "croma.com" in lowered_url else
                "Reliance Digital" if "reliancedigital.in" in lowered_url else
                str(evaluate_store_trust(url)["store_name"])
            )
            trust = evaluate_store_trust(store)
            raw_deals.append({
                "title": title[:180],
                "price": price,
                "price_str": match.group(0) if match else "",
                "old_price": None,
                "currency": "INR",
                "source": store,
                "store": store,
                "url": url,
                "image_url": None,
                "rating": None,
                "reviews": None,
                "discount_percentage": None,
                "snippet": snippet[:300],
                "retrieved_at": fetched_at,
                "provider": "DuckDuckGo fallback",
                "is_live": True,
                "trust_score": int(trust["trust_score"]),
                "badge": str(trust["badge"]),
                "is_verified": bool(trust["is_verified"]),
                "warning": trust.get("warning"),
            })
    except Exception as error:
        logger.warning("Fallback product search failed (%s).", type(error).__name__)
    return filter_and_rank_trustworthy_deals(raw_deals, min_trust_score=30)[:max_results]


def search_live_deals(
    query: str,
    max_results: int = 5,
    force: bool = False,
) -> list[dict[str, object]]:
    """Search shopping results with a cache-first SerpApi path and a DuckDuckGo fallback.

    The local 15-minute cache protects the free API quota. The force flag bypasses
    the intent gate, not the cache. Retailer checkout prices can change.
    """
    clean_query = re.sub(
        r"^(search me|give me|find me|fetch link:?|show me|recommend|suggest)\s*",
        "",
        (query or "").strip(),
        flags=re.IGNORECASE,
    )
    clean_query = re.sub(r"[\r\n\t]+", " ", clean_query).strip()[:140]
    if len(clean_query) < 3:
        return []
    if clean_query.lower() in {"hi", "hello", "hey", "how are you", "who are you", "what can you do"}:
        return []
    if re.search(r"\b(code|coding|programming|debugging)\b", clean_query, re.IGNORECASE):
        return []
    if not force and not should_use_live_search(clean_query):
        return []

    settings = get_settings()
    api_key = (
        getattr(settings, "serpapi_api_key", "")
        or os.getenv("SERPAPI_API_KEY")
        or ""
    ).strip().strip("'").strip('"')
    location = (
        getattr(settings, "serpapi_location", "")
        or os.getenv("SERPAPI_LOCATION")
        or "Mumbai, Maharashtra, India"
    ).strip()
    result_limit = max(1, min(int(max_results), 20))
    provider_key = "serpapi" if api_key else "ddg"
    cache_key = _build_cache_key(
        provider=provider_key,
        api_key=api_key,
        location=location,
        query=clean_query,
        max_results=result_limit,
    )
    ttl_seconds = _cache_ttl_seconds(settings)
    max_entries = _cache_max_entries(settings)
    now = time.monotonic()

    with _CACHE_LOCK:
        _evict_expired_locked(now, ttl_seconds)
        cached = _DEAL_CACHE.get(cache_key)
        if cached is not None:
            _CACHE_METRICS["hits"] += 1
            # Return a copy so callers cannot mutate the cached snapshot.
            return [dict(item) for item in cached[1]]
        _CACHE_METRICS["misses"] += 1

    if api_key:
        succeeded, deals = _search_serpapi(clean_query, max_results=result_limit)
        if not succeeded:
            # A failure is not a fresh result. Do not cache fallback results as if SerpApi succeeded.
            deals = _search_ddg(clean_query, result_limit)
    else:
        succeeded = False
        deals = _search_ddg(clean_query, result_limit)

    # Cache successful SerpApi responses, including valid no-result searches. The no-key
    # fallback has no reliable success flag, so only non-empty DDG results are cached.
    should_cache = (api_key and succeeded) or (not api_key and bool(deals))
    if should_cache:
        with _CACHE_LOCK:
            stored_at = time.monotonic()
            _evict_expired_locked(stored_at, ttl_seconds)
            if cache_key not in _DEAL_CACHE and len(_DEAL_CACHE) >= max_entries:
                oldest_key = min(_DEAL_CACHE, key=lambda key: _DEAL_CACHE[key][0])
                _DEAL_CACHE.pop(oldest_key, None)
                _CACHE_METRICS["evictions"] += 1
            _DEAL_CACHE[cache_key] = (stored_at, [dict(item) for item in deals])
    return [dict(item) for item in deals[:result_limit]]
