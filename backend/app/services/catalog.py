from sqlalchemy import or_, select
from sqlalchemy.orm import Session
from backend.app.models import Product, Review


class CatalogService:
    def __init__(self, db: Session):
        self.db = db

    def search(self, query: str, limit: int = 10) -> list[Product]:
        terms = [t for t in query.split() if len(t) > 2]
        stmt = select(Product)
        if terms:
            filters = [
                Product.name.ilike(f"%{t}%")
                | Product.brand.ilike(f"%{t}%")
                | Product.description.ilike(f"%{t}%")
                for t in terms
            ]
            stmt = stmt.where(or_(*filters))
        return list(self.db.scalars(stmt.order_by(Product.rating.desc()).limit(limit)))

    def by_ids(self, ids: list[int]) -> list[Product]:
        return list(self.db.scalars(select(Product).where(Product.id.in_(ids))))

    def reviews(self, product_id: int) -> list[Review]:
        return list(
            self.db.scalars(select(Review).where(Review.product_id == product_id))
        )
