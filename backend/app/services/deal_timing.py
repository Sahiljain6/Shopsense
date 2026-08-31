from datetime import datetime
import logging
from typing import Any

logger = logging.getLogger("shopsense.deal_timing")

# Indian E-Commerce Major Sales Calendar (month, approximate day, name, typical discount)
INDIAN_SALES_CALENDAR = [
    {"month": 1, "day": 20, "name": "Republic Day Mega Sale (Amazon / Flipkart)", "discount_pct": "10%–20%"},
    {"month": 3, "day": 15, "name": "Holi Tech Fest", "discount_pct": "8%–15%"},
    {"month": 5, "day": 5, "name": "Summer Appliance & Tech Drop", "discount_pct": "10%–18%"},
    {"month": 7, "day": 15, "name": "Amazon Prime Day / Flipkart Big Bachat Days", "discount_pct": "15%–25%"},
    {"month": 8, "day": 10, "name": "Independence Day Freedom Sale", "discount_pct": "12%–22%"},
    {"month": 10, "day": 5, "name": "Great Indian Festival / Big Billion Days (Diwali Mega Sale)", "discount_pct": "20%–35%"},
    {"month": 11, "day": 25, "name": "Black Friday & Cyber Week India", "discount_pct": "10%–20%"},
    {"month": 12, "day": 25, "name": "Year-End Clearance Sale", "discount_pct": "15%–25%"},
]

CATEGORY_DISCOUNT_RANGES = {
    "phones": (10, 18),
    "audio": (15, 30),
    "laptops": (8, 15),
    "peripherals": (15, 25),
    "general": (10, 20),
}


def analyze_deal_timing(
    product_name: str,
    current_price: float | None = None,
    category: str = "general"
) -> dict[str, Any]:
    """Analyze current Indian e-commerce sales cycle and historical price trends
    to advise whether to Buy Now or Wait for an upcoming shopping festival.
    """
    now = datetime.now()
    current_month = now.month
    current_day = now.day

    # Find the next upcoming sale
    next_sale = None
    min_days_ahead = 999

    for sale in INDIAN_SALES_CALENDAR:
        # Approximate day of year
        sale_month = sale["month"]
        sale_day = sale["day"]

        # Approximate days difference
        if sale_month > current_month or (sale_month == current_month and sale_day >= current_day):
            days_diff = (sale_month - current_month) * 30 + (sale_day - current_day)
        else:
            days_diff = ((12 - current_month) + sale_month) * 30 + (sale_day - current_day)

        if days_diff < min_days_ahead:
            min_days_ahead = days_diff
            next_sale = sale

    if not next_sale:
        next_sale = INDIAN_SALES_CALENDAR[0]
        min_days_ahead = 30

    cat_key = category.lower() if category else "general"
    disc_min, disc_max = CATEGORY_DISCOUNT_RANGES.get(cat_key, (10, 20))

    if current_price and current_price > 0:
        est_all_time_low = round(current_price * (1 - (disc_max / 100)))
        potential_saving = round(current_price * (disc_min / 100))
    else:
        est_all_time_low = None
        potential_saving = None

    # Decision verdict
    if min_days_ahead <= 21:
        verdict = f"🟡 WAIT: The {next_sale['name']} is expected in ~{min_days_ahead} days. Wait for {next_sale['discount_pct']} drops and card cashback."
        recommendation = "Wait for Upcoming Sale"
    elif min_days_ahead <= 45 and "Diwali" in next_sale["name"]:
        verdict = f"🟡 HIGH BENEFIT WAIT: The flagship Diwali sales ({next_sale['name']}) are ~{min_days_ahead} days away with up to 35% discounts on electronics."
        recommendation = "Wait for Diwali Sale"
    else:
        verdict = f"🟢 BUY NOW: The next major shopping event is {min_days_ahead} days away ({next_sale['name']}). Current pricing is fair with standard bank card discounts."
        recommendation = "Buy Now"

    summary = (
        f"{product_name}: {verdict} Next event: {next_sale['name']} ({next_sale['discount_pct']} typical category drop)."
    )

    return {
        "product": product_name,
        "current_price": current_price,
        "estimated_all_time_low": est_all_time_low,
        "potential_savings_range": f"{disc_min}%–{disc_max}%",
        "estimated_sale_savings_inr": potential_saving,
        "next_sale_event": next_sale["name"],
        "approx_days_to_sale": min_days_ahead,
        "recommendation": recommendation,
        "verdict": verdict,
        "summary": summary
    }
