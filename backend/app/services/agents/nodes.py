from app.schemas.api import ChatResponse
from app.services.ai import AIOrchestrator, needs_clarification
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
    products = AIOrchestrator(state["db"]).catalog.search(state["message"], 8)
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
    if allowed:
        response.product_ids = [pid for pid in response.product_ids if pid in allowed]
    state["response"] = response
    return state
