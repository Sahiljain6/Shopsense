import logging
from app.models.entities import Product
from app.schemas.api import ChatResponse
from app.services.ai import AIOrchestrator, is_direct_prompt_injection, needs_clarification
from app.services.search import resolve_products
from app.services.agents.state import ShopSenseState


def _check_injection(state: ShopSenseState) -> bool:
    """Comprehensive prompt injection detector across all user input (message, cart, history)."""
    all_inputs = [state.get("message", "")]
    for turn in state.get("history") or []:
        if isinstance(turn, dict) and turn.get("content"):
            all_inputs.append(str(turn["content"]))
    for item in state.get("cart") or []:
        if isinstance(item, dict):
            all_inputs.append(f"{item.get('name', '')} {item.get('brand', '')}")

    return any(is_direct_prompt_injection(text) for text in all_inputs)


def orchestrator_node(state: ShopSenseState) -> ShopSenseState:
    if _check_injection(state):
        state["intent"] = "refuse"
        state["response"] = ChatResponse(
            answer="I am ShopSense, an AI shopping copilot! 🛍️ I can only assist with shopping, products, pricing, and buying advice."
        )
        return state

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
    if state.get("intent") == "refuse":
        return state
    resolved = resolve_products(
        message=state["message"],
        cart=state.get("cart"),
        db=state["db"],
        limit=12
    )
    state["product_ids"] = [p.id for p in resolved.products]
    return state


def recommend_node(state: ShopSenseState) -> ShopSenseState:
    if state.get("intent") == "refuse":
        return state
    state["response"] = AIOrchestrator(state["db"]).answer(state["message"], state.get("mode"), cart=state.get("cart"))
    return state


def compare_node(state: ShopSenseState) -> ShopSenseState:
    if state.get("intent") == "refuse":
        return state
    state["response"] = AIOrchestrator(state["db"]).answer(state["message"], "compare", cart=state.get("cart"))
    return state


def review_node(state: ShopSenseState) -> ShopSenseState:
    if state.get("intent") == "refuse":
        return state
    state["response"] = AIOrchestrator(state["db"]).answer(state["message"], "review_digest", cart=state.get("cart"))
    return state


def guardrail_node(state: ShopSenseState) -> ShopSenseState:
    if state.get("intent") == "refuse":
        return state
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
