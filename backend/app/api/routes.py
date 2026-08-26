import httpx
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from app.core.config import get_settings
from app.core.security import create_access_token, get_current_user, hash_password, require_admin, verify_password
from app.db.session import get_db
from app.models.entities import ChatHistory, Order, Product, Review, User, Wishlist
from app.schemas.api import ChatRequest, ChatResponse, CompareRequest, FetchLinkRequest, FetchLinkResponse, PriceHistoryResponse, ProductCreate, ProductRead, ReviewRead, ReviewSummaryRequest, Token, UserCreate, UserLogin, UserRead, WishlistRequest
from app.services.ai import AIOrchestrator
from app.services.barcode_lookup import lookup_barcode
from app.services.catalog import CatalogService
from app.services.currency import convert_price
from app.services.deal_hunter import fetch_gaming_deals
from app.services.scraper import scrape_product
from app.services.vision import identify_image

router = APIRouter()


def _product_read(product: Product) -> ProductRead:
    data = ProductRead.model_validate(product)
    data.category_name = product.category.name if product.category else None
    return data


@router.post("/auth/register", response_model=UserRead)
def register(payload: UserCreate, db: Session = Depends(get_db)) -> User:
    if db.scalar(select(User).where(User.email == payload.email)):
        raise HTTPException(status_code=400, detail="Email already registered")
    user = User(email=payload.email, full_name=payload.full_name, hashed_password=hash_password(payload.password))
    db.add(user); db.commit(); db.refresh(user)
    return user


@router.post("/auth/login", response_model=Token)
def login(payload: UserLogin, db: Session = Depends(get_db)) -> Token:
    user = db.scalar(select(User).where(User.email == payload.email))
    if user is None or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    return Token(access_token=create_access_token(user.email))


@router.get("/auth/me", response_model=UserRead)
def me(user: User = Depends(get_current_user)) -> User:
    return user


@router.post("/auth/google", response_model=Token)
def google_auth(db: Session = Depends(get_db)) -> Token:
    """One-click Google-style authentication.
    Auto-creates a demo account and returns a JWT token.
    """
    demo_email = "shopper@shopsense.in"
    demo_password = "ShopSense2026!"
    user = db.scalar(select(User).where(User.email == demo_email))
    if not user:
        user = User(
            email=demo_email,
            full_name="ShopSense Shopper",
            hashed_password=hash_password(demo_password),
        )
        db.add(user)
        db.commit()
        db.refresh(user)
    return Token(access_token=create_access_token(user.email))


@router.get("/products", response_model=list[ProductRead])
def products(q: str | None = None, limit: int = 10, db: Session = Depends(get_db)) -> list[ProductRead]:
    return [_product_read(p) for p in CatalogService(db).search(q, limit)]


@router.post("/chat", response_model=ChatResponse)
def chat(payload: ChatRequest, db: Session = Depends(get_db)) -> ChatResponse:
    history = [{"role": turn.role, "content": turn.content} for turn in payload.history]
    response = AIOrchestrator(db).answer_via_agents(payload.message, payload.mode, history)
    db.add(ChatHistory(user_id=None, message=payload.message, response=response.model_dump()))
    db.commit()
    return response


@router.post("/fetch-link", response_model=FetchLinkResponse)
def fetch_link(payload: FetchLinkRequest, db: Session = Depends(get_db)) -> FetchLinkResponse:
    scraped = scrape_product(payload.url)
    if scraped is None:
        raise HTTPException(
            status_code=422,
            detail="Couldn't extract product details from that link. The site may block scrapers or render prices with JavaScript."
        )
    product, created = CatalogService(db).upsert_from_scrape(scraped, payload.url)
    return FetchLinkResponse(product=_product_read(product), created=created)


@router.get("/products/{product_id}/price-history", response_model=PriceHistoryResponse)
def price_history(product_id: int, db: Session = Depends(get_db)) -> PriceHistoryResponse:
    product = db.get(Product, product_id)
    if product is None:
        raise HTTPException(status_code=404, detail="Product not found")

    history = product.attributes.get("price_history", [])

    return PriceHistoryResponse(
        product_id=product.id,
        source_url=product.attributes.get("source_url"),
        history=history
    )


@router.post("/identify-image", response_model=ChatResponse)
async def identify_image_route(file: UploadFile = File(...), db: Session = Depends(get_db)) -> ChatResponse:
    settings = get_settings()
    image_bytes = await file.read()

    try:
        labels = identify_image(image_bytes, settings.google_vision_api_key)
    except httpx.HTTPError:
        labels = identify_image(image_bytes, None)

    if not labels:
        return ChatResponse(answer="I couldn't identify anything specific in that image. Try a clearer or closer photo.")

    top_labels = labels[:5]
    query = " ".join(top_labels)
    products = CatalogService(db).search(query, limit=6)

    detected = ", ".join(top_labels)

    if not products:
        return ChatResponse(answer=f"I detected: {detected}. No close matches in the catalog yet — try pasting a product link instead.")

    ids = [product.id for product in products]
    names = ", ".join(f"{product.name} ({product.currency} {product.price:.0f})" for product in products)

    return ChatResponse(
        answer=f"I detected: {detected}. Closest catalog matches: {names}.",
        product_ids=ids,
        reasons={
            str(product.id): f"Matched from image labels: {', '.join(top_labels[:3])}"
            for product in products
        }
    )


@router.post("/compare", response_model=ChatResponse)
def compare(payload: CompareRequest, db: Session = Depends(get_db)) -> ChatResponse:
    products = CatalogService(db).get_many(payload.product_ids)
    if len(products) < 2:
        raise HTTPException(status_code=404, detail="Need at least two valid products")
    names = ", ".join(p.name for p in products)
    return ChatResponse(answer=f"Comparison grounded in catalog: {names}.", product_ids=[p.id for p in products])


@router.post("/reviews/summary", response_model=ChatResponse)
def review_summary(payload: ReviewSummaryRequest, db: Session = Depends(get_db)) -> ChatResponse:
    reviews = list(db.scalars(select(Review).where(Review.product_id == payload.product_id)).all())
    if not reviews:
        return ChatResponse(answer="No reviews available for this product.", product_ids=[payload.product_id])
    avg = sum(r.rating for r in reviews) / len(reviews)
    return ChatResponse(answer=f"{len(reviews)} reviews average {avg:.1f}/5. Common themes are value, build quality, and usability.", product_ids=[payload.product_id])


@router.get("/reviews/{product_id}", response_model=list[ReviewRead])
def reviews(product_id: int, db: Session = Depends(get_db)) -> list[Review]:
    return list(db.scalars(select(Review).where(Review.product_id == product_id)).all())


@router.get("/history")
def history(db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> list[dict[str, object]]:
    rows = db.scalars(select(ChatHistory).where(ChatHistory.user_id == user.id).order_by(ChatHistory.created_at.desc())).all()
    return [{"message": row.message, "response": row.response, "created_at": row.created_at.isoformat()} for row in rows]


@router.get("/wishlist", response_model=list[int])
def wishlist(db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> list[int]:
    return list(db.scalars(select(Wishlist.product_id).where(Wishlist.user_id == user.id)).all())


@router.post("/wishlist", response_model=list[int])
def add_wishlist(payload: WishlistRequest, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> list[int]:
    if not db.scalar(select(Wishlist).where(Wishlist.user_id == user.id, Wishlist.product_id == payload.product_id)):
        db.add(Wishlist(user_id=user.id, product_id=payload.product_id)); db.commit()
    return wishlist(db, user)


@router.delete("/wishlist/{product_id}", response_model=list[int])
def delete_wishlist(product_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> list[int]:
    row = db.scalar(select(Wishlist).where(Wishlist.user_id == user.id, Wishlist.product_id == product_id))
    if row:
        db.delete(row); db.commit()
    return wishlist(db, user)


@router.get("/admin/analytics")
def admin_analytics(db: Session = Depends(get_db), _: User = Depends(require_admin)) -> dict[str, int]:
    return {"users": db.scalar(select(func.count(User.id))) or 0, "products": db.scalar(select(func.count(Product.id))) or 0, "orders": db.scalar(select(func.count(Order.id))) or 0}


@router.get("/admin/users", response_model=list[UserRead])
def admin_users(db: Session = Depends(get_db), _: User = Depends(require_admin)) -> list[User]:
    return list(db.scalars(select(User)).all())


@router.get("/admin/reviews", response_model=list[ReviewRead])
def admin_reviews(db: Session = Depends(get_db), _: User = Depends(require_admin)) -> list[Review]:
    return list(db.scalars(select(Review)).all())


@router.get("/admin/orders")
def admin_orders(db: Session = Depends(get_db), _: User = Depends(require_admin)) -> list[dict[str, object]]:
    return [{"id": o.id, "user_id": o.user_id, "total": o.total, "status": o.status} for o in db.scalars(select(Order)).all()]


@router.post("/admin/products/{product_id}", response_model=ProductRead)
def create_product(product_id: int, payload: ProductCreate, db: Session = Depends(get_db), _: User = Depends(require_admin)) -> ProductRead:
    product = Product(id=product_id, **payload.model_dump())
    db.add(product); db.commit(); db.refresh(product)
    return _product_read(product)


@router.put("/admin/products/{product_id}", response_model=ProductRead)
def update_product(product_id: int, payload: ProductCreate, db: Session = Depends(get_db), _: User = Depends(require_admin)) -> ProductRead:
    product = db.get(Product, product_id)
    if product is None:
        raise HTTPException(status_code=404, detail="Product not found")
    for key, value in payload.model_dump().items():
        setattr(product, key, value)
    db.commit(); db.refresh(product)
    return _product_read(product)


@router.delete("/admin/products/{product_id}")
def delete_product(product_id: int, db: Session = Depends(get_db), _: User = Depends(require_admin)) -> dict[str, bool]:
    product = db.get(Product, product_id)
    if product is None:
        raise HTTPException(status_code=404, detail="Product not found")
    db.delete(product); db.commit()
    return {"ok": True}


@router.get("/currency/convert")
def convert_currency(amount: float, from_curr: str = "USD", to_curr: str = "INR") -> dict[str, object]:
    converted = convert_price(amount, from_curr, to_curr)
    return {
        "amount": amount,
        "from_currency": from_curr.upper(),
        "to_currency": to_curr.upper(),
        "converted_amount": converted
    }


@router.get("/deals")
def get_deals(q: str = "", limit: int = 6) -> list[dict[str, object]]:
    return fetch_gaming_deals(q, limit)


@router.get("/barcode/{code}")
def get_barcode_product(code: str) -> dict[str, object]:
    result = lookup_barcode(code)
    if not result:
        raise HTTPException(status_code=404, detail="Barcode not found in Open Food Facts database.")
    return result
