import secrets
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional, Set, Tuple

from fastapi import Depends, HTTPException, Request, Response, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.auth_types import (
    ROLE_PERMISSIONS,
    TIER_DEFAULT_QUOTAS,
    SecurityContext,
    TierQuotaConfig,
    UserTier,
)
from app.db.session import get_db
from app.models.entities import User

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login", auto_error=False)

# In-memory fast O(1) state cache (0 DB queries required for auth checks)
# In high-volume production, backed by Redis cluster with local memory fallback
_ACTIVE_TOKEN_VERSIONS: Dict[int, int] = {}
_REVOKED_TOKEN_FAMILIES: Set[str] = set()
_USED_REFRESH_JTIS: Dict[str, str] = {}  # jti -> family_id


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(password: str, hashed_password: str) -> bool:
    return pwd_context.verify(password, hashed_password)


def get_user_tier(user: User) -> UserTier:
    if getattr(user, "is_admin", False):
        return UserTier.ADMIN
    raw_tier = getattr(user, "tier", "free") or "free"
    try:
        return UserTier(raw_tier.lower())
    except ValueError:
        return UserTier.FREE


def get_user_scopes(tier: UserTier) -> list[str]:
    return sorted(list(ROLE_PERMISSIONS.get(tier, ROLE_PERMISSIONS[UserTier.FREE])))


def get_active_token_version(user_id: int, fallback_version: int = 1) -> int:
    return _ACTIVE_TOKEN_VERSIONS.get(user_id, fallback_version)


def set_active_token_version(user_id: int, version: int) -> None:
    _ACTIVE_TOKEN_VERSIONS[user_id] = version


def invalidate_user_sessions(user_id: int) -> int:
    """Increment user token version so all existing access tokens are immediately rejected."""
    current = _ACTIVE_TOKEN_VERSIONS.get(user_id, 1)
    new_version = current + 1
    _ACTIVE_TOKEN_VERSIONS[user_id] = new_version
    return new_version


def create_access_token(
    subject: str,
    user: Optional[User] = None,
    custom_claims: Optional[Dict[str, Any]] = None,
) -> str:
    settings = get_settings()
    expires = datetime.now(timezone.utc) + timedelta(minutes=settings.access_token_minutes)

    tier = get_user_tier(user) if user else UserTier.FREE
    scopes = get_user_scopes(tier)
    quota = TIER_DEFAULT_QUOTAS[tier]
    user_id = getattr(user, "id", None) if user else None
    org_id = getattr(user, "org_id", None) if user else None
    user_token_ver = getattr(user, "token_version", 1) if user else 1

    if user_id:
        active_ver = get_active_token_version(user_id, user_token_ver)
        if active_ver > user_token_ver:
            user_token_ver = active_ver
        else:
            set_active_token_version(user_id, user_token_ver)

    feature_flags = getattr(user, "feature_flags", []) if user else []
    if not isinstance(feature_flags, list):
        feature_flags = list(feature_flags) if feature_flags else []

    payload: Dict[str, Any] = {
        "sub": subject,
        "type": "access",
        "jti": secrets.token_hex(16),
        "iat": int(datetime.now(timezone.utc).timestamp()),
        "exp": expires,
        "user_id": user_id,
        "email": subject,
        "org_id": org_id,
        "tier": tier.value,
        "token_version": user_token_ver,
        "scopes": scopes,
        "feature_flags": feature_flags,
        "quota": quota.model_dump(),
    }

    if custom_claims:
        payload.update(custom_claims)

    return jwt.encode(
        payload,
        settings.jwt_secret,
        algorithm=settings.jwt_algorithm,
    )


def create_refresh_token(
    subject: str,
    family_id: Optional[str] = None,
    user_id: Optional[int] = None,
) -> str:
    settings = get_settings()
    expires = datetime.now(timezone.utc) + timedelta(days=settings.refresh_token_days)
    token_family = family_id or secrets.token_hex(16)
    jti = secrets.token_hex(16)

    payload = {
        "sub": subject,
        "type": "refresh",
        "jti": jti,
        "family_id": token_family,
        "user_id": user_id,
        "iat": int(datetime.now(timezone.utc).timestamp()),
        "exp": expires,
    }
    return jwt.encode(
        payload,
        settings.jwt_secret,
        algorithm=settings.jwt_algorithm,
    )


def rotate_refresh_token(
    token: str,
) -> Tuple[str, str, Optional[int]]:
    """
    Validate refresh token and execute Refresh Token Rotation (RTR).
    Returns (new_refresh_token, email, user_id).
    Raises HTTPException 401 if token is expired, invalid, or reused.
    """
    settings = get_settings()
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
        if payload.get("type") != "refresh":
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token type")

        email = payload.get("sub")
        family_id = payload.get("family_id")
        jti = payload.get("jti")
        user_id = payload.get("user_id")

        if not email or not jti or not family_id:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Malformed refresh token")

        # 1. Family compromised check
        if family_id in _REVOKED_TOKEN_FAMILIES:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Security alert: Token family revoked due to previous reuse.",
            )

        # 2. Token reuse detection (RTR replay attack)
        if jti in _USED_REFRESH_JTIS:
            # Token reuse detected! Revoke the entire token family
            _REVOKED_TOKEN_FAMILIES.add(family_id)
            if user_id:
                invalidate_user_sessions(user_id)
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Security alert: Refresh token reuse detected. All sessions in this family revoked.",
            )

        # 3. Mark current token as used
        _USED_REFRESH_JTIS[jti] = family_id

        # 4. Issue rotated refresh token with same family_id
        new_refresh = create_refresh_token(
            subject=email,
            family_id=family_id,
            user_id=user_id,
        )
        return new_refresh, str(email), user_id

    except JWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
        ) from exc


def decode_refresh_token(token: str) -> str:
    """Legacy helper for backward compatibility."""
    new_token, email, _ = rotate_refresh_token(token)
    return email


def decode_and_validate_access_token(token: str) -> SecurityContext:
    """
    Stateless JWT verification + fast O(1) in-memory revocation check.
    Zero DB queries required!
    """
    settings = get_settings()
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
        if payload.get("type") != "access":
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token type")

        email = payload.get("sub")
        user_id = payload.get("user_id")
        token_ver = payload.get("token_version", 1)

        if not email:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing token subject")

        # Fast O(1) Token Version check (detects tier downgrades or revocations mid-session)
        if user_id is not None:
            active_version = _ACTIVE_TOKEN_VERSIONS.get(user_id)
            if active_version is not None and active_version > token_ver:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Session superseded or tier updated. Please refresh token.",
                )

        raw_tier = payload.get("tier", UserTier.FREE.value)
        try:
            tier = UserTier(raw_tier)
        except ValueError:
            tier = UserTier.FREE

        raw_quota = payload.get("quota")
        quota = (
            TierQuotaConfig(**raw_quota)
            if isinstance(raw_quota, dict)
            else TIER_DEFAULT_QUOTAS.get(tier, TIER_DEFAULT_QUOTAS[UserTier.FREE])
        )

        return SecurityContext(
            user_id=user_id or 0,
            email=email,
            tier=tier,
            org_id=payload.get("org_id"),
            token_version=token_ver,
            scopes=set(payload.get("scopes", [])),
            feature_flags=set(payload.get("feature_flags", [])),
            quota=quota,
        )
    except JWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        ) from exc


def set_auth_cookies(
    response: Response,
    access_token: str,
    refresh_token: str | None = None,
    csrf_token: str | None = None,
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
        path="/",
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
            path="/",
        )

    # 3. Client-accessible CSRF Token
    response.set_cookie(
        key="csrf_token",
        value=csrf_token,
        httponly=False,
        secure=secure,
        samesite=samesite,
        max_age=settings.refresh_token_days * 86400,
        path="/",
    )
    return csrf_token


def clear_auth_cookies(response: Response) -> None:
    settings = get_settings()
    is_prod = (settings.environment or "").lower() == "production"
    samesite = "none" if is_prod else "lax"
    secure = is_prod

    for key in ["access_token", "refresh_token", "csrf_token"]:
        response.delete_cookie(key=key, path="/", samesite=samesite, secure=secure)


def get_token_from_request(
    request: Request,
    token: str | None = Depends(oauth2_scheme),
) -> str:
    """Extract and validate raw token from Authorization header or cookie with CSRF check."""
    raw_token = None
    used_cookie = False

    if token:
        raw_token = token
        used_cookie = False
    elif request.cookies.get("access_token"):
        raw_token = request.cookies.get("access_token")
        used_cookie = True

    if not raw_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
        )

    if used_cookie and request.method in ["POST", "PUT", "DELETE", "PATCH"]:
        cookie_csrf = request.cookies.get("csrf_token")
        header_csrf = request.headers.get("x-csrf-token")
        if not cookie_csrf or not header_csrf or not secrets.compare_digest(cookie_csrf, header_csrf):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="CSRF token validation failed",
            )

    return raw_token


def get_security_context(
    request: Request,
    token: str = Depends(get_token_from_request),
) -> SecurityContext:
    """Fast dependency returning SecurityContext without contacting database (0 DB queries)."""
    return decode_and_validate_access_token(token)


def get_current_user(
    request: Request,
    token: str | None = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> User:
    """Standard user dependency with token validation and database entity hydration."""
    raw_token = get_token_from_request(request, token)
    context = decode_and_validate_access_token(raw_token)

    user = db.scalar(select(User).where(User.email == context.email))
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )

    # Sync token version in cache if needed
    if user.id:
        db_version = getattr(user, "token_version", 1)
        active_ver = get_active_token_version(user.id, db_version)
        if active_ver > context.token_version:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Session superseded or tier updated. Please refresh token.",
            )

    return user


def require_admin(
    user: User = Depends(get_current_user),
) -> User:
    if not (user.is_admin or getattr(user, "tier", "") == UserTier.ADMIN.value):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )
    return user
