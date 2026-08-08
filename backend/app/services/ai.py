import re
from sqlalchemy.orm import Session
from app.core.config import get_settings
from app.models.entities import Product
from app.schemas.api import ChatResponse
from app.services.catalog import CatalogService
from app.services.prompts import MODIFIERS

INJECTION_MARKERS = ["ignore previous", "system prompt", "developer message", "jailbreak", "act as", "you are now"]


def select_modifiers(message: str, requested_mode: str | None = None) -> list[str]:
    lowered = message.lower()
    selected: list[str] = []
    base = requested_mode if requested_mode in MODIFIERS else None
    if base is None:
        base = "compare" if "compare" in lowered else "review_digest" if "review" in lowered else "recommend"
    selected.append(base)
    keyword_map = {"budget_optimizer": ["budget", "under", "cheap", "below", "within", "upto", "up to"], "gift_mode": ["gift", "birthday"], "deal_hunter": ["deal", "value"], "spec_nerd": ["spec", "ram", "processor"], "quick_answer": ["quick", "one line"]}
    for modifier, words in keyword_map.items():
        if modifier != base and any(word in lowered for word in words):
            selected.append(modifier)
    return selected


def is_prompt_injection(message: str) -> bool:
    return any(marker in message.lower() for marker in INJECTION_MARKERS)


def needs_clarification(message: str) -> str | None:
    """ShopSense should answer broadly instead of gating on category, budget, or use case."""
    return None


def parse_budget(message: str) -> float | None:
    lowered = message.lower().replace(",", "")
    money_prefix = r"(?:₹|rs\.?|inr)?\s*"
    budget_words = r"(?:under|below|upto|up to|within|budget|with|have|for|around|less than|maximum|max)"
    patterns = [
        rf"\b{budget_words}\b\s*{money_prefix}(\d+(?:\.\d+)?)\s*(lakhs?|lacs?|k)\b",
        rf"\b{budget_words}\b\s*{money_prefix}(\d{3,7})\b",
        rf"{money_prefix}(\d+(?:\.\d+)?)\s*(lakhs?|lacs?|k)\b",
        rf"(?:₹|rs\.?|inr)\s*(\d{3,7})\b",
    ]
    for pattern in patterns:
        match = re.search(pattern, lowered)
        if not match:
            continue
        amount = float(match.group(1))
        unit = match.group(2) if len(match.groups()) > 1 else ""
        if unit.startswith(("lakh", "lac")):
            amount *= 100000
        elif unit == "k":
            amount *= 1000
        return amount
    return None


class AIOrchestrator:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.catalog = CatalogService(db)

    def answer(self, message: str, mode: str | None = None) -> ChatResponse:
        if is_prompt_injection(message):
            return ChatResponse(answer="I can help with shopping, but I can't follow prompt-changing instructions. Tell me what product, gift, comparison, or budget you want help with.")
        products = self.catalog.search(message, limit=8)
        if not products:
            products = self.catalog.search(None, limit=8)
        if not products:
            return ChatResponse(answer=self._empty_catalog_response(message))
        ranked = self._rank_products(products, message)[: (1 if "quick_answer" in select_modifiers(message, mode) else 3)]
        return self._structured_response(ranked, message)

    def answer_via_agents(self, message: str, mode: str | None = None) -> ChatResponse:
        try:
            if not get_settings().enable_multi_agent:
                return self.answer(message, mode)
            from app.services.agents.graph import run_graph
            data = run_graph({"message": message, "mode": mode, "db": self.db})
            if isinstance(data.get("response"), ChatResponse):
                return data["response"]
            return self.answer(message, mode)
        except Exception:
            return self.answer(message, mode)

    def _rank_products(self, products: list[Product], message: str) -> list[Product]:
        lowered = message.lower()
        budget = parse_budget(message)
        filtered = [p for p in products if budget is None or p.price <= budget] or products
        terms = set(self.catalog.query_terms(message))

        def score(product: Product) -> tuple[float, float, float]:
            text = " ".join([product.name, product.brand, product.description, product.category.name if product.category else ""]).lower()
            relevance = sum(1 for term in terms if term in text)
            if "cheap" in lowered or "cheapest" in lowered:
                relevance += max(0, 5 - product.price / 10000)
            if "best" in lowered or "rated" in lowered or "good" in lowered:
                relevance += product.rating
            return (-relevance, -product.rating, product.price)

        return sorted(filtered, key=score)

    def _structured_response(self, products: list[Product], message: str) -> ChatResponse:
        ids = [p.id for p in products]
        names = ", ".join(f"{p.name} ({p.currency} {p.price:.0f})" for p in products)
        prefix = self._response_prefix(message)
        return ChatResponse(
            answer=f"{prefix} {names}.",
            product_ids=ids,
            reasons={str(p.id): f"Catalog-backed match with {p.rating:.1f} rating at {p.currency} {p.price:.0f}." for p in products},
            pros={str(p.id): ["Catalog-backed choice", "Good rating", "Clear price"] for p in products},
            cons={str(p.id): ["Check detailed specs, seller availability, and warranty before purchase"] for p in products},
        )

    def _response_prefix(self, message: str) -> str:
        lowered = message.lower().strip()
        if lowered in {"hello", "hi", "hey", "namaste"}:
            return "Hi! I'm ShopSense. I can help you find products, compare options, find gifts, or choose within your budget. Here are some highly rated catalog picks:"
        if "gift" in lowered:
            return "I can help with that. Here are some highly rated catalog products that could work as a gift:"
        if "compare" in lowered:
            return "I can compare catalog options. Here are relevant products to start with:"
        if "cheap" in lowered or "cheapest" in lowered:
            return "Here are budget-friendly catalog options:"
        return "Here are catalog-backed recommendations:"

    def _empty_catalog_response(self, message: str) -> str:
        lowered = message.lower().strip()
        if lowered in {"hello", "hi", "hey", "namaste"}:
            return "Hi! I'm ShopSense. I can help you find products, compare options, find gifts, or choose something within your budget. What are you looking for?"
        return "I couldn't find an exact catalog match right now, but I can still help refine the search. Try a product type, brand, use case, or price such as 'gaming headphones under 5000' or 'gift ideas around 20000'."


def validate_product_ids(response: ChatResponse, products: list[Product]) -> ChatResponse:
    allowed = {p.id for p in products}
    response.product_ids = [pid for pid in response.product_ids if pid in allowed]
    return response
