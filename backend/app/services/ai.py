import json
import os
import re
from sqlalchemy.orm import Session
from ollama import Client
from openai import OpenAI

from app.core.config import get_settings
from app.models.entities import Product
from app.schemas.api import ChatResponse
from app.services.catalog import CatalogService
from app.services.live_search import search_live_deals
from app.services.prompts import MODIFIERS
from app.services.trust_engine import generate_trust_pros_cons


def select_modifiers(message: str, requested_mode: str | None = None) -> list[str]:
    lowered = message.lower()

    base = requested_mode if requested_mode in MODIFIERS else (
        "compare" if "compare" in lowered
        else "review_digest" if "review" in lowered
        else "recommend"
    )

    selected = [base]

    keyword_map = {
        "budget_optimizer": ["budget", "under", "cheap", "below", "upto", "lakh"],
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
        r"(?:under|below|upto|up to|within|budget|around)?\s*[₹rs\.]*\s*(\d{4,7})",
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
        "cellphone": "phone",
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


def get_active_groq_models(api_key: str) -> list[str]:
    clean_key = api_key.strip().strip("'").strip('"')
    url = "https://api.groq.com/openai/v1/models"
    headers = {"Authorization": f"Bearer {clean_key}"}

    try:
        import httpx
        with httpx.Client(timeout=5) as client:
            resp = client.get(url, headers=headers)
            if resp.status_code == 200:
                data = resp.json()
                models_data = data.get("data", [])
                active_ids = [
                    m.get("id") for m in models_data
                    if m.get("id") and m.get("active", True) is not False
                ]
                if active_ids:
                    return active_ids
    except Exception as err:
        print(f"Notice fetching Groq model list dynamically: {err}")

    return ["llama-3.3-70b-versatile", "llama-3.1-8b-instant", "mixtral-8x7b-32768"]


class AIOrchestrator:

    def __init__(self, db: Session) -> None:
        self.db = db
        self.catalog = CatalogService(db)

        settings = get_settings()

        self.client = None
        self.provider: str | None = None
        self.model = None
        self.active_models: list[str] = []

        gemini_key = settings.gemini_api_key or os.getenv("GEMINI_API_KEY")
        groq_key = settings.groq_api_key or os.getenv("GROQ_API_KEY")
        ollama_key = settings.ollama_api_key or os.getenv("OLLAMA_API_KEY")

        self.gemini_api_key = None
        if gemini_key:
            self.provider = "gemini"
            self.gemini_api_key = gemini_key.strip().strip("'").strip('"')

        elif groq_key:
            clean_key = groq_key.strip().strip("'").strip('"')
            self.client = OpenAI(
                base_url="https://api.groq.com/openai/v1",
                api_key=clean_key
            )
            self.provider = "groq"
            self.active_models = get_active_groq_models(clean_key)
            self.model = self.active_models[0] if self.active_models else "llama-3.3-70b-versatile"

        elif ollama_key:
            clean_key = ollama_key.strip().strip("'").strip('"')
            self.client = Client(
                host="https://ollama.com",
                headers={
                    "Authorization": f"Bearer {clean_key}"
                }
            )
            self.provider = "ollama"
            self.model = settings.ollama_model

    def _chat(
        self,
        system: str,
        user: str,
        history: list[dict[str, str]] | None = None
    ) -> str | None:
        """Call whichever provider is configured (Gemini 1.5 Flash preferred, Groq/Ollama fallback)."""

        if self.provider == "gemini" and self.gemini_api_key:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={self.gemini_api_key}"
            payload = {
                "system_instruction": {
                    "parts": [{"text": system}]
                },
                "contents": [
                    {"parts": [{"text": user}]}
                ]
            }
            try:
                import httpx
                with httpx.Client(timeout=15) as client:
                    resp = client.post(url, json=payload)
                    if resp.status_code == 200:
                        data = resp.json()
                        candidates = data.get("candidates", [])
                        if candidates:
                            parts = candidates[0].get("content", {}).get("parts", [])
                            if parts:
                                return parts[0].get("text")
                    print(f"Gemini API Notice ({resp.status_code}): {resp.text}")
            except Exception as err:
                print(f"Gemini API error: {err}")

        if not self.client and self.provider != "gemini":
            return None

        clean_messages = [{"role": "system", "content": system}]
        if history:
            for turn in history:
                if isinstance(turn, dict) and turn.get("role") and turn.get("content"):
                    clean_messages.append({
                        "role": str(turn["role"]),
                        "content": str(turn["content"])
                    })
        clean_messages.append({"role": "user", "content": user})

        if self.provider == "groq" and self.client:
            candidate_models = self.active_models or ["llama-3.3-70b-versatile", "llama-3.1-8b-instant"]

            for model_name in candidate_models:
                try:
                    response = self.client.chat.completions.create(
                        model=model_name,
                        messages=clean_messages
                    )
                    if response and response.choices:
                        return response.choices[0].message.content
                except Exception as error:
                    print(f"Groq API error with model '{model_name}': {type(error).__name__}: {error}")
                    continue
            return None

        if self.client:
            try:
                response = self.client.chat(
                    model=self.model,
                    messages=clean_messages,
                    stream=False
                )
                return response.message.content
            except Exception as error:
                print(f"{self.provider} API error: {type(error).__name__}: {error}")
                return None

        return None

    def answer(
        self,
        message: str,
        mode: str | None = None,
        history: list[dict[str, str]] | None = None
    ) -> ChatResponse:

        # Auto-detect product URL pasted in chat message (e.g. "Fetch link: https://amzn.in/d/0au0AjZK" or raw URL)
        url_match = re.search(r'https?://[^\s]+', message)
        if url_match:
            target_url = url_match.group(0)
            try:
                from app.services.scraper import scrape_product
                scraped = scrape_product(target_url)
                if scraped:
                    product, _ = self.catalog.upsert_from_scrape(scraped, target_url)
                    return self._generate_ai_response(message, [product], history)
            except Exception as err:
                print(f"Chat URL auto-scrape notice: {err}")

        normalized = normalize_query(message)

        products = self.catalog.search(normalized, limit=12)

        budget = extract_budget(message)

        if budget is not None:
            products = [
                product
                for product in products
                if product.price <= budget
            ]

        products = self._rank_products(products)

        if products:
            products = products[:(
                1 if "quick_answer" in select_modifiers(message, mode)
                else 3
            )]

            return self._generate_ai_response(message, products, history)

        return self._general_ai_response(message, history)

    def answer_via_agents(
        self,
        message: str,
        mode: str | None = None,
        history: list[dict[str, str]] | None = None
    ) -> ChatResponse:

        try:
            if not get_settings().enable_multi_agent:
                return self.answer(message, mode, history)

            from app.services.agents.graph import run_graph

            data = run_graph({
                "message": message,
                "mode": mode,
                "db": self.db
            })

            if isinstance(data.get("response"), ChatResponse):
                return data["response"]

            return self.answer(message, mode, history)

        except Exception:
            return self.answer(message, mode, history)

    def _rank_products(
        self,
        products: list[Product]
    ) -> list[Product]:

        return sorted(
            products,
            key=lambda product: (
                -(product.rating or 0),
                product.price
            )
        )

    def _generate_ai_response(
        self,
        message: str,
        products: list[Product],
        history: list[dict[str, str]] | None = None
    ) -> ChatResponse:

        ids = [product.id for product in products]

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
You are ShopSense, an intelligent shopping assistant.

User request:
{message}

Available products from the ShopSense catalog:

{json.dumps(product_context, ensure_ascii=False, default=str)}

Give a helpful and natural recommendation.

Use ONLY the products provided above.

Never invent:
- product names
- prices
- ratings
- specifications
- URLs
- brands

Respect the user's budget if one was mentioned.

Consider the user's:
- occasion
- recipient
- use case
- budget
- preferences

If this is a gift request, explain briefly why the selected products
would make suitable gifts.

Keep the response concise and useful.
"""

        answer = self._chat(
            system=(
                "You are ShopSense, a helpful shopping "
                "assistant. Recommend only real products "
                "provided in the catalog context. Use the "
                "conversation history to understand context "
                "like budget or brand mentioned earlier."
            ),
            user=prompt,
            history=history
        )

        if answer is None:
            return self._structured_response(products)

        pros_map = {}
        cons_map = {}
        reasons_map = {}

        for product in products:
            pid_str = str(product.id)
            p_pros, p_cons = generate_trust_pros_cons(
                rating=product.rating or 0.0,
                price=product.price or 0.0,
                brand=product.brand or "",
                store_name="ShopSense Catalog"
            )
            pros_map[pid_str] = p_pros
            cons_map[pid_str] = p_cons
            reasons_map[pid_str] = f"Verified catalog item ({product.rating:.1f}/5★ rating)."

        return ChatResponse(
            answer=answer,
            product_ids=ids,
            reasons=reasons_map,
            pros=pros_map,
            cons=cons_map
        )

    def _general_ai_response(
        self,
        message: str,
        history: list[dict[str, str]] | None = None
    ) -> ChatResponse:

        # Warm greeting response for common conversational intros
        clean_msg = message.strip().lower()
        if clean_msg in ["hi", "hello", "hey", "hi there", "hello there", "help"]:
            return ChatResponse(
                answer=(
                    "Hello! 👋 I'm ShopSense, your AI shopping copilot. "
                    "I can help you find products, compare options, check prices, or find top deals under a budget. "
                    "What are you looking for today?"
                )
            )

        # Fetch 100% free real-time live web product deals via DuckDuckGo
        live_deals = search_live_deals(message, max_results=3)

        live_context_str = ""
        if live_deals:
            deal_items = []
            for d in live_deals:
                price_info = f" ({d['price_str']})" if d.get('price_str') else ""
                deal_items.append(f"- [{d['store']}] {d['title']}{price_info}: {d['url']}")
            live_context_str = "\nLive web deals & product options found:\n" + "\n".join(deal_items)

        prompt = f"{message}\n{live_context_str}" if live_context_str else message

        answer = self._chat(
            system=(
                "You are ShopSense, an expert 100% free AI shopping copilot. "
                "Help the user find the best, most trustworthy products at the cheapest prices. "
                "If live web deal links are provided in the prompt, recommend them with their price and source link."
            ),
            user=prompt,
            history=history
        )

        if answer is None:
            # Fallback 1: Return live web deals formatted directly if LLM unavailable
            if live_deals:
                lines = ["Here are top live deals found online:\n"]
                for d in live_deals:
                    price_info = f" — **{d['price_str']}**" if d.get('price_str') else ""
                    lines.append(f"• **[{d['store']}]** [{d['title']}]({d['url']}){price_info}")
                return ChatResponse(answer="\n".join(lines))

            # Fallback 2: Catalog search fallback
            keywords = ["phone", "iphone", "samsung", "apple", "laptop", "macbook", "headphones", "earbuds", "watch", "buy", "deal", "cheap", "compare"]
            lowered = message.lower()
            matched_keywords = [k for k in keywords if k in lowered]
            if matched_keywords:
                search_query = " ".join(matched_keywords)
                fallback_products = self.catalog.search(search_query, limit=4)
                if not fallback_products:
                    fallback_products = self.catalog.search("", limit=3)
                if fallback_products:
                    return self._structured_response(fallback_products)

            # Fallback 3: Comparison breakdown for iPhone vs Samsung if database has no records
            if "iphone" in lowered and "samsung" in lowered:
                return ChatResponse(
                    answer=(
                        "### 📱 iPhone vs. Samsung Galaxy: Key Comparison\n\n"
                        "• **iPhone (iOS & Apple Ecosystem)**:\n"
                        "  - ✦ **Strengths**: Best-in-class video recording, 5-7 years software updates, Apple Silicon performance & seamless Mac/iPad ecosystem.\n"
                        "  - ✦ **Recommended Models**: iPhone 15 Pro, iPhone 15, iPhone 13 (Best budget entry).\n\n"
                        "• **Samsung Galaxy (Android & Customization)**:\n"
                        "  - ✦ **Strengths**: 100x zoom camera & S-Pen stylus (Ultra models), 120Hz Dynamic AMOLED displays, superior multitasking & Galaxy AI features.\n"
                        "  - ✦ **Recommended Models**: Galaxy S24 Ultra, Galaxy S24, Galaxy A55 5G (Budget champion).\n\n"
                        "💡 **Verdict**: Choose **iPhone** for long-term resale value & ecosystem continuity, or **Samsung** for screen quality, multitasking, and camera zoom flexibility."
                    )
                )

            # Fallback 4: General catalog recommendation
            all_products = self.catalog.search("", limit=3)
            if all_products:
                return self._structured_response(all_products)

            return ChatResponse(
                answer=(
                    "I searched for top matches. To find the exact deal, try asking for a specific model or budget, e.g. **'Best phone under 20000'** or **'Compare iPhone 15 vs Galaxy S24'**!"
                )
            )

        return ChatResponse(answer=answer)

    def _structured_response(
        self,
        products: list[Product]
    ) -> ChatResponse:

        ids = [product.id for product in products]

        names = ", ".join(
            f"{product.name} ({product.currency} {product.price:.0f})"
            for product in products
        )

        pros_map = {}
        cons_map = {}
        reasons_map = {}

        for product in products:
            pid_str = str(product.id)
            p_pros, p_cons = generate_trust_pros_cons(
                rating=product.rating or 0.0,
                price=product.price or 0.0,
                brand=product.brand or "",
                store_name="ShopSense Catalog"
            )
            pros_map[pid_str] = p_pros
            cons_map[pid_str] = p_cons
            reasons_map[pid_str] = f"Trusted catalog match with {product.rating:.1f}/5★ rating."

        return ChatResponse(
            answer=f"Here are top verified options: {names}.",
            product_ids=ids,
            reasons=reasons_map,
            pros=pros_map,
            cons=cons_map
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
