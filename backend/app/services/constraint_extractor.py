"""Deterministic extraction of explicit shopping constraints.

The output is an internal value object for later orchestration stages. This
module does not call an LLM, access a database, or change the public chat API.
Only constraints supported by the user's current message are extracted.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ShoppingConstraints:
    """Structured constraints stated in a single shopping request."""

    budget_min: float | None = None
    budget_max: float | None = None
    budget_target: float | None = None
    budget_currency: str | None = None
    category: str | None = None
    use_cases: tuple[str, ...] = ()
    required_features: tuple[str, ...] = ()
    preferred_features: tuple[str, ...] = ()
    excluded_features: tuple[str, ...] = ()
    preferred_brands: tuple[str, ...] = ()
    excluded_brands: tuple[str, ...] = ()
    delivery_location: str | None = None
    delivery_postal_code: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-friendly copy for internal prompt/orchestration use."""
        return {
            "budget_min": self.budget_min,
            "budget_max": self.budget_max,
            "budget_target": self.budget_target,
            "budget_currency": self.budget_currency,
            "category": self.category,
            "use_cases": list(self.use_cases),
            "required_features": list(self.required_features),
            "preferred_features": list(self.preferred_features),
            "excluded_features": list(self.excluded_features),
            "preferred_brands": list(self.preferred_brands),
            "excluded_brands": list(self.excluded_brands),
            "delivery_location": self.delivery_location,
            "delivery_postal_code": self.delivery_postal_code,
        }


# Explicit product types supported by ShopSense's current catalog resolver.
_CATEGORY_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("Phones", re.compile(
        r"\b(?:smartphones?|cell phones?|mobile phones?|mobiles?|phones?|"
        r"iphone|iphones|galaxy s\d{1,2}|redmi|poco phones?)\b", re.I
    )),
    ("Laptops", re.compile(
        r"\b(?:laptops?|notebooks?|macbooks?|chromebooks?)\b", re.I
    )),
    ("Audio", re.compile(
        r"\b(?:earbuds?|earphones?|headphones?|headsets?|airpods|airdopes|"
        r"tws|audio)\b", re.I
    )),
    ("Peripherals", re.compile(
        r"\b(?:keyboards?|mice|mouse|smart ?watches?|watches?)\b", re.I
    )),
)

_USE_CASE_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("gaming", re.compile(r"\b(?:gaming|gamer|game development)\b", re.I)),
    ("coding", re.compile(r"\b(?:coding|programming|software development|developer)\b", re.I)),
    ("work_productivity", re.compile(r"\b(?:office work|productivity|work meetings|work from home)\b", re.I)),
    ("study", re.compile(r"\b(?:student|students|studying|study|online classes|college)\b", re.I)),
    ("travel", re.compile(r"\b(?:travel|travelling|traveling|commute|commuting)\b", re.I)),
    ("photography", re.compile(r"\b(?:photography|photographer|camera quality|taking photos)\b", re.I)),
    ("content_creation", re.compile(r"\b(?:content creation|video editing|editing videos|youtube|streaming)\b", re.I)),
    ("fitness", re.compile(r"\b(?:fitness|workout|workouts|running|gym)\b", re.I)),
    ("daily_use", re.compile(r"\b(?:daily use|everyday use|everyday phone|regular use)\b", re.I)),
)

_BRANDS = (
    "Apple", "Samsung", "OnePlus", "Xiaomi", "Redmi", "Realme", "Google",
    "Motorola", "Poco", "Vivo", "Oppo", "Sony", "Bose", "JBL", "boAt",
    "Dell", "HP", "Lenovo", "Asus", "Acer", "MSI", "Razer", "Logitech",
    "Cosmic Byte", "Keychron", "Redragon", "Noise", "Garmin", "Amazfit",
)

_AMOUNT_TOKEN = (
    r"(?:(?:₹|(?<![A-Za-z])rs\.?|(?<![A-Za-z])inr\b|\$|(?<![A-Za-z])usd\b)\s*)?"
    r"(?:\d{1,2}(?:,\d{2})*,\d{3}|\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?"
    r"(?:\s*(?:lakhs?|lacs?|k\b|thousand\b|million\b))?"
)
_AMOUNT_RE = re.compile(
    r"(?P<currency>₹|rs\.?|inr\b|\$|usd\b)?\s*"
    r"(?P<number>\d{1,2}(?:,\d{2})*,\d{3}|\d{1,3}(?:,\d{3})+|\d+)"
    r"(?P<decimal>\.\d+)?\s*(?P<unit>lakhs?|lacs?|k\b|thousand\b|million\b)?",
    re.I,
)
_BUDGET_CUE_RE = re.compile(
    r"\b(?:budget|under|below|upto|up to|within|less than|at most|maximum|max|"
    r"over|above|more than|at least|minimum|min|around|about|approximately|approx|"
    r"price|spend|spending|cost|between|from)\b",
    re.I,
)
_UPPER_CUE_RE = re.compile(
    r"\b(?:under|below|upto|up to|within|less than|at most|maximum|max|budget)\b",
    re.I,
)
_LOWER_CUE_RE = re.compile(
    r"\b(?:over|above|more than|at least|minimum|min)\b",
    re.I,
)
_TARGET_CUE_RE = re.compile(r"\b(?:around|about|approximately|approx)\b", re.I)

def _amount_value(token: str, suffix: str = "") -> tuple[float, str]:
    match = _AMOUNT_RE.search(token)
    if not match:
        raise ValueError(f"Cannot parse amount: {token!r}")
    number_text = match.group("number").replace(",", "")
    decimal = match.group("decimal") or ""
    value = float(number_text + decimal)
    unit = (match.group("unit") or "").lower()
    if unit.startswith(("lakh", "lac")):
        value *= 100_000
    elif unit == "k" or unit.startswith("thousand"):
        value *= 1_000
    elif unit.startswith("million"):
        value *= 1_000_000

    currency_marker = (match.group("currency") or "").lower()
    if not currency_marker and suffix:
        suffix_match = re.match(r"\s*(inr\b|rs\.?\b|rupees?\b|usd\b)", suffix, re.I)
        if suffix_match:
            currency_marker = suffix_match.group(1).lower()
    currency = "USD" if currency_marker in {"$", "usd"} else "INR"
    return value, currency


def _budget_values(text: str) -> tuple[float | None, float | None, float | None, str | None]:
    # Prefer explicitly stated ranges before interpreting a single amount.
    range_patterns = (
        re.compile(rf"\bbetween\s+(?P<first>{_AMOUNT_TOKEN})\s+(?:and|to|[-–—])\s+(?P<second>{_AMOUNT_TOKEN})", re.I),
        re.compile(rf"\bfrom\s+(?P<first>{_AMOUNT_TOKEN})\s+to\s+(?P<second>{_AMOUNT_TOKEN})", re.I),
    )
    for pattern in range_patterns:
        match = pattern.search(text)
        if match:
            first_token = match.group("first").strip()
            second_token = match.group("second").strip()
            first_value, first_currency = _amount_value(first_token)
            second_value, second_currency = _amount_value(second_token)
            currency = first_currency if re.search(r"₹|\$|\b(?:INR|USD|Rs\.?)\b", first_token, re.I) else second_currency
            return min(first_value, second_value), max(first_value, second_value), None, currency

    # Dash-separated ranges are accepted only when both numbers look like
    # money (currency/unit marker), avoiding model-number pairs such as 12-14.
    dash_pattern = re.compile(
        rf"(?P<first>{_AMOUNT_TOKEN})\s*[-–—]\s*(?P<second>{_AMOUNT_TOKEN})", re.I
    )
    for match in dash_pattern.finditer(text):
        first_token = match.group("first").strip()
        second_token = match.group("second").strip()
        money_marker = re.compile(r"₹|\$|\b(?:INR|USD|Rs\.?|rupees?|lakhs?|lacs?|k|thousand|million)\b", re.I)
        if money_marker.search(first_token) and money_marker.search(second_token):
            first_value, first_currency = _amount_value(first_token)
            second_value, second_currency = _amount_value(second_token)
            currency = first_currency if money_marker.search(first_token) else second_currency
            return min(first_value, second_value), max(first_value, second_value), None, currency

    for match in _AMOUNT_RE.finditer(text):
        token = match.group(0).strip()
        left_context = text[max(0, match.start() - 36):match.start()]
        right_context = text[match.end():match.end() + 12]
        currency_or_unit = bool(
            re.search(r"₹|\$|\b(?:INR|USD|Rs\.?|rupees?|lakhs?|lacs?|k|thousand|million)\b", token, re.I)
            or re.match(r"\s*(?:INR\b|Rs\.?\b|rupees?\b|USD\b)", right_context, re.I)
        )
        if not currency_or_unit and not _BUDGET_CUE_RE.search(left_context):
            continue

        value, currency = _amount_value(token, right_context)
        if _TARGET_CUE_RE.search(left_context):
            return None, None, value, currency
        if _LOWER_CUE_RE.search(left_context):
            return value, None, None, currency
        if _UPPER_CUE_RE.search(left_context) or currency_or_unit:
            return None, value, None, currency

    return None, None, None, None


def _clean_feature(value: str) -> str | None:
    value = re.sub(r"^(?:and|or|a|an|the|also|ideally)\s+", "", value.strip(), flags=re.I)
    value = re.split(
        r"\b(?:under|below|upto|up to|within|less than|budget|priced at|around ₹|around \$)\b",
        value, maxsplit=1, flags=re.I
    )[0]
    value = re.sub(r"\s+", " ", value).strip(" ,:-")
    value = re.sub(r"^(?:a|an|the)\s+", "", value, flags=re.I)
    if not value or value.lower() in {"it", "one", "product", "device", "item", "budget", "price"}:
        return None
    # Keep useful technical tokens, but remove incidental sentence punctuation.
    value = value.strip(" .")
    normalized = value.lower()
    generic_product_suffix = re.compile(
        r"\s+(?:phones?|mobiles?|laptops?|notebooks?|headphones?|earbuds?|"
        r"earphones?|keyboards?|watches?)$",
        re.I,
    )
    for brand in _BRANDS:
        if normalized == brand.lower() or (
            normalized.startswith(brand.lower() + " ")
            and generic_product_suffix.search(normalized)
            and generic_product_suffix.sub("", normalized).strip() == brand.lower()
        ):
            return None
    return normalized if len(normalized) >= 2 else None


def _split_features(value: str) -> tuple[str, ...]:
    # Remove obvious budget clauses before splitting the remaining feature list.
    value = re.split(
        r"\b(?:under|below|upto|up to|within|less than|at most|budget|priced at)\b",
        value, maxsplit=1, flags=re.I
    )[0]
    parts = re.split(r"\s*(?:,|;|\band\b|\bor\b)\s*", value, flags=re.I)
    cleaned = [_clean_feature(part) for part in parts]
    return tuple(dict.fromkeys(item for item in cleaned if item))


def _extract_feature_groups(text: str) -> tuple[tuple[str, ...], tuple[str, ...], tuple[str, ...]]:
    required: list[str] = []
    preferred: list[str] = []
    excluded: list[str] = []

    required_patterns = (
        r"\bmust[- ]have\s+(.+?)(?=\s*,?\s*(?:prefer(?:ably)?|ideally|nice to have|bonus if|without|avoid|don't want|do not want|no\s+|under\b|below\b|budget\b)|[.!?;\n]|$)",
        r"\brequired features?\s*(?:are|:)?\s+(.+?)(?=[.!?;\n]|$)",
        r"\bessential(?: feature)?s?\s*(?:are|:)?\s+(.+?)(?=[.!?;\n]|$)",
        r"\bnon[- ]negotiable(?:s)?\s*(?:are|:)?\s+(.+?)(?=[.!?;\n]|$)",
        r"\brequires?\s+(.+?)(?=[.!?;\n]|$)",
        r"\bwith\s+(.+?)(?=,|;|[.!?;\n]|\b(?:prefer(?:ably)?|ideally|nice to have|bonus if|without|avoid|don't want|do not want|no\s+|under\b|below\b|up to\b|budget\b)|$)",
    )
    preferred_patterns = (
        r"\bprefer(?:red|ably)?\s+(.+?)(?=\s*,?\s*(?:without|avoid|don't want|do not want|no\s+|under\b|below\b|budget\b)|[.!?;\n]|$)",
        r"\bwould like\s+(.+?)(?=[.!?;\n]|$)",
        r"\bnice to have\s+(.+?)(?=[.!?;\n]|$)",
        r"\bideally\s+(.+?)(?=[.!?;\n]|$)",
        r"\bbonus if\s+(.+?)(?=[.!?;\n]|$)",
    )
    excluded_patterns = (
        r"\b(?:avoid|without|don't want|do not want|not interested in|exclude)\s+([^.!?;\n]+)",
        r"\bno\s+(?!more than\b|less than\b|cost\b|budget\b|preference\b)([^.!?;\n]+)",
    )
    for pattern in required_patterns:
        for match in re.finditer(pattern, text, re.I):
            required.extend(_split_features(match.group(1)))
    for pattern in preferred_patterns:
        for match in re.finditer(pattern, text, re.I):
            preferred.extend(_split_features(match.group(1)))
    for pattern in excluded_patterns:
        for match in re.finditer(pattern, text, re.I):
            excluded.extend(_split_features(match.group(1)))

    return (
        tuple(dict.fromkeys(required)),
        tuple(dict.fromkeys(preferred)),
        tuple(dict.fromkeys(excluded)),
    )


def _extract_brands(text: str) -> tuple[tuple[str, ...], tuple[str, ...]]:
    preferred: list[str] = []
    excluded: list[str] = []
    for brand in sorted(_BRANDS, key=len, reverse=True):
        escaped = re.escape(brand)
        if re.search(
            rf"\b(?:prefer(?:ably)?|from|brand(?: is|:)?|only)\s+(?:the\s+)?{escaped}\b"
            rf"|\b{escaped}\s+(?:is\s+)?(?:preferred|only)\b",
            text, re.I
        ):
            preferred.append(brand)
        if re.search(
            rf"\b(?:avoid|without|don't want|do not want|not interested in|no)\s+(?:the\s+)?{escaped}\b",
            text, re.I
        ):
            excluded.append(brand)
    return tuple(preferred), tuple(excluded)


def _extract_delivery(text: str) -> tuple[str | None, str | None]:
    postal = re.search(
        r"\b(?:pin\s*code|pincode|postal code|zip code)\s*[:#-]?\s*(\d{5,6})\b",
        text, re.I
    )
    location = re.search(
        r"\b(?:deliver|delivery|ship|shipping|available)\s+(?:it\s+)?(?:to|in)\s+"
        r"([A-Za-z][A-Za-z .'-]{1,40}?)"
        r"(?=\s*(?:,|\.|;|!|\?|$|\bwith\b|\bunder\b|\bbelow\b|\bfor\b))",
        text, re.I
    )
    delivery_location = location.group(1).strip(" .,'") if location else None
    # An explicitly stated postal code is more precise than a captured location.
    if postal and delivery_location and re.fullmatch(r"\d{5,6}", delivery_location):
        delivery_location = None
    return delivery_location or None, postal.group(1) if postal else None


def extract_constraints(message: str | None) -> ShoppingConstraints:
    """Extract only explicit constraints from the current user message.

    Amounts with no currency marker are interpreted as INR, matching the
    product catalog's default currency. Dollar-denominated amounts remain USD
    and are not converted using a fixed or stale exchange rate.
    """
    text = (message or "").strip()
    if not text:
        return ShoppingConstraints()

    budget_min, budget_max, budget_target, budget_currency = _budget_values(text)

    category_matches = []
    for category, pattern in _CATEGORY_PATTERNS:
        match = pattern.search(text)
        if match:
            category_matches.append((match.start(), category))
    category = min(category_matches)[1] if category_matches else None

    use_cases = tuple(
        label for label, pattern in _USE_CASE_PATTERNS if pattern.search(text)
    )
    required, preferred, excluded = _extract_feature_groups(text)
    preferred_brands, excluded_brands = _extract_brands(text)
    delivery_location, delivery_postal_code = _extract_delivery(text)

    return ShoppingConstraints(
        budget_min=budget_min,
        budget_max=budget_max,
        budget_target=budget_target,
        budget_currency=budget_currency,
        category=category,
        use_cases=use_cases,
        required_features=required,
        preferred_features=preferred,
        excluded_features=excluded,
        preferred_brands=preferred_brands,
        excluded_brands=excluded_brands,
        delivery_location=delivery_location,
        delivery_postal_code=delivery_postal_code,
    )
