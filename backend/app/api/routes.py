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
from app.core.auth_types import Scope, SecurityContext, UserTier
from app.core.audit import audit_logger
from app.core.db_scoping import ScopedQueryFilter
from app.core.quota import check_quota, quota_engine
from app.core.scoping import require_scope, require_feature_flag, require_tier
from app.core.security import (
    clear_auth_cookies,
    create_access_token,
    create_refresh_token,
    decode_refresh_token,
    get_current_user,
    get_security_context,
    hash_password,
    invalidate_user_sessions,
    require_admin,
    rotate_refresh_token,
    set_auth_cookies,
    verify_password,
)
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
        access_token = create_access_token(user.email, user=user)
        refresh_token = create_refresh_token(user.email, user_id=user.id)
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
    """Refresh access token using httpOnly cookie or payload refresh token with RTR and reuse detection."""
    raw_refresh = request.cookies.get("refresh_token")
    if not raw_refresh and payload and payload.refresh_token:
        raw_refresh = payload.refresh_token

    if not raw_refresh:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh token missing")

    new_refresh, email, user_id = rotate_refresh_token(raw_refresh)
    user = db.scalar(select(User).where(User.email == email))
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")

    new_access = create_access_token(user.email, user=user)
    csrf = set_auth_cookies(response, new_access, new_refresh)
    return Token(access_token=new_access, refresh_token=new_refresh, csrf_token=csrf)


@router.get("/auth/session", response_model=dict[str, object])
def get_current_session(context: SecurityContext = Depends(get_security_context)) -> dict[str, object]:
    """Retrieve verified SecurityContext without contacting database (0 DB queries)."""
    return {
        "user_id": context.user_id,
        "email": context.email,
        "tier": context.tier.value,
        "org_id": context.org_id,
        "token_version": context.token_version,
        "scopes": list(context.scopes),
        "feature_flags": list(context.feature_flags),
        "quota": context.quota.model_dump(),
    }


@router.post("/auth/tier", response_model=dict[str, object])
def update_user_tier(
    tier: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict[str, object]:
    """
    Update user subscription tier and trigger immediate session revocation / version bump
    so outdated JWT tokens are instantly rejected on their next call.
    """
    valid_tiers = [t.value for t in UserTier]
    if tier.lower() not in valid_tiers:
        raise HTTPException(status_code=400, detail=f"Invalid tier. Must be one of {valid_tiers}")

    user.tier = tier.lower()
    new_version = invalidate_user_sessions(user.id)
    user.token_version = new_version
    db.commit()
    db.refresh(user)

    return {
        "user_id": user.id,
        "email": user.email,
        "tier": user.tier,
        "token_version": user.token_version,
        "message": "Tier updated successfully. Previous tokens invalidated.",
    }


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
    """Verify Google Identity Services (GIS) ID token or OAuth2 access token and authenticate or register user."""
    settings = get_settings()
    id_info = None

    if payload.credential:
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
    elif payload.access_token:
        try:
            with httpx.Client(timeout=10.0) as http_client:
                res = http_client.get(
                    "https://www.googleapis.com/oauth2/v3/userinfo",
                    headers={"Authorization": f"Bearer {payload.access_token}"}
                )
                if res.status_code != 200:
                    raise HTTPException(
                        status_code=status.HTTP_401_UNAUTHORIZED,
                        detail="Failed to fetch Google user profile with access token"
                    )
                id_info = res.json()
        except HTTPException:
            raise
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"Error validating Google access token: {exc}"
            )
    else:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Either credential (ID token) or access_token must be provided."
        )

    # Verify email verified
    if not id_info.get("email_verified") and id_info.get("verified_email") is not True:
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

        access_token = create_access_token(user.email, user=user)
        refresh_token = create_refresh_token(user.email, user_id=user.id)
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
    context: SecurityContext = Depends(check_quota(estimated_tokens=500)),
) -> ChatResponse:
    # 1. Advanced Model Scope Validation
    is_advanced_request = (
        payload.mode in ["advanced", "deep_research"]
        or (payload.model and any(adv in payload.model.lower() for adv in ["claude 3.7", "opus", "extended"]))
    )
    if is_advanced_request:
        if not context.has_scope(Scope.LLM_QUERY_ADVANCED.value):
            audit_logger.log_denied_access(
                user_id=context.user_id,
                email=context.email,
                tier=context.tier.value,
                required_scope=Scope.LLM_QUERY_ADVANCED.value,
                assigned_scopes=list(context.scopes),
                reason="insufficient_scope",
                endpoint="/chat",
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "error": "Forbidden",
                    "message": "Advanced reasoning models require Pro or Enterprise tier subscription.",
                    "required_scope": Scope.LLM_QUERY_ADVANCED.value,
                    "current_tier": context.tier.value,
                },
            )

    history = [{"role": turn.role, "content": turn.content} for turn in payload.history]
    try:
        response = AIOrchestrator(db).answer_via_agents(
            payload.message,
            payload.mode,
            history,
            cart=payload.cart,
            model=payload.model,
        )
        tokens_consumed = max(50, (len(payload.message) + len(response.answer)) // 4 + 50)
        quota_engine.record_usage(user.id, tokens_consumed)
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
def admin_analytics(
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
) -> dict[str, object]:
    """
    Platform-wide analytics with user tier breakdown (admin:analytics:platform_wide).
    """
    try:
        all_users = db.scalars(select(User)).all()
        tier_breakdown: dict[str, int] = {}
        for u in all_users:
            t = getattr(u, "tier", "free") or "free"
            tier_breakdown[t] = tier_breakdown.get(t, 0) + 1

        chat_total = db.scalar(select(func.count(ChatHistory.id))) or 0
        return {
            "total_users": len(all_users),
            "total_products": db.scalar(select(func.count(Product.id))) or 0,
            "total_orders": db.scalar(select(func.count(Order.id))) or 0,
            "total_chat_messages": chat_total,
            "users_by_tier": tier_breakdown,
        }
    except Exception:
        db.rollback()
        return {"error": "Failed to compute analytics."}


@router.get("/admin/users", response_model=list[UserRead])
def admin_users(db: Session = Depends(get_db), _: User = Depends(require_admin)) -> list[User]:
    try:
        return list(db.scalars(select(User)).all())
    except Exception:
        db.rollback()
        return []


@router.patch("/admin/users/{user_id}/tier", response_model=dict[str, object])
def admin_update_user_tier(
    user_id: int,
    tier: str,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
) -> dict[str, object]:
    """
    Admin: update a user's subscription tier and immediately invalidate all
    existing sessions (token version bump) so stale tokens are rejected on the
    very next request without requiring a forced logout.
    """
    valid_tiers = [t.value for t in UserTier]
    if tier.lower() not in valid_tiers:
        raise HTTPException(status_code=400, detail=f"Invalid tier '{tier}'. Must be one of {valid_tiers}.")

    target = db.get(User, user_id)
    if not target:
        raise HTTPException(status_code=404, detail=f"User {user_id} not found.")

    old_tier = getattr(target, "tier", "free")
    target.tier = tier.lower()
    new_version = invalidate_user_sessions(user_id)
    target.token_version = new_version
    db.commit()
    db.refresh(target)

    audit_logger.log(audit_logger.__class__.__name__ and __import__("app.core.audit", fromlist=["AuditEvent"]).AuditEvent(
        event_type="admin_tier_update",
        user_id=user_id,
        reason="admin_action",
        details={"old_tier": old_tier, "new_tier": tier.lower(), "new_token_version": new_version},
    ))

    return {
        "user_id": user_id,
        "email": target.email,
        "old_tier": old_tier,
        "new_tier": target.tier,
        "token_version": new_version,
        "message": "Tier updated. All existing sessions immediately invalidated.",
    }


@router.patch("/admin/users/{user_id}/feature-flags", response_model=dict[str, object])
def admin_update_feature_flags(
    user_id: int,
    flags: list[str],
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
) -> dict[str, object]:
    """
    Admin: Set the full list of feature flags for a user.
    The new JWT issued on next login/refresh will reflect the updated flags.
    """
    target = db.get(User, user_id)
    if not target:
        raise HTTPException(status_code=404, detail=f"User {user_id} not found.")

    old_flags = list(getattr(target, "feature_flags", []) or [])
    target.feature_flags = sorted(list(set(flags)))
    db.commit()
    db.refresh(target)

    return {
        "user_id": user_id,
        "email": target.email,
        "old_flags": old_flags,
        "new_flags": target.feature_flags,
        "message": "Feature flags updated. Changes take effect on next token refresh.",
    }


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


@router.get("/user/conversations", response_model=list[dict[str, object]])
def get_user_conversations(
    limit: int = 50,
    db: Session = Depends(get_db),
    context: SecurityContext = Depends(get_security_context),
) -> list[dict[str, object]]:
    """
    Retrieve user conversations strictly isolated to the caller's identity (IDOR-safe).
    Row-level isolation is applied via ScopedQueryFilter.
    """
    stmt = select(ChatHistory).order_by(ChatHistory.created_at.desc()).limit(limit)
    stmt = ScopedQueryFilter.apply_user_scope(stmt, ChatHistory, context)
    records = db.scalars(stmt).all()
    return [
        {
            "id": r.id,
            "user_id": r.user_id,
            "message": r.message,
            "response": r.response,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in records
    ]


@router.get("/admin/audit-logs", response_model=list[dict[str, object]])
def get_security_audit_logs(
    event_type: str | None = None,
    context: SecurityContext = require_scope(Scope.ADMIN_ALL.value),
) -> list[dict[str, object]]:
    """
    Retrieve recent security audit logs (Admin only with admin:* scope).
    """
    events = audit_logger.get_events(event_type=event_type)
    return [e.model_dump() for e in events]


@router.get("/user/quota", response_model=dict[str, object])
def get_user_quota(
    context: SecurityContext = Depends(get_security_context),
) -> dict[str, object]:
    """
    Live quota dashboard: returns current monthly token usage, limits,
    rate limit settings, and remaining allowances for the authenticated user.
    Zero database queries — reads from quota engine in-memory store.
    """
    current_usage = quota_engine.get_usage(context.user_id)
    monthly_limit = context.quota.monthly_tokens
    remaining = max(0, monthly_limit - current_usage)
    used_pct = round((current_usage / monthly_limit) * 100, 2) if monthly_limit > 0 else 0.0

    return {
        "user_id": context.user_id,
        "tier": context.tier.value,
        "monthly_tokens": {
            "limit": monthly_limit,
            "used": current_usage,
            "remaining": remaining,
            "used_percent": used_pct,
        },
        "rate_limits": {
            "requests_per_minute": context.quota.rate_limit_rpm,
        },
        "context_window": {
            "max_tokens": context.quota.max_context_window,
        },
        "feature_flags": sorted(list(context.feature_flags)),
        "scopes": sorted(list(context.scopes)),
    }


@router.get("/user/profile", response_model=UserRead)
def get_user_profile(
    user: User = Depends(get_current_user),
) -> User:
    """Return current authenticated user's full profile."""
    return user


@router.patch("/user/profile", response_model=UserRead)
def update_user_profile(
    full_name: str | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> User:
    """Update mutable profile fields (full_name) for the authenticated user."""
    try:
        if full_name is not None:
            user.full_name = full_name.strip()
        db.commit()
        db.refresh(user)
        return user
    except Exception:
        db.rollback()
        raise HTTPException(status_code=500, detail="Failed to update profile.")



