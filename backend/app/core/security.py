from datetime import datetime, timedelta, timezone
from jose import jwt
from passlib.context import CryptContext
from backend.app.core.config import get_settings
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
def hash_password(password: str) -> str: return pwd_context.hash(password)
def verify_password(password: str, hashed: str) -> bool: return pwd_context.verify(password, hashed)
def create_token(subject: str) -> str:
    s = get_settings(); exp = datetime.now(timezone.utc) + timedelta(hours=12)
    return jwt.encode({"sub": subject, "exp": exp}, s.jwt_secret, algorithm=s.jwt_algorithm)
