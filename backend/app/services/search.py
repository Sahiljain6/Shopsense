import difflib
import re
from dataclasses import dataclass
from sqlalchemy import or_, select
from sqlalchemy.orm import Session, selectinload
from app.models.entities import Category, Product


CATEGORY_KEYWORDS = {
    "Phones": ["phone", "phones", "mobile", "mobiles", "smartphone", "smartphones", "cellphone", "cellphones", "iphone", "samsung", "galaxy", "redmi", "oneplus", "realme", "poco", "motorola", "moto", "cmf", "xiaomi"],
    "Laptops": ["laptop", "laptops", "notebook", "notebooks", "macbook", "asus", "tuf"],
    "Audio": ["earbuds", "earbud", "earphone", "earphones", "headphone", "headphones", "audio", "tws", "airdopes", "buds"],
    "Peripherals": ["keyboard", "keyboards", "mechanical keyboard", "gaming keyboard", "mouse", "watch", "smartwatch"]
}


def _matches_category(text: str, keywords: list[str]) -> bool:
    """Match complete category terms while allowing common spacing and typo variants."""
    lowered = text.lower()
    words = re.findall(r"[a-z0-9]+", lowered)

    for kw in keywords:
        kw_lower = kw.lower()
        if re.search(rf"(?<!\w){re.escape(kw_lower)}(?!\w)", lowered):
            return True

        # Match compounds such as "mac book" -> "macbook" by joining adjacent
        # tokens, rather than substring-matching "phone" inside "headphones".
        kw_nospaces = re.sub(r"[\s\-_]+", "", kw_lower)
        for start_index in range(len(words)):
            joined = ""
            for end_index in range(start_index, min(start_index + 3, len(words))):
                joined += words[end_index]
                if joined == kw_nospaces:
                    return True

        # Fuzzy match only against a whole token, never a substring of a longer word.
        if len(kw_nospaces) >= 4:
            for word in words:
                if abs(len(word) - len(kw_nospaces)) <= 2:
                    if difflib.SequenceMatcher(None, word, kw_nospaces).ratio() >= 0.85:
                        return True

    return False

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

    # Spacing normalizations for common compound brands / models
    spacing_fixes = {
        r"\bmac\s+book\b": "macbook",
        r"\bone\s+plus\b": "oneplus",
        r"\bi\s+phone\b": "iphone",
        r"\bi\s+pad\b": "ipad",
        r"\bair\s+dopes\b": "airdopes",
        r"\bair\s+pods\b": "airpods",
        r"\breal\s+me\b": "realme",
        r"\bred\s+mi\b": "redmi",
    }
    for pattern, replacement in spacing_fixes.items():
        text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)

    # Word-boundary category normalizations (prevents 'earbuds' -> 'earbudss')
    replacements = {
        r"\bsmartphones?\b": "phone",
        r"\bmobiles?\b": "phone",
        r"\bcell\s*phones?\b": "phone",
        r"\bnotebooks?\b": "laptop",
        r"\b(?:mechanical\s+keyboards?|gaming\s+keyboards?|keyboards?)\b": "keyboard",
        r"\b(?:wireless\s+earbuds?|earphones?|earbuds?|tws|airdopes?)\b": "earbuds",
        r"\bheadsets?\b": "headphones",
        r"\bsmart\s*watch(?:es)?\b": "watch",
    }

    for pattern, replacement in replacements.items():
        text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)

    return text


def clean_search_terms(text: str, budget: float | None = None) -> str:
    """Clean action words, stop words, and budget numbers so SQL full-text search
    searches strictly for the core product category and model terms.
    Preserves model numbers (e.g. 12, 15, 24, 34, m3, m5) while stripping budget figures.
    """
    cleaned = re.sub(
        r'\b(?:search|me|give|find|show|recommend|suggest|under|below|budget|upto|up to|within|around|rs|inr|₹|less than)\b',
        ' ',
        text,
        flags=re.IGNORECASE
    )
    if budget is not None:
        b_int = int(budget)
        cleaned = re.sub(rf'\b{b_int}\b', ' ', cleaned)
        if b_int >= 1000 and b_int % 1000 == 0:
            cleaned = re.sub(rf'\b{b_int // 1000}k\b', ' ', cleaned, flags=re.IGNORECASE)

    # Remove 4+ digit standalone numbers which are prices (e.g. 15000, 20000), not model numbers (like 12, 15)
    cleaned = re.sub(r'\b\d{4,}\b', ' ', cleaned)
    # Remove standalone 'k' suffix prices like '15k', '20k'
    cleaned = re.sub(r'\b\d+k\b', ' ', cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r'\s+', ' ', cleaned).strip()
    return cleaned


@dataclass
class ResolvedSearch:
    query: str
    cleaned_query: str
    category_name: str | None
    budget: float | None
    products: list[Product]


def resolve_category(
    message: str,
    history: list[dict[str, str]] | None = None,
    cart: list[dict[str, object]] | None = None,
    db: Session | None = None
) -> str | None:
    for cat_name, kws in CATEGORY_KEYWORDS.items():
        if _matches_category(message, kws):
            return cat_name

    # Fallback to history turns if query has no explicit category keyword
    if history:
        for turn in reversed(history[-6:]):
            content = turn.get("content") or ""
            for cat_name, kws in CATEGORY_KEYWORDS.items():
                if _matches_category(content, kws):
                    return cat_name

    # Fallback to cart items if history has no category
    if cart and db:
        for item in reversed(cart):
            item_name = item.get("name") or ""
            if item_name:
                for cat_name, kws in CATEGORY_KEYWORDS.items():
                    if _matches_category(item_name, kws):
                        return cat_name

    return None



_ALTERNATIVE_FOLLOWUP_PATTERN = re.compile(
    r"\b(?:some\s+other(?:\s+(?:product|option|options|one|ones|choice|choices))?"
    r"|any\s+other(?:\s+(?:product|option|options|one|ones|choice|choices))?"
    r"|another\s+(?:option|product|one|choice)|other\s+options?"
    r"|different\s+(?:option|product|one|choice)|more\s+options?"
    r"|alternatives?|something\s+else|anything\s+else|something\s+better"
    r"|anything\s+better|cheaper\s+(?:option|one|alternative)|one\s+more)\b",
    re.IGNORECASE,
)


def is_alternative_follow_up(message: str) -> bool:
    """Return True for short requests that ask for a different recommendation."""
    text = (message or "").strip()
    return (
        len(text.split()) <= 10
        and bool(_ALTERNATIVE_FOLLOWUP_PATTERN.search(text))
    )


def _recent_category_context(
    history: list[dict[str, str]] | None,
) -> tuple[str | None, float | None, str]:
    """Find the most recent user-stated category and its budget, without LLM calls."""
    if not history:
        return None, None, ""

    recent = history[-12:]
    for turn in reversed(recent):
        if not isinstance(turn, dict) or turn.get("role") != "user":
            continue
        content = turn.get("content")
        if not isinstance(content, str) or not content.strip():
            continue
        category = resolve_category(content)
        if category:
            return category, extract_budget(content), content.strip()

    # Some clients only include assistant history (e.g. an imported chat). Use its
    # category as a last resort, but do not infer a budget from assistant prices.
    for turn in reversed(recent):
        if not isinstance(turn, dict) or turn.get("role") != "assistant":
            continue
        content = turn.get("content")
        if isinstance(content, str) and content.strip():
            category = resolve_category(content)
            if category:
                return category, None, content.strip()

    return None, None, ""


def resolve_follow_up_query(
    message: str,
    history: list[dict[str, str]] | None = None,
) -> str:
    """Resolve a short alternative request into a category/budget search query.

    This is deterministic and local: it reuses conversation context and adds no
    model/API call. Explicit current category and budget always take priority.
    """
    if not is_alternative_follow_up(message):
        return message

    current_category = resolve_category(message)
    current_budget = extract_budget(message)
    context_category, context_budget, context_text = _recent_category_context(history)

    category = current_category or context_category
    if not category:
        return message

    budget = current_budget
    if budget is None and (current_category is None or context_category == current_category):
        budget = context_budget

    source = message if current_category else context_text
    if category == "Audio":
        if re.search(r"\bheadphones?\b", source, re.IGNORECASE):
            term = "headphones"
        elif re.search(r"\bearphones?\b", source, re.IGNORECASE):
            term = "earphones"
        else:
            term = "earbuds"
    elif category == "Laptops":
        term = "laptops"
    elif category == "Phones":
        term = "phones"
    elif category == "Peripherals":
        if re.search(r"\b(?:smartwatches?|watches?)\b", source, re.IGNORECASE):
            term = "smartwatch"
        elif re.search(r"\bmice|mouse\b", source, re.IGNORECASE):
            term = "mouse"
        else:
            term = "keyboard"
    else:
        return message

    query = term
    if budget is not None:
        budget_text = str(int(budget)) if float(budget).is_integer() else f"{budget:g}"
        query += f" under ₹{budget_text}"
    return query


def _filter_previously_suggested(
    products: list[Product],
    history: list[dict[str, str]] | None,
) -> list[Product]:
    """Prefer catalog alternatives not named in recent assistant turns."""
    if not products or not history:
        return products

    assistant_text = " ".join(
        str(turn.get("content") or "")
        for turn in history[-6:]
        if isinstance(turn, dict) and turn.get("role") == "assistant"
    )
    normalized_history = re.sub(r"[^a-z0-9]+", "", assistant_text.casefold())
    if not normalized_history:
        return products

    alternatives = []
    for product in products:
        normalized_name = re.sub(r"[^a-z0-9]+", "", str(product.name).casefold())
        if normalized_name and len(normalized_name) >= 6 and normalized_name in normalized_history:
            continue
        alternatives.append(product)

    # Never turn a valid category search into an empty result set solely because
    # the conversation mentioned every available catalog item.
    return alternatives or products


def resolve_products(
    message: str,
    history: list[dict[str, str]] | None = None,
    cart: list[dict[str, object]] | None = None,
    db: Session | None = None,
    limit: int = 12
) -> ResolvedSearch:
    alternative_follow_up = is_alternative_follow_up(message)
    search_message = resolve_follow_up_query(message, history) if alternative_follow_up else message
    budget = extract_budget(search_message)
    normalized = normalize_query(search_message)
    cleaned = clean_search_terms(normalized, budget=budget)

    if db is None:
        return ResolvedSearch(
            query=message,
            cleaned_query=cleaned,
            category_name=None,
            budget=budget,
            products=[]
        )

    try:
        category_name = resolve_category(search_message, history, cart, db)

        # 1. Primary Filter by Category Relationship & Budget in SQL
        if category_name:
            matched_cat = db.scalars(
                select(Category).where(Category.name.ilike(category_name))
            ).first()

            if matched_cat:
                stmt = select(Product).options(selectinload(Product.category)).where(Product.category_id == matched_cat.id)
                if budget is not None:
                    stmt = stmt.where(Product.price <= budget)

                # Identify specific brand or model terms beyond generic category words
                generic_cat_words = {
                    "phone", "phones", "mobile", "mobiles", "smartphone", "smartphones",
                    "cellphone", "cellphones", "laptop", "laptops", "notebook", "notebooks",
                    "earbuds", "earbud", "earphone", "earphones", "headphone", "headphones",
                    "audio", "keyboard", "keyboards", "mouse", "watch", "smartwatch",
                    "under", "below", "budget", "show", "me", "give", "find", "best",
                    "good", "recommend", "suggest", "compare", "buy", "price",
                    "on", "in", "at", "for", "with", "and", "the", "a", "an", "to", "of",
                    "by", "from", "tell", "options", "products", "items"
                }

                specific_words = [
                    w for w in cleaned.split()
                    if w not in generic_cat_words
                    and len(w) >= 2
                ]

                if specific_words:
                    spec_stmt = stmt
                    for sw in specific_words:
                        spec_stmt = spec_stmt.where(
                            or_(
                                Product.name.ilike(f"%{sw}%"),
                                Product.brand.ilike(f"%{sw}%"),
                                Product.description.ilike(f"%{sw}%")
                            )
                        )
                    spec_stmt = spec_stmt.order_by(Product.rating.desc()).limit(limit)
                    spec_results = list(db.scalars(spec_stmt).all())
                    if spec_results:
                        return ResolvedSearch(
                            query=message,
                            cleaned_query=cleaned,
                            category_name=category_name,
                            budget=budget,
                            products=spec_results
                        )

                    # Specific model/brand was requested but not found in catalog.
                    # Return empty results so live web search can take over rather than
                    # returning unrelated top-rated products from the category.
                    return ResolvedSearch(
                        query=message,
                        cleaned_query=cleaned,
                        category_name=category_name,
                        budget=budget,
                        products=[]
                    )

                # Only if NO specific terms were in the query (e.g. "laptops under 60000"),
                # return top-rated products in that category.
                stmt = stmt.order_by(Product.rating.desc()).limit(limit)
                results = list(db.scalars(stmt).all())
                if alternative_follow_up:
                    results = _filter_previously_suggested(results, history)
                return ResolvedSearch(
                    query=message,
                    cleaned_query=cleaned,
                    category_name=category_name,
                    budget=budget,
                    products=results
                )

        # 2. If no category is resolved, perform strict product term matching
        non_product_words = {
            "fetch", "some", "offer", "offers", "deal", "deals", "discount", "discounts",
            "coupon", "coupons", "cashback", "emi", "flipkart", "amazon", "croma",
            "under", "below", "budget", "recommend", "suggest", "good", "best", "show",
            "me", "give", "find", "buy", "pick", "want", "need", "price", "today", "running",
            "tell", "options", "products", "items", "what", "which", "are", "there", "any",
            "on", "in", "at", "to", "of", "by", "for", "is", "an", "as", "or", "the", "with", "from"
        }

        terms = [
            t for t in cleaned.split()
            if len(t) >= 2
            and t not in non_product_words
            and not t.isdigit()
        ]

        if terms:
            fallback_stmt = select(Product).options(selectinload(Product.category))
            if budget is not None:
                fallback_stmt = fallback_stmt.where(Product.price <= budget)

            for t in terms:
                fallback_stmt = fallback_stmt.where(
                    or_(
                        Product.name.ilike(f"%{t}%"),
                        Product.brand.ilike(f"%{t}%"),
                        Product.description.ilike(f"%{t}%")
                    )
                )
            fallback_stmt = fallback_stmt.order_by(Product.rating.desc()).limit(limit)
            results = list(db.scalars(fallback_stmt).all())
        else:
            results = []

        return ResolvedSearch(
            query=message,
            cleaned_query=cleaned,
            category_name=category_name,
            budget=budget,
            products=results
        )
    except Exception as err:
        db.rollback()
        print(f"Notice during resolve_products DB query: {err}")
        return ResolvedSearch(
            query=message,
            cleaned_query=cleaned,
            category_name=None,
            budget=budget,
            products=[]
        )
