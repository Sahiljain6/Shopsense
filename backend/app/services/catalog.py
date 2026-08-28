from sqlalchemy import or_, select
from sqlalchemy.orm import Session
from app.models.entities import Category, Product


CATEGORY_KEYWORDS = {
    "Phones": ["phone", "phones", "mobile", "mobiles", "smartphone", "smartphones", "cellphone", "cellphones", "iphone", "samsung", "galaxy", "redmi", "oneplus", "realme", "poco", "motorola", "moto", "cmf", "xiaomi"],
    "Laptops": ["laptop", "laptops", "notebook", "notebooks", "macbook", "asus", "tuf"],
    "Audio": ["earbuds", "earbud", "earphone", "earphones", "headphone", "headphones", "audio", "tws", "airdopes", "buds"],
    "Peripherals": ["keyboard", "keyboards", "mechanical keyboard", "gaming keyboard", "mouse", "watch", "smartwatch"]
}


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

        text = q.lower()
        matched_cat_name = self.resolve_category_name(text)

        # 1. Primary Filter by Category Relationship if Category is Resolved
        if matched_cat_name:
            cat_obj = self.db.scalars(
                select(Category).where(Category.name.ilike(matched_cat_name))
            ).first()

            if cat_obj:
                stmt = select(Product).where(Product.category_id == cat_obj.id)
                if max_price is not None:
                    stmt = stmt.where(Product.price <= max_price)

                # Check for secondary specific terms (e.g. "5g", "pro", "128gb", "oled")
                specific_words = [
                    w for w in text.split()
                    if w not in {"phone", "phones", "mobile", "mobiles", "smartphone", "laptop", "laptops", "earbuds", "keyboard", "under", "below", "budget", "show", "me", "give", "find", "best", "good", "recommend"}
                    and len(w) > 2 and not w.isdigit()
                ]
                if specific_words:
                    spec_filters = []
                    for sw in specific_words:
                        spec_filters.extend([
                            Product.name.ilike(f"%{sw}%"),
                            Product.brand.ilike(f"%{sw}%"),
                            Product.description.ilike(f"%{sw}%")
                        ])
                    spec_stmt = stmt.where(or_(*spec_filters)).order_by(Product.rating.desc()).limit(limit)
                    spec_results = list(self.db.scalars(spec_stmt).all())
                    if spec_results:
                        return spec_results

                stmt = stmt.order_by(Product.rating.desc()).limit(limit)
                results = list(self.db.scalars(stmt).all())
                if results:
                    return results

        # 2. Fallback to Substring & Alias Matching if Category is not matched or returned empty
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
