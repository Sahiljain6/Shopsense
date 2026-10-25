from app.core.resilience import get_provider_breaker
from app.services.ai import AIOrchestrator


def test_ai_provider_breaker_fails_fast_after_repeated_transient_request_failures(monkeypatch, db_session):
    breaker = get_provider_breaker("openai")
    breaker.reset()

    orchestrator = AIOrchestrator(db_session)
    orchestrator.provider = "openai"
    calls = []

    def transient_failure(*_args, **_kwargs):
        calls.append(1)
        orchestrator._transient_failure_seen = True
        return None

    monkeypatch.setattr(orchestrator, "_chat_with_budget", transient_failure)

    for _ in range(5):
        assert orchestrator._chat("system", "find headphones") is None

    assert breaker.snapshot()["state"] == "open"
    assert len(calls) == 5

    assert orchestrator._chat("system", "find headphones") is None
    assert len(calls) == 5

    breaker.reset()
