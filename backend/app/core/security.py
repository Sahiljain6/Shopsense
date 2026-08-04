from datetime import datetime, timedelta, timezone
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy import select
from sqlalchemy.orm import Session
from backend.app.core.config import get_settings
from backend.app.db.session import get_db
from backend.app.models import User

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/login")

def hash_password(password: str) -> str: return pwd_context.hash(password)
def verify_password(password: str, hashed: str) -> bool: return pwd_context.verify(password, hashed)
def create_token(subject: str) -> str:
    s = get_settings(); exp = datetime.now(timezone.utc) + timedelta(hours=12)
    return jwt.encode({"sub": subject, "exp": exp}, s.jwt_secret, algorithm=s.jwt_algorithm)

def current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> User:
    try:
        payload = jwt.decode(token, get_settings().jwt_secret, algorithms=[get_settings().jwt_algorithm])
        email = payload.get("sub")
    except JWTError:
        email = None
    if not email: raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid authentication token")
    user = db.scalar(select(User).where(User.email == email))
    if not user: raise HTTPException(status.HTTP_401_UNAUTHORIZED, "User no longer exists")
    return user

def admin_user(user: User = Depends(current_user)) -> User:
    if not user.is_admin: raise HTTPException(status.HTTP_403_FORBIDDEN, "Admin access required")
    return user
