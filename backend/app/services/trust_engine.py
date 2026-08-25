from urllib.parse import urlparse

# Trust scores for well-known reputable e-commerce platforms (0-100 scale)
TRUSTED_STORES = {
    "amazon": {"name": "Amazon", "trust_score": 98, "badge": "🛡️ Verified Store"},
    "flipkart": {"name": "Flipkart", "trust_score": 95, "badge": "🛡️ Verified Store"},
    "myntra": {"name": "Myntra", "trust_score": 94, "badge": "🛡️ Verified Fashion"},
    "croma": {"name": "Croma", "trust_score": 92, "badge": "🛡️ Authorized Electronics"},
    "reliancedigital": {"name": "Reliance Digital", "trust_score": 92, "badge": "🛡️ Authorized Electronics"},
    "tatacliq": {"name": "Tata CLIQ", "trust_score": 90, "badge": "🛡️ Verified Store"},
    "vijaysales": {"name": "Vijay Sales", "trust_score": 88, "badge": "🛡️ Retail Partner"},
    "ajio": {"name": "AJIO", "trust_score": 89, "badge": "🛡️ Verified Retailer"},
    "nykaa": {"name": "Nykaa", "trust_score": 91, "badge": "🛡️ Official Beauty"},
    "apple": {"name": "Apple Store", "trust_score": 100, "badge": "⭐ Official Brand"},
    "samsung": {"name": "Samsung Store", "trust_score": 98, "badge": "⭐ Official Brand"},
    "ebay": {"name": "eBay", "trust_score": 85, "badge": "🛡️ Global Marketplace"},
    "bestbuy": {"name": "Best Buy", "trust_score": 95, "badge": "🛡️ Verified Retailer"},
}


def evaluate_store_trust(url_or_store: str) -> dict[str, object]:
    """Evaluates domain or store name to assign a trust score and verification status."""
    lowered = url_or_store.lower()

    domain = lowered
    if "http://" in lowered or "https://" in lowered:
        parsed = urlparse(lowered)
        domain = parsed.netloc or parsed.path

    for store_key, info in TRUSTED_STORES.items():
        if store_key in domain:
            return {
                "store_name": info["name"],
                "trust_score": info["trust_score"],
                "is_verified": True,
                "badge": info["badge"],
                "warning": None
            }

    return {
        "store_name": domain.replace("www.", "").capitalize(),
        "trust_score": 65,
        "is_verified": False,
        "badge": "ℹ️ Third-Party Store",
        "warning": "Verify return policy before purchasing from unverified third-party sellers."
    }


def filter_and_rank_trustworthy_deals(deals: list[dict], min_trust_score: int = 70) -> list[dict]:
    """Filters out low-credibility stores and ranks deals by trust score & value."""
    evaluated_deals = []

    for deal in deals:
        url = deal.get("url") or ""
        store_info = evaluate_store_trust(url or deal.get("store", ""))
        
        trust_score = int(store_info["trust_score"])
        if trust_score >= min_trust_score:
            deal_copy = dict(deal)
            deal_copy["trust_score"] = trust_score
            deal_copy["badge"] = store_info["badge"]
            deal_copy["is_verified"] = store_info["is_verified"]
            deal_copy["store"] = store_info["store_name"]
            evaluated_deals.append(deal_copy)

    return sorted(evaluated_deals, key=lambda d: d.get("trust_score", 0), reverse=True)


def generate_trust_pros_cons(rating: float, price: float, brand: str, store_name: str) -> tuple[list[str], list[str]]:
    """Generates transparent, honest trust Pros & Cons for customer confidence."""
    pros = []
    cons = []

    if rating >= 4.2:
        pros.append(f"Top-rated product ({rating:.1f}/5 stars)")
    elif rating >= 3.8:
        pros.append(f"Solid customer rating ({rating:.1f}/5 stars)")

    store_trust = evaluate_store_trust(store_name)
    if store_trust["is_verified"]:
        pros.append(f"Available from {store_trust['badge']}")

    if price > 0:
        pros.append("Verified catalog price tag")

    if rating < 4.0:
        cons.append("Rating is below 4.0 stars — compare user reviews before buying")

    if not store_trust["is_verified"]:
        cons.append("Sold by a third-party store — check seller return policy")

    if not cons:
        cons.append("Standard manufacturer warranty applies")

    return pros, cons
