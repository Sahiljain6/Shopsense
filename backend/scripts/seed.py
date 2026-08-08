from app.db.session import Base, SessionLocal, engine
from app.models.entities import Category, Product, Review, User
from app.core.security import hash_password

Base.metadata.create_all(bind=engine)
CATS = ["Phones", "Laptops", "Audio", "Wearables"]
BRANDS = ["Samsung", "Xiaomi", "OnePlus", "Apple", "HP", "Lenovo", "Sony", "Boat"]

def main() -> None:
    db = SessionLocal()
    try:
        if db.query(Product).count():
            return
        cats = {name: Category(name=name) for name in CATS}
        db.add_all(cats.values()); db.flush()
        products = []
        for i in range(40):
            cat = CATS[i % len(CATS)]
            brand = BRANDS[i % len(BRANDS)]
            products.append(Product(name=f"{brand} {cat[:-1]} Sense {i+1}", brand=brand, description=f"Reliable {cat.lower()} option for work, travel, gifting, and everyday use.", price=float(7999 + i * 1250), rating=round(3.8 + (i % 12) / 10, 1), stock=0 if i % 9 == 0 else 12 + i, image_url="https://placehold.co/600x400", attributes={"memory": "8GB" if cat in ["Phones", "Laptops"] else "N/A", "battery": f"{3000+i*50}mAh", "warranty": "1 year"}, category_id=cats[cat].id))
        db.add_all(products); db.flush()
        for p in products:
            db.add_all([Review(product_id=p.id, user_name="Demo shopper", rating=p.rating, title="Solid choice", body="Good value and dependable performance."), Review(product_id=p.id, user_name="Verified buyer", rating=max(3.0, p.rating-0.2), title="Worth considering", body="Useful features, but compare specs before buying.")])
        db.add(User(email="admin@shopsense.local", full_name="Admin", hashed_password=hash_password("adminpass123"), is_admin=True))
        db.commit()
    finally:
        db.close()

if __name__ == "__main__":
    main()
