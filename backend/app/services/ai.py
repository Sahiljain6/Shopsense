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


def check_shopping_guardrail(message: str) -> str | None:
    """Check if the user request is strictly out-of-scope (e.g. coding, programming, non-shopping essays).
    Returns a polite refusal string if out-of-scope, or None if it's a shopping query.
    """
    lowered = message.lower().strip()

    # Exclude common legitimate e-commerce code terms first
    is_shopping_code_term = any(
        term in lowered
        for term in [
            "coupon code", "promo code", "discount code", "voucher code",
            "postal code", "pincode", "zip code", "barcode", "qr code",
            "product code", "sku code", "gift card code", "referral code"
        ]
    )

    # 1. Coding / Programming / Software Development requests
    coding_patterns = [
        r"\b(write|generate|create|build|debug|fix|explain|refactor)\b.*\b(code|python|javascript|typescript|c\+\+|java|html|css|sql|script|function|algorithm|regex|class|component|api|backend|frontend)\b",
        r"\b(python|javascript|typescript|c\+\+|java|react|django|fastapi|node\.?js|php|rust|golang)\s+(code|script|program|function|snippet|app)\b",
        r"^(def |function |const |let |var |import |class |SELECT |INSERT |UPDATE |DELETE |public class )",
        r"\b(write a program|write a script|write an algorithm|debug this|fix this code|solve this bug|write unit test)\b",
    ]

    if not is_shopping_code_term:
        for pattern in coding_patterns:
            if re.search(pattern, lowered):
                return (
                    "I am **ShopSense**, an AI shopping copilot! 🛍️\n\n"
                    "I am specialized strictly in helping you discover products, compare prices, analyze specifications, and find deals. "
                    "I cannot write code, debug software, or assist with programming tasks.\n\n"
                    "Let me know if you need help finding, comparing, or budgeting for any tech products, gadgets, or shopping items!"
                )

    # 2. General Non-Shopping Tasks (Essays, Stories, Poetry, Homework)
    non_shopping_patterns = [
        r"\b(write|compose|generate)\b.*\b(essay|poem|poetry|song|lyrics|story|novel|speech|letter to my)\b",
        r"\b(solve this math|solve equation|calculate derivative|integral of|who won the 1\d{3} election)\b",
    ]

    for pattern in non_shopping_patterns:
        if re.search(pattern, lowered):
            return (
                "I am **ShopSense**, a dedicated AI shopping assistant! 🛍️\n\n"
                "I specialize solely in e-commerce, product recommendations, and price tracking. "
                "I cannot help with general essays, creative writing, or non-shopping homework.\n\n"
                "How can I help you find or compare products today?"
            )

    return None


def needs_clarification(message: str) -> str | None:
    return None


def extract_budget(message: str) -> float | None:
    text = message.lower().replace(",", "")

    # USD to INR conversion ($100 -> ₹8,300)
    usd = re.search(r"\$\s*(\d+(?:\.\d+)?)", text)
    if usd:
        return float(usd.group(1)) * 83.0

    lakh = re.search(r"(\d+(?:\.\d+)?)\s*lakhs?", text)
    if lakh:
        return float(lakh.group(1)) * 100000

    thousand = re.search(r"(\d+(?:\.\d+)?)\s*k\b", text)
    if thousand:
        return float(thousand.group(1)) * 1000

    amount = re.search(
        r"(?:under|below|upto|up to|within|budget|around|less than)?\s*[₹rs\.]*\s*(\d{3,7})",
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
        "mechanical keyboards": "keyboard",
        "gaming keyboard": "keyboard",
        "gaming keyboards": "keyboard",
        "keyboards": "keyboard",
        "wireless earbuds": "earbuds",
        "earphones": "earbuds",
        "earbud": "earbuds",
        "tws": "earbuds",
        "headsets": "headphones",
        "smartwatch": "watch",
        "smart watches": "watch",
    }

    for old, new in replacements.items():
        text = text.replace(old, new)

    return text
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

        openai_key = settings.openai_api_key or os.getenv("OPENAI_API_KEY")
        gemini_key = settings.gemini_api_key or os.getenv("GEMINI_API_KEY")
        groq_key = settings.groq_api_key or os.getenv("GROQ_API_KEY")
        ollama_key = settings.ollama_api_key or os.getenv("OLLAMA_API_KEY")

        self.gemini_api_key = None

        if openai_key and openai_key.strip():
            clean_key = openai_key.strip().strip("'").strip('"')
            self.client = OpenAI(api_key=clean_key)
            self.provider = "openai"
            self.model = settings.openai_model or "gpt-4o-mini"

        elif gemini_key and gemini_key.strip():
            self.provider = "gemini"
            self.gemini_api_key = gemini_key.strip().strip("'").strip('"')
            self.model = settings.gemini_model or "gemini-1.5-flash"

        elif groq_key and groq_key.strip():
            clean_key = groq_key.strip().strip("'").strip('"')
            self.client = OpenAI(
                base_url="https://api.groq.com/openai/v1",
                api_key=clean_key
            )
            self.provider = "groq"
            self.active_models = get_active_groq_models(clean_key)
            self.model = self.active_models[0] if self.active_models else "llama-3.3-70b-versatile"

        elif ollama_key and ollama_key.strip():
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
        """Call whichever provider is configured (OpenAI, Gemini, Groq, Ollama)."""

        if self.provider == "gemini" and self.gemini_api_key:
            # Try official Gemini REST endpoint
            models_to_try = ["gemini-1.5-flash", "gemini-1.5-flash-latest", "gemini-2.0-flash", "gemini-1.5-pro"]
            for model_name in models_to_try:
                url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={self.gemini_api_key}"
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
                        print(f"Gemini ({model_name}) Notice ({resp.status_code}): {resp.text[:150]}")
                except Exception as err:
                    print(f"Gemini ({model_name}) API error: {err}")

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

        if self.provider == "openai" and self.client:
            candidate_models = [self.model, "gpt-4o-mini", "gpt-4o", "gpt-3.5-turbo"]
            for model_name in candidate_models:
                try:
                    response = self.client.chat.completions.create(
                        model=model_name,
                        messages=clean_messages
                    )
                    if response and response.choices:
                        return response.choices[0].message.content
                except Exception as error:
                    print(f"OpenAI API error with model '{model_name}': {type(error).__name__}: {error}")
                    continue
            return None

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

        # 1. Strict Scope & Guardrail check (Prevent coding, hacking, homework, and non-shopping usage)
        guardrail_refusal = check_shopping_guardrail(message)
        if guardrail_refusal:
            return ChatResponse(answer=guardrail_refusal)

        # 2. Auto-detect product URL pasted in chat message (e.g. "Fetch link: https://amzn.in/d/0au0AjZK" or raw URL)
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
                "You are ShopSense, an expert AI shopping copilot.\n"
                "STRICT CONSTRAINT: You are EXCLUSIVELY a shopping and e-commerce assistant. "
                "You ONLY assist with product discovery, price comparisons, deal finding, budgeting, and buying decisions. "
                "You MUST REFUSE any requests to write code, debug software, solve non-shopping math/homework, write essays/stories, or perform non-shopping tasks. "
                "If the user asks for coding or non-shopping tasks, politely refuse and redirect them to shopping products.\n"
                "Recommend only real products provided in the catalog context. Use the conversation history to understand context like budget or brand."
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
                "You are ShopSense, an expert AI shopping copilot.\n"
                "STRICT CONSTRAINT: You ONLY answer shopping, product discovery, e-commerce, pricing, and buying advice questions. "
                "You MUST NEVER write programming code (Python, JS, HTML, etc.), debug code, solve general math/science homework, or write creative essays. "
                "If the user asks for code or off-topic non-shopping tasks, politely decline and ask what product they'd like to shop for.\n"
                "If live web deal links are provided in the prompt, recommend them with their price and source link."
            ),
            user=prompt,
            history=history
        )

        if answer is None:
            # Fallback 1: Return live Indian e-commerce deals formatted directly
            if live_deals:
                lines = ["### 🇮🇳 Top Live Deals Found in India:\n"]
                for d in live_deals:
                    price_info = f" — **{d['price_str']}**" if d.get('price_str') else ""
                    lines.append(f"• **[{d['store']}]** [{d['title']}]({d['url']}){price_info}")
                return ChatResponse(answer="\n".join(lines))

            # Fallback 2: Intelligent Catalog Search Matching
            keywords = ["keyboard", "earbuds", "phone", "iphone", "samsung", "apple", "laptop", "macbook", "audio", "watch", "deal", "gaming", "tws"]
            lowered = message.lower()
            matched_keywords = [k for k in keywords if k in lowered]
            if matched_keywords:
                search_query = " ".join(matched_keywords)
                fallback_products = self.catalog.search(search_query, limit=4)
                if fallback_products:
                    return self._structured_response(fallback_products)

            # Fallback 3: Category-specific expert breakdown
            if any(w in lowered for w in ["earbud", "earbuds", "tws", "headphone", "earphone", "audio"]):
                earbuds = self.catalog.search("earbuds", limit=4)
                if earbuds:
                    return self._structured_response(earbuds)
                return ChatResponse(
                    answer=(
                        "### 🎧 Top Wireless Earbuds in India (Best Value to Flagship)\n\n"
                        "• **Budget King (Under ₹2,000)**: **boAt Airdopes 141 ANC** (₹1,499) — 32dB ANC, 42H battery, low latency beast.\n"
                        "• **Mid-Range Champion (Under ₹5,000)**: **Realme Buds Air 6 Pro** (₹4,999) — 50dB ANC, Hi-Res LDAC audio, dual drivers.\n"
                        "• **Flagship Excellence (Under ₹10,000)**: **OnePlus Buds Pro 2** (₹8,999) — Dynaudio tuning, Spatial Audio, 48dB ANC.\n"
                        "• **Ultimate Audiophile Pick**: **Sony WF-1000XM5** (₹24,990) — Industry-leading noise cancellation & LDAC Hi-Res sound."
                    )
                )

            if any(w in lowered for w in ["keyboard", "keyboards", "mechanical keyboard", "gaming keyboard"]):
                keyboards = self.catalog.search("keyboard", limit=4)
                if keyboards:
                    return self._structured_response(keyboards)
                return ChatResponse(
                    answer=(
                        "### ⌨️ Top Mechanical Keyboards in India (Budget to Premium)\n\n"
                        "• **Best Budget TKL (Under ₹2,500)**: **Cosmic Byte CB-GK-16 Firefly** (₹2,199) — Outemu Blue tactile clicky switches, per-key RGB.\n"
                        "• **Best Durable Gaming (Under ₹3,500)**: **Redragon K552 Kumara RGB** (₹2,790) — Metal base, red linear switches, splash-proof.\n"
                        "• **Best Wireless & Typing (Under ₹8,000)**: **Keychron K2 V2 Wireless** (₹7,999) — Hot-swappable Gateron Brown, Mac/Win support, 4000mAh battery."
                    )
                )

            # Fallback 4: General catalog recommendation
            all_products = self.catalog.search("", limit=4)
            if all_products:
                return self._structured_response(all_products)

            return ChatResponse(
                answer=(
                    "I searched verified Indian catalogs. Try asking for **'Best wireless earbuds under ₹2,000'**, **'Mechanical keyboard for gaming'**, or **'Compare iPhone 15 vs OnePlus 12'**!"
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
