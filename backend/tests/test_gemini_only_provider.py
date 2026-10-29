from __future__ import annotations

from types import SimpleNamespace

from app.services import ai


def _settings(**overrides):
    values = {
        "ai_provider_timeout_seconds": 5,
        "ai_provider_chain_timeout_seconds": 20,
        "gemini_api_key": "gemini-test-key",
        "openai_api_key": "openai-should-not-be-used",
        "groq_api_key": "groq-should-not-be-used",
        "ollama_api_key": "ollama-should-not-be-used",
        "hf_token": "hf-should-not-be-used",
        "huggingface_api_key": "hf-should-not-be-used",
        "gemini_model": "gemini-3.5-flash-lite",
        "openai_model": "gpt-4o-mini",
        "groq_model": "llama-3.3-70b-versatile",
        "ollama_model": "llama3.1:8b",
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def test_gemini_is_only_selected_provider_even_when_other_keys_are_configured(monkeypatch, db_session):
    monkeypatch.setattr(ai, "get_settings", lambda: _settings())
    monkeypatch.setattr(
        ai,
        "get_active_models_nonblocking",
        lambda provider, key: ["gemini-3.5-flash-lite", "gemini-3.1-flash-lite"],
    )
    monkeypatch.setenv("HF_TOKEN", "environment-hf-token")
    monkeypatch.setenv("GROQ_API_KEY", "environment-groq-token")
    monkeypatch.setenv("OLLAMA_API_KEY", "environment-ollama-token")
    monkeypatch.setenv("OPENAI_API_KEY", "environment-openai-token")

    orchestrator = ai.AIOrchestrator(db_session)

    assert orchestrator.provider == "gemini"
    assert orchestrator.model == "gemini-3.5-flash-lite"
    assert orchestrator.active_gemini_models == [
        "gemini-3.5-flash-lite",
        "gemini-3.1-flash-lite",
    ]
    assert orchestrator.client is None
    assert orchestrator.hf_token is None


def test_no_gemini_key_does_not_silently_fall_back_to_groq_ollama_or_huggingface(monkeypatch, db_session):
    monkeypatch.setattr(
        ai,
        "get_settings",
        lambda: _settings(
            gemini_api_key="",
            openai_api_key="",
            groq_api_key="groq-key",
            ollama_api_key="ollama-key",
            hf_token="hf-key",
            huggingface_api_key="hf-key",
        ),
    )
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.setenv("GROQ_API_KEY", "environment-groq-token")
    monkeypatch.setenv("OLLAMA_API_KEY", "environment-ollama-token")
    monkeypatch.setenv("HF_TOKEN", "environment-hf-token")

    orchestrator = ai.AIOrchestrator(db_session)

    assert orchestrator.provider is None
    assert orchestrator.model is None
    assert orchestrator.client is None
    assert orchestrator.hf_token is None
