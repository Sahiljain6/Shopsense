import logging
import httpx
from fastapi import APIRouter, Depends, File, HTTPException, Request, Response, UploadFile, status
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from app.core.config import get_settings
from app.core.security import clear_auth_cookies, create_access_token, create_refresh_token, decode_refresh_token, get_current_user, hash_password, require_admin, set_auth_cookies, verify_password
from app.db.session import get_db
from app.models.entities import ChatHistory, Order, Product, Review, SeedVersion, User, Wishlist
from app.schemas.api import ChatRequest, ChatResponse, CompareRequest, FetchLinkRequest, FetchLinkResponse, GoogleAuthRequest, PriceHistoryResponse, ProductCreate, ProductRead, RefreshTokenRequest, ReviewRead, ReviewSummaryRequest, Token, UserCreate, UserLogin, UserRead, WishlistRequest
from app.services.ai import AIOrchestrator
from app.services.barcode_lookup import lookup_barcode
from app.services.catalog import CatalogService
from app.services.currency import convert_price
from app.services.deal_hunter import fetch_gaming_deals
from app.services.scraper import scrape_product
from app.services.ssrf_validator import SSRFError, validate_url
from app.services.vision import identify_image

logger = logging.getLogger("shopsense.api")
router = APIRouter()
limiter = Limiter(key_func=get_remote_address)


def _product_read(product: Product) -> ProductRead:
    data = ProductRead.model_validate(product)
    data.category_name = product.category.name if product.category else None
    return data


@router.post("/auth/register", response_model=UserRead)
@limiter.limit("5/minute")
def register(request: Request, payload: UserCreate, db: Session = Depends(get_db)) -> User:
    try:
        if db.scalar(select(User).where(User.email == payload.email)):
            raise HTTPException(status_code=400, detail="Email already registered")
        user = User(email=payload.email, full_name=payload.full_name, hashed_password=hash_password(payload.password))
        db.add(user)
        db.commit()
        db.refresh(user)
        return user
    except HTTPException:
        db.rollback()
        raise
    except Exception:
        db.rollback()
        raise HTTPException(status_code=500, detail="Registration failed. Please try again.")


@router.post("/auth/login", response_model=Token)
@limiter.limit("10/minute")
def login(request: Request, response: Response, payload: UserLogin, db: Session = Depends(get_db)) -> Token:
    try:
        user = db.scalar(select(User).where(User.email == payload.email))
        if user is None or not user.hashed_password or not verify_password(payload.password, user.hashed_password):
            raise HTTPException(status_code=401, detail="Invalid credentials")
        access_token = create_access_token(user.email)
        refresh_token = create_refresh_token(user.email)
        csrf = set_auth_cookies(response, access_token, refresh_token)
        return Token(access_token=access_token, refresh_token=refresh_token, csrf_token=csrf)
    except HTTPException:
        db.rollback()
        raise
    except Exception:
        db.rollback()
        raise HTTPException(status_code=500, detail="Login failed. Please try again.")


@router.post("/auth/refresh", response_model=Token)
def refresh_auth(
    request: Request,
    response: Response,
    payload: RefreshTokenRequest | None = None,
    db: Session = Depends(get_db)
) -> Token:
    """Refresh access token using httpOnly cookie or payload refresh token."""
    raw_refresh = request.cookies.get("refresh_token")
    if not raw_refresh and payload and payload.refresh_token:
        raw_refresh = payload.refresh_token

    if not raw_refresh:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh token missing")

    email = decode_refresh_token(raw_refresh)
    user = db.scalar(select(User).where(User.email == email))
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")

    new_access = create_access_token(user.email)
    new_refresh = create_refresh_token(user.email)
    csrf = set_auth_cookies(response, new_access, new_refresh)
    return Token(access_token=new_access, refresh_token=new_refresh, csrf_token=csrf)


@router.post("/auth/logout")
def logout(response: Response) -> dict[str, str]:
    """Clear authentication cookies."""
    clear_auth_cookies(response)
    return {"message": "Logged out successfully"}


@router.get("/auth/me", response_model=UserRead)
def me(user: User = Depends(get_current_user)) -> User:
    return user


@router.post("/auth/google", response_model=Token)
@limiter.limit("15/minute")
def google_auth(
    request: Request,
    response: Response,
    payload: GoogleAuthRequest,
    db: Session = Depends(get_db)
) -> Token:
    """Verify Google Identity Services (GIS) ID token and authenticate or register user."""
    settings = get_settings()
    try:
        audience = settings.google_client_id if settings.google_client_id else None
        id_info = id_token.verify_oauth2_token(
            payload.credential,
            google_requests.Request(),
            audience=audience
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid Google ID token: {exc}"
        )

    # Verify issuer
    if id_info.get("iss") not in ["accounts.google.com", "https://accounts.google.com"]:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Google token issuer"
        )

    # Verify email verified
    if not id_info.get("email_verified"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Google email not verified"
        )

    google_id = id_info.get("sub")
    email = id_info.get("email")
    full_name = id_info.get("name", "")

    if not google_id or not email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Incomplete Google user profile"
        )

    try:
        # 1. Match by google_id
        user = db.scalar(select(User).where(User.google_id == google_id))

        # 2. Fall back to matching by email (link existing password account)
        if user is None:
            user = db.scalar(select(User).where(User.email == email))
            if user:
                user.google_id = google_id
                if not user.full_name and full_name:
                    user.full_name = full_name
                db.commit()
                db.refresh(user)

        # 3. Create new user if not found
        if user is None:
            user = User(
                email=email,
                google_id=google_id,
                full_name=full_name,
                hashed_password=None,
            )
            db.add(user)
            db.commit()
            db.refresh(user)

        access_token = create_access_token(user.email)
        refresh_token = create_refresh_token(user.email)
        csrf = set_auth_cookies(response, access_token, refresh_token)
        return Token(access_token=access_token, refresh_token=refresh_token, csrf_token=csrf)
    except Exception as err:
        db.rollback()
        raise HTTPException(status_code=500, detail="Google authentication failed.") from err


@router.get("/products", response_model=list[ProductRead])
def products(q: str | None = None, limit: int = 10, db: Session = Depends(get_db)) -> list[ProductRead]:
    try:
        return [_product_read(p) for p in CatalogService(db).search(q, limit)]
    except Exception:
        db.rollback()
        return []


@router.post("/chat", response_model=ChatResponse)
@limiter.limit("30/minute")
def chat(
    request: Request,
    payload: ChatRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ChatResponse:
    history = [{"role": turn.role, "content": turn.content} for turn in payload.history]
    try:
        response = AIOrchestrator(db).answer_via_agents(payload.message, payload.mode, history, cart=payload.cart)
    except Exception as err:
        db.rollback()
        print(f"Error during AIOrchestrator.answer: {err}")
        response = ChatResponse(
            answer="I ran into a temporary issue retrieving product data. Please try asking again in a moment."
        )

    # Save chat history in an isolated transaction so history logging never crashes the response
    try:
        db.add(ChatHistory(user_id=user.id, message=payload.message, response=response.model_dump()))
        db.commit()
    except Exception as err:
        db.rollback()
        print(f"Notice: unable to save chat history: {err}")

    return response


@router.post("/fetch-link", response_model=FetchLinkResponse)
def fetch_link(payload: FetchLinkRequest, db: Session = Depends(get_db)) -> FetchLinkResponse:
    try:
        validate_url(payload.url)
    except SSRFError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Prohibited or invalid URL: {exc}"
        )

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
    image_bytes = await file.read()
    if not image_bytes:
        return ChatResponse(answer="Empty image uploaded. Please upload a valid product photo.")

    try:
        from app.services.agents.photo_deal_agent import resolve_photo_mismatch_and_find_deals
        return resolve_photo_mismatch_and_find_deals(image_bytes, db)
    except Exception as err:
        logger.exception("Error in multi-agent photo deal finder: %s", err)
        return ChatResponse(answer="I couldn't process that photo properly. Please try another image or search by text.")


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
    try:
        if not db.scalar(select(Wishlist).where(Wishlist.user_id == user.id, Wishlist.product_id == payload.product_id)):
            db.add(Wishlist(user_id=user.id, product_id=payload.product_id))
            db.commit()
        return wishlist(db, user)
    except Exception:
        db.rollback()
        raise HTTPException(status_code=500, detail="Unable to update wishlist.")


@router.delete("/wishlist/{product_id}", response_model=list[int])
def delete_wishlist(product_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> list[int]:
    try:
        row = db.scalar(select(Wishlist).where(Wishlist.user_id == user.id, Wishlist.product_id == product_id))
        if row:
            db.delete(row)
            db.commit()
        return wishlist(db, user)
    except Exception:
        db.rollback()
        raise HTTPException(status_code=500, detail="Unable to remove from wishlist.")


@router.get("/admin/analytics")
def admin_analytics(db: Session = Depends(get_db), _: User = Depends(require_admin)) -> dict[str, int]:
    try:
        return {"users": db.scalar(select(func.count(User.id))) or 0, "products": db.scalar(select(func.count(Product.id))) or 0, "orders": db.scalar(select(func.count(Order.id))) or 0}
    except Exception:
        db.rollback()
        return {"users": 0, "products": 0, "orders": 0}


@router.get("/admin/users", response_model=list[UserRead])
def admin_users(db: Session = Depends(get_db), _: User = Depends(require_admin)) -> list[User]:
    try:
        return list(db.scalars(select(User)).all())
    except Exception:
        db.rollback()
        return []


@router.get("/admin/reviews", response_model=list[ReviewRead])
def admin_reviews(db: Session = Depends(get_db), _: User = Depends(require_admin)) -> list[Review]:
    try:
        return list(db.scalars(select(Review)).all())
    except Exception:
        db.rollback()
        return []


@router.get("/admin/orders")
def admin_orders(db: Session = Depends(get_db), _: User = Depends(require_admin)) -> list[dict[str, object]]:
    try:
        return [{"id": o.id, "user_id": o.user_id, "total": o.total, "status": o.status} for o in db.scalars(select(Order)).all()]
    except Exception:
        db.rollback()
        return []


@router.post("/admin/products/{product_id}", response_model=ProductRead)
def create_product(product_id: int, payload: ProductCreate, db: Session = Depends(get_db), _: User = Depends(require_admin)) -> ProductRead:
    try:
        product = Product(id=product_id, **payload.model_dump())
        db.add(product)
        db.commit()
        db.refresh(product)
        return _product_read(product)
    except Exception:
        db.rollback()
        raise HTTPException(status_code=500, detail="Failed to create product.")


@router.put("/admin/products/{product_id}", response_model=ProductRead)
def update_product(product_id: int, payload: ProductCreate, db: Session = Depends(get_db), _: User = Depends(require_admin)) -> ProductRead:
    try:
        product = db.get(Product, product_id)
        if product is None:
            raise HTTPException(status_code=404, detail="Product not found")
        for key, value in payload.model_dump().items():
            setattr(product, key, value)
        db.commit()
        db.refresh(product)
        return _product_read(product)
    except HTTPException:
        db.rollback()
        raise
    except Exception:
        db.rollback()
        raise HTTPException(status_code=500, detail="Failed to update product.")


@router.delete("/admin/products/{product_id}")
def delete_product(product_id: int, db: Session = Depends(get_db), _: User = Depends(require_admin)) -> dict[str, bool]:
    try:
        product = db.get(Product, product_id)
        if product is None:
            raise HTTPException(status_code=404, detail="Product not found")
        db.delete(product)
        db.commit()
        return {"ok": True}
    except HTTPException:
        db.rollback()
        raise
    except Exception:
        db.rollback()
        raise HTTPException(status_code=500, detail="Failed to delete product.")


@router.post("/admin/reseed")
def force_reseed(db: Session = Depends(get_db), _: User = Depends(require_admin)) -> dict[str, object]:
    """Force a full catalog reseed by resetting the stored seed version to 0."""
    from app.main import auto_seed_catalog, SEED_VERSION
    stored = db.query(SeedVersion).first()
    if stored:
        stored.version = 0
    db.commit()
    auto_seed_catalog(db)
    return {"status": "reseeded", "version": SEED_VERSION}


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
