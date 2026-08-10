from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from app.core.security import create_access_token, get_current_user, hash_password, require_admin, verify_password
from app.db.session import get_db
from app.models.entities import ChatHistory, Order, Product, Review, User, Wishlist
from app.schemas.api import ChatRequest, ChatResponse, CompareRequest, ProductCreate, ProductRead, ReviewRead, ReviewSummaryRequest, Token, UserCreate, UserLogin, UserRead, WishlistRequest
from app.services.ai import AIOrchestrator
from app.services.catalog import CatalogService

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
