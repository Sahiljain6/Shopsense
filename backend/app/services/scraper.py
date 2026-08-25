import json
import os
import re

import httpx
from bs4 import BeautifulSoup

from app.core.config import get_settings

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-IN,en;q=0.9"
}


def fetch_with_scraperapi(
    url: str,
    api_key: str | None = None,
    render: bool = False,
    country_code: str | None = None
) -> str | None:
    """Fetch HTML or page content directly via ScraperAPI API gateway.
    
    Args:
        url: The web URL to scrape.
        api_key: Optional explicit API key. Defaults to settings or SCRAPERAPI_KEY env var.
        render: Pass True if Javascript rendering is needed for single-page applications.
        country_code: Optional ISO country code to geo-target proxy requests.
    """
    key = api_key or get_settings().scraperapi_key or os.getenv("SCRAPERAPI_KEY")
    if not key:
        return None

    params = {
        "api_key": key,
        "url": url,
    }
    if render:
        params["render"] = "true"
    if country_code:
        params["country_code"] = country_code

    try:
        with httpx.Client(timeout=30) as client:
            response = client.get("https://api.scraperapi.com/", params=params)
            response.raise_for_status()
            return response.text
    except httpx.HTTPError:
        return None


def fetch_html(url: str) -> str | None:
    """Try a direct fetch first (fast, free). If the site blocks us or
    errors out and SCRAPERAPI_KEY is configured, retry through ScraperAPI's
    proxy (handles JS-rendering/anti-bot sites)."""
    try:
        with httpx.Client(
            headers=HEADERS,
            timeout=10,
            follow_redirects=True
        ) as client:
            response = client.get(url)
            response.raise_for_status()
            return response.text
    except httpx.HTTPError:
        pass

    return fetch_with_scraperapi(url)


def _fetch_html(url: str) -> str | None:
    return fetch_html(url)


def scrape_product(url: str) -> dict | None:
    """Fetch a product page and extract name/price/image/brand.
    Tries schema.org JSON-LD first (most reliable), falls back to
    Open Graph / product meta tags. Returns None if no usable price
    could be found (e.g. JS-rendered page, or site blocked us and no
    ScraperAPI fallback is configured)."""

    html = _fetch_html(url)

    if html is None:
        return None

    soup = BeautifulSoup(html, "html.parser")

    data = _from_json_ld(soup) or _from_meta_tags(soup)

    if not data or data.get("price") is None:
        return None

    if not data.get("name"):
        data["name"] = (
            soup.title.string.strip()
            if soup.title and soup.title.string
            else "Imported product"
        )

    data.setdefault("description", "")
    data.setdefault("brand", "Unknown")
    data.setdefault("currency", "INR")
    data.setdefault("image_url", "")

    return data


def _clean_price(raw: object) -> float | None:
    if raw is None:
        return None

    if isinstance(raw, (int, float)):
        return float(raw)

    text = re.sub(r"[^\d.]", "", str(raw).replace(",", ""))

    if not text:
        return None

    try:
        return float(text)
    except ValueError:
        return None


def _first(value: object) -> object:
    if isinstance(value, list):
        return value[0] if value else None
    return value


def _find_products(node: object, found: list[dict]) -> None:
    if isinstance(node, dict):
        types = node.get("@type")
        types = types if isinstance(types, list) else [types]

        if any(str(t).lower() == "product" for t in types if t):
            found.append(node)

        for value in node.values():
            _find_products(value, found)

    elif isinstance(node, list):
        for item in node:
            _find_products(item, found)


def _from_json_ld(soup: BeautifulSoup) -> dict | None:
    for script in soup.find_all("script", type="application/ld+json"):
        raw = script.string or script.get_text()

        if not raw:
            continue

        try:
            parsed = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            continue

        found: list[dict] = []
        _find_products(parsed, found)

        for product in found:
            offers = _first(product.get("offers"))

            price = None
            currency = None

            if isinstance(offers, dict):
                price = _clean_price(offers.get("price") or offers.get("lowPrice"))
                currency = offers.get("priceCurrency")

            if price is None:
                continue

            brand = product.get("brand")
            if isinstance(brand, dict):
                brand = brand.get("name")

            image = _first(product.get("image"))
            if isinstance(image, dict):
                image = image.get("url")

            return {
                "name": product.get("name"),
                "brand": brand,
                "description": product.get("description"),
                "price": price,
                "currency": currency or "INR",
                "image_url": image
            }

    return None


def _from_meta_tags(soup: BeautifulSoup) -> dict | None:

    def meta(*names: str) -> str | None:
        for name in names:
            tag = (
                soup.find("meta", attrs={"property": name})
                or soup.find("meta", attrs={"name": name})
            )
            if tag and tag.get("content"):
                return tag["content"]
        return None

    price = _clean_price(meta("product:price:amount", "og:price:amount"))

    if price is None:
        return None

    return {
        "name": meta("og:title", "twitter:title"),
        "brand": meta("og:site_name"),
        "description": meta("og:description", "description"),
        "price": price,
        "currency": meta("product:price:currency", "og:price:currency") or "INR",
        "image_url": meta("og:image", "twitter:image")
    }
