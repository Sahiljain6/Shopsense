"""Regression tests for high-headroom Gemini text model selection and failover."""
from __future__ import annotations

import httpx

from app.services import ai


def test_high_headroom_text_models_are_prioritized() -> None:
    assert ai.ACTIVE_GEMINI_MODELS == [
        "gemini-3.5-flash-lite",
        "gemini-3.1-flash-lite",
        "gemini-3.8-flash",
        "gemini-3.6-flash",
        "gemini-3.1-pro-preview",
    ]
    assert not any(model.startswith("gemini-2.5-") for model in ai.ACTIVE_GEMINI_MODELS)
    assert not any(model.startswith("gemini-2.0-") for model in ai.ACTIVE_GEMINI_MODELS)


def test_discovery_only_prioritizes_models_listed_for_this_api_key(monkeypatch) -> None:
    api_key = "shopsense-gemini-priority-test-key"
    monkeypatch.delitem(ai._GEMINI_MODELS_CACHE, api_key, raising=False)

    class FakeResponse:
        status_code = 200

        def json(self):
            return {
                "models": [
                    {
                        "name": "models/gemini-3.8-live",
                        "supportedGenerationMethods": ["generateContent"],
                    },
                    {
                        "name": "models/gemini-3.8-flash",
                        "supportedGenerationMethods": ["generateContent"],
                    },
                    {
                        "name": "models/gemini-3.5-transcribe",
                        "supportedGenerationMethods": ["generateContent"],
                    },
                    {
                        "name": "models/gemini-2.5-flash-image",
                        "supportedGenerationMethods": ["generateContent"],
                    },
                    {
                        "name": "models/gemini-2.0-flash-lite",
                        "supportedGenerationMethods": ["generateContent"],
                    },
                ]
            }

    class FakeClient:
        def __init__(self, timeout=None):
            self.timeout = timeout

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def get(self, _url):
            return FakeResponse()

    monkeypatch.setattr(httpx, "Client", FakeClient)
    models = ai.get_active_gemini_models(api_key)

    # Gemini 3.8 Flash is the only compatible text-output model in this fake
    # project's ListModels response. Do not inject other defaults that were not
    # confirmed for this API key; those were the source of production 404s.
    assert models == ["gemini-3.8-flash"]
    assert "gemini-3.8-flash" in models
    assert not any("live" in model.lower() for model in models)
    assert not any("transcribe" in model.lower() for model in models)
    assert not any("image" in model.lower() for model in models)
    assert not any(model.startswith("gemini-2.0-") for model in models)


def test_gemini_429_fails_over_to_next_text_model(monkeypatch, db_session) -> None:
    calls = []

    class FakeResponse:
        def __init__(self, status_code, text):
            self.status_code = status_code
            self.text = text

        def json(self):
            if self.status_code == 200:
                return {
                    "candidates": [
                        {"content": {"parts": [{"text": "Answer from fallback model."}]}}
                    ]
                }
            return {"error": {"message": "rate limit exceeded"}}

    class FakeClient:
        def __init__(self, timeout=None):
            self.timeout = timeout

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def post(self, url, json=None):
            calls.append(url)
            if len(calls) == 1:
                return FakeResponse(429, "quota exceeded")
            return FakeResponse(200, "ok")

    monkeypatch.setattr(httpx, "Client", FakeClient)
    orchestrator = ai.AIOrchestrator(db_session)
    orchestrator.provider = "gemini"
    orchestrator.gemini_api_key = "test-only-key"
    monkeypatch.setattr(ai, "_GEMINI_MODEL_COOLDOWNS", {})
    orchestrator.active_gemini_models = [
        "gemini-3.5-flash-lite",
        "gemini-3.1-flash-lite",
    ]
    orchestrator.hf_token = None

    result = orchestrator._chat_with_tools("system prompt", "find earbuds")

    assert result == "Answer from fallback model."
    assert len(calls) == 2
    assert "/models/gemini-3.5-flash-lite:" in calls[0]
    assert "/models/gemini-3.1-flash-lite:" in calls[1]



def test_gemini_404_model_is_cooled_down_across_requests(monkeypatch, db_session) -> None:
    calls = []

    class FakeResponse:
        def __init__(self, status_code, text):
            self.status_code = status_code
            self.text = text
            self.headers = {}

        def json(self):
            if self.status_code == 200:
                return {
                    "candidates": [
                        {"content": {"parts": [{"text": "Answer from available model."}]}}
                    ]
                }
            return {"error": {"message": "model not found"}}

    class FakeClient:
        def __init__(self, timeout=None):
            self.timeout = timeout

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def post(self, url, json=None):
            calls.append(url)
            if "missing-model" in url:
                return FakeResponse(404, "model not found")
            return FakeResponse(200, "ok")

    monkeypatch.setattr(httpx, "Client", FakeClient)
    monkeypatch.setattr(ai, "_GEMINI_MODEL_COOLDOWNS", {})
    orchestrator = ai.AIOrchestrator(db_session)
    orchestrator.provider = "gemini"
    orchestrator.gemini_api_key = "test-only-key"
    orchestrator.active_gemini_models = [
        "missing-model",
        "gemini-3.5-flash-lite",
    ]
    orchestrator.hf_token = None

    assert orchestrator._chat_with_tools("system prompt", "find earbuds") == "Answer from available model."
    assert orchestrator._chat_with_tools("system prompt", "find headphones") == "Answer from available model."
    assert len(calls) == 3
    assert "missing-model" in calls[0]
    assert "gemini-3.5-flash-lite" in calls[1]
    assert "gemini-3.5-flash-lite" in calls[2]


def test_gemini_discovery_failure_never_adds_live_models(monkeypatch) -> None:
    api_key = "shopsense-gemini-excluded-model-test-key"
    monkeypatch.delitem(ai._GEMINI_MODELS_CACHE, api_key, raising=False)

    class FakeResponse:
        status_code = 200

        def json(self):
            return {
                "models": [
                    {"name": "models/gemini-3.1-flash-live", "supportedGenerationMethods": ["generateContent"]},
                    {"name": "models/gemini-3.5-flash-lite", "supportedGenerationMethods": ["generateContent"]},
                ]
            }

    class FakeClient:
        def __init__(self, timeout=None):
            self.timeout = timeout
        def __enter__(self):
            return self
        def __exit__(self, *_args):
            return False
        def get(self, _url):
            return FakeResponse()

    monkeypatch.setattr(httpx, "Client", FakeClient)
    assert ai.get_active_gemini_models(api_key) == ["gemini-3.5-flash-lite"]
