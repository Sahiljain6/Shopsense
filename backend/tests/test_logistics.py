import pytest
from app.services.logistics import lookup_pincode
from app.services.ai import AIOrchestrator


def test_lookup_pincode_valid_metro() -> None:
    res = lookup_pincode("400071")
    assert res["valid"] is True
    assert res["pincode"] == "400071"
    assert res["is_metro"] is True
    assert "Business Days" in res["estimated_days"]
    assert "Maharashtra" in res["state"] or "Mumbai" in res["district"]


def test_lookup_pincode_delhi() -> None:
    res = lookup_pincode("110001")
    assert res["valid"] is True
    assert res["is_metro"] is True
    assert "Delhi" in res["district"] or "Delhi" in res["state"]


def test_lookup_pincode_invalid() -> None:
    res = lookup_pincode("012345")
    assert res["valid"] is False
    assert "Invalid PIN" in res["error"]

    res_short = lookup_pincode("4000")
    assert res_short["valid"] is False


def test_ai_orchestrator_pincode_precheck(db_session) -> None:
    orch = AIOrchestrator(db_session)
    chat_res = orch.answer("Can you do delivery to 400071?")
    assert chat_res is not None
    assert "Delivery & Shipping Status (PIN: 400071)" in chat_res.answer
    assert "Metro Express Zone" in chat_res.answer


def test_ai_orchestrator_pincode_tool_execution(db_session) -> None:
    orch = AIOrchestrator(db_session)
    raw = orch._execute_tool("check_delivery_pincode", {"pincode": "560001"})
    import json
    parsed = json.loads(raw)
    assert parsed["valid"] is True
    assert parsed["pincode"] == "560001"
    assert parsed["is_metro"] is True
