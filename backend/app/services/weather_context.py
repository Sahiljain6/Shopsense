import logging
from typing import Any
import httpx

logger = logging.getLogger("shopsense.weather")

CITY_COORDINATES: dict[str, tuple[float, float]] = {
    "mumbai": (19.0760, 72.8777),
    "delhi": (28.6139, 77.2090),
    "new delhi": (28.6139, 77.2090),
    "bengaluru": (12.9716, 77.5946),
    "bangalore": (12.9716, 77.5946),
    "hyderabad": (17.3850, 78.4867),
    "chennai": (13.0827, 80.2707),
    "kolkata": (22.5726, 88.3639),
    "pune": (18.5204, 73.8567),
    "ahmedabad": (23.0225, 72.5714),
    "jaipur": (26.9124, 75.7873),
    "gurugram": (28.4595, 77.0266),
    "noida": (28.5355, 77.3910),
}


def get_weather_shopping_advice(location: str = "Mumbai") -> dict[str, Any]:
    """Fetch live weather from Open-Meteo public API and generate climate-aware shopping advice."""
    clean_loc = location.strip().lower()
    lat, lon = CITY_COORDINATES.get(clean_loc, (19.0760, 72.8777))

    # Match city substring if exact key isn't in dictionary
    if clean_loc not in CITY_COORDINATES:
        for city, coords in CITY_COORDINATES.items():
            if city in clean_loc:
                lat, lon = coords
                break

    url = (
        f"https://api.open-meteo.com/v1/forecast"
        f"?latitude={lat}&longitude={lon}"
        f"&current=temperature_2m,relative_humidity_2m,precipitation,weather_code"
    )

    temp = 30.0
    humidity = 65
    precip = 0.0

    try:
        with httpx.Client(timeout=4.0) as client:
            resp = client.get(url)
            if resp.status_code == 200:
                data = resp.json()
                current = data.get("current", {})
                temp = float(current.get("temperature_2m", temp))
                humidity = int(current.get("relative_humidity_2m", humidity))
                precip = float(current.get("precipitation", precip))
    except Exception as exc:
        logger.warning("Open-Meteo weather fetch notice for %s: %s", location, exc)

    # Weather-conditioned shopping advice
    is_rain = precip > 0.5
    is_hot = temp >= 34.0
    is_cold = temp <= 16.0

    recommendations = []
    condition = "Pleasant / Clear"

    if is_rain:
        condition = "Rainy / Monsoon"
        recommendations = [
            "IP68 Water-Resistant Smartphones & Earbuds",
            "Waterproof Laptop Sleeves & Commuter Backpacks",
            "Compact Windproof Umbrellas & Rain Protection",
            "Silica Gel / Moisture Absorbers for Electronics"
        ]
    elif is_hot:
        condition = "Hot / Heatwave"
        recommendations = [
            "Laptop Cooling Pads with High-RPM Dual Fans",
            "Portable USB-C Rechargeable Neck / Desk Fans",
            "Insulated Thermal Water Flasks (24h Cold Retention)",
            "5-Star Inverter Air Conditioners & Air Purifiers"
        ]
    elif is_cold:
        condition = "Cold / Winter"
        recommendations = [
            "Ceramic Room Heaters & Oil-Filled Radiators",
            "Smart Thermal Mugs & Electric Kettles",
            "Warm Over-Ear ANC Headphones with Padded Cushions"
        ]
    else:
        recommendations = [
            "True Wireless Earbuds with Long Battery Playtime",
            "High-Capacity 20,000mAh Fast-Charging Power Banks",
            "Ergonomic Mechanical Keyboards & Workspace Setup"
        ]

    city_title = location.strip().title() if location else "India"
    summary = (
        f"{city_title} is currently {temp:.1f}°C ({humidity}% humidity, {condition}). "
        f"Recommended: {', '.join(recommendations[:2])}."
    )

    return {
        "location": city_title,
        "temperature_celsius": temp,
        "humidity_percent": humidity,
        "precipitation_mm": precip,
        "condition": condition,
        "recommended_products": recommendations,
        "summary": summary
    }
