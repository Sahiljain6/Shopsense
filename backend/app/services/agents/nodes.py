from app.models.entities import Product
from app.schemas.api import ChatResponse
from app.services.ai import AIOrchestrator, clean_search_terms, extract_budget, needs_clarification
from app.services.agents.state import ShopSenseState


def orchestrator_node(state: ShopSenseState) -> ShopSenseState:
    message = state["message"].lower()
    if needs_clarification(message):
        state["intent"] = "clarify"
    elif "compare" in message:
        state["intent"] = "compare"
    elif "review" in message:
        state["intent"] = "review"
    else:
        state["intent"] = "recommend"
    return state


def search_node(state: ShopSenseState) -> ShopSenseState:
    message = state["message"]
    cleaned_query = clean_search_terms(message)
    budget = extract_budget(message)

    orchestrator = AIOrchestrator(state["db"])
    products = orchestrator.catalog.search(cleaned_query, limit=12, max_price=budget)

    if budget is not None:
        products = [p for p in products if p.price <= budget]

    if budget is not None and not products:
        all_catalog = orchestrator.catalog.search("", limit=50, max_price=budget)
        budget_items = [p for p in all_catalog if p.price <= budget]

        lowered_msg = message.lower()
        if any(w in lowered_msg for w in ["phone", "mobile", "smartphone"]):
            phone_items = [p for p in budget_items if "phone" in p.name.lower() or (p.category and p.category.name.lower() == "phones")]
            if phone_items:
                budget_items = phone_items
        elif any(w in lowered_msg for w in ["earbud", "earphone", "audio", "tws"]):
            audio_items = [p for p in budget_items if p.category and p.category.name.lower() == "audio"]
            if audio_items:
                budget_items = audio_items

        products = budget_items

    state["product_ids"] = [p.id for p in products]
    return state


def recommend_node(state: ShopSenseState) -> ShopSenseState:
    state["response"] = AIOrchestrator(state["db"]).answer(state["message"], state.get("mode"))
    return state


def compare_node(state: ShopSenseState) -> ShopSenseState:
    state["response"] = AIOrchestrator(state["db"]).answer(state["message"], "compare")
    return state


def review_node(state: ShopSenseState) -> ShopSenseState:
    state["response"] = AIOrchestrator(state["db"]).answer(state["message"], "review_digest")
    return state


def guardrail_node(state: ShopSenseState) -> ShopSenseState:
    response = state.get("response") or ChatResponse(answer="I can help you find products, compare options, find gifts, or choose something within your budget. What are you looking for?")
    allowed = set(state.get("product_ids", []))
    if allowed and response.product_ids:
        filtered = [pid for pid in response.product_ids if pid in allowed]
        if filtered:
            response.product_ids = filtered
        else:
            budget = extract_budget(state["message"])
            if budget is not None:
                valid_ids = []
                for pid in response.product_ids:
                    p = state["db"].get(Product, pid)
                    if p and p.price <= budget:
                        valid_ids.append(pid)
                response.product_ids = valid_ids
    state["response"] = response
    return state
