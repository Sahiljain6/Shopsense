import json
import os
import re

import httpx
from bs4 import BeautifulSoup

from app.core.config import get_settings
from app.services.ssrf_validator import SSRFError, safe_fetch_url, validate_url

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


def fetch_html(url: str) -> tuple[str, str | None]:
    """Safely fetch HTML with SSRF validation, size capping, and redirect checks."""
    try:
        final_url, html = safe_fetch_url(url, timeout=10)
        return final_url, html
    except SSRFError as exc:
        print(f"SSRF validation blocked URL '{url}': {exc}")
        return url, None
    except Exception:
        pass

    try:
        validate_url(url)
        return url, fetch_with_scraperapi(url)
    except Exception:
        return url, None


def _fetch_html(url: str) -> tuple[str, str | None]:
    return fetch_html(url)


def _from_amazon_or_html(soup: BeautifulSoup) -> dict | None:
    """Extract product data from Amazon or generic product page HTML structure."""
    name = None
    title_tag = soup.find(id="productTitle") or soup.find("title") or soup.find("h1")
    if title_tag:
        name = title_tag.get_text().strip()

    price = None
    price_tag = (
        soup.find("span", class_="a-price-whole")
        or soup.find("span", class_="a-offscreen")
        or soup.find(id="priceblock_ourprice")
        or soup.find(id="priceblock_dealprice")
    )
    if price_tag:
        price = _clean_price(price_tag.get_text())

    if price is None and soup.title:
        price_match = re.search(r"(?:₹|Rs\.?|INR|\$)\s*([\d,]+)", soup.title.get_text())
        if price_match:
            price = _clean_price(price_match.group(1))

    image_url = ""
    img_tag = soup.find(id="landingImage") or soup.find("meta", attrs={"property": "og:image"})
    if img_tag:
        image_url = img_tag.get("src") or img_tag.get("content") or ""

    if name and price is not None:
        return {
            "name": name[:150],
            "brand": "Amazon Item",
            "description": f"Imported product from {name[:100]}",
            "price": price,
            "currency": "INR",
            "image_url": image_url
        }

    return None


def scrape_product(url: str) -> dict | None:
    """Fetch a product page and extract name/price/image/brand.
    Supports Amazon shortlinks (amzn.in), schema.org JSON-LD, OpenGraph,
    and 100% free web search fallback if site blocks scrapers."""
    try:
        validate_url(url)
    except SSRFError as exc:
        print(f"SSRF validation blocked product scrape for '{url}': {exc}")
        return None

    final_url, html = fetch_html(url)

    if html:
        soup = BeautifulSoup(html, "html.parser")
        data = _from_json_ld(soup) or _from_meta_tags(soup) or _from_amazon_or_html(soup)
        if data and data.get("price") is not None:
            data.setdefault("description", "")
            data.setdefault("brand", "Imported Product")
            data.setdefault("currency", "INR")
            data.setdefault("image_url", "")
            return data

    # 100% Free Live Search Fallback if page blocked or structure unparsed
    try:
        from app.services.live_search import search_live_deals
        search_query = final_url.replace("https://", "").replace("http://", "").replace("www.", "")
        deals = search_live_deals(search_query, max_results=1)
        if deals:
            d = deals[0]
            price_val = _clean_price(d.get("price_str")) or 999.0
            return {
                "name": d.get("title", "Imported Product")[:150],
                "brand": d.get("store", "Online Store"),
                "description": d.get("snippet", ""),
                "price": price_val,
                "currency": "INR",
                "image_url": ""
            }
    except Exception as err:
        print(f"Scraper live search fallback notice: {err}")

    return None


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
