import re
from sqlalchemy import or_, select
from sqlalchemy.orm import Session
from app.models.entities import Product

TERM_SYNONYMS = {
    "mobile": "phone",
    "mobiles": "phone",
    "smartphone": "phone",
    "smartphones": "phone",
    "cell": "phone",
    "notebook": "laptop",
    "notebooks": "laptop",
    "buds": "earbuds",
    "earphones": "headphones",
    "headsets": "headphones",
    "headset": "headphones",
    "smartwatch": "watch",
    "smartwatches": "watch",
    "pc": "computer",
    "television": "tv",
    "tv": "television",
}
STOP_WORDS = {"a", "an", "the", "for", "with", "under", "below", "upto", "up", "to", "within", "what", "can", "i", "buy", "recommend", "suggest", "show", "me", "best", "good", "cheap", "rated", "product", "products", "something", "need", "want", "have", "rs", "inr", "lakh", "lakhs", "k"}


class CatalogService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def query_terms(self, q: str | None) -> list[str]:
        if not q:
            return []
        normalized = q.lower().replace("cell phone", "phone").replace("smart watches", "watches").replace("gaming pc", "computer")
        raw_terms = re.findall(r"[a-z0-9]+", normalized)
        terms: list[str] = []
        for term in raw_terms:
            if term.isdigit() or term in STOP_WORDS:
                continue
            mapped = TERM_SYNONYMS.get(term, term)
            if mapped not in terms:
                terms.append(mapped)
        return terms

    def search(self, q: str | None = None, limit: int = 10) -> list[Product]:
        stmt = select(Product).limit(limit)
        terms = self.query_terms(q)
        if terms:
            filters = [Product.name.ilike(f"%{term}%") | Product.brand.ilike(f"%{term}%") | Product.description.ilike(f"%{term}%") for term in terms]
            stmt = select(Product).where(or_(*filters)).limit(limit)
        return list(self.db.scalars(stmt).all())

    def get_many(self, product_ids: list[int]) -> list[Product]:
        return list(self.db.scalars(select(Product).where(Product.id.in_(product_ids))).all())
