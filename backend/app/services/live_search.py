import re
from duckduckgo_search import DDGS
from app.services.trust_engine import evaluate_store_trust, filter_and_rank_trustworthy_deals


def search_live_deals(query: str, max_results: int = 5) -> list[dict[str, str | int | bool | None]]:
    """Search live web for real e-commerce products, prices, and direct buy links for free,
    filtering for store trust and credibility.
    """
    search_term = f"{query} price buy online deal"
    raw_deals: list[dict[str, str | None]] = []

    try:
        with DDGS() as ddgs:
            raw_results = list(ddgs.text(search_term, max_results=max_results * 3))
            for item in raw_results:
                link = item.get("href") or item.get("link") or ""
                title = item.get("title") or ""
                snippet = item.get("body") or item.get("snippet") or ""

                if not link or not title:
                    continue

                trust_info = evaluate_store_trust(link)

                # Extract price if present in snippet or title
                price_match = re.search(r"(?:₹|Rs\.?|INR|\$)\s*([\d,]+)", f"{title} {snippet}")
                price_str = price_match.group(0) if price_match else None

                raw_deals.append({
                    "title": title,
                    "url": link,
                    "snippet": snippet,
                    "price_str": price_str,
                    "store": trust_info["store_name"]
                })

    except Exception as error:
        print(f"Live DDG web search notice: {type(error).__name__}: {error}")

    # Apply trust ranking & filtering
    trustworthy_deals = filter_and_rank_trustworthy_deals(raw_deals, min_trust_score=70)
    return trustworthy_deals[:max_results]
