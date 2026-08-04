from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session
from backend.app.core.security import create_token, hash_password, verify_password
from backend.app.db.session import get_db
from backend.app.models import ChatHistory, Product, User, Wishlist
from backend.app.schemas.api import *
from backend.app.services.ai import AIOrchestrator
from backend.app.services.catalog import CatalogService

router = APIRouter()
def demo_user_id() -> int: return 1

@router.post("/register", response_model=TokenResponse)
def register(req: RegisterRequest, db: Session = Depends(get_db)):
    if db.scalar(select(User).where(User.email == req.email)): raise HTTPException(409, "Email already registered")
    user = User(email=req.email, full_name=req.full_name, hashed_password=hash_password(req.password)); db.add(user); db.commit()
    return TokenResponse(access_token=create_token(req.email))
@router.post("/login", response_model=TokenResponse)
def login(req: LoginRequest, db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(User.email == req.email))
    if not user or not verify_password(req.password, user.hashed_password): raise HTTPException(401, "Invalid credentials")
    return TokenResponse(access_token=create_token(req.email))
@router.get("/products", response_model=list[ProductOut])
def products(q: str = "", db: Session = Depends(get_db)): return CatalogService(db).search(q, 50)
@router.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest, db: Session = Depends(get_db)):
    ai = AIOrchestrator(); clarification = ai.needs_clarification(req.message)
    found = [] if clarification else CatalogService(db).search(req.message, 3)
    answer = clarification or ai.answer(req.message, found)
    db.add(ChatHistory(user_id=demo_user_id(), role="user", content=req.message, memory={}))
    db.add(ChatHistory(user_id=demo_user_id(), role="assistant", content=answer, memory={"products": [p.id for p in found]})); db.commit()
    return ChatResponse(answer=answer, products=found, clarification=clarification)
@router.post("/recommend", response_model=ChatResponse)
def recommend(req: ChatRequest, db: Session = Depends(get_db)): return chat(req, db)
@router.post("/compare")
def compare(req: CompareRequest, db: Session = Depends(get_db)): return AIOrchestrator().compare(CatalogService(db).by_ids(req.product_ids))
@router.post("/reviews")
def reviews(req: ReviewsRequest, db: Session = Depends(get_db)): return AIOrchestrator().summarize_reviews(CatalogService(db).reviews(req.product_id))
@router.get("/history")
def history(db: Session = Depends(get_db)): return list(db.scalars(select(ChatHistory).order_by(ChatHistory.created_at.desc()).limit(50)))
@router.post("/wishlist")
def wishlist(req: WishlistRequest, db: Session = Depends(get_db)):
    if not db.get(Product, req.product_id): raise HTTPException(404, "Product not found")
    db.add(Wishlist(user_id=demo_user_id(), product_id=req.product_id)); db.commit(); return {"saved": True}
