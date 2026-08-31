import httpx
from functools import lru_cache

FALLBACK_RATES = {
    "USD": 1.0,
    "INR": 86.5,
    "EUR": 0.92,
    "GBP": 0.78,
    "AED": 3.67,
    "SGD": 1.34,
    "CAD": 1.38,
    "AUD": 1.54,
    "JPY": 152.0,
    "THB": 36.5,
}


def convert_price(amount: float, from_curr: str = "USD", to_curr: str = "INR") -> float:
    """Convert an amount from one currency to another using the free Frankfurter API,
    with local static rate fallback.
    """
    from_curr = from_curr.upper()
    to_curr = to_curr.upper()

    if from_curr == to_curr or amount <= 0:
        return amount

    # Frankfurter supports EUR, USD, GBP, JPY, CAD, AUD, etc.
    try:
        url = f"https://api.frankfurter.app/latest?amount={amount}&from={from_curr}&to={to_curr}"
        with httpx.Client(timeout=5) as client:
            resp = client.get(url)
            if resp.status_code == 200:
                data = resp.json()
                rates = data.get("rates", {})
                if to_curr in rates:
                    return round(float(rates[to_curr]), 2)
    except Exception as error:
        pass

    from_usd = FALLBACK_RATES.get(from_curr, 1.0)
    to_usd = FALLBACK_RATES.get(to_curr, 86.5)
    amount_in_usd = amount / from_usd
    converted = amount_in_usd * to_usd
    return round(converted, 2)


def calculate_import_comparison(
    product_name: str,
    foreign_amount: float,
    foreign_currency: str = "USD",
    india_mrp: float | None = None
) -> dict:
    """Calculate landed cost in India for tech products bought abroad (US, Dubai, Singapore)
    factoring in currency exchange, customs duty, and domestic warranty considerations.
    """
    curr = foreign_currency.upper()
    base_inr = convert_price(foreign_amount, curr, "INR")

    # Estimated customs duty (10% BCD + 18% IGST) for courier imports
    # For personal travel/carry-on baggage: 1 laptop/phone carried personally is generally duty-free
    customs_estimate = round(base_inr * 0.18)
    commercial_landed = round(base_inr * 1.33)  # ~33% effective duty + IGST if shipped via DHL/FedEx

    # Brand warranty rules in India
    prod_lower = product_name.lower()
    if any(b in prod_lower for b in ["apple", "macbook", "ipad", "iphone", "airpods"]):
        warranty_note = "Apple provides Global International Warranty across India for most hardware (except select carrier-locked devices)."
    elif any(b in prod_lower for b in ["sony", "bose", "sennheiser"]):
        warranty_note = "Limited international warranty. Authorized Indian service centers usually require an Indian retail invoice for free repair."
    else:
        warranty_note = "Regional warranty applies. Products bought abroad generally do not receive free warranty repairs at Indian service centers."

    diff_personal = (india_mrp - base_inr) if india_mrp else None

    if diff_personal and diff_personal > 5000:
        verdict = f"Buying in {curr} saves approx ₹{diff_personal:,.0f} if carried in personal baggage."
    else:
        verdict = "Comparable price when factoring in courier customs duties and domestic warranty peace of mind."

    return {
        "product": product_name,
        "foreign_price": f"{foreign_amount:,.2f} {curr}",
        "converted_base_inr": base_inr,
        "personal_baggage_landed_inr": base_inr,
        "courier_shipped_landed_inr": commercial_landed,
        "india_reference_mrp": india_mrp,
        "savings_personal_travel": diff_personal,
        "warranty_advice": warranty_note,
        "verdict": verdict,
        "summary": f"{product_name}: Converted base cost is ₹{base_inr:,.0f} ({foreign_amount} {curr}). {verdict}"
    }

