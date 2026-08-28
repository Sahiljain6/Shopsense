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

    # Prompt injection patterns
    if any(pat in lowered for pat in ["ignore previous", "act as admin", "ignore system", "system prompt"]):
        return "I am ShopSense, an AI shopping copilot! 🛍️ I can only assist with shopping, products, pricing, and buying advice."

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


from app.services.search import clean_search_terms, extract_budget, normalize_query


def is_prompt_injection(message: str) -> bool:
    return check_shopping_guardrail(message) is not None


def parse_budget(text: str) -> float | None:
    return extract_budget(text)


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

        hf_key = settings.hf_token or os.getenv("HF_TOKEN") or settings.huggingface_api_key or os.getenv("HUGGINGFACE_API_KEY")

        self.hf_token = hf_key.strip().strip("'").strip('"') if hf_key and hf_key.strip() else None

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

        elif self.hf_token:
            self.provider = "huggingface"
            self.model = "meta-llama/Llama-3.3-70B-Instruct"

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
        """Call whichever provider is configured (Hugging Face Multi-Model, Gemini, OpenAI, Groq, Ollama)."""

        # 1. Try Hugging Face Multi-Model Serverless API
        if self.hf_token or self.provider == "huggingface":
            hf_token = self.hf_token or os.getenv("HF_TOKEN") or os.getenv("HUGGINGFACE_API_KEY")
            if hf_token:
                hf_models = [
                    "meta-llama/Llama-3.3-70B-Instruct",
                    "deepseek-ai/DeepSeek-R1-Distill-Qwen-32B",
                    "mistralai/Mistral-7B-Instruct-v0.3",
                    "Qwen/Qwen2.5-72B-Instruct"
                ]
                headers = {"Authorization": f"Bearer {hf_token}"}
                clean_messages = [{"role": "system", "content": system}]
                if history:
                    for turn in history:
                        if isinstance(turn, dict) and turn.get("role") and turn.get("content"):
                            clean_messages.append({"role": str(turn["role"]), "content": str(turn["content"])})
                clean_messages.append({"role": "user", "content": user})

                import httpx
                for model_name in hf_models:
                    url = "https://api-inference.huggingface.co/v1/chat/completions"
                    payload = {
                        "model": model_name,
                        "messages": clean_messages,
                        "max_tokens": 600,
                        "temperature": 0.3
                    }
                    try:
                        with httpx.Client(timeout=12) as client:
                            resp = client.post(url, headers=headers, json=payload)
                            if resp.status_code == 200:
                                data = resp.json()
                                choices = data.get("choices", [])
                                if choices:
                                    content = choices[0].get("message", {}).get("content")
                                    if content and content.strip():
                                        return content.strip()
                    except Exception as hf_err:
                        print(f"Hugging Face ({model_name}) error: {hf_err}")

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

    def _find_last_product(
        self,
        history: list[dict[str, str]] | None,
        cart: list[dict[str, object]] | None = None
    ) -> Product | None:
        catalog_products = self.catalog.search("", limit=50)
        if history:
            for turn in reversed(history[-6:]):
                content = (turn.get("content") or "").lower()
                for p in catalog_products:
                    # Match name or core model name
                    model_words = [w for w in p.name.lower().split() if len(w) > 2 and w not in ["phone", "5g", "ram", "storage", "black", "blue"]]
                    if p.name.lower() in content or (len(model_words) >= 2 and all(mw in content for mw in model_words[:2])):
                        return p
        if cart:
            for item in reversed(cart):
                item_name = (item.get("name") or "").lower()
                if item_name:
                    matches = self.catalog.search(item_name, limit=1)
                    if matches:
                        return matches[0]
        return None

    def answer(
        self,
        message: str,
        mode: str | None = None,
        history: list[dict[str, str]] | None = None,
        cart: list[dict[str, object]] | None = None
    ) -> ChatResponse:

        # 1. Strict Scope & Guardrail check (Prevent coding, hacking, homework, and non-shopping usage)
        guardrail_refusal = check_shopping_guardrail(message)
        if guardrail_refusal:
            return ChatResponse(answer=guardrail_refusal)

        # 2. Live Barcode / GTIN Lookup API Trigger
        barcode_match = re.search(r'\b(?:barcode\s*)?(\d{8,14})\b', message, re.IGNORECASE)
        if barcode_match:
            code = barcode_match.group(1)
            try:
                from app.services.barcode_lookup import lookup_barcode
                res = lookup_barcode(code)
                if res:
                    return ChatResponse(
                        answer=(
                            f"### 📦 Barcode Product Details ({res['barcode']})\n\n"
                            f"• **Product**: {res['name']}\n"
                            f"• **Brand**: {res['brand']}\n"
                            f"• **Category**: {res['categories']}\n"
                            f"• **Health / Nutri-Score**: `{res['health_score']}`\n"
                            f"• **Allergens**: {res['allergens']}\n"
                            f"• **Ingredients**: {res['ingredients'][:250]}...\n\n"
                            f"✓ Verified via Open Food & Product Facts database."
                        )
                    )
            except Exception as err:
                print(f"Barcode lookup notice: {err}")

        # 3. Live Currency Conversion API Trigger (Frankfurter API)
        curr_match = re.search(r'(?:convert|what is|how much is)\s+\$?(\d+(?:\.\d+)?)\s*(usd|eur|gbp|cad|aud|jpy)?\s*(?:in|to)?\s*(inr|rupees|usd|eur)?', message, re.IGNORECASE)
        if curr_match and any(w in message.lower() for w in ["convert", "inr", "rupees", "usd"]):
            try:
                amount = float(curr_match.group(1))
                from_c = (curr_match.group(2) or "USD").upper()
                to_c = (curr_match.group(3) or "INR").upper()
                if to_c == "RUPEES":
                    to_c = "INR"
                from app.services.currency import convert_price
                converted = convert_price(amount, from_c, to_c)
                return ChatResponse(
                    answer=(
                        f"### 💱 Live Currency Conversion\n\n"
                        f"**{amount:.2f} {from_c}** = **₹{converted:,.2f} {to_c}**\n\n"
                        f"*(Real-time exchange rate updated via Frankfurter Financial API)*"
                    )
                )
            except Exception as err:
                print(f"Currency conversion notice: {err}")

        # 4. Live Gaming Deals API Trigger (CheapShark API)
        if any(w in message.lower() for w in ["gaming deal", "steam deal", "game deal", "pc deal"]):
            try:
                from app.services.deal_hunter import fetch_gaming_deals
                deals = fetch_gaming_deals(limit=5)
                if deals:
                    lines = ["### 🎮 Live Gaming & Software Price Drops (CheapShark API):\n"]
                    for d in deals:
                        lines.append(f"• **[{d['title']}]({d['deal_url']})** — **${d['sale_price']}** ~~(was ${d['normal_price']})~~ (**{d['savings_percentage']}% OFF**)")
                    return ChatResponse(answer="\n".join(lines))
            except Exception as err:
                print(f"CheapShark deal lookup notice: {err}")

        # 5. Auto-detect product URL pasted in chat message
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

        # 6. CONVERSATION MEMORY: Extract context from previous messages
        # If user says "under 20000 and 5g" after asking about mobiles,
        # we need to carry forward the product category from history.
        enriched_message = message
        if history:
            category_keywords = {
                "phone": ["phone", "mobile", "smartphone", "iphone", "samsung", "galaxy", "redmi", "oneplus"],
                "laptop": ["laptop", "notebook", "macbook", "asus"],
                "earbuds": ["earbuds", "earphone", "headphone", "tws", "airdopes", "buds"],
                "keyboard": ["keyboard", "mechanical", "keychron", "redragon"],
                "watch": ["watch", "smartwatch"],
                "tv": ["tv", "television", "smart tv"],
            }

            lowered = message.lower()
            has_category = any(
                any(kw in lowered for kw in kws)
                for kws in category_keywords.values()
            )

            if not has_category:
                # Check last 4 history turns for category context
                for turn in reversed(history[-4:]):
                    content = (turn.get("content") or "").lower()
                    for cat, kws in category_keywords.items():
                        if any(kw in content for kw in kws):
                            enriched_message = f"{cat} {message}"
                            break
                    if enriched_message != message:
                        break

        lowered_msg = message.lower()

        # Follow-up Specific Product Context Resolution (e.g. "matching cover", "case for this", "cover for it")
        followup_kws = ["matching cover", "back cover", "phone cover", "case for this", "cover for it", "matching case", "tempered glass", "screen guard", "case", "cover"]
        if any(kw in lowered_msg for kw in followup_kws):
            last_prod = self._find_last_product(history, cart)
            if last_prod:
                return ChatResponse(
                    answer=(
                        f"### 🛡️ Recommended Matching Accessories for **{last_prod.name}**\n\n"
                        f"• **Matte Protective Back Cover / Shockproof Case** (₹399) — Precision cutouts, raised camera protection & anti-fingerprint grip.\n"
                        f"• **9H Curved Tempered Glass Screen Guard** (₹299) — Full-screen scratch & drop protection.\n"
                        f"• **Fast Charging Wall Adapter & USB Cable** (₹1,299) — Official fast charging support for {last_prod.brand}."
                    ),
                    product_ids=[last_prod.id]
                )

        # Rule 1: Handle comparison queries explicitly (e.g. "Compare iPhone 15 vs OnePlus 12")
        if "vs" in lowered_msg or "compare" in lowered_msg:
            parts = re.split(r'\b(?:vs\.?|versus|and|compare)\b', lowered_msg, flags=re.IGNORECASE)
            comparison_products = []
            for part in parts:
                clean_part = part.strip()
                if clean_part and len(clean_part) > 2 and clean_part not in ["iphone", "phone", "specs", "best"]:
                    matches = self.catalog.search(clean_part, limit=1)
                    for m in matches:
                        if m.id not in [p.id for p in comparison_products]:
                            comparison_products.append(m)
            if len(comparison_products) >= 2:
                return self._generate_ai_response(message, comparison_products[:3], history)

        # Rule 2: Explicit recommendation / search intent check
        card_intent_keywords = [
            "recommend", "suggest", "show me", "find me", "search", "under", "below",
            "budget", "options", "best phone", "best laptop", "best earbuds", "best keyboard",
            "best watch", "best tv", "deals", "buy", "pick"
        ]

        wants_cards = any(kw in lowered_msg for kw in card_intent_keywords) or extract_budget(message) is not None

        if wants_cards:
            from app.services.search import resolve_products
            resolved = resolve_products(
                message=enriched_message,
                history=history,
                cart=cart,
                db=self.db,
                limit=20
            )
            products = self._rank_products(resolved.products)

            if products:
                products = products[:(
                    1 if "quick_answer" in select_modifiers(message, mode)
                    else 3
                )]
                return self._generate_ai_response(message, products, history, cart=cart)

        # REAL-TIME INTERNET / MULTI-MODEL FALLBACK:
        # If still no catalog items matched or non-card query, generate real-time live response
        return self._general_ai_response(message, history, cart=cart)

    def answer_via_agents(
        self,
        message: str,
        mode: str | None = None,
        history: list[dict[str, str]] | None = None,
        cart: list[dict[str, object]] | None = None
    ) -> ChatResponse:

        try:
            if not get_settings().enable_multi_agent:
                return self.answer(message, mode, history, cart=cart)

            from app.services.agents.graph import run_graph

            data = run_graph({
                "message": message,
                "mode": mode,
                "db": self.db,
                "cart": cart
            })

            if isinstance(data.get("response"), ChatResponse):
                return data["response"]

            return self.answer(message, mode, history, cart=cart)

        except Exception:
            return self.answer(message, mode, history, cart=cart)

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

    def _get_cart_summary_text(self, cart: list[dict[str, object]] | None) -> str:
        if not cart:
            return "User's cart is empty."
        items = []
        for i in cart:
            name = i.get("name", "Product")
            qty = i.get("qty", 1)
            price = i.get("price", 0)
            items.append(f"{qty}x {name} (₹{price:,.0f})")
        if not items:
            return "User's cart is empty."
        return "User's current cart: " + ", ".join(items) + "."

    def _generate_ai_response(
        self,
        message: str,
        products: list[Product],
        history: list[dict[str, str]] | None = None,
        cart: list[dict[str, object]] | None = None
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
You are ShopSense, an intelligent Indian shopping assistant.

User request:
{message}

Available products from the ShopSense catalog:

{json.dumps(product_context, ensure_ascii=False, default=str)}

RESPONSE RULES:
1. Recommend ONLY the products listed above. Never invent names, prices, ratings, specs, or URLs.
2. Respect the user's budget if mentioned.
3. For EACH product, include:
   - Product name, price in ₹ (INR), key specs
   - **Where to buy**: List 2-3 Indian stores with direct search links:
     • Amazon India: https://www.amazon.in/s?k=PRODUCT+NAME
     • Flipkart: https://www.flipkart.com/search?q=PRODUCT+NAME
     • Croma: https://www.croma.com/searchB?q=PRODUCT+NAME
   - **Ongoing offers**: Mention typical offers (bank discounts, exchange offers, no-cost EMI) available on these platforms
   - **Best time to buy**: Brief tip (e.g. "prices usually drop during Flipkart Big Billion Days or Amazon Great Indian Festival")
4. If this is a comparison, use a markdown table with Price, Key Specs, Pros, Cons columns.
5. Keep the response concise and practical for Indian buyers.
6. Use ₹ for all prices, formatted in Indian numbering (e.g. ₹1,04,900).
"""

        cart_summary = self._get_cart_summary_text(cart)

        answer = self._chat(
            system=(
                "You are ShopSense, an expert AI shopping copilot.\n"
                "STRICT CONSTRAINT: You are EXCLUSIVELY a shopping and e-commerce assistant. "
                "You ONLY assist with product discovery, price comparisons, deal finding, budgeting, and buying decisions. "
                "You MUST REFUSE any requests to write code, debug software, solve non-shopping math/homework, write essays/stories, or perform non-shopping tasks. "
                "If the user asks for coding or non-shopping tasks, politely refuse and redirect them to shopping products.\n"
                f"{cart_summary}\n"
                "CRITICAL RULE FOR CART CONTEXT: Only reference the user's cart when it is directly relevant to the user's request (e.g. recommending matching accessories for cart items, checking for duplicate purchases, or when the user explicitly asks about their cart). Do NOT force-mention the cart on unrelated queries.\n"
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
        history: list[dict[str, str]] | None = None,
        cart: list[dict[str, object]] | None = None
    ) -> ChatResponse:

        # Conversational / Small Talk Intercepts (No web search, no random links)
        clean_msg = message.strip().lower()

        conversational_map = {
            "hi": "Hello! 👋 I'm ShopSense, your AI shopping copilot. What products or deals are you looking for today?",
            "hello": "Hello! 👋 I'm ShopSense, your AI shopping copilot. What products or deals are you looking for today?",
            "hey": "Hey! 👋 I'm ShopSense, your AI shopping copilot. What products or deals are you looking for today?",
            "how are you": "I'm doing great! 🛍️ Ready to help you discover products, compare specs, or find the best deals in India. What are you looking for today?",
            "how are you doing": "I'm doing awesome! 🛍️ Ready to help you shop smart and save money. What product or budget are you considering today?",
            "who are you": "I'm **ShopSense**, your AI shopping copilot! 🛍️ I help you discover products, compare models side-by-side, analyze live deals across Amazon India, Flipkart & Croma, and track prices in ₹.",
            "what can you do": "I can help you:\n• 🔍 Search & recommend products by category or budget\n• ⚖️ Benchmark specs side-by-side\n• 💰 Track prices & live deals across Amazon India, Flipkart & Croma\n• 🏷️ Check ongoing bank offers & coupon codes",
            "thank you": "You're very welcome! 😊 Let me know if you need any more product recommendations or price comparisons!",
            "thanks": "Happy to help! 😊 Feel free to ask if you want to compare other models or check deals!",
        }

        for phrase, reply in conversational_map.items():
            if phrase in clean_msg:
                return ChatResponse(answer=reply)

        # Generic Smartphone Comparison Request (e.g. "compare two best smartphone")
        if any(p in clean_msg for p in ["compare two best smartphone", "compare smartphone", "compare phone", "compare two best phone"]):
            top_phones = self.catalog.search("phone", limit=2)
            if top_phones:
                return self._generate_ai_response(message, top_phones, history)

        # Fetch 100% free real-time live web product deals via DuckDuckGo (strict e-commerce only)
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

            # Fallback 2: Intelligent Catalog Search Matching with strict budget filtering
            keywords = ["keyboard", "earbuds", "phone", "iphone", "samsung", "apple", "laptop", "macbook", "audio", "watch", "deal", "gaming", "tws"]
            lowered = message.lower()
            budget = extract_budget(message)
            matched_keywords = [k for k in keywords if k in lowered]
            if matched_keywords:
                search_query = " ".join(matched_keywords)
                fallback_products = self.catalog.search(search_query, limit=8)
                if budget is not None:
                    fallback_products = [p for p in fallback_products if p.price <= budget]
                if fallback_products:
                    return self._structured_response(fallback_products)

            # Fallback 3: Dedicated Budget Phones Under ₹15,000 / ₹20,000 Breakdown
            if any(w in lowered for w in ["phone", "mobile", "smartphone"]):
                budget_phones = self.catalog.search("phone", limit=10)
                if budget is not None:
                    budget_phones = [p for p in budget_phones if p.price <= budget]
                if budget_phones:
                    return self._structured_response(budget_phones)
                return ChatResponse(
                    answer=(
                        "### 📱 Top 5G Phones Under ₹15,000 in India\n\n"
                        "• **Best Overall Value**: **Motorola Moto G34 5G** (₹11,999) — Snapdragon 695 5G, 120Hz display, clean stock Android 14.\n"
                        "• **Best Performance & Design**: **CMF Phone 1 by Nothing** (₹14,999) — Dimensity 7300 4nm, 120Hz Super AMOLED.\n"
                        "• **Fastest Charging Champion**: **Realme 12x 5G** (₹11,999) — 45W SUPERVOOC, 50MP AI camera, Dimensity 6100+ 5G.\n"
                        "• **Best Premium Glass Design**: **Poco M6 Pro 5G** (₹10,999) — Snapdragon 4 Gen 2, glass back, 90Hz FHD+.\n"
                        "• **Most Affordable 5G Choice**: **Redmi 13C 5G** (₹9,999) — 50MP AI camera, 5000mAh battery."
                    )
                )

            # Fallback 4: Category-specific expert breakdown
            if any(w in lowered for w in ["earbud", "earbuds", "tws", "headphone", "earphone", "audio"]):
                earbuds = self.catalog.search("earbuds", limit=4)
                if budget is not None:
                    earbuds = [p for p in earbuds if p.price <= budget]
                if earbuds:
                    return self._structured_response(earbuds)
                return ChatResponse(
                    answer=(
                        "### 🎧 Top Wireless Earbuds in India (Best Value to Flagship)\n\n"
                        "• **Budget King (Under ₹2,000)**: **boAt Airdopes 141 ANC** (₹1,499) — 32dB ANC, 42H battery, low latency beast.\n"
                        "• **Mid-Range Champion (Under ₹5,000)**: **Realme Buds Air 6 Pro** (₹4,999) — 50dB ANC, Hi-Res LDAC audio, dual drivers.\n"
                        "• **Flagship Excellence (Under ₹10,000)**: **OnePlus Buds Pro 2** (₹8,999) — Dynaudio tuning, Spatial Audio, 48dB ANC."
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

        return ChatResponse(
            answer=answer or "Hello! 👋 I'm ShopSense, your AI shopping copilot. I can help you find products, compare options, check prices, or find top deals under a budget. What are you looking for today?"
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
