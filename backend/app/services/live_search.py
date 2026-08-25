import re
import httpx

try:
    from duckduckgo_search import DDGS
    HAS_DDG = True
except ImportError:
    DDGS = None
    HAS_DDG = False

from app.services.trust_engine import evaluate_store_trust, filter_and_rank_trustworthy_deals


def search_live_deals(query: str, max_results: int = 5) -> list[dict[str, str | int | bool | None]]:
    """Search live web for real e-commerce products, prices, and direct buy links for free,
    filtering for store trust and credibility.
    """
    clean_query = re.sub(r"^(search me|give me|find me|fetch link:?|show me)\s*", "", query.strip(), flags=re.IGNORECASE)
    search_term = f"{clean_query} price buy online"
    raw_deals: list[dict[str, str | None]] = []

    if HAS_DDG and DDGS is not None:
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
                    price_match = re.search(r"(?:₹|Rs\.?|INR|\$)\s*([\d,]+)", f"{title} {snippet}")
                    price_str = price_match.group(0) if price_match else None

                    raw_deals.append({
                        "title": title[:120],
                        "url": link,
                        "snippet": snippet,
                        "price_str": price_str,
                        "store": trust_info["store_name"]
                    })
        except Exception as error:
            print(f"Live DDG web search notice: {type(error).__name__}: {error}")

    # Fallback to direct HTTP search if DDGS produced no results
    if not raw_deals:
        try:
            headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/124.0.0.0 Safari/537.36"}
            with httpx.Client(headers=headers, timeout=8, follow_redirects=True) as client:
                resp = client.get(f"https://html.duckduckgo.com/html/?q={clean_query}")
                if resp.status_code == 200:
                    from bs4 import BeautifulSoup
                    soup = BeautifulSoup(resp.text, "html.parser")
                    for a in soup.find_all("a", class_="result__url", limit=max_results * 2):
                        link = a.get("href") or ""
                        title = a.get_text().strip()
                        if link and title:
                            trust_info = evaluate_store_trust(link)
                            raw_deals.append({
                                "title": title[:120],
                                "url": link,
                                "snippet": "Product deal found online",
                                "price_str": None,
                                "store": trust_info["store_name"]
                            })
        except Exception as err:
            print(f"HTML web search fallback notice: {err}")

    # Apply trust ranking & filtering
    trustworthy_deals = filter_and_rank_trustworthy_deals(raw_deals, min_trust_score=40)
    return trustworthy_deals[:max_results]
