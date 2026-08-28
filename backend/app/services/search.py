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


def clean_search_terms(text: str) -> str:
    """Clean action words, stop words, and budget numbers so SQL full-text search
    searches strictly for the core product category (e.g. 'phone' instead of 'search me phone under 10000').
    """
    cleaned = re.sub(
        r'\b(?:search|me|give|find|show|recommend|suggest|under|below|budget|upto|up to|within|around|rs|inr|₹|less than|\d+k?)\b',
        ' ',
        text,
        flags=re.IGNORECASE
    )
    cleaned = re.sub(r'\b\d+\b', ' ', cleaned)
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
    lowered = message.lower()
    for cat_name, kws in CATEGORY_KEYWORDS.items():
        if any(kw in lowered for kw in kws):
            return cat_name

    # Fallback to history turns if query has no explicit category keyword
    if history:
        for turn in reversed(history[-6:]):
            content = (turn.get("content") or "").lower()
            for cat_name, kws in CATEGORY_KEYWORDS.items():
                if any(kw in content for kw in kws):
                    return cat_name

    # Fallback to cart items if history has no category
    if cart and db:
        for item in reversed(cart):
            item_name = (item.get("name") or "").lower()
            if item_name:
                for cat_name, kws in CATEGORY_KEYWORDS.items():
                    if any(kw in item_name for kw in kws):
                        return cat_name

    return None


def resolve_products(
    message: str,
    history: list[dict[str, str]] | None = None,
    cart: list[dict[str, object]] | None = None,
    db: Session | None = None,
    limit: int = 12
) -> ResolvedSearch:
    normalized = normalize_query(message)
    cleaned = clean_search_terms(normalized)
    budget = extract_budget(message)

    if db is None:
        return ResolvedSearch(
            query=message,
            cleaned_query=cleaned,
            category_name=None,
            budget=budget,
            products=[]
        )

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

            # Apply secondary specific term filters if specific model words exist
            specific_words = [
                w for w in cleaned.split()
                if w not in {"phone", "phones", "mobile", "mobiles", "smartphone", "laptop", "laptops", "earbuds", "keyboard", "under", "below", "budget", "show", "me", "give", "find", "best", "good", "recommend"}
                and len(w) > 2 and not w.isdigit()
            ]

            if specific_words:
                spec_filters = []
                for sw in specific_words:
                    spec_filters.extend([
                        Product.name.ilike(f"%{sw}%"),
                        Product.brand.ilike(f"%{sw}%"),
                        Product.description.ilike(f"%{sw}%")
                    ])
                spec_stmt = stmt.where(or_(*spec_filters)).order_by(Product.rating.desc()).limit(limit)
                spec_results = list(db.scalars(spec_stmt).all())
                if spec_results:
                    return ResolvedSearch(
                        query=message,
                        cleaned_query=cleaned,
                        category_name=category_name,
                        budget=budget,
                        products=spec_results
                    )

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
        "me", "give", "find", "buy", "pick", "want", "need", "price", "today", "running"
    }

    terms = [
        t for t in cleaned.split()
        if len(t) > 2
        and t not in non_product_words
        and not t.isdigit()
    ]

    if terms:
        fallback_stmt = select(Product)
        if budget is not None:
            fallback_stmt = fallback_stmt.where(Product.price <= budget)

        term_filters = []
        for t in terms:
            term_filters.extend([
                Product.name.ilike(f"%{t}%"),
                Product.brand.ilike(f"%{t}%"),
                Product.description.ilike(f"%{t}%")
            ])
        fallback_stmt = fallback_stmt.where(or_(*term_filters)).order_by(Product.rating.desc()).limit(limit)
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
