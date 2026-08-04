from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from backend.app.core.security import admin_user, create_token, current_user, hash_password, verify_password
from backend.app.db.session import get_db
from backend.app.models import ChatHistory, Order, Product, Review, User, Wishlist
from backend.app.schemas.api import *
from backend.app.services.ai import AIOrchestrator
from backend.app.services.catalog import CatalogService

router=APIRouter()
@router.post('/register',response_model=TokenResponse)
def register(req:RegisterRequest,db:Session=Depends(get_db)):
    if db.scalar(select(User).where(User.email==req.email)): raise HTTPException(409,'Email already registered')
    user=User(email=req.email,full_name=req.full_name,hashed_password=hash_password(req.password)); db.add(user); db.commit(); return TokenResponse(access_token=create_token(req.email))
@router.post('/login',response_model=TokenResponse)
def login(req:LoginRequest,db:Session=Depends(get_db)):
    user=db.scalar(select(User).where(User.email==req.email))
    if not user or not verify_password(req.password,user.hashed_password): raise HTTPException(401,'Invalid credentials')
    return TokenResponse(access_token=create_token(req.email))
@router.get('/me',response_model=UserOut)
def me(user:User=Depends(current_user)): return user
@router.get('/products',response_model=list[ProductOut])
def products(q:str='',limit:int=50,db:Session=Depends(get_db)): return CatalogService(db).search(q,limit)
@router.post('/chat',response_model=ChatResponse)
def chat(req:ChatRequest,db:Session=Depends(get_db),user:User=Depends(current_user)):
    history=[h.content for h in db.scalars(select(ChatHistory).where(ChatHistory.user_id==user.id).order_by(ChatHistory.created_at.desc()).limit(8))]
    ai=AIOrchestrator(); clarification=ai.needs_clarification(req.message); found=[] if clarification else CatalogService(db).search(req.message,5); answer=clarification or ai.answer(req.message,found,history)
    db.add_all([ChatHistory(user_id=user.id,role='user',content=req.message,memory={}),ChatHistory(user_id=user.id,role='assistant',content=answer,memory={'products':[p.id for p in found]})]); db.commit()
    return ChatResponse(answer=answer,products=found,clarification=clarification)
@router.post('/recommend',response_model=ChatResponse)
def recommend(req:ChatRequest,db:Session=Depends(get_db),user:User=Depends(current_user)): return chat(req,db,user)
@router.post('/compare')
def compare(req:CompareRequest,db:Session=Depends(get_db),user:User=Depends(current_user)): return AIOrchestrator().compare(CatalogService(db).by_ids(req.product_ids))
@router.post('/reviews/summary')
def reviews(req:ReviewsRequest,db:Session=Depends(get_db)): return AIOrchestrator().summarize_reviews(CatalogService(db).reviews(req.product_id))
@router.get('/reviews/{product_id}',response_model=list[ReviewOut])
def product_reviews(product_id:int,db:Session=Depends(get_db)): return CatalogService(db).reviews(product_id)
@router.get('/history')
def history(db:Session=Depends(get_db),user:User=Depends(current_user)): return list(db.scalars(select(ChatHistory).where(ChatHistory.user_id==user.id).order_by(ChatHistory.created_at.desc()).limit(50)))
@router.get('/wishlist',response_model=list[ProductOut])
def get_wishlist(db:Session=Depends(get_db),user:User=Depends(current_user)):
    return list(db.scalars(select(Product).join(Wishlist,Wishlist.product_id==Product.id).where(Wishlist.user_id==user.id)))
@router.post('/wishlist')
def wishlist(req:WishlistRequest,db:Session=Depends(get_db),user:User=Depends(current_user)):
    if not db.get(Product,req.product_id): raise HTTPException(404,'Product not found')
    if not db.scalar(select(Wishlist).where(Wishlist.user_id==user.id,Wishlist.product_id==req.product_id)): db.add(Wishlist(user_id=user.id,product_id=req.product_id)); db.commit()
    return {'saved':True}
@router.delete('/wishlist/{product_id}')
def remove_wishlist(product_id:int,db:Session=Depends(get_db),user:User=Depends(current_user)):
    item=db.scalar(select(Wishlist).where(Wishlist.user_id==user.id,Wishlist.product_id==product_id));
    if item: db.delete(item); db.commit()
    return {'removed':True}
@router.get('/admin/analytics')
def analytics(db:Session=Depends(get_db),user:User=Depends(admin_user)):
    return {'products':db.scalar(select(func.count(Product.id))),'users':db.scalar(select(func.count(User.id))),'reviews':db.scalar(select(func.count(Review.id))),'orders':db.scalar(select(func.count(Order.id))),'revenue':db.scalar(select(func.coalesce(func.sum(Order.total),0)))}
@router.get('/admin/users',response_model=list[UserOut])
def admin_users(db:Session=Depends(get_db),user:User=Depends(admin_user)): return list(db.scalars(select(User).limit(200)))
@router.post('/admin/products',response_model=ProductOut)
def create_product(req:ProductWrite,db:Session=Depends(get_db),user:User=Depends(admin_user)):
    p=Product(**req.model_dump()); db.add(p); db.commit(); db.refresh(p); return p
@router.put('/admin/products/{product_id}',response_model=ProductOut)
def update_product(product_id:int,req:ProductWrite,db:Session=Depends(get_db),user:User=Depends(admin_user)):
    p=db.get(Product,product_id)
    if not p: raise HTTPException(404,'Product not found')
    for k,v in req.model_dump().items(): setattr(p,k,v)
    db.commit(); db.refresh(p); return p
@router.delete('/admin/products/{product_id}')
def delete_product(product_id:int,db:Session=Depends(get_db),user:User=Depends(admin_user)):
    p=db.get(Product,product_id)
    if not p: raise HTTPException(404,'Product not found')
    db.delete(p); db.commit(); return {'deleted':True}
@router.get('/admin/reviews',response_model=list[ReviewOut])
def admin_reviews(db:Session=Depends(get_db),user:User=Depends(admin_user)): return list(db.scalars(select(Review).limit(200)))
@router.get('/admin/orders',response_model=list[OrderOut])
def admin_orders(db:Session=Depends(get_db),user:User=Depends(admin_user)): return list(db.scalars(select(Order).limit(200)))
