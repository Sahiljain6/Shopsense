import json
from typing import Any

from openai import OpenAI
from pinecone import Pinecone
from backend.app.core.config import get_settings
from backend.app.models import Product, Review
from backend.app.services.prompts import JSON_OUTPUT_PROMPT, MODIFIERS, SYSTEM_PROMPT

INJECTION_MARKERS = (
    "ignore previous",
    "system prompt",
    "developer message",
    "jailbreak",
    "you are now",
    "act as",
)


def select_modifiers(message: str, requested_mode: str | None = None) -> list[str]:
    m = message.lower()
    mods: list[str] = []
    if requested_mode and requested_mode in MODIFIERS:
        mods.append(requested_mode)
    else:
        if any(w in m for w in ("vs", "versus", "compare", "or")):
            mods.append("compare")
        elif any(w in m for w in ("review", "worth it", "any complaints")):
            mods.append("review_digest")
        else:
            mods.append("recommend")
    if any(w in m for w in ("budget", "cheap", "affordable", "under ")):
        mods.append("budget_optimizer")
    if any(w in m for w in ("gift", "present", "for my", "birthday")):
        mods.append("gift_mode")
    if any(w in m for w in ("spec", "specs", "technical", "detailed")):
        mods.append("spec_nerd")
    if any(w in m for w in ("quick", "just tell me", "tl;dr")):
        mods.append("quick_answer")
    return mods


def build_system_prompt(modifiers: list[str]) -> str:
    return SYSTEM_PROMPT + "\n\n" + "\n".join(MODIFIERS[m] for m in modifiers)


class AIOrchestrator:
    def __init__(self):
        self.settings = get_settings()
        self.client = (
            OpenAI(api_key=self.settings.openai_api_key)
            if self.settings.openai_api_key
            else None
        )
        self.last_products: list[Product] = []
        self.last_clarification: str | None = None

    def embed(self, text: str) -> list[float]:
        if self.client:
            return (
                self.client.embeddings.create(
                    model=self.settings.embedding_model, input=text
                )
                .data[0]
                .embedding
            )
        return [float((sum(map(ord, text[i::64])) % 997) / 997) for i in range(64)]

    def vector_context(self, message: str, products: list[Product]) -> str:
        if self.settings.pinecone_api_key:
            try:
                pc = Pinecone(api_key=self.settings.pinecone_api_key)
                idx = pc.Index(self.settings.pinecone_index)
                res = idx.query(
                    vector=self.embed(message), top_k=5, include_metadata=True
                )
                return "\n".join(
                    str(m.get("metadata", {})) for m in res.get("matches", [])
                )
            except Exception:
                pass
        return "\n".join(
            f"id={p.id}; {p.name}: {p.description} {p.currency} {p.price} "
            f"rating {p.rating} stock {p.stock} attributes {p.attributes}"
            for p in products[:5]
        )

    def _complete(
        self,
        prompt: str,
        system_prompt: str = SYSTEM_PROMPT,
        json_mode: bool = False,
    ) -> str:
        if self.client:
            kwargs: dict[str, Any] = {
                "model": self.settings.openai_model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt},
                ],
            }
            if json_mode:
                kwargs["response_format"] = {"type": "json_object"}
            r = self.client.chat.completions.create(**kwargs)
            return r.choices[0].message.content or ""
        return ""

    def needs_clarification(self, message: str) -> str | None:
        m = message.lower()
        if any(x in m for x in INJECTION_MARKERS):
            return "What product category are you shopping for?"
        if len(m.split()) < 3:
            return "What is your budget and primary use case?"
        if not any(ch.isdigit() for ch in m) and not any(
            w in m for w in ("cheap", "premium", "budget", "best")
        ):
            return "Do you have a budget range or preferred brand?"
        return None

    def _fallback_answer(self, products: list[Product]) -> str:
        names = ", ".join(p.name for p in products[:3])
        return (
            f"I recommend {names}. They best match your request by rating, stock, "
            "and catalog relevance."
        )

    def answer(
        self,
        message: str,
        products: list[Product],
        memory: list[str] | None = None,
        requested_mode: str | None = None,
    ) -> str:
        self.last_products = products[:3]
        self.last_clarification = None
        if not products:
            self.last_products = []
            return "I could not find matching catalog products. Share a category, brand, feature, or budget and I will narrow it down."
        context = self.vector_context(message, products)
        prompt = f"User: {message}\nMemory: {memory or []}\nCatalog context:\n{context}"
        system_prompt = build_system_prompt(select_modifiers(message, requested_mode))
        ai = self._complete(
            prompt,
            system_prompt=f"{system_prompt}\n\n{JSON_OUTPUT_PROMPT}",
            json_mode=True,
        )
        if ai:
            try:
                payload = json.loads(ai)
                product_map = {str(p.id): p for p in products}
                ids = [str(pid) for pid in payload.get("product_ids", [])]
                self.last_products = [
                    product_map[pid] for pid in ids if pid in product_map
                ]
                self.last_clarification = payload.get("clarification")
                answer = payload.get("answer") or self.last_clarification
                if isinstance(answer, str) and answer:
                    return answer
            except (TypeError, ValueError, json.JSONDecodeError):
                pass
        plain = self._complete(
            f"{prompt}\nGive concise recommendations with reasons.",
            system_prompt=system_prompt,
        )
        return plain or self._fallback_answer(products)

    def summarize_reviews(self, reviews: list[Review]) -> dict:
        avg = sum(r.rating for r in reviews) / len(reviews) if reviews else 0
        pros = [r.title for r in reviews if r.rating >= 4][:5]
        cons = [r.title for r in reviews if r.rating < 4][:5]
        return {
            "pros": pros,
            "cons": cons,
            "overall_opinion": f"Average rating {avg:.1f} from {len(reviews)} reviews.",
            "sentiment": (
                "positive" if avg >= 4 else "mixed" if avg >= 3 else "negative"
            ),
        }

    def compare(self, products: list[Product]) -> dict:
        rows = [
            {
                "id": p.id,
                "name": p.name,
                "brand": p.brand,
                "price": p.price,
                "rating": p.rating,
                "stock": p.stock,
                "strength": p.description[:120],
            }
            for p in products
        ]
        winner = max(products, key=lambda p: (p.rating, -p.price)) if products else None
        return {
            "products": rows,
            "winner": winner.name if winner else None,
            "recommendation": (
                f"Choose {winner.name} for the strongest rating-to-price balance."
                if winner
                else "No products found."
            ),
        }
