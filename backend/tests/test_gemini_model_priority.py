"""Regression tests for high-headroom Gemini text model selection and failover."""
from __future__ import annotations

import httpx

from app.services import ai


def test_high_headroom_text_models_are_prioritized() -> None:
    assert ai.ACTIVE_GEMINI_MODELS[:4] == [
        "gemini-2.5-flash-lite",
        "gemini-3.5-flash-lite",
        "gemini-3.1-flash-lite",
        "gemini-2.5-flash",
    ]
    assert not any(model.startswith("gemini-2.0-") for model in ai.ACTIVE_GEMINI_MODELS)


def test_discovery_keeps_preferred_text_models_and_excludes_live_api(monkeypatch) -> None:
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

    assert models[: len(ai.ACTIVE_GEMINI_MODELS)] == ai.ACTIVE_GEMINI_MODELS
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
    orchestrator.active_gemini_models = [
        "gemini-2.5-flash-lite",
        "gemini-3.5-flash-lite",
    ]
    orchestrator.hf_token = None

    result = orchestrator._chat_with_tools("system prompt", "find earbuds")

    assert result == "Answer from fallback model."
    assert len(calls) == 2
    assert "/models/gemini-2.5-flash-lite:" in calls[0]
    assert "/models/gemini-3.5-flash-lite:" in calls[1]
