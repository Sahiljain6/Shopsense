import threading
import time

from app.services import ai


def test_cold_model_discovery_does_not_block_chat_request(monkeypatch):
    """A cold provider model-list lookup must not sit on the request critical path."""
    api_key = "latency-test-groq-key"
    fallback = list(ai._GROQ_DEFAULT_MODELS)
    refresh_started = threading.Event()
    release_refresh = threading.Event()
    refresh_finished = threading.Event()

    def slow_discovery(key):
        assert key == api_key
        refresh_started.set()
        try:
            # Hold the refresh open until the test confirms the caller has returned.
            release_refresh.wait(timeout=2)
            with ai._MODEL_CACHE_LOCK:
                ai._GROQ_MODELS_CACHE[key] = (time.time(), ["cached-model-from-refresh"])
            return ["cached-model-from-refresh"]
        finally:
            refresh_finished.set()

    with ai._MODEL_CACHE_LOCK:
        ai._GROQ_MODELS_CACHE.pop(api_key, None)
        ai._MODEL_REFRESH_PENDING.discard(("groq", api_key))

    monkeypatch.setattr(ai, "get_active_groq_models", slow_discovery)
    try:
        models = ai.get_active_models_nonblocking("groq", api_key)
        assert models == fallback
        assert refresh_started.wait(timeout=1), "background refresh did not start"
        assert not refresh_finished.is_set(), "model discovery blocked the caller"
    finally:
        release_refresh.set()

    assert refresh_finished.wait(timeout=1), "background refresh did not finish after release"
    with ai._MODEL_CACHE_LOCK:
        ai._GROQ_MODELS_CACHE.pop(api_key, None)
        ai._MODEL_REFRESH_PENDING.discard(("groq", api_key))


def test_fresh_model_cache_is_returned_without_discovery(monkeypatch):
    api_key = "latency-test-cached-groq-key"
    cached_models = ["known-good-model"]
    with ai._MODEL_CACHE_LOCK:
        ai._GROQ_MODELS_CACHE[api_key] = (time.time(), cached_models)
        ai._MODEL_REFRESH_PENDING.discard(("groq", api_key))

    def unexpected_refresh(_key):
        raise AssertionError("fresh cache should prevent model-list discovery")

    monkeypatch.setattr(ai, "get_active_groq_models", unexpected_refresh)
    try:
        assert ai.get_active_models_nonblocking("groq", api_key) == cached_models
    finally:
        with ai._MODEL_CACHE_LOCK:
            ai._GROQ_MODELS_CACHE.pop(api_key, None)
            ai._MODEL_REFRESH_PENDING.discard(("groq", api_key))
