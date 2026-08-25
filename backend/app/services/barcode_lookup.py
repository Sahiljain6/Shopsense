import httpx


def lookup_barcode(barcode: str) -> dict[str, object] | None:
    """Lookup product details, ingredients, Nutri-Score, and allergens by barcode GTIN/UPC
    using Open Food Facts API (100% Free).
    """
    clean_barcode = barcode.strip().replace(" ", "")
    if not clean_barcode:
        return None

    url = f"https://world.openfoodfacts.org/api/v2/product/{clean_barcode}.json"

    try:
        with httpx.Client(timeout=8) as client:
            resp = client.get(url, headers={"User-Agent": "ShopSense-Free-AI-Assistant/1.0"})
            if resp.status_code == 200:
                data = resp.json()
                if data.get("status") == 1:
                    product = data.get("product", {})

                    nutriscore = product.get("nutriscore_grade", "unknown").upper()
                    ingredients = product.get("ingredients_text_en") or product.get("ingredients_text") or "Not specified"
                    allergens = product.get("allergens_from_ingredients") or "None listed"

                    return {
                        "barcode": clean_barcode,
                        "name": product.get("product_name") or product.get("product_name_en") or "Barcode Product",
                        "brand": product.get("brands") or "Unknown Brand",
                        "categories": product.get("categories") or "General Grocery",
                        "health_score": nutriscore,
                        "ingredients": ingredients,
                        "allergens": allergens,
                        "image_url": product.get("image_front_url") or product.get("image_url") or "",
                        "is_grocery": True
                    }
    except Exception as error:
        print(f"Open Food Facts Barcode API notice: {error}")

    return None
