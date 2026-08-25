import httpx


def fetch_gaming_deals(title_query: str = "", limit: int = 5) -> list[dict[str, object]]:
    """Fetch active gaming deals, discounts, and historic price drops via CheapShark API (100% Free)."""
    url = f"https://www.cheapshark.com/api/1.0/deals?title={title_query}&pageSize={limit}"
    results = []

    try:
        with httpx.Client(timeout=8) as client:
            resp = client.get(url)
            if resp.status_code == 200:
                raw_deals = resp.json()
                for d in raw_deals:
                    savings = float(d.get("savings", 0))
                    sale_price = float(d.get("salePrice", 0))
                    normal_price = float(d.get("normalPrice", 0))
                    deal_id = d.get("dealID", "")

                    results.append({
                        "title": d.get("title"),
                        "deal_id": deal_id,
                        "sale_price": sale_price,
                        "normal_price": normal_price,
                        "savings_percentage": round(savings, 1),
                        "deal_rating": d.get("dealRating"),
                        "thumb": d.get("thumb"),
                        "deal_url": f"https://www.cheapshark.com/redirect?dealID={deal_id}"
                    })
    except Exception as error:
        print(f"CheapShark Deal API notice: {error}")

    return results
