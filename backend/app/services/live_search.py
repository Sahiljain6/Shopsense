import re
import httpx

try:
    from duckduckgo_search import DDGS
    HAS_DDG = True
except ImportError:
    DDGS = None
    HAS_DDG = False

from app.services.trust_engine import evaluate_store_trust, filter_and_rank_trustworthy_deals

# E-commerce store domains whitelist
ALLOWED_STORES = [
    "amazon.in", "amazon.com", "flipkart.com", "croma.com",
    "reliancedigital.in", "tatacliq.com", "myntra.com", "jiomart.com",
    "vijaysales.com", "shopclues.com", "snapdeal.com", "meesho.com", "oneplus.in", "samsung.com"
]

# Blacklisted non-shopping sites
BLOCKED_DOMAINS = [
    "youtube.com", "netflix.com", "diffchecker.com", "text-compare.com",
    "draftable.com", "wikipedia.org", "facebook.com", "twitter.com", "reddit.com", "instagram.com"
]


def search_live_deals(query: str, max_results: int = 5) -> list[dict[str, str | int | bool | None]]:
    """Search live web specifically for Indian e-commerce products (Amazon.in, Flipkart, Croma)
    and prices in INR (₹). Strictly excludes non-shopping websites.
    """
    clean_query = re.sub(r"^(search me|give me|find me|fetch link:?|show me|recommend|suggest)\s*", "", query.strip(), flags=re.IGNORECASE)

    # Don't search live web for non-product / conversational queries
    if len(clean_query) < 3 or any(w in clean_query.lower() for w in ["how are you", "who are you", "what can you do", "hi", "hello", "code"]):
        return []

    search_term = f"{clean_query} price buy online india amazon flipkart croma"
    raw_deals: list[dict[str, str | None]] = []

    if HAS_DDG and DDGS is not None:
        try:
            with DDGS() as ddgs:
                raw_results = list(ddgs.text(search_term, max_results=max_results * 4))
                for item in raw_results:
                    link = (item.get("href") or item.get("link") or "").lower()
                    title = item.get("title") or ""
                    snippet = item.get("body") or item.get("snippet") or ""

                    if not link or not title:
                        continue

                    # Reject non-shopping sites
                    if any(blocked in link for blocked in BLOCKED_DOMAINS):
                        continue

                    # Strictly require allowed e-commerce domains
                    if not any(allowed in link for allowed in ALLOWED_STORES):
                        continue

                    # Determine store name
                    store_name = (
                        "Amazon India" if "amazon.in" in link
                        else "Flipkart" if "flipkart.com" in link
                        else "Croma" if "croma.com" in link
                        else "Reliance Digital" if "reliancedigital.in" in link
                        else evaluate_store_trust(link)["store_name"]
                    )

                    price_match = re.search(r"(?:₹|Rs\.?|INR)\s*([\d,]+)", f"{title} {snippet}")
                    price_str = price_match.group(0) if price_match else None

                    raw_deals.append({
                        "title": title[:120],
                        "url": link,
                        "snippet": snippet,
                        "price_str": price_str,
                        "store": store_name
                    })
        except Exception as error:
            print(f"Live DDG web search notice: {type(error).__name__}: {error}")

    # Apply trust ranking & filtering
    trustworthy_deals = filter_and_rank_trustworthy_deals(raw_deals, min_trust_score=30)
    return trustworthy_deals[:max_results]
