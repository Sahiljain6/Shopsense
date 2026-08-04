from backend.app.db.session import Base, SessionLocal, engine
from backend.app.models import Category, Product, Review, User
from backend.app.core.security import hash_password
Base.metadata.create_all(engine); db = SessionLocal()
if not db.query(User).first(): db.add(User(id=1,email="admin@shopsense.dev",full_name="Admin",hashed_password=hash_password("Password123"),is_admin=True))
if not db.query(Category).first():
    c=Category(name="Electronics",slug="electronics"); db.add(c); db.flush()
    p=Product(category_id=c.id,name="AeroBook Gaming 15",brand="Aero",description="RTX gaming laptop under ₹80,000 with 16GB RAM",price=79999,currency="INR",rating=4.5,stock=12,image_url="https://res.cloudinary.com/demo/image/upload/laptop.jpg",attributes={"gpu":"RTX","ram":"16GB"}); db.add(p); db.flush()
    db.add(Review(product_id=p.id,rating=5,title="Great gaming value",body="Fast and cool.",sentiment="positive"))
db.commit(); db.close()
