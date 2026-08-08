import json
import re
from sqlalchemy.orm import Session
from openai import OpenAI

from app.core.config import get_settings
from app.models.entities import Product
from app.schemas.api import ChatResponse
from app.services.catalog import CatalogService
from app.services.prompts import MODIFIERS

INJECTION_MARKERS = [
    "ignore previous",
    "system prompt",
    "developer message",
    "jailbreak"
]

CATEGORIES = [
    "phone", "mobile", "smartphone",
    "laptop", "notebook",
    "headphone", "headphones", "earbuds", "earphones",
    "watch", "smartwatch",
    "speaker", "tablet"
]


def select_modifiers(message: str, requested_mode: str | None = None) -> list[str]:
    lowered = message.lower()
    selected = []

    base = requested_mode if requested_mode in MODIFIERS else None

    if base is None:
        base = (
            "compare"
            if "compare" in lowered
            else "review_digest"
            if "review" in lowered
            else "recommend"
        )

    selected.append(base)

    keyword_map = {
        "budget_optimizer": ["budget", "under", "cheap", "below", "upto"],
        "gift_mode": ["gift", "birthday", "rakshabandhan"],
        "deal_hunter": ["deal", "value"],
        "spec_nerd": ["spec", "ram", "processor"],
        "quick_answer": ["quick", "one line"]
    }

    for modifier, words in keyword_map.items():
        if modifier != base and any(word in lowered for word in words):
            selected.append(modifier)

    return selected


def needs_clarification(message: str) -> str | None:
    return None


def extract_budget(message: str) -> float | None:
    text = message.lower().replace(",", "")

    lakh = re.search(r"(\d+(?:\.\d+)?)\s*lakhs?", text)
    if lakh:
        return float(lakh.group(1)) * 100000

    thousand = re.search(r"(\d+(?:\.\d+)?)\s*k\b", text)
    if thousand:
        return float(thousand.group(1)) * 1000

    amount = re.search(
        r"(?:under|below|upto|up to|within|budget)?\s*[₹rs\.]*\s*(\d{4,7})",
        text
    )

    if amount:
        return float(amount.group(1))

    return None


def normalize_query(message: str) -> str:
    text = message.lower()

    replacements = {
        "smartphones": "phone",
        "smartphone": "phone",
        "mobiles": "phone",
        "mobile": "phone",
        "cell phone": "phone",
        "notebooks": "laptop",
        "notebook": "laptop",
        "earphones": "headphones",
        "earbuds": "headphones",
        "headsets": "headphones",
        "smartwatch": "watch",
        "smart watches": "watch",
    }

    for old, new in replacements.items():
        text = text.replace(old, new)

    return text


class AIOrchestrator:

    def __init__(self, db: Session) -> None:
        self.db = db
        self.catalog = CatalogService(db)

        settings = get_settings()

        self.client = None

        if settings.openai_api_key:
            self.client = OpenAI(api_key=settings.openai_api_key)

    def answer(self, message: str, mode: str | None = None) -> ChatResponse:

        normalized = normalize_query(message)

        products = self.catalog.search(normalized, limit=12)

        budget = extract_budget(message)

        if budget is not None:
            products = [
                product
                for product in products
                if product.price <= budget
            ]

        products = self._rank_products(products, message)

        if not products:
            return self._general_ai_response(message)

        products = products[:(
            1 if "quick_answer" in select_modifiers(message, mode)
            else 3
        )]

        return self._generate_ai_response(message, products)

    def answer_via_agents(
        self,
        message: str,
        mode: str | None = None
    ) -> ChatResponse:

        try:
            if not get_settings().enable_multi_agent:
                return self.answer(message, mode)

            from app.services.agents.graph import run_graph

            data = run_graph({
                "message": message,
                "mode": mode,
                "db": self.db
            })

            if isinstance(data.get("response"), ChatResponse):
                return data["response"]

            return self.answer(message, mode)

        except Exception:
            return self.answer(message, mode)

    def _rank_products(
        self,
        products: list[Product],
        message: str
    ) -> list[Product]:

        return sorted(
            products,
            key=lambda product: (
                -product.rating,
                product.price
            )
        )

    def _generate_ai_response(
        self,
        message: str,
        products: list[Product]
    ) -> ChatResponse:

        ids = [product.id for product in products]

        if not self.client:
            return self._structured_response(products)

        product_context = []

        for product in products:
            product_context.append({
                "id": product.id,
                "name": product.name,
                "brand": product.brand,
                "description": product.description,
                "price": product.price,
                "currency": product.currency,
                "rating": product.rating,
                "stock": product.stock,
                "attributes": product.attributes
            })

        prompt = f"""
You are ShopSense, a helpful shopping assistant.

User request:
{message}

These are the ONLY products you are allowed to recommend:

{json.dumps(product_context, ensure_ascii=False)}

Give a concise, useful shopping recommendation.

Explain why the products fit the user's request.

Never invent products, prices, ratings, specifications or URLs.

If the user mentioned a budget, respect it.

If the user mentioned a gift, occasion or use case, consider it.

Return only the natural language answer.
"""

        try:
            response = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {
                        "role": "system",
                        "content": "You are ShopSense, a helpful and concise shopping assistant."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                temperature=0.3,
                max_tokens=400
            )

            answer = response.choices[0].message.content or ""

            return ChatResponse(
                answer=answer,
                product_ids=ids,
                reasons={
                    str(product.id):
                    f"Recommended based on relevance and {product.rating:.1f}/5 rating."
                    for product in products
                },
                pros={
                    str(product.id):
                    ["Catalog-backed product", "Good rating", "Real catalog price"]
                    for product in products
                },
                cons={
                    str(product.id):
                    ["Check detailed specifications before purchase"]
                    for product in products
                }
            )

        except Exception:
            return self._structured_response(products)

    def _general_ai_response(self, message: str) -> ChatResponse:

        if not self.client:
            return ChatResponse(
                answer=(
                    "I couldn't find matching products in the current catalog. "
                    "Try another shopping request."
                )
            )

        try:
            response = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are ShopSense, a helpful shopping assistant. "
                            "Answer naturally. Do not force users to provide a "
                            "category or budget."
                        )
                    },
                    {
                        "role": "user",
                        "content": message
                    }
                ],
                temperature=0.5,
                max_tokens=300
            )

            answer = response.choices[0].message.content or ""

            return ChatResponse(answer=answer)

        except Exception:
            return ChatResponse(
                answer=(
                    "I couldn't find an exact product match right now, "
                    "but I can still help you with shopping advice."
                )
            )

    def _structured_response(
        self,
        products: list[Product]
    ) -> ChatResponse:

        ids = [product.id for product in products]

        names = ", ".join(
            f"{product.name} ({product.currency} {product.price:.0f})"
            for product in products
        )

        return ChatResponse(
            answer=f"Here are some good options: {names}.",
            product_ids=ids,
            reasons={
                str(product.id):
                f"Good catalog match with {product.rating:.1f}/5 rating."
                for product in products
            },
            pros={
                str(product.id):
                ["Catalog-backed choice", "Good rating", "Clear price"]
                for product in products
            },
            cons={
                str(product.id):
                ["Check detailed specifications before purchase"]
                for product in products
            }
        )


def validate_product_ids(
    response: ChatResponse,
    products: list[Product]
) -> ChatResponse:

    allowed = {product.id for product in products}

    response.product_ids = [
        pid for pid in response.product_ids
        if pid in allowed
    ]

    return response
