import logging
from app.models.entities import Product
from app.schemas.api import ChatResponse
from app.services.ai import AIOrchestrator, check_shopping_guardrail, is_direct_prompt_injection, needs_clarification
from app.services.constraint_extractor import extract_constraints
from app.services.intent_classifier import ShoppingIntent, classify_intent
from app.services.prompt_pipeline import build_prompt_context, filter_and_rank_products
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

    message = state["message"]
    scope_refusal = check_shopping_guardrail(message)
    if scope_refusal:
        state["intent"] = "refuse"
        state["response"] = ChatResponse(answer=scope_refusal)
        return state

    lowered = message.lower()
    if state.get("image_bytes") or any(w in lowered for w in ["photo mismatch", "image mismatch", "picture mismatch", "mismatch in photo"]):
        state["intent"] = "photo_deal"
        state["shopping_intent"] = ShoppingIntent.PRODUCT_RECOMMENDATION.value
        return state

    result = classify_intent(message, state.get("history"))
    state["shopping_intent"] = result.intent.value
    clarification = needs_clarification(message, state.get("history"))
    if clarification:
        state["intent"] = "clarify"
        state["response"] = ChatResponse(answer=clarification, clarification=clarification)
    elif result.intent == ShoppingIntent.PRODUCT_COMPARISON:
        state["intent"] = "compare"
    elif result.intent == ShoppingIntent.PRODUCT_REVIEW_SUMMARY:
        state["intent"] = "review"
    else:
        # Specialist intents still go through AIOrchestrator.answer so existing
        # finance, delivery, deal timing, currency, and weather tools remain active.
        state["intent"] = "recommend"
    return state


def search_node(state: ShopSenseState) -> ShopSenseState:
    if state.get("intent") in {"refuse", "clarify"}:
        return state
    specialist_intents = {
        ShoppingIntent.DEAL_SEARCH.value,
        ShoppingIntent.FINANCE_OR_EMI.value,
        ShoppingIntent.DELIVERY_OR_LOGISTICS.value,
        ShoppingIntent.PRODUCT_INFORMATION.value,
    }
    if state.get("shopping_intent") in specialist_intents:
        state["products"] = []
        state["product_ids"] = []
        return state
    resolved = resolve_products(
        message=state["message"],
        history=state.get("history"),
        cart=state.get("cart"),
        db=state["db"],
        limit=12
    )
    plan = build_prompt_context(state["message"], state.get("history"), state.get("mode"))
    filtered = filter_and_rank_products(resolved.products, plan.constraints)
    resolved_products = filtered
    state["products"] = resolved_products
    state["product_ids"] = [p.id for p in resolved_products]
    return state


def recommend_node(state: ShopSenseState) -> ShopSenseState:
    if state.get("intent") in {"refuse", "clarify"}:
        return state
    orch = AIOrchestrator(state["db"])
    specialist_intents = {
        ShoppingIntent.DEAL_SEARCH.value,
        ShoppingIntent.FINANCE_OR_EMI.value,
        ShoppingIntent.DELIVERY_OR_LOGISTICS.value,
        ShoppingIntent.PRODUCT_INFORMATION.value,
        ShoppingIntent.OUT_OF_SCOPE.value,
    }
    if state.get("shopping_intent") in specialist_intents:
        state["response"] = orch.answer(
            state["message"], state.get("mode"),
            history=state.get("history"), cart=state.get("cart")
        )
    elif state.get("products"):
        state["response"] = orch._generate_ai_response(
            message=state["message"],
            products=state["products"][:4],
            history=state.get("history"),
            cart=state.get("cart")
        )
    else:
        state["response"] = orch.answer(
            state["message"], state.get("mode"),
            history=state.get("history"), cart=state.get("cart")
        )
    return state


def compare_node(state: ShopSenseState) -> ShopSenseState:
    if state.get("intent") == "refuse":
        return state
    state["response"] = AIOrchestrator(state["db"]).answer(
        state["message"], "compare", history=state.get("history"), cart=state.get("cart")
    )
    return state


def review_node(state: ShopSenseState) -> ShopSenseState:
    if state.get("intent") == "refuse":
        return state
    state["response"] = AIOrchestrator(state["db"]).answer(
        state["message"], "review_digest", history=state.get("history"), cart=state.get("cart")
    )
    return state



def clarify_node(state: ShopSenseState) -> ShopSenseState:
    """Preserve the one-question clarification selected by the orchestrator."""
    if state.get("intent") == "refuse":
        return state
    existing = state.get("response")
    if isinstance(existing, ChatResponse) and existing.clarification:
        return state
    question = needs_clarification(state.get("message", ""), state.get("history"))
    if not question:
        question = "Which product or shopping category are you referring to?"
    state["response"] = ChatResponse(answer=question, clarification=question)
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


def photo_inspector_node(state: ShopSenseState) -> ShopSenseState:
    """Agent 1: Visual Inspector examines image_bytes and flags potential mismatch."""
    if state.get("intent") == "refuse":
        return state

    image_bytes = state.get("image_bytes") or b"mock_photo_bytes"

    from app.services.agents.photo_deal_agent import VisualInspectorAgent
    from app.core.config import get_settings
    agent_1 = VisualInspectorAgent(api_key=get_settings().google_vision_api_key)
    state["visual_data"] = agent_1.inspect(image_bytes, state["db"])
    return state


def deal_specialist_node(state: ShopSenseState) -> ShopSenseState:
    """Agent 2: Deal & Offer Specialist resolves mismatch, finds optimal option, and attaches deals."""
    if state.get("intent") == "refuse":
        return state

    from app.services.agents.photo_deal_agent import resolve_photo_mismatch_and_find_deals
    image_bytes = state.get("image_bytes") or b"mock_photo_bytes"
    resp = resolve_photo_mismatch_and_find_deals(image_bytes, state["db"])
    state["response"] = resp
    state["product_ids"] = resp.product_ids or []
    return state

