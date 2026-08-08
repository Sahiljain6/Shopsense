import json
import re
from sqlalchemy.orm import Session
from app.core.config import get_settings
from app.models.entities import Product
from app.schemas.api import ChatResponse
from app.services.catalog import CatalogService
from app.services.prompts import MODIFIERS

INJECTION_MARKERS = ["ignore previous", "system prompt", "developer message", "jailbreak", "act as", "you are now"]
CATEGORIES = ["phone", "laptop", "headphone", "watch", "speaker", "tablet"]


def select_modifiers(message: str, requested_mode: str | None = None) -> list[str]:
    lowered = message.lower()
    selected: list[str] = []
    base = requested_mode if requested_mode in MODIFIERS else None
    if base is None:
        base = "compare" if "compare" in lowered else "review_digest" if "review" in lowered else "recommend"
    selected.append(base)
    keyword_map = {"budget_optimizer": ["budget", "under", "cheap"], "gift_mode": ["gift", "birthday"], "deal_hunter": ["deal", "value"], "spec_nerd": ["spec", "ram", "processor"], "quick_answer": ["quick", "one line"]}
    for modifier, words in keyword_map.items():
        if modifier != base and any(word in lowered for word in words):
            selected.append(modifier)
    return selected


def needs_clarification(message: str) -> str | None:
    lowered = message.lower()
    if any(marker in lowered for marker in INJECTION_MARKERS):
        return "I can help with shopping, but I can't follow prompt-changing instructions. What product category and budget should I use?"
    has_category = any(category in lowered or category + "s" in lowered for category in CATEGORIES)
    has_budget = bool(re.search(r"\b(under|below|budget|₹|rs\.?|inr|\d{4,6})\b", lowered))
    has_use = any(word in lowered for word in ["gaming", "work", "student", "travel", "music", "gift", "camera"])
    if not has_category:
        return "Which product category should I search in?"
    if not has_budget and not has_use:
        return "What budget or use-case should I optimize for?"
    return None


class AIOrchestrator:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.catalog = CatalogService(db)

    def answer(self, message: str, mode: str | None = None) -> ChatResponse:
        clarification = needs_clarification(message)
        if clarification:
            return ChatResponse(answer=clarification, clarification=clarification)
        products = self.catalog.search(message, limit=8)
        if not products:
            question = "I couldn't find matching catalog products. Which category, brand, or budget should I try next?"
            return ChatResponse(answer=question, clarification=question)
        ranked = self._rank_products(products, message)[: (1 if "quick_answer" in select_modifiers(message, mode) else 3)]
        return self._structured_response(ranked)

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
        budget_match = re.search(r"(\d{4,6})", message)
        budget = float(budget_match.group(1)) if budget_match else None
        filtered = [p for p in products if budget is None or p.price <= budget] or products
        return sorted(filtered, key=lambda p: (-p.rating, p.price))

    def _structured_response(self, products: list[Product]) -> ChatResponse:
        ids = [p.id for p in products]
        names = ", ".join(f"{p.name} ({p.currency} {p.price:.0f})" for p in products)
        return ChatResponse(
            answer=f"Top grounded picks: {names}.",
            product_ids=ids,
            reasons={str(p.id): f"Strong fit from the current catalog with {p.rating:.1f} rating." for p in products},
            pros={str(p.id): ["Catalog-backed choice", "Good rating", "Clear price"] for p in products},
            cons={str(p.id): ["Check detailed specs before purchase"] for p in products},
        )


def validate_product_ids(response: ChatResponse, products: list[Product]) -> ChatResponse:
    allowed = {p.id for p in products}
    response.product_ids = [pid for pid in response.product_ids if pid in allowed]
    return response
