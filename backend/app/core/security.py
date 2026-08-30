import secrets
from datetime import datetime, timedelta, timezone
from fastapi import Depends, HTTPException, Request, Response, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.core.config import get_settings
from app.db.session import get_db
from app.models.entities import User

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login", auto_error=False)


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(password: str, hashed_password: str) -> bool:
    return pwd_context.verify(password, hashed_password)


def create_access_token(subject: str) -> str:
    settings = get_settings()
    expires = datetime.now(timezone.utc) + timedelta(minutes=settings.access_token_minutes)
    return jwt.encode(
        {"sub": subject, "exp": expires, "type": "access", "jti": secrets.token_hex(8)},
        settings.jwt_secret,
        algorithm=settings.jwt_algorithm
    )


def create_refresh_token(subject: str) -> str:
    settings = get_settings()
    expires = datetime.now(timezone.utc) + timedelta(days=settings.refresh_token_days)
    return jwt.encode(
        {"sub": subject, "exp": expires, "type": "refresh", "jti": secrets.token_hex(8)},
        settings.jwt_secret,
        algorithm=settings.jwt_algorithm
    )


def decode_refresh_token(token: str) -> str:
    settings = get_settings()
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
        if payload.get("type") != "refresh":
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token type")
        email = payload.get("sub")
        if not email:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token subject")
        return str(email)
    except JWTError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired refresh token") from exc


def set_auth_cookies(
    response: Response,
    access_token: str,
    refresh_token: str | None = None,
    csrf_token: str | None = None
) -> str:
    settings = get_settings()
    is_prod = (settings.environment or "").lower() == "production"
    samesite = "none" if is_prod else "lax"
    secure = is_prod

    if not csrf_token:
        csrf_token = secrets.token_hex(16)

    # 1. httpOnly Access Token
    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,
        secure=secure,
        samesite=samesite,
        max_age=settings.access_token_minutes * 60,
        path="/"
    )

    # 2. httpOnly Refresh Token
    if refresh_token:
        response.set_cookie(
            key="refresh_token",
            value=refresh_token,
            httponly=True,
            secure=secure,
            samesite=samesite,
            max_age=settings.refresh_token_days * 86400,
            path="/"
        )

    # 3. Client-accessible CSRF Token
    response.set_cookie(
        key="csrf_token",
        value=csrf_token,
        httponly=False,
        secure=secure,
        samesite=samesite,
        max_age=settings.refresh_token_days * 86400,
        path="/"
    )
    return csrf_token


def clear_auth_cookies(response: Response) -> None:
    settings = get_settings()
    is_prod = (settings.environment or "").lower() == "production"
    samesite = "none" if is_prod else "lax"
    secure = is_prod

    for key in ["access_token", "refresh_token", "csrf_token"]:
        response.delete_cookie(key=key, path="/", samesite=samesite, secure=secure)


def get_current_user(
    request: Request,
    token: str | None = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
) -> User:
    settings = get_settings()
    raw_token = None
    used_cookie = False

    # 1. Prefer explicit Authorization header if provided (not ambient/CSRF-vulnerable)
    if token:
        raw_token = token
        used_cookie = False
    elif request.cookies.get("access_token"):
        raw_token = request.cookies.get("access_token")
        used_cookie = True

    if not raw_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")

    # 2. Check CSRF on state-changing methods if cookie auth was used
    if used_cookie and request.method in ["POST", "PUT", "DELETE", "PATCH"]:
        cookie_csrf = request.cookies.get("csrf_token")
        header_csrf = request.headers.get("x-csrf-token")
        if not cookie_csrf or not header_csrf or not secrets.compare_digest(cookie_csrf, header_csrf):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="CSRF token validation failed")

    try:
        payload = jwt.decode(raw_token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
        email = payload.get("sub")
        token_type = payload.get("type", "access")
        if token_type != "access" or not email:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    except JWTError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token") from exc

    user = db.scalar(select(User).where(User.email == email))
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    return user


def require_admin(user: User = Depends(get_current_user)) -> User:
    if not user.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin only")
    return user
