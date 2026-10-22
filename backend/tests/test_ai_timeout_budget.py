from types import SimpleNamespace

from app.services import ai


def _settings(**overrides):
    values = {
        "openai_api_key": "",
        "openai_model": "test-model",
        "gemini_api_key": "",
        "gemini_model": "test-model",
        "groq_api_key": "",
        "groq_model": "test-model",
        "ollama_api_key": "",
        "ollama_model": "test-model",
        "hf_token": "",
        "huggingface_api_key": "",
        "ai_provider_timeout_seconds": 5,
        "ai_provider_chain_timeout_seconds": 10,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


class _FakeClient:
    def __init__(self, create):
        self.create = create
        self.options = []
        self.chat = SimpleNamespace(
            completions=SimpleNamespace(create=self._create)
        )

    def with_options(self, **kwargs):
        self.options.append(kwargs)
        return self

    def _create(self, **kwargs):
        return self.create(**kwargs)


def test_openai_call_uses_explicit_timeout_and_disables_sdk_retries(monkeypatch, db_session):
    monkeypatch.setattr(ai, "get_settings", lambda: _settings())
    orchestrator = ai.AIOrchestrator(db_session)
    orchestrator.provider = "openai"
    orchestrator.model = "test-model"

    def complete(**_kwargs):
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content="Bounded answer"))]
        )

    fake = _FakeClient(complete)
    orchestrator.client = fake

    answer = orchestrator._chat("system", "find headphones")

    assert answer == "Bounded answer"
    assert fake.options
    assert fake.options[0]["timeout"] == 5
    assert fake.options[0]["max_retries"] == 0


def test_model_fallback_stops_after_total_provider_budget(monkeypatch, db_session):
    clock = {"now": 0.0}
    monkeypatch.setattr(ai, "get_settings", lambda: _settings())
    monkeypatch.setattr(ai.time, "monotonic", lambda: clock["now"])

    orchestrator = ai.AIOrchestrator(db_session)
    orchestrator.provider = "openai"
    orchestrator.model = "first-model"
    attempts = []

    def fail_slowly(**kwargs):
        attempts.append(kwargs["model"])
        clock["now"] = 11.0
        raise TimeoutError("simulated provider timeout")

    orchestrator.client = _FakeClient(fail_slowly)

    assert orchestrator._chat("system", "find headphones") is None
    assert attempts == ["first-model"]
