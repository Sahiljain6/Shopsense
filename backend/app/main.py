from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlalchemy.orm import Session
from app.api.routes import router
from app.db.session import Base, SessionLocal, engine
from app import models  # noqa: F401
from app.models.entities import Category, Product, Review, SeedVersion
from app.core.config import get_settings

Base.metadata.create_all(bind=engine)


def ensure_schema_upgrades() -> None:
    """Ensure database schema is up-to-date across all database engines (PostgreSQL, SQLite)."""
    try:
        with engine.connect() as conn:
            if engine.dialect.name == "postgresql":
                conn.execute(text("ALTER TABLE products ADD COLUMN IF NOT EXISTS sku VARCHAR(120);"))
                conn.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS ix_products_sku ON products (sku);"))
                conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS google_id VARCHAR(255);"))
                conn.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS ix_users_google_id ON users (google_id);"))
                conn.execute(text("ALTER TABLE users ALTER COLUMN hashed_password DROP NOT NULL;"))
                conn.commit()
            elif engine.dialect.name == "sqlite":
                cols = [r[1] for r in conn.execute(text("PRAGMA table_info(products);")).fetchall()]
                if cols and "sku" not in cols:
                    conn.execute(text("ALTER TABLE products ADD COLUMN sku VARCHAR(120);"))
                    conn.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS ix_products_sku ON products (sku);"))
                    conn.commit()
                u_cols = [r[1] for r in conn.execute(text("PRAGMA table_info(users);")).fetchall()]
                if u_cols and "google_id" not in u_cols:
                    conn.execute(text("ALTER TABLE users ADD COLUMN google_id VARCHAR(255);"))
                    conn.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS ix_users_google_id ON users (google_id);"))
                    conn.commit()
    except Exception as err:
        print(f"Notice during schema upgrade check: {err}")


ensure_schema_upgrades()

# Bump this number whenever seed_data changes (new products, price updates, etc.)
SEED_VERSION = 3

SEED_DATA = [
    # Earbuds & Audio
    {
        "sku": "oneplus-buds-pro-2",
        "name": "OnePlus Buds Pro 2 (ANC, Spatial Audio)",
        "brand": "OnePlus",
        "category": "Audio",
        "price": 8999,
        "rating": 4.6,
        "image": "https://images.unsplash.com/photo-1590658268037-6bf12165a8df?w=500&q=80",
        "desc": "Premium Dynaudio dual drivers, 48dB Active Noise Cancellation, and 39 hours battery life with Google Spatial Audio.",
        "attrs": {
            "best_for": "Best audiophile ANC earbuds with Spatial Audio",
            "driver": "11mm bass + 6mm planar tweeter dual drivers (Dynaudio co-tuned)",
            "anc": "48dB Smart Adaptive Active Noise Cancellation",
            "battery": "39 hours total playtime (9h earbuds + 30h case)",
            "charging": "Fast Warp Charge (10 mins = 10 hours) + Qi wireless charging",
            "connectivity": "Bluetooth 5.3, LHDC 4.0 Lossless Hi-Res Audio, 54ms low latency",
            "water_resistance": "IP55 dust and water resistant",
            "store_prices": {"OnePlus Store": 8999, "Amazon India": 8999, "Flipkart": 9499}
        }
    },
    {
        "sku": "sony-wf-1000xm5",
        "name": "Sony WF-1000XM5 Wireless Noise Cancelling Earbuds",
        "brand": "Sony",
        "category": "Audio",
        "price": 24990,
        "rating": 4.8,
        "image": "https://images.unsplash.com/photo-1572536147248-ac59a8abfa4b?w=500&q=80",
        "desc": "Industry-leading noise cancellation, dual proprietary processors, LDAC Hi-Res audio, and bone conduction sensors.",
        "attrs": {
            "best_for": "Best noise cancellation & premium flagship audio quality",
            "driver": "8.4mm Dynamic Driver X for wide-frequency rich vocals",
            "anc": "HD Noise Cancelling Processor QN2e & Integrated Processor V2",
            "battery": "24 hours battery life (8h continuous + 16h case)",
            "charging": "3-minute quick charge gives 60 minutes playtime; Qi wireless supported",
            "connectivity": "Bluetooth 5.3 with LDAC, Multipoint connection up to 2 devices",
            "water_resistance": "IPX4 splash resistant",
            "store_prices": {"Sony Center": 24990, "Amazon India": 24990, "Croma": 25990}
        }
    },
    {
        "sku": "boat-airdopes-141-anc",
        "name": "boAt Airdopes 141 ANC (42H Playtime)",
        "brand": "boAt",
        "category": "Audio",
        "price": 1499,
        "rating": 4.3,
        "image": "https://images.unsplash.com/photo-1590658268037-6bf12165a8df?w=500&q=80",
        "desc": "Affordable true wireless earbuds with 32dB active noise cancellation, ENx technology, and low latency gaming mode.",
        "attrs": {
            "best_for": "Best budget ANC earbuds under ₹1,500",
            "driver": "10mm dynamic bass drivers with boAt Signature Sound",
            "anc": "Up to 32dB active noise cancellation",
            "battery": "42 hours massive total playback time",
            "charging": "ASAP Charge (10 mins charge = 150 mins playtime)",
            "connectivity": "Bluetooth 5.3 with BEAST 50ms low latency mode",
            "water_resistance": "IPX5 sweat and splash resistance",
            "store_prices": {"boAt Official": 1499, "Amazon India": 1499, "Flipkart": 1499}
        }
    },
    {
        "sku": "realme-buds-air-6-pro",
        "name": "Realme Buds Air 6 Pro (50dB ANC)",
        "brand": "Realme",
        "category": "Audio",
        "price": 4999,
        "rating": 4.5,
        "image": "https://images.unsplash.com/photo-1606220588913-b3aacb4d2f46?w=500&q=80",
        "desc": "Flagship 50dB active noise cancellation with Hi-Res LDAC support, dual coaxial drivers, and 360-degree spatial audio.",
        "attrs": {
            "best_for": "Best value high-res ANC earbuds under ₹5,000",
            "driver": "11mm bass driver + 6mm micro-planar tweeter dual drivers",
            "anc": "50dB Smart Deep Active Noise Cancellation (4000Hz ultra-wideband)",
            "battery": "40 hours total battery life with fast charging",
            "charging": "Dart Charge (10 mins = 7 hours music playback)",
            "connectivity": "Bluetooth 5.3, LDAC Hi-Res Audio, 55ms super low latency",
            "water_resistance": "IP55 water and dust resistance",
            "store_prices": {"realme Store": 4999, "Flipkart": 4999, "Amazon India": 5299}
        }
    },

    # Mechanical Keyboards & PC
    {
        "sku": "cosmic-byte-cb-gk-16",
        "name": "Cosmic Byte CB-GK-16 Firefly Mechanical Keyboard (Outemu Blue)",
        "brand": "Cosmic Byte",
        "category": "Peripherals",
        "price": 2199,
        "rating": 4.4,
        "image": "https://images.unsplash.com/photo-1618384887929-16ec33fab9ef?w=500&q=80",
        "desc": "Tenkeyless (TKL) compact mechanical gaming keyboard with tactile Outemu Blue switches and per-key RGB backlighting.",
        "attrs": {
            "best_for": "Best budget tactile mechanical keyboard for PC gaming",
            "switch": "Outemu Blue mechanical switches with distinct tactile click",
            "layout": "Tenkeyless (TKL) 87-key compact aluminum body",
            "lighting": "Full RGB backlighting with 18 dynamic preset modes",
            "connectivity": "Detachable braided USB Type-C cable",
            "anti_ghosting": "100% Anti-Ghosting with full N-Key Rollover",
            "store_prices": {"Cosmic Byte": 2199, "Amazon India": 2199, "Flipkart": 2299}
        }
    },
    {
        "sku": "keychron-k2-v2",
        "name": "Keychron K2 V2 Wireless Mechanical Keyboard (Gateron Brown)",
        "brand": "Keychron",
        "category": "Peripherals",
        "price": 7999,
        "rating": 4.8,
        "image": "https://images.unsplash.com/photo-1587829741301-dc798b83add3?w=500&q=80",
        "desc": "75% compact wireless keyboard compatible with Mac & Windows, hot-swappable switches, and 4000mAh battery.",
        "attrs": {
            "best_for": "Best productivity and wireless typing keyboard for Mac & Windows",
            "switch": "Hot-swappable Gateron G Pro Brown tactile quiet switches",
            "layout": "75% compact layout (84 keys) with dedicated arrow keys",
            "connectivity": "Wireless Bluetooth 5.1 (switches up to 3 devices) + USB-C wired",
            "battery": "4000mAh lithium rechargeable battery (up to 240 hours without RGB)",
            "compatibility": "Mac and Windows switch with extra dedicated Mac/Windows keycaps included",
            "store_prices": {"Keychron India": 7999, "Amazon India": 7999, "Meckeys": 7999}
        }
    },
    {
        "sku": "redragon-k552-kumara",
        "name": "Redragon K552 Kumara RGB Mechanical Gaming Keyboard",
        "brand": "Redragon",
        "category": "Peripherals",
        "price": 2790,
        "rating": 4.5,
        "image": "https://images.unsplash.com/photo-1595225476474-87563907a212?w=500&q=80",
        "desc": "Durable metal-ABS construction with custom mechanical red linear switches and splash-proof design.",
        "attrs": {
            "best_for": "Best fast-action quiet linear switches for competitive FPS esports",
            "switch": "Custom quiet Red linear switches (equivalent Cherry Red)",
            "layout": "Tenkeyless (TKL) space-saving compact design",
            "lighting": "Vibrant RGB backlit with 18 different lighting effects",
            "build": "Aircraft-grade metal alloy faceplate with splash-proof construction",
            "connectivity": "Gold-plated corrosion-free USB connector with braided cable",
            "store_prices": {"Redragon India": 2790, "Amazon India": 2790, "Flipkart": 2899}
        }
    },

    # Phones — Flagship & Mid-Range
    {
        "sku": "oneplus-12-5g",
        "name": "OnePlus 12 5G (16GB RAM, 512GB Storage)",
        "brand": "OnePlus",
        "category": "Phones",
        "price": 64999,
        "rating": 4.7,
        "image": "https://images.unsplash.com/photo-1592750475338-74b7b21085ab?w=500&q=80",
        "desc": "Snapdragon 8 Gen 3, 2K 120Hz ProXDR Display, Hasselblad 4th Gen camera, and 100W SUPERVOOC charging.",
        "attrs": {
            "best_for": "Best all-round flagship for battery life, display & fast charging",
            "processor": "Qualcomm Snapdragon 8 Gen 3 (4nm TSMC flagship processor)",
            "display": "6.82-inch 2K 120Hz ProXDR LTPO AMOLED (4500 nits peak brightness)",
            "camera": "50MP Sony LYT-808 OIS + 64MP 3x periscope telephoto + 48MP ultra-wide (Hasselblad tuned)",
            "battery": "5400mAh dual-cell battery with 100W SUPERVOOC wired + 50W AIRVOOC wireless",
            "ram_storage": "16GB LPDDR5X RAM + 512GB UFS 4.0 storage",
            "os": "OxygenOS 14 (Android 14) with 4 years major OS updates guaranteed",
            "store_prices": {"OnePlus Store": 64999, "Amazon India": 64999, "Croma": 64999}
        }
    },
    {
        "sku": "apple-iphone-15-128gb",
        "name": "Apple iPhone 15 (128GB, Black)",
        "brand": "Apple",
        "category": "Phones",
        "price": 69900,
        "rating": 4.8,
        "image": "https://images.unsplash.com/photo-1695048133142-1a20484d2569?w=500&q=80",
        "desc": "Dynamic Island, 48MP main camera with 2x Telephoto, A16 Bionic chip, and USB-C connectivity.",
        "attrs": {
            "best_for": "Best premium smartphone for video recording, cameras & iOS ecosystem",
            "processor": "Apple A16 Bionic (6-core CPU, 5-core GPU, 16-core Neural Engine)",
            "display": "6.1-inch Super Retina XDR OLED with Dynamic Island (2000 nits outdoor peak)",
            "camera": "48MP main sensor with sensor-shift OIS + 12MP ultra-wide with 2x optical telephoto crop",
            "battery": "3349mAh all-day battery life with USB-C universal charging",
            "ram_storage": "6GB RAM + 128GB NVMe high-speed storage",
            "os": "iOS 17 with 5+ years of guaranteed software and security support",
            "store_prices": {"Apple Store": 69900, "Amazon India": 69900, "Flipkart": 69900}
        }
    },
    {
        "sku": "samsung-galaxy-s24-ultra",
        "name": "Samsung Galaxy S24 Ultra 5G (12GB RAM, 256GB)",
        "brand": "Samsung",
        "category": "Phones",
        "price": 129999,
        "rating": 4.8,
        "image": "https://images.unsplash.com/photo-1610945265064-0e34e5519bbf?w=500&q=80",
        "desc": "Titanium frame, Galaxy AI live translation, 200MP camera with 100x Space Zoom, and built-in S-Pen.",
        "attrs": {
            "best_for": "Best ultimate Android flagship for zoom photography, productivity & Galaxy AI",
            "processor": "Qualcomm Snapdragon 8 Gen 3 for Galaxy (overclocked 4nm chipset)",
            "display": "6.8-inch Dynamic AMOLED 2X QHD+ 120Hz flat display with Gorilla Armor anti-reflective glass (2600 nits)",
            "camera": "200MP OIS main + 50MP 5x optical telephoto (100x Space Zoom) + 10MP 3x telephoto + 12MP ultra-wide",
            "battery": "5000mAh with 45W wired fast charging + 15W wireless charging",
            "ram_storage": "12GB LPDDR5X RAM + 256GB UFS 4.0 storage",
            "features": "Built-in S-Pen stylus, Titanium frame, 7 years guaranteed Android OS & security updates",
            "store_prices": {"Samsung Store": 129999, "Amazon India": 129999, "Croma": 129999}
        }
    },
    {
        "sku": "redmi-note-13-pro-plus",
        "name": "Redmi Note 13 Pro+ 5G (8GB RAM, 256GB)",
        "brand": "Xiaomi",
        "category": "Phones",
        "price": 27999,
        "rating": 4.4,
        "image": "https://images.unsplash.com/photo-1598327105666-5b89351aff97?w=500&q=80",
        "desc": "200MP OIS camera, 3D Curved 1.5K AMOLED display, IP68 water resistance, and 120W HyperCharge.",
        "attrs": {
            "best_for": "Best premium curved display and ultra-fast 120W charging under ₹30,000",
            "processor": "MediaTek Dimensity 7200 Ultra (efficient 4nm process)",
            "display": "6.67-inch 3D Curved 1.5K 120Hz CrystalRes AMOLED with Gorilla Glass Victus (1800 nits)",
            "camera": "200MP Samsung ISOCELL HP3 with OIS + 8MP ultra-wide + 2MP macro",
            "battery": "5000mAh with 120W HyperCharge (charges 0 to 100% in 19 minutes)",
            "ram_storage": "8GB LPDDR5 RAM + 256GB UFS 3.1 storage",
            "durability": "IP68 certified dust and water resistance",
            "store_prices": {"Mi Store": 27999, "Flipkart": 27999, "Amazon India": 28499}
        }
    },

    # Budget 5G Phones Under ₹15,000
    {
        "sku": "moto-g34-5g",
        "name": "Motorola Moto G34 5G (8GB RAM, 128GB)",
        "brand": "Motorola",
        "category": "Phones",
        "price": 11999,
        "rating": 4.5,
        "image": "https://images.unsplash.com/photo-1511707171634-5f897ff02aa9?w=500&q=80",
        "desc": "Best overall 5G phone under ₹12,000. Snapdragon 695 5G, 120Hz display, clean stock Android 14, and 5000mAh battery.",
        "attrs": {
            "best_for": "Best overall balance with 8GB RAM and clean stock Android 14 under ₹12,000",
            "processor": "Qualcomm Snapdragon 695 5G (6nm octa-core with 13 5G bands)",
            "display": "6.5-inch 120Hz smooth IPS LCD display",
            "camera": "50MP Quad Pixel primary camera with f/1.8 + 2MP macro sensor",
            "battery": "5000mAh all-day battery with 20W TurboPower charger in box",
            "ram_storage": "8GB LPDDR4X RAM + 128GB UFS 2.2 storage (expandable up to 1TB)",
            "os": "Clean near-stock Android 14 with Moto gestures and zero bloatware",
            "store_prices": {"Motorola India": 11999, "Flipkart": 11999, "Croma": 12499}
        }
    },
    {
        "sku": "realme-12x-5g",
        "name": "Realme 12x 5G (6GB RAM, 128GB)",
        "brand": "Realme",
        "category": "Phones",
        "price": 11999,
        "rating": 4.4,
        "image": "https://images.unsplash.com/photo-1598327105666-5b89351aff97?w=500&q=80",
        "desc": "Dimensity 6100+ 5G processor, 45W SUPERVOOC fast charging, 50MP AI camera, and 120Hz display.",
        "attrs": {
            "best_for": "Best fast charging (45W) & sleek design under ₹12,000",
            "processor": "MediaTek Dimensity 6100+ 5G (6nm energy-efficient octa-core)",
            "display": "6.72-inch 120Hz FHD+ dynamic ultra-smooth display with Rainwater Smart Touch",
            "camera": "50MP AI primary camera with street portrait mode",
            "battery": "5000mAh with 45W SUPERVOOC fast charging (50% in 30 mins)",
            "ram_storage": "6GB RAM + 128GB internal storage (expandable up to 2TB)",
            "durability": "IP54 water and dust resistance",
            "store_prices": {"realme Store": 11999, "Flipkart": 11999, "Amazon India": 12299}
        }
    },
    {
        "sku": "poco-m6-pro-5g",
        "name": "Poco M6 Pro 5G (6GB RAM, 128GB)",
        "brand": "POCO",
        "category": "Phones",
        "price": 10999,
        "rating": 4.3,
        "image": "https://images.unsplash.com/photo-1592750475338-74b7b21085ab?w=500&q=80",
        "desc": "Snapdragon 4 Gen 2 4nm 5G chipset, premium glass back design, 90Hz FHD+ display, and IP53 splash resistance.",
        "attrs": {
            "best_for": "Best value-for-money performance and premium glass back under ₹11,000",
            "processor": "Qualcomm Snapdragon 4 Gen 2 (efficient 4nm process)",
            "display": "6.79-inch 90Hz FHD+ DotDisplay with Corning Gorilla Glass protection",
            "camera": "50MP AI dual camera + 2MP portrait depth sensor",
            "battery": "5000mAh high-capacity battery with 18W Type-C fast charging",
            "ram_storage": "6GB LPDDR4X RAM + 128GB UFS 2.2 storage",
            "build": "Dual-sided Gorilla Glass back with IP53 splash resistance",
            "store_prices": {"Flipkart": 10999, "Amazon India": 11299, "Mi Store": 10999}
        }
    },
    {
        "sku": "samsung-galaxy-m14-5g",
        "name": "Samsung Galaxy M14 5G (6GB RAM, 128GB)",
        "brand": "Samsung",
        "category": "Phones",
        "price": 12490,
        "rating": 4.4,
        "image": "https://images.unsplash.com/photo-1610945265064-0e34e5519bbf?w=500&q=80",
        "desc": "Monster 6000mAh battery, 5nm Exynos 1330 5G processor, 50MP triple camera, and 13 5G bands.",
        "attrs": {
            "best_for": "Best battery life (6000mAh monster battery) & Samsung reliability under ₹13,000",
            "processor": "Samsung Exynos 1330 5nm octa-core 5G chipset (13 5G bands)",
            "display": "6.6-inch 90Hz FHD+ PLS LCD with Gorilla Glass 5 protection",
            "camera": "50MP f/1.8 main camera + 2MP depth + 2MP macro triple camera",
            "battery": "6000mAh monster battery (up to 25 hours continuous video playback)",
            "ram_storage": "6GB RAM + 128GB storage (expandable up to 1TB via dedicated slot)",
            "os": "One UI 5.1 Core with Knox Security and 2 years of OS updates",
            "store_prices": {"Samsung Shop": 12490, "Amazon India": 12490, "Flipkart": 12990}
        }
    },
    {
        "sku": "cmf-phone-1",
        "name": "CMF Phone 1 by Nothing (6GB RAM, 128GB)",
        "brand": "Nothing",
        "category": "Phones",
        "price": 14999,
        "rating": 4.6,
        "image": "https://images.unsplash.com/photo-1598327105666-5b89351aff97?w=500&q=80",
        "desc": "Best design & performance under ₹15,000. Dimensity 7300 4nm processor, 120Hz Super AMOLED display, and unique modular back panel.",
        "attrs": {
            "best_for": "Best Super AMOLED display, fastest processor & clean software under ₹15,000",
            "processor": "MediaTek Dimensity 7300 5G (flagship-grade 4nm architecture)",
            "display": "6.67-inch 120Hz Super AMOLED with HDR10+ and 2000 nits peak brightness",
            "camera": "50MP Sony flagship sensor with Ultra XDR processing + portrait sensor",
            "battery": "5000mAh with 33W fast charging and 5W reverse wired charging",
            "ram_storage": "6GB LPDDR4X RAM + 128GB UFS 2.2 storage (expandable up to 2TB)",
            "os": "Nothing OS 2.6 (Android 14) with zero bloatware and modular accessory point",
            "store_prices": {"Flipkart": 14999, "Croma": 14999, "Vijay Sales": 15499}
        }
    },
    {
        "sku": "redmi-13c-5g",
        "name": "Redmi 13C 5G (4GB RAM, 128GB)",
        "brand": "Xiaomi",
        "category": "Phones",
        "price": 9999,
        "rating": 4.2,
        "image": "https://images.unsplash.com/photo-1511707171634-5f897ff02aa9?w=500&q=80",
        "desc": "Most affordable 5G phone in India under ₹10,000. Dimensity 6100+ processor, 50MP AI camera, and starshine glass design.",
        "attrs": {
            "best_for": "Most affordable 5G smartphone under ₹10,000",
            "processor": "MediaTek Dimensity 6100+ 5G (6nm octa-core processor)",
            "display": "6.74-inch 90Hz HD+ display with Corning Gorilla Glass",
            "camera": "50MP AI primary camera with HDR and night mode",
            "battery": "5000mAh battery with 18W Type-C fast charging support",
            "ram_storage": "4GB RAM + 128GB internal storage (expandable up to 1TB)",
            "design": "Starshine glass-like back with side-mounted fingerprint scanner",
            "store_prices": {"Mi Store": 9999, "Amazon India": 9999, "Flipkart": 10199}
        }
    },

    # Laptops
    {
        "sku": "macbook-air-m3-13",
        "name": "Apple MacBook Air M3 (13.6-inch, 8GB RAM, 256GB SSD)",
        "brand": "Apple",
        "category": "Laptops",
        "price": 104900,
        "rating": 4.9,
        "image": "https://images.unsplash.com/photo-1517336714731-489689fd1ca8?w=500&q=80",
        "desc": "Blazing-fast M3 chip with 8-core CPU and 10-core GPU, Liquid Retina display, and 18 hours battery life.",
        "attrs": {
            "best_for": "Best premium ultraportable laptop for battery life, silent thermals & build quality",
            "processor": "Apple M3 chip (8-core CPU, 10-core GPU, 16-core Neural Engine)",
            "display": "13.6-inch Liquid Retina display with True Tone (500 nits, P3 wide color)",
            "battery": "Up to 18 hours battery life with MagSafe 3 fast charging",
            "ram_storage": "8GB Unified Memory + 256GB high-speed SSD",
            "features": "Fanless silent design, 1080p FaceTime HD camera, 4-speaker spatial sound system",
            "store_prices": {"Apple Store": 104900, "Amazon India": 104900, "Croma": 104900}
        }
    },
    {
        "sku": "asus-tuf-f15-i5",
        "name": "ASUS TUF Gaming F15 (Intel Core i5-11400H, RTX 2050 4GB)",
        "brand": "ASUS",
        "category": "Laptops",
        "price": 49990,
        "rating": 4.5,
        "image": "https://images.unsplash.com/photo-1603302576837-37561b2e2302?w=500&q=80",
        "desc": "15.6-inch FHD 144Hz display, 16GB DDR4 RAM, 512GB NVMe SSD, and military-grade durability.",
        "attrs": {
            "best_for": "Best value gaming laptop under ₹50,000 with dedicated NVIDIA RTX graphics",
            "processor": "Intel Core i5-11400H (6 cores, 12 threads, up to 4.5GHz)",
            "gpu": "NVIDIA GeForce RTX 2050 4GB GDDR6 dedicated graphics",
            "display": "15.6-inch FHD (1920x1080) 144Hz anti-glare IPS display",
            "battery": "48Wh battery with 150W AC adapter (fast-charge 50% in 30 mins)",
            "ram_storage": "16GB DDR4 3200MHz RAM + 512GB PCIe 3.0 NVMe M.2 SSD",
            "durability": "MIL-STD-810H military-grade construction with dual-fan anti-dust cooling",
            "store_prices": {"ASUS Store": 49990, "Amazon India": 49990, "Flipkart": 50990}
        }
    }
]


# Auto-seed initial catalog for Indian Market with version-based upsert
from app.models.entities import Category, Product, Review, SeedVersion, Wishlist
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded


def cleanup_duplicate_products(db: Session) -> int:
    """Find and delete duplicate products by name or SKU, preserving the row with complete/correct SKU."""
    deleted_count = 0
    try:
        # Check by name duplicates
        names_with_dupes = db.execute(
            text("SELECT name FROM products GROUP BY name HAVING COUNT(*) > 1")
        ).fetchall()

        for row in names_with_dupes:
            name = row[0]
            prods = db.query(Product).filter(Product.name == name).all()
            # Sort: products with non-empty SKU first, then by id descending
            prods.sort(key=lambda p: (1 if p.sku else 0, p.id), reverse=True)
            if len(prods) > 1:
                for dup in prods[1:]:
                    db.query(Review).filter(Review.product_id == dup.id).delete(synchronize_session=False)
                    db.query(Wishlist).filter(Wishlist.product_id == dup.id).delete(synchronize_session=False)
                    db.delete(dup)
                    deleted_count += 1

        # Check by SKU duplicates (if any exist)
        skus_with_dupes = db.execute(
            text("SELECT sku FROM products WHERE sku IS NOT NULL AND sku != '' GROUP BY sku HAVING COUNT(*) > 1")
        ).fetchall()

        for row in skus_with_dupes:
            sku = row[0]
            prods = db.query(Product).filter(Product.sku == sku).order_by(Product.id.desc()).all()
            if len(prods) > 1:
                for dup in prods[1:]:
                    db.query(Review).filter(Review.product_id == dup.id).delete(synchronize_session=False)
                    db.query(Wishlist).filter(Wishlist.product_id == dup.id).delete(synchronize_session=False)
                    db.delete(dup)
                    deleted_count += 1

        if deleted_count > 0:
            db.commit()
            print(f"Cleaned up {deleted_count} duplicate product records.")
    except Exception as err:
        db.rollback()
        print(f"Notice during duplicate cleanup: {err}")

    return deleted_count


# Auto-seed initial catalog for Indian Market with version-based upsert
def auto_seed_catalog(db: Session | None = None):
    should_close = False
    if db is None:
        db = SessionLocal()
        should_close = True
    try:
        # 1. Clean up any existing duplicates first
        cleanup_duplicate_products(db)

        # 2. Check stored seed version — skip if already up to date
        stored = db.query(SeedVersion).first()
        if stored and stored.version >= SEED_VERSION:
            return

        # Ensure categories exist (upsert by name)
        cat_names = set(item["category"] for item in SEED_DATA)
        cats: dict[str, Category] = {}
        for name in cat_names:
            existing_cat = db.query(Category).filter(Category.name == name).first()
            if existing_cat:
                cats[name] = existing_cat
            else:
                new_cat = Category(name=name)
                db.add(new_cat)
                db.flush()
                cats[name] = new_cat

        # Upsert products by stable SKU (or match existing name to avoid duplicates)
        for item in SEED_DATA:
            existing = db.query(Product).filter(Product.sku == item["sku"]).first()
            if not existing:
                existing = db.query(Product).filter(Product.name == item["name"]).first()

            if existing:
                # Update fields that may have changed
                existing.sku = item["sku"]
                existing.name = item["name"]
                existing.brand = item["brand"]
                existing.description = item["desc"]
                existing.price = float(item["price"])
                existing.rating = float(item["rating"])
                existing.image_url = item["image"]
                existing.attributes = item["attrs"]
                existing.category_id = cats[item["category"]].id
            else:
                p = Product(
                    sku=item["sku"],
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

        # Final cleanup pass
        cleanup_duplicate_products(db)

        # Update or create seed version record
        if stored:
            stored.version = SEED_VERSION
        else:
            db.add(SeedVersion(version=SEED_VERSION))

        db.commit()
        print(f"Catalog seeded/updated to version {SEED_VERSION} ({len(SEED_DATA)} products)")
    except Exception as err:
        print(f"Auto-seed notice: {err}")
    finally:
        if should_close:
            db.close()

auto_seed_catalog()

settings = get_settings()

limiter = Limiter(key_func=get_remote_address, default_limits=["120/minute"])

app = FastAPI(title="ShopSense API - India Edition", version="1.1.0")
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_origin_regex=settings.cors_origin_regex,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def security_headers_middleware(request: Request, call_next):
    response = await call_next(request)
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; "
        "connect-src 'self' https://accounts.google.com https://router.huggingface.co; "
        "script-src 'self' https://accounts.google.com https://apis.google.com; "
        "frame-src https://accounts.google.com; "
        "img-src 'self' data: https:; "
        "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
        "font-src 'self' https://fonts.gstatic.com;"
    )
    return response


app.include_router(router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "region": "IN", "currency": "INR"}


@app.exception_handler(Exception)
async def global_exception_handler(request, exc: Exception):
    import traceback
    print(f"Unhandled server error: {exc}\n{traceback.format_exc()}")
    from fastapi.responses import JSONResponse
    return JSONResponse(
        status_code=500,
        content={"detail": "An internal server error occurred. Please try again."}
    )
