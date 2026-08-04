from random import choice, randint, uniform, seed
from backend.app.db.session import Base, SessionLocal, engine
from backend.app.models import Category, Product, Review, User, Order
from backend.app.core.security import hash_password
seed(42); Base.metadata.create_all(engine); db=SessionLocal()
if not db.query(User).filter_by(email='admin@shopsense.dev').first(): db.add(User(id=1,email='admin@shopsense.dev',full_name='Admin',hashed_password=hash_password('Password123'),is_admin=True))
if db.query(Product).count()<500:
    cats=[('Laptops','laptops'),('Phones','phones'),('Audio','audio'),('Home','home'),('Fitness','fitness')]
    cat_objs=[]
    for name,slug in cats:
        c=db.query(Category).filter_by(slug=slug).first() or Category(name=name,slug=slug); db.add(c); db.flush(); cat_objs.append(c)
    brands=['Aero','Nova','Pulse','Zenith','Eco','Orion','Nimbus','Vertex','Luma','Atlas']
    adjectives=['Pro','Air','Max','Smart','Ultra','Prime','Flex','Go','Elite','Core']
    for i in range(1,526):
        c=choice(cat_objs); brand=choice(brands); name=f'{brand} {choice(adjectives)} {c.name[:-1]} {i}'
        price=round(uniform(29,2499),2); rating=round(uniform(3.1,5.0),1)
        p=Product(category_id=c.id,name=name,brand=brand,description=f'{name} with reliable performance, modern design, strong battery life, and best-fit features for {c.name.lower()} shoppers.',price=price,currency='USD',rating=rating,stock=randint(0,150),image_url=f'https://picsum.photos/seed/shopsense-{i}/640/480',attributes={'category':c.slug,'warranty':'1 year','color':choice(['black','silver','blue','green'])})
        db.add(p); db.flush()
        for r in range(3):
            rr=max(1,min(5,round(rating+uniform(-1,1),1))); db.add(Review(product_id=p.id,rating=rr,title=choice(['Great value','Solid choice','Premium feel','Could be better','Highly recommended']),body=f'Customer review for {name}: performance, quality, delivery, and value were evaluated after daily use.',sentiment='positive' if rr>=4 else 'mixed' if rr>=3 else 'negative'))
    db.add(Order(user_id=1,status='paid',total=1299.99)); db.commit()
db.close(); print('Seeded ShopSense catalog')
