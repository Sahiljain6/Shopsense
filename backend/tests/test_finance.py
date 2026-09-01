import json
import pytest
from app.services.finance import lookup_ifsc, calculate_emi_options
from app.services.ai import AIOrchestrator


def test_lookup_ifsc_valid() -> None:
    res = lookup_ifsc("HDFC0000001")
    assert res["valid"] is True
    assert "HDFC" in res["bank"]
    assert res["ifsc"] == "HDFC0000001"


def test_lookup_ifsc_sbi() -> None:
    res = lookup_ifsc("SBIN0000300")
    assert res["valid"] is True
    assert "State Bank" in res["bank"] or "SBI" in res["bank"] or "SBIN" in res["summary"]


def test_lookup_ifsc_invalid() -> None:
    res = lookup_ifsc("NOTANIFSC")
    assert res["valid"] is False
    assert "Invalid IFSC" in res["error"]


def test_calculate_emi_eligible() -> None:
    res = calculate_emi_options(30000)
    assert res["eligible"] is True
    assert len(res["no_cost_plans"]) == 2  # 3 and 6 months
    # 6 month no cost: 30000 / 6 = 5000
    assert res["no_cost_plans"][1]["monthly_amount"] == 5000
    assert len(res["standard_plans"]) > 0
    assert len(res["bank_offers"]) > 0


def test_calculate_emi_ineligible_low_amount() -> None:
    res = calculate_emi_options(1200)
    assert res["eligible"] is False
    assert "₹3,000" in res["message"]


def test_ai_orchestrator_emi_precheck(db_session) -> None:
    orch = AIOrchestrator(db_session)
    chat_res = orch.answer("what is the emi on 45000?")
    assert chat_res is not None
    assert "EMI & Financing Breakdown for ₹45,000" in chat_res.answer
    assert "No-Cost EMI" in chat_res.answer


def test_ai_orchestrator_emi_tool_execution(db_session) -> None:
    orch = AIOrchestrator(db_session)
    raw = orch._execute_tool("calculate_emi_and_offers", {"amount": 60000})
    parsed = json.loads(raw)
    assert parsed["eligible"] is True
    assert parsed["amount"] == 60000
    assert len(parsed["no_cost_plans"]) == 2


def test_amortization_schedule_valid() -> None:
    from app.services.finance import calculate_amortization_schedule
    schedule = calculate_amortization_schedule(12000, 12.0, 12)
    assert len(schedule) == 12
    assert schedule[0]["month"] == 1
    assert schedule[0]["principal"] > 0
    assert schedule[0]["interest"] > 0
    assert schedule[-1]["month"] == 12
    assert schedule[-1]["balance"] == 0.0


def test_amortization_schedule_zero_or_negative() -> None:
    from app.services.finance import calculate_amortization_schedule
    assert calculate_amortization_schedule(0, 12.0, 6) == []
    assert calculate_amortization_schedule(10000, 12.0, 0) == []
    assert calculate_amortization_schedule(-5000, 12.0, 6) == []


def test_amortization_schedule_zero_interest() -> None:
    from app.services.finance import calculate_amortization_schedule
    schedule = calculate_amortization_schedule(6000, 0.0, 6)
    assert len(schedule) == 6
    assert schedule[0]["emi"] == 1000.0
    assert schedule[0]["interest"] == 0.0
    assert schedule[-1]["balance"] == 0.0

