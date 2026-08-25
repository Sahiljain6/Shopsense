import httpx
from functools import lru_cache

FALLBACK_RATES = {
    "USD": 1.0,
    "INR": 86.5,
    "EUR": 0.92,
    "GBP": 0.78,
    "CAD": 1.38,
    "AUD": 1.54,
    "JPY": 152.0,
}


def convert_price(amount: float, from_curr: str = "USD", to_curr: str = "INR") -> float:
    """Convert an amount from one currency to another using the free Frankfurter API,
    with local static rate fallback.
    """
    from_curr = from_curr.upper()
    to_curr = to_curr.upper()

    if from_curr == to_curr or amount <= 0:
        return amount

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
        print(f"Currency API notice (using fallback): {error}")

    from_usd = FALLBACK_RATES.get(from_curr, 1.0)
    to_usd = FALLBACK_RATES.get(to_curr, 86.5)
    amount_in_usd = amount / from_usd
    converted = amount_in_usd * to_usd
    return round(converted, 2)
