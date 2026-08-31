import json
import pytest
from app.services.deal_timing import analyze_deal_timing
from app.services.ai import AIOrchestrator


def test_analyze_deal_timing_phones() -> None:
    res = analyze_deal_timing("OnePlus 12", 54999, "phones")
    assert res["product"] == "OnePlus 12"
    assert res["current_price"] == 54999
    assert res["estimated_all_time_low"] < 54999
    assert "Sale" in res["next_sale_event"] or "Mega" in res["next_sale_event"]
    assert res["approx_days_to_sale"] >= 0
    assert "WAIT" in res["verdict"] or "BUY NOW" in res["verdict"]


def test_analyze_deal_timing_without_price() -> None:
    res = analyze_deal_timing("iPad Air", None, "general")
    assert res["product"] == "iPad Air"
    assert res["current_price"] is None
    assert res["estimated_all_time_low"] is None
    assert len(res["next_sale_event"]) > 0


def test_ai_orchestrator_deal_timing_precheck(db_session) -> None:
    orch = AIOrchestrator(db_session)
    chat_res = orch.answer("Should I buy this phone now or wait for sale?")
    assert chat_res is not None
    assert "Deal Timing & Sales Cycle Advice (Phone)" in chat_res.answer
    assert "Next Major Festival Sale" in chat_res.answer


def test_ai_orchestrator_deal_timing_tool_execution(db_session) -> None:
    orch = AIOrchestrator(db_session)
    raw = orch._execute_tool("check_deal_timing", {
        "product_name": "Sony WH-1000XM5",
        "current_price": 26990,
        "category": "audio"
    })
    parsed = json.loads(raw)
    assert parsed["product"] == "Sony WH-1000XM5"
    assert parsed["potential_savings_range"] == "15%–30%"
    assert parsed["estimated_all_time_low"] < 26990
