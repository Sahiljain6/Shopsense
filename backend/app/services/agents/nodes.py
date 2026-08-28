import logging
from app.models.entities import Product
from app.schemas.api import ChatResponse
from app.services.ai import AIOrchestrator, needs_clarification
from app.services.search import resolve_products
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
    resolved = resolve_products(
        message=state["message"],
        cart=state.get("cart"),
        db=state["db"],
        limit=12
    )
    state["product_ids"] = [p.id for p in resolved.products]
    return state


def recommend_node(state: ShopSenseState) -> ShopSenseState:
    state["response"] = AIOrchestrator(state["db"]).answer(state["message"], state.get("mode"), cart=state.get("cart"))
    return state


def compare_node(state: ShopSenseState) -> ShopSenseState:
    state["response"] = AIOrchestrator(state["db"]).answer(state["message"], "compare", cart=state.get("cart"))
    return state


def review_node(state: ShopSenseState) -> ShopSenseState:
    state["response"] = AIOrchestrator(state["db"]).answer(state["message"], "review_digest", cart=state.get("cart"))
    return state


def guardrail_node(state: ShopSenseState) -> ShopSenseState:
    response = state.get("response") or ChatResponse(answer="I can help you find products, compare options, find gifts, or choose something within your budget. What are you looking for?")
    search_product_ids = set(state.get("product_ids", []))
    recommend_product_ids = response.product_ids

    if recommend_product_ids:
        if search_product_ids:
            filtered = [pid for pid in recommend_product_ids if pid in search_product_ids]
            if filtered:
                response.product_ids = filtered
            else:
                logging.warning(
                    f"guardrail_node intersection was empty for message '{state.get('message')}'. "
                    f"search_node IDs: {search_product_ids}, recommend IDs: {recommend_product_ids}. "
                    "Using recommend_node IDs as fallback."
                )
                response.product_ids = recommend_product_ids
        else:
            response.product_ids = recommend_product_ids

    state["response"] = response
    return state
