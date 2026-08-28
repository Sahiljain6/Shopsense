from sqlalchemy import select
from sqlalchemy.orm import Session
from app.models.entities import Product
from app.services.search import resolve_products, CATEGORY_KEYWORDS


class CatalogService:

    def __init__(self, db: Session) -> None:
        self.db = db

    def resolve_category_name(self, text: str) -> str | None:
        lowered = text.lower()
        for cat_name, kws in CATEGORY_KEYWORDS.items():
            if any(kw in lowered for kw in kws):
                return cat_name
        return None

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

        resolved = resolve_products(q, db=self.db, limit=limit)
        products = resolved.products

        if max_price is not None:
            products = [p for p in products if p.price <= max_price]

        return products[:limit]

    def get_many(
        self,
        product_ids: list[int]
    ) -> list[Product]:

        return list(
            self.db.scalars(
                select(Product).where(Product.id.in_(product_ids))
            ).all()
        )
