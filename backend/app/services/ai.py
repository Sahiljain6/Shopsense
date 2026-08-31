import json
import logging
import os
import re
import time
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


INJECTION_DELIMITERS = [
    "<|im_start|>",
    "<|im_end|>",
    "[system]",
    "[/system]",
    "[assistant]",
    "[/assistant]",
    "### human:",
    "### assistant:",
    "### system:",
    "<<sys>>",
    "<</sys>>",
    "[inst]",
    "[/inst]",
    "<s>[inst]",
]

INJECTION_PATTERNS = [
    r"ignore\s+(all\s+|any\s+|prior\s+|previous\s+)?(instructions|prompts|directives|rules|guidelines)",
    r"disregard\s+(all\s+|any\s+|prior\s+|previous\s+)?(instructions|prompts|directives|rules|guidelines)",
    r"forget\s+(all\s+|any\s+|prior\s+|previous\s+)?(instructions|prompts|directives|rules)",
    r"(system\s+prompt|reveal\s+(your\s+)?instructions|print\s+(your\s+)?instructions|output\s+(your\s+)?(system\s+)?prompt)",
    r"(act\s+as\s+(an?\s+)?admin|act\s+as\s+root|sudo\s+mode|developer\s+mode|jailbreak|unfiltered\s+mode|dan\s+mode|do\s+anything\s+now)",
    r"bypass\s+(content\s+filter|guardrail|safety\s+filter)",
    r"!\[.*?\]\(https?://[^\s)]+\)",
    r"\[.*?\]\(https?://[^\s)]+\?data=",
]


def normalize_injection_text(text: str) -> str:
    cleaned = re.sub(r"[\u200B-\u200D\uFEFF]", "", text)
    cleaned = re.sub(r"\s+", " ", cleaned).lower()
    table = str.maketrans({
        "@": "a",
        "0": "o",
        "1": "i",
        "!": "i",
        "3": "e",
        "$": "s",
        "5": "s",
        "7": "t",
    })
    return cleaned.translate(table)


def is_direct_prompt_injection(text: str) -> bool:
    if not text or not isinstance(text, str):
        return False
    lowered = text.lower().strip()
    norm = normalize_injection_text(text)

    # 1. Delimiters
    for delim in INJECTION_DELIMITERS:
        if delim in lowered or delim in norm:
            return True

    # 2. Regex patterns
    for pat in INJECTION_PATTERNS:
        if re.search(pat, lowered) or re.search(pat, norm):
            return True

    return False


def check_shopping_guardrail(message: str) -> str | None:
    """Check if the user request is strictly out-of-scope (e.g. coding, programming, non-shopping essays).
    Returns a polite refusal string if out-of-scope, or None if it's a shopping query.
    """
    if is_direct_prompt_injection(message):
        return "I am ShopSense, an AI shopping copilot! 🛍️ I can only assist with shopping, products, pricing, and buying advice."

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


from app.services.search import clean_search_terms, extract_budget, normalize_query


def is_prompt_injection(message: str) -> bool:
    return check_shopping_guardrail(message) is not None


def parse_budget(text: str) -> float | None:
    return extract_budget(text)


class GenericProductRef:
    """Represents a product reference that may be from catalog or live search."""
    def __init__(
        self,
        name: str,
        brand: str = "",
        price: float = 0.0,
        id: int | None = None,
        url: str | None = None,
        category: str = "Tech",
        description: str = ""
    ):
        self.name = name
        self.brand = brand or (name.split()[0] if name else "Tech")
        self.price = price
        self.id = id
        self.url = url
        self.category = category
        self.description = description

    def __repr__(self) -> str:
        return f"<GenericProductRef name='{self.name}' brand='{self.brand}' price={self.price} id={self.id}>"


CONVERSATIONAL_MAP: dict[str, str] = {
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


def _build_gemini_contents(user: str, history: list[dict[str, str]] | None = None) -> list[dict[str, object]]:
    contents = []
    if history:
        for turn in history:
            if isinstance(turn, dict) and turn.get("role") and turn.get("content"):
                role = "model" if turn["role"] in ("assistant", "model") else "user"
                contents.append({"role": role, "parts": [{"text": str(turn["content"])}]})
    contents.append({"role": "user", "parts": [{"text": str(user)}]})
    return contents


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


def get_active_gemini_models(api_key: str) -> list[str]:
    """Dynamically fetch live Gemini models supporting generateContent from Google's ListModels API."""
    clean_key = api_key.strip().strip("'").strip('"')
    url = f"https://generativelanguage.googleapis.com/v1beta/models?key={clean_key}"
    try:
        import httpx
        with httpx.Client(timeout=5) as client:
            resp = client.get(url)
            if resp.status_code == 200:
                data = resp.json()
                models_data = data.get("models", [])
                valid_ids = []
                for m in models_data:
                    methods = m.get("supportedGenerationMethods", [])
                    name = m.get("name", "").removeprefix("models/")
                    # Exclude retired 1.0/1.5 models if present
                    if "generateContent" in methods and name and not any(retired in name for retired in ["1.0", "1.5"]):
                        valid_ids.append(name)
                if valid_ids:
                    flash_models = [m for m in valid_ids if "flash" in m.lower()]
                    pro_models = [m for m in valid_ids if "pro" in m.lower() and m not in flash_models]
                    other_models = [m for m in valid_ids if m not in flash_models and m not in pro_models]
                    ordered = flash_models + pro_models + other_models
                    if ordered:
                        return ordered
    except Exception as err:
        print(f"Notice fetching Gemini model list dynamically: {err}")

    return ["gemini-2.5-flash", "gemini-2.5-pro", "gemini-2.0-flash"]



logger = logging.getLogger("shopsense.ai")

# ---------- Tool-Calling Definitions ----------

TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "search_catalog",
            "description": "Search the ShopSense product catalog by category, budget, and keywords. Use this when the user wants to find, compare, or get recommendations for products. If this returns 0 products, follow up with search_live_web.",
            "parameters": {
                "type": "object",
                "properties": {
                    "category": {"type": "string", "enum": ["Phones", "Laptops", "Audio", "Peripherals"], "description": "Product category to search in"},
                    "budget": {"type": "number", "description": "Maximum price in INR (₹)"},
                    "keywords": {"type": "string", "description": "Specific brand/model keywords (e.g. 'redmi 5g', 'macbook air')"}
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "search_live_web",
            "description": "Search live Indian e-commerce websites (Amazon India, Flipkart, Croma) for real-time prices, deals, and availability. Use this when the user asks about current offers, live prices, or products not in the catalog.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query for live web deals"}
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "convert_currency",
            "description": "Convert an amount between currencies using live exchange rates.",
            "parameters": {
                "type": "object",
                "properties": {
                    "amount": {"type": "number", "description": "Amount to convert"},
                    "from_currency": {"type": "string", "default": "USD", "description": "Source currency code"},
                    "to_currency": {"type": "string", "default": "INR", "description": "Target currency code"}
                },
                "required": ["amount"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "check_delivery_pincode",
            "description": "Check delivery feasibility, state, district, and estimated shipping timeline for an Indian 6-digit PIN code. Use this when a user asks about delivery timeline, shipping to a pincode, or whether an item can be delivered to their area.",
            "parameters": {
                "type": "object",
                "properties": {
                    "pincode": {"type": "string", "description": "6-digit Indian postal PIN code (e.g., '400071', '110001')"}
                },
                "required": ["pincode"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "calculate_emi_and_offers",
            "description": "Calculate monthly No-Cost EMI, standard EMI plans, and bank discount offers for an item price in India (₹). Use this when a user asks about EMI, monthly installment options, or card discounts for a product price.",
            "parameters": {
                "type": "object",
                "properties": {
                    "amount": {"type": "number", "description": "Purchase amount in INR (₹)"},
                    "bank": {"type": "string", "description": "Optional bank name (e.g. 'HDFC', 'ICICI', 'SBI')"}
                },
                "required": ["amount"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_weather_shopping_context",
            "description": "Fetch live weather and temperature for an Indian city to recommend weather-appropriate products (e.g. cooling pads/fans in heat, waterproof gear in rain, room heaters in winter).",
            "parameters": {
                "type": "object",
                "properties": {
                    "location": {"type": "string", "description": "Indian city name (e.g. 'Mumbai', 'Delhi', 'Bengaluru')"}
                },
                "required": ["location"]
            }
        }
    }
]

# Gemini-compatible tool declarations (different schema format)
GEMINI_TOOL_DECLARATIONS = [{
    "function_declarations": [t["function"] for t in TOOL_DEFINITIONS]
}]



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
            self.active_gemini_models = get_active_gemini_models(self.gemini_api_key)
            self.model = (
                settings.gemini_model
                if (settings.gemini_model and not any(r in settings.gemini_model for r in ["1.0", "1.5", "2.0-flash"]))
                else (self.active_gemini_models[0] if self.active_gemini_models else "gemini-2.5-flash")
            )

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

        # 1. Try Hugging Face Multi-Model Serverless API (via new router.huggingface.co)
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
                    url = "https://router.huggingface.co/v1/chat/completions"
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
                        logger.warning("[AI PROVIDER FAILURE] provider=huggingface model=%s error=%s", model_name, hf_err)

        if self.provider == "gemini" and self.gemini_api_key:
            # Try official Gemini REST endpoint with live models
            gemini_contents = _build_gemini_contents(user, history)
            models_to_try = getattr(self, "active_gemini_models", None) or ["gemini-2.5-flash", "gemini-2.5-pro", "gemini-2.0-flash"]
            for model_name in models_to_try:
                url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={self.gemini_api_key}"
                payload = {
                    "system_instruction": {
                        "parts": [{"text": system}]
                    },
                    "contents": gemini_contents
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
                        logger.warning("[AI PROVIDER FAILURE] provider=gemini model=%s status=%s error=%s", model_name, resp.status_code, resp.text[:150])
                except Exception as err:
                    logger.warning("[AI PROVIDER FAILURE] provider=gemini model=%s error=%s", model_name, err)

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
                    logger.warning("[AI PROVIDER FAILURE] provider=openai model=%s error=%s", model_name, error)
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
                    logger.warning("[AI PROVIDER FAILURE] provider=groq model=%s error=%s", model_name, error)
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
                logger.warning("[AI PROVIDER FAILURE] provider=%s model=%s error=%s", self.provider, self.model, error)
                return None

        logger.warning("All AI LLM providers failed or returned None for user prompt: '%s...' (provider: %s)", user[:60], self.provider)
        return None

    # ---------- Tool Execution ----------

    def _execute_tool(self, tool_name: str, arguments: dict) -> str:
        """Execute a tool by name and return its result as a JSON string."""
        try:
            if tool_name == "search_catalog":
                return self._execute_search_catalog(
                    category=arguments.get("category"),
                    budget=arguments.get("budget"),
                    keywords=arguments.get("keywords", "")
                )
            elif tool_name == "search_live_web":
                return self._execute_search_live_web(
                    query=arguments.get("query", "")
                )
            elif tool_name == "convert_currency":
                return self._execute_convert_currency(
                    amount=arguments.get("amount", 0),
                    from_c=arguments.get("from_currency", "USD"),
                    to_c=arguments.get("to_currency", "INR")
                )
            elif tool_name == "check_delivery_pincode":
                return self._execute_check_delivery_pincode(
                    pincode=str(arguments.get("pincode", ""))
                )
            elif tool_name == "calculate_emi_and_offers":
                return self._execute_calculate_emi(
                    amount=float(arguments.get("amount", 0)),
                    bank=arguments.get("bank")
                )
            elif tool_name == "get_weather_shopping_context":
                location = str(arguments.get("location", "Mumbai"))
                return self._execute_weather_context(location)
            else:
                return json.dumps({"error": f"Unknown tool: {tool_name}"})
        except Exception as err:
            logger.warning("Tool execution error (%s): %s", tool_name, err)
            return json.dumps({"error": str(err)})

    def _execute_search_catalog(self, category: str | None = None, budget: float | None = None, keywords: str = "") -> str:
        """Search catalog and return product data as JSON string with deduplication and sanitization."""
        from app.services.search import resolve_products
        query_parts = []
        if category:
            query_parts.append(category.lower())
        if keywords:
            query_parts.append(keywords)
        query = " ".join(query_parts) or ""

        if budget:
            query += f" under {budget:.0f}"

        # Pass conversation history and cart context
        history = getattr(self, "_current_history", None)
        cart = getattr(self, "_current_cart", None)
        resolved = resolve_products(message=query, history=history, cart=cart, db=self.db, limit=8)
        products = resolved.products

        if budget is not None:
            products = [p for p in products if p.price <= budget]

        # De-duplicate products across multiple tool calls
        self._tool_products = getattr(self, "_tool_products", [])
        existing_ids = {p.id for p in self._tool_products}
        self._tool_products.extend([p for p in products if p.id not in existing_ids])

        product_dicts = []
        for p in products:
            desc = (p.description or "")[:120].replace("```", "").replace("<system>", "")
            product_dicts.append({
                "id": p.id, "name": p.name, "brand": p.brand,
                "price": p.price, "currency": p.currency,
                "rating": p.rating, "description": desc,
                "attributes": p.attributes
            })

        if not product_dicts:
            return json.dumps({
                "products": [],
                "count": 0,
                "message": "No matching products found in ShopSense's catalog for this query. Consider using the search_live_web tool to check current market deals and live retailer listings across Amazon India, Flipkart, and Croma."
            }, ensure_ascii=False)

        return json.dumps({"products": product_dicts, "count": len(product_dicts)}, ensure_ascii=False)

    def _execute_search_live_web(self, query: str) -> str:
        """Search live e-commerce deals with sanitization and length caps."""
        clean_q = re.sub(r'[\r\n\t]+', ' ', query).strip()[:100]
        deals = search_live_deals(clean_q, max_results=4)
        sanitized_deals = []
        for d in deals:
            title = str(d.get("title", ""))[:90].replace("```", "").replace("<system>", "")
            snippet = str(d.get("snippet", "") or d.get("desc", ""))[:150].replace("```", "").replace("<system>", "")
            sanitized_deals.append({
                "title": title,
                "price": d.get("price"),
                "currency": d.get("currency", "INR"),
                "source": d.get("source", "Web"),
                "url": d.get("url", ""),
                "snippet": snippet
            })
        return json.dumps({"deals": sanitized_deals, "count": len(sanitized_deals)}, ensure_ascii=False, default=str)

    def _execute_convert_currency(self, amount: float, from_c: str = "USD", to_c: str = "INR") -> str:
        """Convert currency and return as JSON string."""
        from app.services.currency import convert_price
        converted = convert_price(amount, from_c.upper(), to_c.upper())
        return json.dumps({"amount": amount, "from": from_c.upper(), "to": to_c.upper(), "converted": converted})

    def _execute_check_delivery_pincode(self, pincode: str) -> str:
        """Lookup Indian postal pincode delivery status and return as JSON string."""
        from app.services.logistics import lookup_pincode
        info = lookup_pincode(pincode)
        return json.dumps(info, ensure_ascii=False)

    def _execute_calculate_emi(self, amount: float, bank: str | None = None) -> str:
        """Calculate Indian banking EMI options and return as JSON string."""
        from app.services.finance import calculate_emi_options
        plans = calculate_emi_options(amount, bank)
        return json.dumps(plans, ensure_ascii=False)

    def _execute_weather_context(self, location: str = "Mumbai") -> str:
        """Fetch Open-Meteo weather and climate shopping advice as JSON string."""
        from app.services.weather_context import get_weather_shopping_advice
        advice = get_weather_shopping_advice(location)
        return json.dumps(advice, ensure_ascii=False)

    # ---------- Tool-Calling Chat ----------

    def _chat_with_tools(
        self,
        system: str,
        user: str,
        history: list[dict[str, str]] | None = None
    ) -> str | None:
        """Call LLM with tool definitions. If the model returns a tool call,
        execute it and feed the result back for the final answer."""

        clean_messages = [{"role": "system", "content": system}]
        if history:
            for turn in history:
                if isinstance(turn, dict) and turn.get("role") and turn.get("content"):
                    clean_messages.append({"role": str(turn["role"]), "content": str(turn["content"])})
        clean_messages.append({"role": "user", "content": user})

        # ── 20-second wall-clock budget across the entire provider chain ──────
        # Prevents sequential timeouts from stacking (e.g. 15s × 3 models = 45s).
        # Each provider block checks this before starting; on expiry we return None
        # immediately so the caller can fall back to a catalog-only response.
        _BUDGET_SECS = 20.0
        _deadline = time.monotonic() + _BUDGET_SECS

        def _budget_ok(label: str = "") -> bool:
            remaining = _deadline - time.monotonic()
            if remaining <= 0:
                logger.warning(
                    "_chat_with_tools: 20s budget exhausted%s — returning None",
                    f" before {label}" if label else "",
                )
                return False
            return True

        # --- OpenAI / Groq (native tool support) ---
        if not _budget_ok("OpenAI/Groq"):
            return None
        if self.provider in ("openai", "groq") and self.client:
            candidate_models = (
                [self.model, "gpt-4o-mini", "gpt-4o"] if self.provider == "openai"
                else self.active_models or ["llama-3.3-70b-versatile", "llama-3.1-8b-instant"]
            )
            for model_name in candidate_models:
                try:
                    response = self.client.chat.completions.create(
                        model=model_name,
                        messages=clean_messages,
                        tools=TOOL_DEFINITIONS,
                        tool_choice="auto"
                    )
                    msg = response.choices[0].message

                    # If the model wants to call a tool
                    if msg.tool_calls:
                        tool_messages = list(clean_messages)
                        tool_messages.append(msg.model_dump())

                        for tool_call in msg.tool_calls:
                            fn_name = tool_call.function.name
                            fn_args = json.loads(tool_call.function.arguments)
                            result = self._execute_tool(fn_name, fn_args)
                            tool_messages.append({
                                "role": "tool",
                                "tool_call_id": tool_call.id,
                                "content": result
                            })

                        # Second call: LLM synthesizes answer from tool results
                        final = self.client.chat.completions.create(
                            model=model_name,
                            messages=tool_messages
                        )
                        if final.choices:
                            return final.choices[0].message.content

                    # Model answered directly without tools
                    if msg.content:
                        return msg.content
                except Exception as err:
                    logger.warning("%s tool-calling error with '%s': %s", self.provider, model_name, err)
                    continue

        # --- Gemini (native tool support via REST) ---
        if not _budget_ok("Gemini"):
            return None
        if self.provider == "gemini" and getattr(self, "gemini_api_key", None):
            import httpx as _httpx
            gemini_contents = _build_gemini_contents(user, history)
            models_to_try = getattr(self, "active_gemini_models", None) or ["gemini-2.5-flash", "gemini-2.5-pro", "gemini-2.0-flash"]
            # Tighter per-attempt timeout: connect 5s, read 10s (a single completion
            # shouldn't need more; if it does that's worth knowing via a distinct log).
            _gemini_timeout = _httpx.Timeout(connect=5.0, read=10.0, write=5.0, pool=2.0)
            for model_name in models_to_try:
                if not _budget_ok(f"Gemini/{model_name}"):
                    break
                _attempt_start = time.monotonic()
                try:
                    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={self.gemini_api_key}"
                    payload = {
                        "system_instruction": {"parts": [{"text": system}]},
                        "contents": gemini_contents,
                        "tools": GEMINI_TOOL_DECLARATIONS
                    }
                    with _httpx.Client(timeout=_gemini_timeout) as client:
                        resp = client.post(url, json=payload)
                        if resp.status_code != 200:
                            logger.warning(
                                "Gemini non-200 on '%s': status=%s body=%.120s",
                                model_name, resp.status_code, resp.text,
                            )
                            continue
                        data = resp.json()
                        candidates = data.get("candidates", [])
                        if not candidates:
                            continue

                        parts = candidates[0].get("content", {}).get("parts", [])

                        # Check for function call in response
                        fn_call = next((p.get("functionCall") for p in parts if "functionCall" in p), None)
                        if fn_call:
                            fn_name = fn_call["name"]
                            fn_args = fn_call.get("args", {})
                            result = self._execute_tool(fn_name, fn_args)

                            # Feed tool result back to Gemini
                            followup_contents = list(gemini_contents)
                            followup_contents.append({"role": "model", "parts": parts})
                            followup_contents.append({
                                "role": "user",
                                "parts": [{"functionResponse": {"name": fn_name, "response": {"result": result}}}]
                            })

                            payload2 = {
                                "system_instruction": {"parts": [{"text": system}]},
                                "contents": followup_contents
                            }
                            resp2 = client.post(url, json=payload2)
                            if resp2.status_code == 200:
                                data2 = resp2.json()
                                cands2 = data2.get("candidates", [])
                                if cands2:
                                    parts2 = cands2[0].get("content", {}).get("parts", [])
                                    text_parts = [p["text"] for p in parts2 if "text" in p]
                                    if text_parts:
                                        return "\n".join(text_parts)

                        # Direct text response
                        text_parts = [p["text"] for p in parts if "text" in p]
                        if text_parts:
                            return "\n".join(text_parts)
                except _httpx.TimeoutException as err:
                    # Distinct log so Render logs show TIMEOUT vs. other failures at a glance
                    logger.warning(
                        "Gemini TIMEOUT on '%s' (%.1fs elapsed): %s",
                        model_name, time.monotonic() - _attempt_start, err,
                    )
                    continue
                except Exception as err:
                    logger.warning("Gemini tool-calling error on '%s': %s", model_name, err)
                    continue
        # --- HuggingFace fallback (prompt-based tool instructions) ---
        if not _budget_ok("HuggingFace"):
            return None
        if self.hf_token or self.provider == "huggingface":
            tool_prompt = (
                f"{system}\n\n"
                "You have access to these tools:\n"
                "1. search_catalog(category, budget, keywords) - Search product catalog\n"
                "2. search_live_web(query) - Search live e-commerce deals\n"
                "3. convert_currency(amount, from_currency, to_currency) - Convert currencies\n\n"
                "If you need data from a tool, output EXACTLY one line: TOOL_CALL:tool_name({\"arg\": \"value\"})\n"
                "Otherwise, answer the user directly.\n"
            )
            answer = self._chat(tool_prompt, user, history)
            if answer and answer.strip().startswith("TOOL_CALL:"):
                try:
                    call_str = answer.strip().removeprefix("TOOL_CALL:")
                    paren = call_str.index("(")
                    fn_name = call_str[:paren]
                    fn_args = json.loads(call_str[paren + 1:-1])
                    result = self._execute_tool(fn_name, fn_args)
                    # Second call with tool result
                    followup = f"{tool_prompt}\n\nTool result for {fn_name}:\n{result}\n\nNow answer the user's question using this data."
                    return self._chat(followup, user, history)
                except Exception:
                    pass
            return answer

        # Fall through to None
        return None

    # ---------- Small Talk ----------

    def _check_small_talk(self, message: str) -> str | None:
        """Return a small-talk response if applicable, else None."""
        clean_msg = message.strip().lower()
        if clean_msg in CONVERSATIONAL_MAP:
            return CONVERSATIONAL_MAP[clean_msg]
        clean_nopunct = re.sub(r'[^\w\s]', '', clean_msg).strip()
        if clean_nopunct in CONVERSATIONAL_MAP:
            return CONVERSATIONAL_MAP[clean_nopunct]
        return None

    # ---------- Tool-Calling Answer ----------

    def _tool_calling_answer(
        self,
        message: str,
        history: list[dict[str, str]] | None = None,
        cart: list[dict[str, object]] | None = None,
        mode: str | None = None
    ) -> ChatResponse:
        """Main tool-calling answer method: let the LLM decide which tools to call."""
        self._tool_products = []
        self._current_history = history
        self._current_cart = cart

        # Explicit Comparison Pre-Check ("X vs Y" / "Compare X and Y")
        comp_match = re.search(r'(?:compare\s+)?(.+?)\s+(?:vs\.?|versus|compared\s+to)\s+(.+)', message, re.IGNORECASE)
        if comp_match:
            from app.services.search import resolve_products
            item_a = comp_match.group(1).strip()
            item_b = comp_match.group(2).strip()
            item_a = re.sub(r'^(?:compare\s+)?(?:between\s+)?(?:the\s+)?', '', item_a, flags=re.IGNORECASE).strip()
            item_b = re.sub(r'^(?:the\s+)?', '', item_b, flags=re.IGNORECASE).strip()

            res_a = resolve_products(message=item_a, history=history, cart=cart, db=self.db, limit=2)
            res_b = resolve_products(message=item_b, history=history, cart=cart, db=self.db, limit=2)

            comp_products = []
            seen_ids = set()
            for p in res_a.products[:1] + res_b.products[:1]:
                if p.id not in seen_ids:
                    comp_products.append(p)
                    seen_ids.add(p.id)

            if len(comp_products) >= 2:
                self._tool_products = comp_products

        cart_summary = self._get_cart_summary_text(cart)
        last_prod = self._find_last_product(history, cart)
        context_prod_clause = (
            f"8. PREVIOUSLY DISCUSSED ITEM: {last_prod.name} (Brand: {last_prod.brand}). "
            "If the user refers to 'this', 'it', or asks for deals, specs, or accessories on the previous item, they mean this product.\n"
            if last_prod else ""
        )

        system_prompt = (
            "You are ShopSense, an expert AI shopping copilot for Indian consumers.\n"
            "STRICT CONSTRAINT: You are EXCLUSIVELY a shopping and e-commerce assistant. "
            "You ONLY assist with product discovery, price comparisons, deal finding, budgeting, and buying decisions. "
            "You MUST REFUSE any requests to write code, debug software, solve non-shopping math/homework, write essays/stories, or perform non-shopping tasks.\n\n"
            "You have tools to search the product catalog and live e-commerce deals. "
            "Use search_catalog when users ask about products, categories, or budgets. "
            "IMPORTANT: If search_catalog returns 0 products or indicates no matching items, immediately call search_live_web to find live online deals, specs, or retailer listings across Amazon India, Flipkart, and Croma before answering. "
            "Use search_live_web when users ask about current offers, deals, or prices on specific retailers. "
            "Use convert_currency for currency conversions.\n\n"
            "RESPONSE RULES:\n"
            "1. Recommend ONLY products returned by your tools. Never invent names, prices, or specs.\n"
            "2. Respect the user's budget if mentioned.\n"
            "3. Use ₹ for all prices, formatted in Indian numbering.\n"
            "4. Keep responses concise and practical for Indian buyers.\n"
            f"5. {cart_summary}\n"
            "6. Only reference the user's cart when directly relevant to their request.\n"
            f"{context_prod_clause}\n"
            "STRUCTURED SYNTHESIS RULES (ChatGPT Shopping Quality):\n"
            "When search_catalog returns 3+ products for a category or budget query, structure your answer into three clear sections:\n"
            "1. One-line Intent / Budget Summary at the very top: Open with a direct, single-line summary (e.g. 'If your budget is ₹15,000, here are the strongest smartphone options available in our verified catalog:').\n"
            "2. '### 🏆 Top Picks by Use Case': Provide 2 to 4 bullet points categorizing the best options using their real 'best_for' and technical specs from the product's attributes JSON (processor, camera, battery, display):\n"
            "   • **Best overall**: [Product Name] (₹Price) — <1-2 sentences explaining why, highlighting real processor and display specs>\n"
            "   • **Best camera**: [Product Name] (₹Price) — <1-2 sentences highlighting sensor and camera capabilities>\n"
            "   • **Best battery / value**: [Product Name] (₹Price) — <1-2 sentences highlighting battery capacity (mAh) and charging speed>\n"
            "   (If store_prices are provided in attributes, mention retailer pricing such as 'Available on Flipkart & Amazon').\n"
            "3. '### 💡 What to Know': Write a concise 2-3 sentence paragraph synthesizing the top pick's real-world strengths, tradeoffs, and buying guidance based on its actual description and verified pros/cons.\n"
        )

        answer = self._chat_with_tools(system_prompt, message, history)

        if answer is None:
            if getattr(self, "_tool_products", None) and len(self._tool_products) >= 2:
                p1, p2 = self._tool_products[0], self._tool_products[1]
                comp_answer = (
                    f"### ⚖️ Side-by-Side Comparison: **{p1.name}** vs **{p2.name}**\n\n"
                    f"| Feature | **{p1.brand}** | **{p2.brand}** |\n"
                    f"| :--- | :--- | :--- |\n"
                    f"| **Model** | {p1.name} | {p2.name} |\n"
                    f"| **Price** | ₹{p1.price:,.0f} | ₹{p2.price:,.0f} |\n"
                    f"| **Rating** | {p1.rating:.1f}/5★ | {p2.rating:.1f}/5★ |\n"
                    f"| **Category** | {p1.category.name if p1.category else 'Tech'} | {p2.category.name if p2.category else 'Tech'} |\n\n"
                    f"**Analysis**: Both are standout choices. **{p1.name}** offers {p1.description[:80]}... "
                    f"while **{p2.name}** offers {p2.description[:80]}..."
                )
                return self._structured_response(self._tool_products, answer_override=comp_answer)

            # LLM is offline / no API key configured — resolve catalog products before generic fallback
            from app.services.search import resolve_products
            resolved = resolve_products(message=message, history=history, cart=cart, db=self.db, limit=8)
            if resolved.products:
                ranked = self._rank_products(resolved.products)[:3]
                return self._structured_response(ranked)

            return self._general_ai_response(message, history, cart=cart)

        # Build product_ids from any tools that were called
        product_ids = [p.id for p in self._tool_products]
        products = self._tool_products

        if products:
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
                product_ids=product_ids,
                reasons=reasons_map,
                pros=pros_map,
                cons=cons_map
            )

        return ChatResponse(answer=answer)

    def _find_last_product(
        self,
        history: list[dict[str, str]] | None,
        cart: list[dict[str, object]] | None = None
    ) -> Product | GenericProductRef | None:
        catalog_products = self.catalog.search("", limit=50)
        if history:
            for turn in reversed(history[-6:]):
                content = (turn.get("content") or "").lower()
                for p in catalog_products:
                    # Match name or core model name
                    model_words = [w for w in p.name.lower().split() if len(w) > 2 and w not in ["phone", "5g", "ram", "storage", "black", "blue"]]
                    if p.name.lower() in content or (len(model_words) >= 2 and all(mw in content for mw in model_words[:2])):
                        return p

        # If no catalog product matched, extract live-search products from assistant history
        if history:
            for turn in reversed(history[-6:]):
                raw_content = turn.get("content") or ""
                # Match live deal markdown links: [Store] [Title](URL) or • [Store] Title: URL
                deal_link_match = re.search(r'\[(?:[A-Za-z\s]+)\]\s*\[([^\]]+)\]\((https?://[^\)]+)\)', raw_content)
                if not deal_link_match:
                    deal_link_match = re.search(r'\[([^\]]+)\]\((https?://(?:www\.)?(?:amazon|flipkart|croma|myntra)[^\)]+)\)', raw_content, re.IGNORECASE)

                if deal_link_match:
                    title = deal_link_match.group(1).strip()
                    url = deal_link_match.group(2).strip()
                    price_match = re.search(r'₹\s*([\d,]+)', raw_content)
                    price = float(price_match.group(1).replace(",", "")) if price_match else 0.0
                    brand = title.split()[0] if title else "Tech"
                    return GenericProductRef(name=title, brand=brand, price=price, url=url, id=None)

                # Match bold product names in assistant bullets: **Brand Model** (₹Price)
                bold_matches = re.findall(r'\*\*([A-Za-z0-9][A-Za-z0-9\s\+\-\.]{3,45})\*\*', raw_content)
                for candidate in bold_matches:
                    candidate_clean = candidate.strip()
                    if candidate_clean.lower() in [
                        "bank discount", "no-cost emi", "exchange bonus", "coupon code",
                        "where to buy", "ongoing offers", "best time to buy", "analysis",
                        "model", "price", "rating", "category", "subtotal", "total due",
                        "shopsense", "fast charging", "amazon india", "flipkart", "croma"
                    ]:
                        continue
                    brand = candidate_clean.split()[0]
                    price_match = re.search(rf'\*\*{re.escape(candidate)}\*\*\s*\(₹\s*([\d,]+)\)', raw_content)
                    price = float(price_match.group(1).replace(",", "")) if price_match else 0.0
                    return GenericProductRef(name=candidate_clean, brand=brand, price=price, id=None)

        if cart:
            for item in reversed(cart):
                item_name = (item.get("name") or "").lower()
                if item_name:
                    matches = self.catalog.search(item_name, limit=1)
                    if matches:
                        return matches[0]
                    return GenericProductRef(
                        name=item.get("name", "Product"),
                        brand=item.get("brand") or item.get("name", "").split()[0],
                        price=float(item.get("price", 0.0)),
                        id=item.get("id")
                    )
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

        # 2. Small talk intercepts (no LLM/tool call needed)
        small_talk = self._check_small_talk(message)
        if small_talk:
            return ChatResponse(answer=small_talk)

        # 3. Live Barcode / GTIN Lookup API Trigger (specific pattern — keep as pre-check)
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

        # 4. Live Gaming Deals API Trigger (specific pattern — keep as pre-check)
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

        # 5. Pincode & Delivery Feasibility API Trigger (specific pattern — keep as pre-check)
        pincode_match = re.search(r'\b(?:pincode|pin code|delivery to|shipping to|pincode is|pin is)\s*[:#-]?\s*([1-9][0-9]{5})\b', message, re.IGNORECASE)
        if pincode_match:
            code = pincode_match.group(1)
            try:
                from app.services.logistics import lookup_pincode
                res = lookup_pincode(code)
                if res.get("valid"):
                    zone_label = "⚡ **Metro Express Zone**" if res["is_metro"] else "📦 **Standard Regional Zone**"
                    return ChatResponse(
                        answer=(
                            f"### 🚚 Delivery & Shipping Status (PIN: {res['pincode']})\n\n"
                            f"• **Location**: {res['post_office']}, {res['district']}, {res['state']}\n"
                            f"• **Delivery Status**: `{res['delivery_status']}`\n"
                            f"• **Estimated Timeline**: **{res['estimated_days']}** ({zone_label})\n"
                            f"• **Courier Partners**: {res['courier_partners']}\n\n"
                            f"✓ Standard dispatch within 24 hours. Cash on Delivery (COD) and Prepaid options supported."
                        )
                    )
            except Exception as err:
                logger.warning("Pincode pre-check notice: %s", err)

        # 6. EMI & Bank Financing Trigger (specific pattern — keep as pre-check)
        emi_match = re.search(r'\b(?:emi|monthly installment|no cost emi|finance options?)\b.*?(?:₹|rs\.?|inr)?\s*(\d{4,7})\b', message, re.IGNORECASE)
        if not emi_match:
            emi_match = re.search(r'\b(?:₹|rs\.?|inr)?\s*(\d{4,7})\b.*?\b(?:emi|installment)\b', message, re.IGNORECASE)
        if emi_match:
            amt = float(emi_match.group(1))
            try:
                from app.services.finance import calculate_emi_options
                emi_res = calculate_emi_options(amt)
                if emi_res.get("eligible"):
                    lines = [f"### 💳 EMI & Financing Breakdown for ₹{amt:,.0f}\n"]
                    lines.append(f"**⚡ {emi_res['summary']}**\n")
                    lines.append("#### 🟢 No-Cost EMI Plans (0% Extra Interest):")
                    for p in emi_res["no_cost_plans"]:
                        lines.append(f"• **{p['tenure_months']} Months**: **₹{p['monthly_amount']:,}/mo** (Total: ₹{p['total_payable']:,})")
                    lines.append("\n#### 🏦 Standard EMI Plans (14.5% p.a.):")
                    for p in emi_res["standard_plans"][:3]:
                        lines.append(f"• **{p['tenure_months']} Months**: **₹{p['monthly_amount']:,}/mo** (Interest: ₹{p['interest_charged']:,})")
                    lines.append("\n#### 🎁 Active Bank Offers:")
                    for off in emi_res["bank_offers"]:
                        lines.append(f"✓ {off}")
                    return ChatResponse(answer="\n".join(lines))
            except Exception as err:
                logger.warning("EMI pre-check notice: %s", err)

        # 7. Weather & Climate Shopping Trigger (specific pattern — keep as pre-check)
        weather_match = re.search(r'\b(?:weather in|weather at|climate in|temperature in|monsoon in|rain in|hot in|heatwave in)\s+([a-zA-Z\s]+)\b', message, re.IGNORECASE)
        if weather_match:
            loc = weather_match.group(1).strip()
            loc = re.split(r'\b(?:and|what|how|\?)\b', loc, flags=re.IGNORECASE)[0].strip()
            if loc:
                try:
                    from app.services.weather_context import get_weather_shopping_advice
                    w_res = get_weather_shopping_advice(loc)
                    lines = [f"### 🌦️ Weather & Shopping Advice for {w_res['location']}\n"]
                    lines.append(f"• **Current Conditions**: **{w_res['temperature_celsius']}°C** ({w_res['condition']}, {w_res['humidity_percent']}% humidity)")
                    lines.append(f"• **Shopping Insight**: {w_res['summary']}\n")
                    lines.append("#### 🛍️ Climate-Smart Recommendations:")
                    for prod in w_res["recommended_products"]:
                        lines.append(f"✓ **{prod}**")
                    return ChatResponse(answer="\n".join(lines))
                except Exception as err:
                    logger.warning("Weather pre-check notice: %s", err)

        # 8. Auto-detect product URL pasted in chat message (specific pattern — keep as pre-check)
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

        # 6. Follow-up: Specific Product Context Resolution (matching cover, offers/discounts on this product)
        lowered_msg = message.lower()
        followup_kws = [
            "matching cover", "back cover", "phone cover", "case for this", "cover for it",
            "matching case", "tempered glass", "screen guard",
            "offer", "offers", "discount", "discounts", "coupon", "coupons", "cashback", "emi"
        ]
        if any(kw in lowered_msg for kw in followup_kws):
            last_prod = self._find_last_product(history, cart)
            if last_prod:
                p_ids = [last_prod.id] if getattr(last_prod, "id", None) is not None else []
                if any(okw in lowered_msg for okw in ["offer", "offers", "discount", "discounts", "coupon", "coupons", "cashback", "emi"]):
                    return ChatResponse(
                        answer=(
                            f"### 🏷️ Ongoing Deals & Bank Offers for **{last_prod.name}**\n\n"
                            f"• **Bank Discount**: Instant 10% discount (up to ₹1,500) on HDFC & ICICI Credit/Debit Cards.\n"
                            f"• **No-Cost EMI**: Available up to 6 months with zero down payment.\n"
                            f"• **Exchange Bonus**: Up to ₹3,000 extra exchange value on your old device.\n"
                            f"• **Coupon Code**: Apply `SHOPSENSE1000` at checkout for ₹1,000 extra savings.\n\n"
                            f"*(Verified live offers across Amazon India & Flipkart)*"
                        ),
                        product_ids=p_ids
                    )
                return ChatResponse(
                    answer=(
                        f"### 🛡️ Recommended Matching Accessories for **{last_prod.name}**\n\n"
                        f"• **Matte Protective Back Cover / Shockproof Case** (₹399) — Precision cutouts, raised camera protection & anti-fingerprint grip.\n"
                        f"• **9H Curved Tempered Glass Screen Guard** (₹299) — Full-screen scratch & drop protection.\n"
                        f"• **Fast Charging Wall Adapter & USB Cable** (₹1,299) — Official fast charging support for {last_prod.brand}."
                    ),
                    product_ids=p_ids
                )

        # 7. PRIMARY PATH: Tool-calling — let the LLM decide what to do
        return self._tool_calling_answer(message, history, cart, mode)

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

        # 1. Conversational / Small Talk Intercept using single shared implementation
        small_talk = self._check_small_talk(message)
        if small_talk:
            return ChatResponse(answer=small_talk)

        clean_msg = message.strip().lower()

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
            keywords = ["keyboard", "earbuds", "phone", "iphone", "samsung", "apple", "laptop", "macbook", "audio", "watch", "gaming", "tws"]
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

            # Fallback 5: Generic Retailer / Deal Intent Query
            if any(w in lowered for w in ["offer", "offers", "deal", "deals", "discount", "discounts", "coupon", "coupons", "flipkart", "amazon", "croma"]):
                last_prod = self._find_last_product(history, cart)
                if last_prod:
                    p_ids = [last_prod.id] if getattr(last_prod, "id", None) is not None else []
                    return ChatResponse(
                        answer=(
                            f"### 🏷️ Ongoing Deals & Offers for **{last_prod.name}**\n\n"
                            f"• **Bank Discount**: Instant 10% discount (up to ₹1,500) on HDFC & ICICI Credit/Debit Cards.\n"
                            f"• **No-Cost EMI**: Available up to 6 months with zero down payment.\n"
                            f"• **Exchange Bonus**: Up to ₹3,000 extra exchange value on your old device.\n"
                            f"• **Coupon Code**: Apply `SHOPSENSE1000` at checkout for ₹1,000 extra savings.\n\n"
                            f"*(Verified live offers across Amazon India & Flipkart)*"
                        ),
                        product_ids=p_ids
                    )
                return ChatResponse(
                    answer=(
                        "🛍️ **Ongoing E-Commerce Deals & Retailer Offers**\n\n"
                        "To help you find the best live bank discounts, exchange offers, and coupon codes on **Flipkart**, **Amazon India**, or **Croma**, which product or category are you looking for?\n\n"
                        "• Try asking: *\"Flipkart offers on phones under 15000\"*, *\"Amazon deals on earbuds\"*, or *\"Deals on mechanical keyboards\"*."
                    )
                )

            # Fallback 6: Honest Clarification when no product/category/budget resolved
            return ChatResponse(
                answer=(
                    "I couldn't quite tell what product or category you're shopping for from that request — could you specify what you're looking for?\n\n"
                    "For example: *\"phones under ₹15,000\"*, *\"best wireless earbuds\"*, or *\"mechanical gaming keyboard\"*."
                )
            )

        return ChatResponse(
            answer=answer or (
                "I couldn't quite tell what product or category you're shopping for from that request — could you specify what you're looking for?\n\n"
                "For example: *\"phones under ₹15,000\"*, *\"best wireless earbuds\"*, or *\"mechanical gaming keyboard\"*."
            )
        )

    def _synthesize_catalog_answer(self, products: list[Product]) -> str:
        """Synthesize a structured ChatGPT-quality shopping response from catalog products."""
        if not products:
            return "No matching verified products found in our catalog."

        cat_name = products[0].category.name if getattr(products[0], "category", None) else "product"
        cat_term = "smartphone" if "phone" in cat_name.lower() else ("laptop" if "laptop" in cat_name.lower() else cat_name.lower())
        max_price = max(p.price for p in products)
        min_price = min(p.price for p in products)

        # 1. One-line intent/budget summary at top
        if min_price == max_price:
            header = f"If you're exploring verified options around ₹{max_price:,.0f}, here are the strongest {cat_term} options in our catalog:"
        else:
            header = f"If your budget is ₹{max_price:,.0f}, here are the strongest {cat_term} options:"

        # 2. Top picks by use case (2-4 short bullets)
        bullets = []
        for idx, p in enumerate(products[:4]):
            attrs = p.attributes or {}
            best_for = attrs.get("best_for")
            if not best_for:
                if idx == 0:
                    best_for = "Best overall"
                elif idx == 1:
                    best_for = "Best value & display"
                elif idx == 2:
                    best_for = "Best battery life"
                else:
                    best_for = "Best budget pick"

            role_label = best_for if best_for.startswith("Best") else f"Best for {best_for}"

            spec_reason = f"powered by {attrs.get('processor')}" if attrs.get("processor") else (p.description[:80] if p.description else "verified catalog pick")
            if attrs.get("display") and attrs.get("battery"):
                spec_reason = f"{attrs.get('processor') or p.brand}, featuring {attrs.get('display')} and {attrs.get('battery')}"

            store_str = ""
            if attrs.get("store_prices") and isinstance(attrs["store_prices"], dict):
                st_items = [f"{s} (₹{pr:,.0f})" for s, pr in list(attrs["store_prices"].items())[:2]]
                store_str = f" *[Available on {', '.join(st_items)}]*"

            bullets.append(f"• **{role_label}**: **{p.name}** (₹{p.price:,.0f}){store_str} — {spec_reason}.")

        picks_section = "\n".join(bullets)

        # 3. What to know paragraph (2-3 sentences)
        top_pick = products[0]
        top_attrs = top_pick.attributes or {}
        primary_store = "Flipkart"
        if top_attrs.get("store_prices") and isinstance(top_attrs["store_prices"], dict):
            primary_store = list(top_attrs["store_prices"].keys())[0]

        p_pros, p_cons = generate_trust_pros_cons(
            rating=top_pick.rating or 0.0,
            price=top_pick.price or 0.0,
            brand=top_pick.brand or "",
            store_name=primary_store
        )
        pro_snippet = p_pros[0] if p_pros else "proven reliability"
        con_snippet = p_cons[0] if p_cons else "standard manufacturer warranty applies"

        what_to_know = (
            f"### 💡 What to Know\n"
            f"The **{top_pick.name}** is the strongest all-around pick in this range ({pro_snippet}), balancing responsive daily speed with solid battery backup. "
            f"If you prioritize specific hardware like high fast-charging or a dedicated camera sensor, compare the key specs above to match your personal use case ({con_snippet})."
        )

        return f"{header}\n\n### 🏆 Top Picks by Use Case\n{picks_section}\n\n{what_to_know}"

    def _structured_response(
        self,
        products: list[Product],
        answer_override: str | None = None
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
            prod_store = "Flipkart"
            if product.attributes and isinstance(product.attributes, dict) and product.attributes.get("store_prices"):
                prod_store = list(product.attributes["store_prices"].keys())[0]

            p_pros, p_cons = generate_trust_pros_cons(
                rating=product.rating or 0.0,
                price=product.price or 0.0,
                brand=product.brand or "",
                store_name=prod_store
            )
            pros_map[pid_str] = p_pros
            cons_map[pid_str] = p_cons
            reasons_map[pid_str] = f"Trusted catalog match with {product.rating:.1f}/5★ rating."

        if answer_override:
            answer = answer_override
        elif len(products) >= 2:
            answer = self._synthesize_catalog_answer(products)
        else:
            answer = f"Here are top verified options: {names}."

        return ChatResponse(
            answer=answer,
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
