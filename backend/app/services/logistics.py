import os
import re
import logging
from typing import Any
import httpx

from app.core.config import get_settings

logger = logging.getLogger("shopsense.logistics")

METRO_DISTRICTS = {
    "mumbai", "delhi", "new delhi", "bengaluru", "bangalore", "bengaluru urban",
    "chennai", "hyderabad", "kolkata", "pune", "ahmedabad", "gurugram", "gurgaon", "noida"
}

# Offline resilient fallback for key Indian cities
PINCODE_FALLBACKS: dict[str, dict[str, str]] = {
    "400001": {"district": "Mumbai", "state": "Maharashtra", "po": "Mumbai G.P.O."},
    "400071": {"district": "Mumbai", "state": "Maharashtra", "po": "Chembur"},
    "110001": {"district": "Central Delhi", "state": "Delhi", "po": "New Delhi G.P.O."},
    "560001": {"district": "Bengaluru", "state": "Karnataka", "po": "Bangalore G.P.O."},
    "500001": {"district": "Hyderabad", "state": "Telangana", "po": "Hyderabad G.P.O."},
    "600001": {"district": "Chennai", "state": "Tamil Nadu", "po": "Chennai G.P.O."},
    "700001": {"district": "Kolkata", "state": "West Bengal", "po": "Kolkata G.P.O."},
    "411001": {"district": "Pune", "state": "Maharashtra", "po": "Pune G.P.O."},
}


def lookup_pincode(pincode: str) -> dict[str, Any]:
    """Lookup an Indian 6-digit PIN code via the official Postal Pincode API
    or a configured provider with API key, resolving district, state,
    and estimated delivery timeline.
    """
    clean_pin = re.sub(r"\D", "", str(pincode).strip())
    if not re.match(r"^[1-9][0-9]{5}$", clean_pin):
        return {
            "valid": False,
            "pincode": str(pincode),
            "error": "Invalid PIN code. Indian postal codes must be exactly 6 digits starting with 1-9."
        }

    settings = get_settings()
    api_key = (
        getattr(settings, "pincode_api_key", "")
        or os.getenv("PINCODE_API_KEY", "")
        or os.getenv("POSTAL_PINCODE_API_KEY", "")
        or os.getenv("POSTAL_API_KEY", "")
    ).strip()

    custom_url = (
        getattr(settings, "pincode_api_url", "")
        or os.getenv("PINCODE_API_URL", "")
    ).strip()

    # Determine endpoint URL
    if custom_url:
        if "{pincode}" in custom_url:
            url = custom_url.replace("{pincode}", clean_pin)
        elif "{pin}" in custom_url:
            url = custom_url.replace("{pin}", clean_pin)
        elif custom_url.endswith("/"):
            url = f"{custom_url}{clean_pin}"
        else:
            url = custom_url
    else:
        url = f"https://api.postalpincode.in/pincode/{clean_pin}"

    headers: dict[str, str] = {
        "User-Agent": "Shopsense-Logistics/1.0",
        "Accept": "application/json",
    }
    params: dict[str, str] = {}

    if api_key:
        headers["api-key"] = api_key
        headers["x-api-key"] = api_key
        headers["Authorization"] = f"Bearer {api_key}"
        headers["X-RapidAPI-Key"] = api_key
        params["api_key"] = api_key
        params["apikey"] = api_key

    if custom_url and ("{pincode}" not in custom_url and "{pin}" not in custom_url and not custom_url.endswith("/")):
        params["pincode"] = clean_pin

    district = ""
    state = ""
    post_office = ""
    delivery_status = "Deliverable"

    try:
        with httpx.Client(timeout=4.0) as client:
            resp = client.get(url, headers=headers, params=params if params else None)
            if resp.status_code == 200:
                data = resp.json()
                if isinstance(data, list) and len(data) > 0:
                    first_node = data[0] if isinstance(data[0], dict) else {}
                    if first_node.get("Status") == "Success" or "PostOffice" in first_node:
                        po_list = first_node.get("PostOffice") or []
                        if po_list and isinstance(po_list, list) and len(po_list) > 0:
                            first_po = po_list[0]
                            district = first_po.get("District") or first_po.get("district") or ""
                            state = first_po.get("State") or first_po.get("state") or ""
                            post_office = first_po.get("Name") or first_po.get("name") or ""
                            delivery_status = first_po.get("DeliveryStatus") or first_po.get("delivery_status") or "Deliverable"
                elif isinstance(data, dict):
                    po_list = data.get("PostOffice") or data.get("post_office") or data.get("places") or data.get("data")
                    if isinstance(po_list, list) and len(po_list) > 0:
                        first_po = po_list[0]
                        if isinstance(first_po, dict):
                            district = first_po.get("District") or first_po.get("district") or ""
                            state = first_po.get("State") or first_po.get("state") or ""
                            post_office = first_po.get("Name") or first_po.get("name") or ""
                            delivery_status = first_po.get("DeliveryStatus") or first_po.get("delivery_status") or "Deliverable"
                    if not district:
                        district = data.get("district") or data.get("District") or data.get("city") or data.get("City") or ""
                    if not state:
                        state = data.get("state") or data.get("State") or ""
                    if not post_office:
                        post_office = data.get("post_office") or data.get("name") or data.get("Name") or ""
    except Exception as exc:
        logger.warning("Pincode API lookup notice for %s: %s", clean_pin, exc)

    # Fallback if API was unavailable or returned empty
    if not district and clean_pin in PINCODE_FALLBACKS:
        fb = PINCODE_FALLBACKS[clean_pin]
        district = fb["district"]
        state = fb["state"]
        post_office = fb["po"]

    if not district:
        # Check prefix heuristics for major zones
        prefix = clean_pin[:2]
        zone_map = {
            "11": ("Delhi", "Delhi"),
            "40": ("Mumbai", "Maharashtra"),
            "56": ("Bengaluru", "Karnataka"),
            "50": ("Hyderabad", "Telangana"),
            "60": ("Chennai", "Tamil Nadu"),
            "70": ("Kolkata", "West Bengal"),
            "41": ("Pune", "Maharashtra"),
        }
        if prefix in zone_map:
            district, state = zone_map[prefix]
            post_office = f"{district} Hub"

    dist_lower = district.lower()
    state_lower = state.lower()
    is_metro = any(kw in dist_lower for kw in METRO_DISTRICTS) or "delhi" in state_lower

    if is_metro:
        est_days = "1–2 Business Days"
        couriers = "Blue Dart, Delhivery Express, Amazon Shipping"
        speed = "Express Metro Transit"
    else:
        est_days = "3–5 Business Days"
        couriers = "Delhivery, DTDC, India Post Speed Post"
        speed = "Standard Regional Transit"

    return {
        "valid": True,
        "pincode": clean_pin,
        "district": district or "Unknown District",
        "state": state or "India",
        "post_office": post_office or "Head Post Office",
        "delivery_status": delivery_status,
        "is_metro": is_metro,
        "estimated_days": est_days,
        "speed": speed,
        "courier_partners": couriers,
        "summary": f"PIN {clean_pin} ({district or 'India'}, {state}): {est_days} via {couriers}."
    }


def estimate_shipping_sla(is_metro: bool, is_express: bool = False) -> dict[str, Any]:
    """Estimate delivery turnaround time, transit days, and cutoff advice based on zone."""
    if is_metro and is_express:
        return {
            "tier": "Same-Day / Next-Day Priority",
            "min_days": 0,
            "max_days": 1,
            "cutoff_time": "12:00 PM IST",
            "eligible_for_instant": True
        }
    elif is_metro:
        return {
            "tier": "Metro Express",
            "min_days": 1,
            "max_days": 2,
            "cutoff_time": "6:00 PM IST",
            "eligible_for_instant": False
        }
    else:
        return {
            "tier": "Standard Regional",
            "min_days": 3,
            "max_days": 5,
            "cutoff_time": "4:00 PM IST",
            "eligible_for_instant": False
        }

