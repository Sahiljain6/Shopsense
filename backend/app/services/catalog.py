from sqlalchemy import or_, select
from sqlalchemy.orm import Session
from app.models.entities import Product


class CatalogService:

    def __init__(self, db: Session) -> None:
        self.db = db

    def search(
        self,
        q: str | None = None,
        limit: int = 10
    ) -> list[Product]:

        if not q:
            return list(
                self.db.scalars(
                    select(Product)
                    .order_by(Product.rating.desc())
                    .limit(limit)
                ).all()
            )

        text = q.lower()

        aliases = {
            "mobile": ["phone", "mobile", "smartphone", "iphone", "samsung"],
            "phone": ["phone", "mobile", "smartphone", "iphone", "samsung", "galaxy"],
            "iphone": ["iphone", "apple", "phone", "smartphone"],
            "samsung": ["samsung", "galaxy", "phone", "smartphone"],
            "apple": ["apple", "iphone", "macbook", "ipad", "airpods"],
            "laptop": ["laptop", "notebook", "macbook"],
            "headphones": ["headphone", "headphones", "earbuds", "earphones", "airpods"],
            "watch": ["watch", "smartwatch", "apple watch", "galaxy watch"],
            "speaker": ["speaker", "speakers", "soundbar"],
            "tablet": ["tablet", "tablets", "ipad"]
        }

        words = set(text.split())

        search_terms = set(words)

        for key, values in aliases.items():
            if key in text:
                search_terms.update(values)

        search_terms = [
            term for term in search_terms
            if len(term) > 2
            and term not in {
                "under",
                "below",
                "budget",
                "recommend",
                "suggest",
                "good",
                "best",
                "with",
                "for",
                "around",
                "upto",
                "within"
            }
            and not term.isdigit()
        ]

        filters = []

        for term in search_terms:
            filters.extend([
                Product.name.ilike(f"%{term}%"),
                Product.brand.ilike(f"%{term}%"),
                Product.description.ilike(f"%{term}%")
            ])

        if not filters:
            return list(
                self.db.scalars(
                    select(Product)
                    .order_by(Product.rating.desc())
                    .limit(limit)
                ).all()
            )

        stmt = (
            select(Product)
            .where(or_(*filters))
            .order_by(Product.rating.desc())
            .limit(limit)
        )

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
