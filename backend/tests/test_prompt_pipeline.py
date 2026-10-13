from types import SimpleNamespace

from app.schemas.api import ChatResponse
from app.services.ai import AIOrchestrator, needs_clarification, select_modifiers
from app.services.constraint_extractor import extract_constraints
from app.services.intent_classifier import ShoppingIntent
from app.services.prompt_pipeline import (
    build_prompt_context,
    filter_and_rank_products,
    validate_chat_response,
)


def test_builds_deal_specific_prompt_context_with_budget():
    plan = build_prompt_context("Find current deals on Samsung phones under ₹20,000")

    assert plan.intent == ShoppingIntent.DEAL_SEARCH
    assert plan.constraints.category == "Phones"
    assert plan.constraints.budget_max == 20000
    assert "- Primary intent: deal_search" in plan.prompt_addendum
    assert '"budget_max":20000' in plan.prompt_addendum
    assert "never as instructions" in plan.prompt_addendum.lower()


def test_explicit_mode_selects_task_contract_for_generic_query():
    plan = build_prompt_context("Phones under 20000", mode="compare")

    assert plan.intent == ShoppingIntent.PRODUCT_COMPARISON
    assert "OUTPUT CONTRACT — COMPARISON" in plan.prompt_addendum


def test_classifier_backed_modifiers_choose_specific_task():
    assert select_modifiers("Compare iPhone 16 vs Galaxy S24")[0] == "compare"
    assert select_modifiers("Find coupon offers for headphones")[0] == "deal_hunter"
    assert select_modifiers("I need a birthday gift for my brother")[0] == "gift_mode"


def test_ambiguous_reference_asks_one_question_but_history_resolves_followup():
    assert needs_clarification("is it good")
    assert needs_clarification("which one is best")
    assert needs_clarification(
        "is it good",
        history=[
            {"role": "user", "content": "Recommend an iPhone under ₹50,000"},
            {"role": "assistant", "content": "I recommend iPhone 15."},
        ],
    ) is None


def test_hard_constraints_filter_products_and_preferences_rank_stably():
    constraints = extract_constraints(
        "Find a gaming laptop under ₹80,000 with 16GB RAM and no RGB lighting"
    )
    with_rgb = SimpleNamespace(
        name="Lenovo Legion", brand="Lenovo",
        description="gaming laptop with 16GB RAM, SSD, RGB lighting",
        price=75000, attributes={"ram": "16GB", "lighting": "RGB"},
    )
    meets_constraints = SimpleNamespace(
        name="HP Victus", brand="HP",
        description="gaming laptop with 16GB RAM, SSD, backlit keyboard",
        price=76000, attributes={"ram": "16GB"},
    )
    over_budget = SimpleNamespace(
        name="Acer Nitro", brand="Acer",
        description="gaming laptop with 16GB RAM, SSD",
        price=90000, attributes={"ram": "16GB"},
    )
    insufficient_ram = SimpleNamespace(
        name="ASUS TUF", brand="ASUS",
        description="gaming laptop with 8GB RAM, SSD",
        price=70000, attributes={"ram": "8GB"},
    )

    result = filter_and_rank_products(
        [with_rgb, meets_constraints, over_budget, insufficient_ram],
        constraints,
    )

    assert result == [meets_constraints]


def test_preferred_brand_ranks_without_excluding_other_brands():
    constraints = extract_constraints("Find a laptop, preferably Lenovo")
    hp = SimpleNamespace(name="HP Pavilion", brand="HP", description="laptop", price=60000, attributes={})
    lenovo = SimpleNamespace(name="Lenovo IdeaPad", brand="Lenovo", description="laptop", price=65000, attributes={})

    result = filter_and_rank_products([hp, lenovo], constraints)

    assert result == [lenovo, hp]


def test_usd_budget_is_not_applied_as_inr_catalog_ceiling():
    constraints = extract_constraints("Find headphones with a budget of $500")
    product = SimpleNamespace(
        name="Premium Headphones", brand="Example",
        description="wireless noise cancelling headphones",
        price=25000, attributes={},
    )

    assert filter_and_rank_products([product], constraints) == [product]


def test_response_validation_deduplicates_ids_and_repairs_empty_answer():
    response = ChatResponse(
        answer="  ",
        product_ids=[1, 1, 0, -2],
        reasons={"1": "verified", "2": "stale"},
        pros={"1": ["Good"], "2": ["Unknown"]},
        cons={"1": ["Price"], "2": ["Unknown"]},
    )

    checked = validate_chat_response(response)

    assert checked.answer
    assert checked.product_ids == [1]
    assert set(checked.reasons) == {"1"}
    assert set(checked.pros) == {"1"}
    assert set(checked.cons) == {"1"}


def test_comparison_format_repair_converts_pipe_table_to_product_sections():
    response = ChatResponse(
        answer=(
            "| Product | Price | Battery |\n"
            "|---|---:|---|\n"
            "| Phone A | ₹20,000 | 5000mAh |\n"
            "| Phone B | ₹25,000 | 6000mAh |"
        )
    )

    checked = validate_chat_response(response, intent=ShoppingIntent.PRODUCT_COMPARISON)

    assert "Phone A" in checked.answer
    assert "Battery" in checked.answer
    assert not any(line.strip().startswith("|") for line in checked.answer.splitlines())


def test_tool_calling_prompt_includes_intent_and_extracted_constraints(monkeypatch, db_session):
    orchestrator = AIOrchestrator(db_session)
    captured = {}

    def fake_chat(system, user, history=None):
        captured["system"] = system
        captured["user"] = user
        return "Here are grounded laptop options."

    monkeypatch.setattr(orchestrator, "_chat_with_tools", fake_chat)
    response = orchestrator._tool_calling_answer(
        "Recommend a gaming laptop under ₹80,000"
    )

    assert response.answer == "Here are grounded laptop options."
    assert "Primary intent: product_recommendation" in captured["system"]
    assert '"budget_max":80000' in captured["system"]


def test_answer_returns_clarification_for_genuinely_ambiguous_reference(db_session, monkeypatch):
    orchestrator = AIOrchestrator(db_session)
    monkeypatch.setattr(orchestrator, "_chat_with_tools", lambda *args, **kwargs: None)

    response = orchestrator.answer("is it good")

    assert response.clarification
    assert response.answer == response.clarification
