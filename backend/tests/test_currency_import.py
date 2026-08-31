import json
import pytest
from app.services.currency import convert_price, calculate_import_comparison
from app.services.ai import AIOrchestrator


def test_convert_price_usd_to_inr() -> None:
    res = convert_price(100, "USD", "INR")
    assert res > 8000
    assert isinstance(res, float)


def test_convert_price_aed_to_inr() -> None:
    res = convert_price(1000, "AED", "INR")
    assert res > 20000  # 1000 AED is ~23,000 INR


def test_calculate_import_comparison_iphone() -> None:
    comp = calculate_import_comparison("iPhone 16 Pro", 3799, "AED", india_mrp=119900)
    assert comp["product"] == "iPhone 16 Pro"
    assert "3,799" in comp["foreign_price"]
    assert comp["converted_base_inr"] > 0
    assert comp["courier_shipped_landed_inr"] > comp["converted_base_inr"]
    assert "Apple provides Global" in comp["warranty_advice"]


def test_calculate_import_comparison_sony() -> None:
    comp = calculate_import_comparison("Sony WH-1000XM5", 299, "USD")
    assert comp["product"] == "Sony WH-1000XM5"
    assert "Limited international warranty" in comp["warranty_advice"]


def test_ai_orchestrator_import_precheck(db_session) -> None:
    orch = AIOrchestrator(db_session)
    chat_res = orch.answer("is iphone cheaper in dubai for aed 3799?")
    assert chat_res is not None
    assert "Global Tech Import Analysis: Iphone" in chat_res.answer or "Global Tech Import Analysis: iPhone" in chat_res.answer or "Global Tech Import Analysis" in chat_res.answer
    assert "Foreign Retail Price" in chat_res.answer


def test_ai_orchestrator_import_tool_execution(db_session) -> None:
    orch = AIOrchestrator(db_session)
    raw = orch._execute_tool("compare_import_cost", {
        "product_name": "MacBook Air M3",
        "foreign_amount": 999,
        "foreign_currency": "USD"
    })
    parsed = json.loads(raw)
    assert parsed["product"] == "MacBook Air M3"
    assert parsed["converted_base_inr"] > 70000
