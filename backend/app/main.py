from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from app.api.routes import router
from app.db.session import Base, SessionLocal, engine
from app import models  # noqa: F401
from app.models.entities import Category, Product, Review
from app.core.config import get_settings

Base.metadata.create_all(bind=engine)

# Auto-seed initial catalog for Indian Market if database is fresh
def auto_seed_catalog(db: Session | None = None):
    should_close = False
    if db is None:
        db = SessionLocal()
        should_close = True
    try:
        existing_count = db.query(Product).count()
        has_budget_phone = db.query(Product).filter(Product.price <= 15000).count() > 0
        if existing_count > 0 and has_budget_phone:
            return

        seed_data = [
            # Earbuds & Audio
            {"name": "OnePlus Buds Pro 2 (ANC, Spatial Audio)", "brand": "OnePlus", "category": "Audio", "price": 8999, "rating": 4.6, "image": "https://images.unsplash.com/photo-1590658268037-6bf12165a8df?w=500&q=80", "desc": "Premium Dynaudio dual drivers, 48dB Active Noise Cancellation, and 39 hours battery life.", "attrs": {"battery": "39h", "anc": "48dB", "connectivity": "Bluetooth 5.3"}},
            {"name": "Sony WF-1000XM5 Wireless Noise Cancelling Earbuds", "brand": "Sony", "category": "Audio", "price": 24990, "rating": 4.8, "image": "https://images.unsplash.com/photo-1572536147248-ac59a8abfa4b?w=500&q=80", "desc": "Industry-leading noise cancellation, dual processors, LDAC Hi-Res audio, and bone conduction sensors.", "attrs": {"battery": "24h", "anc": "HD QN2e", "driver": "8.4mm Dynamic"}},
            {"name": "boAt Airdopes 141 ANC (42H Playtime)", "brand": "boAt", "category": "Audio", "price": 1499, "rating": 4.3, "image": "https://images.unsplash.com/photo-1590658268037-6bf12165a8df?w=500&q=80", "desc": "Affordable true wireless earbuds with 32dB active noise cancellation, ENx technology, and low latency gaming mode.", "attrs": {"battery": "42h", "driver": "10mm", "charging": "ASAP Fast Charge"}},
            {"name": "Realme Buds Air 6 Pro (50dB ANC)", "brand": "Realme", "category": "Audio", "price": 4999, "rating": 4.5, "image": "https://images.unsplash.com/photo-1606220588913-b3aacb4d2f46?w=500&q=80", "desc": "Flagship 50dB active noise cancellation with Hi-Res LDAC support and dual coaxial drivers.", "attrs": {"battery": "40h", "anc": "50dB", "latency": "55ms"}},

            # Mechanical Keyboards & PC
            {"name": "Cosmic Byte CB-GK-16 Firefly Mechanical Keyboard (Outemu Blue)", "brand": "Cosmic Byte", "category": "Peripherals", "price": 2199, "rating": 4.4, "image": "https://images.unsplash.com/photo-1618384887929-16ec33fab9ef?w=500&q=80", "desc": "Tenkeyless (TKL) compact mechanical gaming keyboard with tactile Outemu Blue switches and per-key RGB backlighting.", "attrs": {"switch": "Outemu Blue", "layout": "TKL 87-key", "cable": "Braided Type-C"}},
            {"name": "Keychron K2 V2 Wireless Mechanical Keyboard (Gateron Brown)", "brand": "Keychron", "category": "Peripherals", "price": 7999, "rating": 4.8, "image": "https://images.unsplash.com/photo-1587829741301-dc798b83add3?w=500&q=80", "desc": "75% compact wireless keyboard compatible with Mac & Windows, hot-swappable switches, and 4000mAh battery.", "attrs": {"switch": "Gateron Brown Tactile", "layout": "75% 84-Key", "connectivity": "Bluetooth 5.1 / Type-C"}},
            {"name": "Redragon K552 Kumara RGB Mechanical Gaming Keyboard", "brand": "Redragon", "category": "Peripherals", "price": 2790, "rating": 4.5, "image": "https://images.unsplash.com/photo-1595225476474-87563907a212?w=500&q=80", "desc": "Durable metal-ABS construction with custom mechanical red linear switches and splash-proof design.", "attrs": {"switch": "Red Linear Switches", "layout": "Tenkeyless", "lighting": "RGB 18 Modes"}},

            # Phones — Flagship & Mid-Range
            {"name": "OnePlus 12 5G (16GB RAM, 512GB Storage)", "brand": "OnePlus", "category": "Phones", "price": 64999, "rating": 4.7, "image": "https://images.unsplash.com/photo-1592750475338-74b7b21085ab?w=500&q=80", "desc": "Snapdragon 8 Gen 3, 2K 120Hz ProXDR Display, Hasselblad 4th Gen camera, and 100W SUPERVOOC charging.", "attrs": {"processor": "Snapdragon 8 Gen 3", "camera": "50MP Sony LYT-808", "battery": "5400mAh 100W"}},
            {"name": "Apple iPhone 15 (128GB, Black)", "brand": "Apple", "category": "Phones", "price": 69900, "rating": 4.8, "image": "https://images.unsplash.com/photo-1695048133142-1a20484d2569?w=500&q=80", "desc": "Dynamic Island, 48MP main camera with 2x Telephoto, A16 Bionic chip, and USB-C connectivity.", "attrs": {"processor": "A16 Bionic", "camera": "48MP Dual", "display": "6.1 Super Retina XDR"}},
            {"name": "Samsung Galaxy S24 Ultra 5G (12GB RAM, 256GB)", "brand": "Samsung", "category": "Phones", "price": 129999, "rating": 4.8, "image": "https://images.unsplash.com/photo-1610945265064-0e34e5519bbf?w=500&q=80", "desc": "Titanium frame, Galaxy AI live translation, 200MP camera with 100x Space Zoom, and built-in S-Pen.", "attrs": {"processor": "Snapdragon 8 Gen 3 for Galaxy", "camera": "200MP Quad", "screen": "6.8 QHD+ AMOLED 120Hz"}},
            {"name": "Redmi Note 13 Pro+ 5G (8GB RAM, 256GB)", "brand": "Xiaomi", "category": "Phones", "price": 27999, "rating": 4.4, "image": "https://images.unsplash.com/photo-1598327105666-5b89351aff97?w=500&q=80", "desc": "200MP OIS camera, 3D Curved 1.5K AMOLED display, IP68 water resistance, and 120W HyperCharge.", "attrs": {"processor": "Dimensity 7200 Ultra", "camera": "200MP OIS", "charging": "120W Fast Charge"}},

            # Budget 5G Phones Under ₹15,000
            {"name": "Motorola Moto G34 5G (8GB RAM, 128GB)", "brand": "Motorola", "category": "Phones", "price": 11999, "rating": 4.5, "image": "https://images.unsplash.com/photo-1511707171634-5f897ff02aa9?w=500&q=80", "desc": "Best overall 5G phone under ₹12,000. Snapdragon 695 5G, 120Hz display, clean stock Android 14, and 5000mAh battery.", "attrs": {"processor": "Snapdragon 695 5G", "screen": "120Hz HD+", "battery": "5000mAh"}},
            {"name": "Realme 12x 5G (6GB RAM, 128GB)", "brand": "Realme", "category": "Phones", "price": 11999, "rating": 4.4, "image": "https://images.unsplash.com/photo-1598327105666-5b89351aff97?w=500&q=80", "desc": "Dimensity 6100+ 5G processor, 45W SUPERVOOC fast charging, 50MP AI camera, and 120Hz display.", "attrs": {"processor": "Dimensity 6100+", "charging": "45W Fast Charge", "camera": "50MP AI"}},
            {"name": "Poco M6 Pro 5G (6GB RAM, 128GB)", "brand": "POCO", "category": "Phones", "price": 10999, "rating": 4.3, "image": "https://images.unsplash.com/photo-1592750475338-74b7b21085ab?w=500&q=80", "desc": "Snapdragon 4 Gen 2 4nm 5G chipset, premium glass back design, 90Hz FHD+ display, and IP53 splash resistance.", "attrs": {"processor": "Snapdragon 4 Gen 2", "display": "90Hz FHD+ Glass Back", "battery": "5000mAh"}},
            {"name": "Samsung Galaxy M14 5G (6GB RAM, 128GB)", "brand": "Samsung", "category": "Phones", "price": 12490, "rating": 4.4, "image": "https://images.unsplash.com/photo-1610945265064-0e34e5519bbf?w=500&q=80", "desc": "Monster 6000mAh battery, 5nm Exynos 1330 5G processor, 50MP triple camera, and 13 5G bands.", "attrs": {"battery": "6000mAh", "processor": "Exynos 1330 5G", "camera": "50MP Triple"}},
            {"name": "CMF Phone 1 by Nothing (6GB RAM, 128GB)", "brand": "Nothing", "category": "Phones", "price": 14999, "rating": 4.6, "image": "https://images.unsplash.com/photo-1598327105666-5b89351aff97?w=500&q=80", "desc": "Best design & performance under ₹15,000. Dimensity 7300 4nm processor, 120Hz Super AMOLED display, and unique modular back panel.", "attrs": {"processor": "MediaTek Dimensity 7300", "display": "120Hz Super AMOLED", "camera": "50MP Sony"}},
            {"name": "Redmi 13C 5G (4GB RAM, 128GB)", "brand": "Xiaomi", "category": "Phones", "price": 9999, "rating": 4.2, "image": "https://images.unsplash.com/photo-1511707171634-5f897ff02aa9?w=500&q=80", "desc": "Most affordable 5G phone in India under ₹10,000. Dimensity 6100+ processor, 50MP AI camera, and starshine glass design.", "attrs": {"processor": "Dimensity 6100+", "screen": "90Hz HD+", "battery": "5000mAh"}},

            # Laptops
            {"name": "Apple MacBook Air M3 (13.6-inch, 8GB RAM, 256GB SSD)", "brand": "Apple", "category": "Laptops", "price": 104900, "rating": 4.9, "image": "https://images.unsplash.com/photo-1517336714731-489689fd1ca8?w=500&q=80", "desc": "Blazing-fast M3 chip with 8-core CPU and 10-core GPU, Liquid Retina display, and 18 hours battery life.", "attrs": {"processor": "Apple M3 Chip", "display": "13.6 Liquid Retina", "battery": "18 Hours"}},
            {"name": "ASUS TUF Gaming F15 (Intel Core i5-11400H, RTX 2050 4GB)", "brand": "ASUS", "category": "Laptops", "price": 49990, "rating": 4.5, "image": "https://images.unsplash.com/photo-1603302576837-37561b2e2302?w=500&q=80", "desc": "15.6-inch FHD 144Hz display, 16GB DDR4 RAM, 512GB NVMe SSD, and military-grade durability.", "attrs": {"gpu": "NVIDIA RTX 2050 4GB", "ram": "16GB DDR4", "screen": "144Hz IPS"}}
        ]

        cat_names = set(item["category"] for item in seed_data)
        cats = {name: Category(name=name) for name in cat_names}
        db.add_all(cats.values())
        db.flush()

        for item in seed_data:
            p = Product(
                name=item["name"],
                brand=item["brand"],
                description=item["desc"],
                price=float(item["price"]),
                currency="₹",
                rating=float(item["rating"]),
                stock=25,
                image_url=item["image"],
                attributes=item["attrs"],
                category_id=cats[item["category"]].id
            )
            db.add(p)
            db.flush()
            db.add(Review(
                product_id=p.id,
                user_name="Verified Buyer",
                rating=p.rating,
                title="Excellent value in India",
                body="Performs exceptionally well in this price bracket. Highly recommended for daily use."
            ))
        db.commit()
    except Exception as err:
        print(f"Auto-seed notice: {err}")
    finally:
        if should_close:
            db.close()

auto_seed_catalog()

settings = get_settings()

app = FastAPI(title="ShopSense API - India Edition")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "region": "IN", "currency": "INR"}
