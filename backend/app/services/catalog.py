from sqlalchemy import or_, select
from sqlalchemy.orm import Session
from app.models.entities import Product


class CatalogService:

    def __init__(self, db: Session) -> None:
        self.db = db

    def search(
        self,
        q: str | None = None,
        limit: int = 10,
        max_price: float | None = None
    ) -> list[Product]:

        if not q or not q.strip():
            stmt = select(Product).order_by(Product.rating.desc())
            if max_price is not None:
                stmt = stmt.where(Product.price <= max_price)
            stmt = stmt.limit(limit)
            return list(self.db.scalars(stmt).all())

        text = q.lower()

        aliases = {
            "mobile": ["phone", "mobile", "smartphone", "iphone", "samsung"],
            "phone": ["phone", "mobile", "smartphone", "iphone", "samsung", "galaxy"],
            "iphone": ["iphone", "apple", "phone", "smartphone"],
            "samsung": ["samsung", "galaxy", "phone", "smartphone"],
            "apple": ["apple", "iphone", "macbook", "ipad", "airpods"],
            "laptop": ["laptop", "notebook", "macbook", "asus", "tuf"],
            "keyboard": ["keyboard", "mechanical keyboard", "firefly", "keychron", "redragon", "cosmic byte", "gaming keyboard"],
            "earbuds": ["earbuds", "earbud", "tws", "airdopes", "oneplus buds", "sony", "headphones"],
            "headphones": ["headphone", "headphones", "earbuds", "earphones", "airpods", "airdopes"],
            "watch": ["watch", "smartwatch", "apple watch", "galaxy watch"],
            "speaker": ["speaker", "speakers", "soundbar"],
            "tablet": ["tablet", "tablets", "ipad"]
        }

        words = set(text.split())

        search_terms = set(words)

        for key, values in aliases.items():
            if key in text:
                search_terms.update(values)

        non_informative_words = {
            "under", "below", "budget", "recommend", "suggest", "good", "best",
            "with", "for", "around", "upto", "within", "search", "give", "show",
            "me", "find", "less", "than", "price", "please", "get", "product",
            "item", "option", "options", "buy", "pick", "want", "need", "cheap",
            "affordable", "like", "which", "what", "where", "how", "much"
        }

        search_terms = [
            term for term in search_terms
            if len(term) > 2
            and term not in non_informative_words
            and not term.isdigit()
        ]

        filters = []

        for term in search_terms:
            filters.extend([
                Product.name.ilike(f"%{term}%"),
                Product.brand.ilike(f"%{term}%"),
                Product.description.ilike(f"%{term}%")
            ])

        stmt = select(Product)

        if filters:
            stmt = stmt.where(or_(*filters))

        if max_price is not None:
            stmt = stmt.where(Product.price <= max_price)

        stmt = stmt.order_by(Product.rating.desc()).limit(limit)

        return list(self.db.scalars(stmt).all())

    def get_many(
        self,
        product_ids: list[int]
    ) -> list[Product]:

        return list(
            self.db.scalars(
                select(Product).where(Product.id.in_(product_ids))
            ).all()
        )
