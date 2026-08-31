import json
import pytest
from app.services.weather_context import get_weather_shopping_advice
from app.services.ai import AIOrchestrator


def test_get_weather_shopping_advice_mumbai() -> None:
    res = get_weather_shopping_advice("Mumbai")
    assert res["location"] == "Mumbai"
    assert isinstance(res["temperature_celsius"], (int, float))
    assert isinstance(res["humidity_percent"], int)
    assert len(res["recommended_products"]) > 0
    assert "Mumbai" in res["summary"]


def test_get_weather_shopping_advice_delhi() -> None:
    res = get_weather_shopping_advice("Delhi")
    assert res["location"] == "Delhi"
    assert len(res["recommended_products"]) > 0


def test_ai_orchestrator_weather_precheck(db_session) -> None:
    orch = AIOrchestrator(db_session)
    chat_res = orch.answer("what is the weather in Delhi and what should I buy?")
    assert chat_res is not None
    assert "Weather & Shopping Advice for Delhi" in chat_res.answer
    assert "Climate-Smart Recommendations" in chat_res.answer


def test_ai_orchestrator_weather_tool_execution(db_session) -> None:
    orch = AIOrchestrator(db_session)
    raw = orch._execute_tool("get_weather_shopping_context", {"location": "Bengaluru"})
    parsed = json.loads(raw)
    assert parsed["location"] == "Bengaluru"
    assert len(parsed["recommended_products"]) > 0
