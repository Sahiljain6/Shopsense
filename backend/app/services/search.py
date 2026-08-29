import difflib
import re
from dataclasses import dataclass
from sqlalchemy import or_, select
from sqlalchemy.orm import Session
from app.models.entities import Category, Product


CATEGORY_KEYWORDS = {
    "Phones": ["phone", "phones", "mobile", "mobiles", "smartphone", "smartphones", "cellphone", "cellphones", "iphone", "samsung", "galaxy", "redmi", "oneplus", "realme", "poco", "motorola", "moto", "cmf", "xiaomi"],
    "Laptops": ["laptop", "laptops", "notebook", "notebooks", "macbook", "asus", "tuf"],
    "Audio": ["earbuds", "earbud", "earphone", "earphones", "headphone", "headphones", "audio", "tws", "airdopes", "buds"],
    "Peripherals": ["keyboard", "keyboards", "mechanical keyboard", "gaming keyboard", "mouse", "watch", "smartwatch"]
}


def _matches_category(text: str, keywords: list[str]) -> bool:
    """Matches text against category keywords with space-insensitivity, normalization, and fuzzy matching."""
    lowered = text.lower()
    lowered_nospaces = re.sub(r'[\s\-_]+', '', lowered)

    for kw in keywords:
        kw_lower = kw.lower()
        # 1. Direct substring match
        if kw_lower in lowered:
            return True
        # 2. Spaceless match (e.g. "mac book" matches "macbook", "one plus" matches "oneplus", "i phone" matches "iphone")
        kw_nospaces = re.sub(r'[\s\-_]+', '', kw_lower)
        if kw_nospaces in lowered_nospaces:
            return True
        # 3. Fuzzy match for single words of length >= 4 (handles common typos like "mackbook", "samusng", "keybaord")
        if len(kw_nospaces) >= 4:
            for word in lowered.split():
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


def resolve_products(
    message: str,
    history: list[dict[str, str]] | None = None,
    cart: list[dict[str, object]] | None = None,
    db: Session | None = None,
    limit: int = 12
) -> ResolvedSearch:
    budget = extract_budget(message)
    normalized = normalize_query(message)
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
        category_name = resolve_category(message, history, cart, db)

        # 1. Primary Filter by Category Relationship & Budget in SQL
        if category_name:
            matched_cat = db.scalars(
                select(Category).where(Category.name.ilike(category_name))
            ).first()

            if matched_cat:
                stmt = select(Product).where(Product.category_id == matched_cat.id)
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
            fallback_stmt = select(Product)
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
