from sqlalchemy import or_, select
from sqlalchemy.orm import Session
from app.models.entities import Product


class CatalogService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def search(self, q: str | None = None, limit: int = 10) -> list[Product]:
        stmt = select(Product).limit(limit)
        if q:
            terms = [term for term in q.lower().split() if not term.isdigit()]
            filters = [Product.name.ilike(f"%{term}%") | Product.brand.ilike(f"%{term}%") | Product.description.ilike(f"%{term}%") for term in terms]
            if filters:
                stmt = select(Product).where(or_(*filters)).limit(limit)
        return list(self.db.scalars(stmt).all())

    def get_many(self, product_ids: list[int]) -> list[Product]:
        return list(self.db.scalars(select(Product).where(Product.id.in_(product_ids))).all())
