import asyncio
from contextvars import copy_context
import hashlib
import hmac
import json
import logging
import time
from datetime import datetime, timedelta
from decimal import Decimal, InvalidOperation
import httpx
from fastapi import APIRouter, Depends, File, HTTPException, Request, Response, UploadFile, status
from fastapi.responses import StreamingResponse
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy import delete, func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from app.core.config import get_settings
from app.core.auth_types import Scope, SecurityContext, UserTier
from app.core.audit import audit_logger
from app.core.db_scoping import ScopedQueryFilter
from app.core.observability import current_request_id
from app.core.quota import quota_engine
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
from app.models.entities import ChatHistory, ChatIdempotency, Order, PaymentAttempt, Product, Review, SeedVersion, User, Wishlist
from app.schemas.api import ChatRequest, ChatResponse, CompareRequest, FetchLinkRequest, FetchLinkResponse, GoogleAuthRequest, ParbadPaymentEvent, PaymentCheckoutRequest, PriceHistoryResponse, ProductCreate, ProductRead, RefreshTokenRequest, ReviewRead, ReviewSummaryRequest, Token, UserCreate, UserLogin, UserRead, WishlistRequest
from app.services.ai import AIOrchestrator
from app.services.barcode_lookup import lookup_barcode
from app.services.catalog import CatalogService
from app.services.currency import convert_price
from app.services.deal_hunter import fetch_gaming_deals
from app.services.scraper import scrape_product
from app.services.ssrf_validator import SSRFError, validate_url
from app.services.vision import identify_image
from app.services.context_manager import ContextWindowManager, SummarizationService
from app.services.conversation_service import ConversationService

logger = logging.getLogger("shopsense.api")
router = APIRouter()


def _request_rate_limit_key(request: Request) -> str:
    """Use a verified user ID for authenticated routes and the host-derived IP otherwise."""
    user_id = getattr(request.state, "user_id", None)
    return f"user:{user_id}" if user_id is not None else get_remote_address(request)


limiter = Limiter(key_func=_request_rate_limit_key)


CHAT_IDEMPOTENCY_TTL = timedelta(hours=24)
CHAT_IDEMPOTENCY_STALE_AFTER = timedelta(minutes=3)


def _enforce_chat_quota(context: SecurityContext, estimated_tokens: int = 500) -> str:
    """Atomically reserve quota after cache lookup so replays do not consume allowance."""
    monthly_limit = context.quota.monthly_tokens
    allowed, current_usage, reservation_id = quota_engine.reserve(
        context.user_id,
        estimated_tokens=estimated_tokens,
        monthly_limit=monthly_limit,
    )
    if allowed and reservation_id:
        return reservation_id
    try:
        audit_logger.log_quota_exceeded(
            user_id=context.user_id,
            email=context.email,
            tier=context.tier.value,
            metric="monthly_tokens",
            limit=monthly_limit,
            current_usage=current_usage,
            requested=estimated_tokens,
        )
    except Exception:
        pass
    raise HTTPException(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        detail={
            "error": "Quota Exceeded",
            "reason": "monthly_token_quota_exceeded",
            "monthly_limit": monthly_limit,
            "current_usage": current_usage,
            "requested_tokens": estimated_tokens,
            "tier": context.tier.value,
            "upgrade_hint": "Upgrade to Pro or Enterprise for increased token allowances.",
        },
    )


def _chat_request_fingerprint(payload: ChatRequest) -> str:
    """Fingerprint the semantic request without its idempotency key."""
    request_data = payload.model_dump(mode="json", exclude={"idempotency_key"})
    canonical = json.dumps(request_data, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _claim_chat_idempotency(
    db: Session, user_id: int, payload: ChatRequest
) -> tuple[str, ChatResponse | None]:
    """Claim a chat operation or return its completed response for a safe retry."""
    key = payload.idempotency_key
    if not key:
        return "new", None

    fingerprint = _chat_request_fingerprint(payload)
    now = datetime.utcnow()
    db.execute(delete(ChatIdempotency).where(ChatIdempotency.expires_at <= now))
    db.commit()

    for _attempt in range(3):
        record = db.scalar(
            select(ChatIdempotency)
            .where(ChatIdempotency.user_id == user_id, ChatIdempotency.key == key)
            .with_for_update()
        )
        if record is not None:
            if record.request_hash != fingerprint:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="This idempotency key was already used for a different chat request.",
                )
            if record.status == "completed" and record.response_payload is not None:
                logger.info(
                    "chat_idempotency request_id=%s outcome=replay",
                    current_request_id(),
                )
                return "replay", ChatResponse.model_validate(record.response_payload)

            age = now - record.updated_at if record.updated_at else CHAT_IDEMPOTENCY_STALE_AFTER
            if record.status == "processing" and age <= CHAT_IDEMPOTENCY_STALE_AFTER:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="This chat request is already processing. Retry with the same idempotency key.",
                )

            previous_updated_at = record.updated_at
            result = db.execute(
                update(ChatIdempotency)
                .where(
                    ChatIdempotency.id == record.id,
                    ChatIdempotency.status == record.status,
                    ChatIdempotency.updated_at == previous_updated_at,
                )
                .values(
                    status="processing",
                    response_payload=None,
                    updated_at=now,
                    expires_at=now + CHAT_IDEMPOTENCY_TTL,
                )
            )
            db.commit()
            if result.rowcount == 1:
                return "new", None
            db.expire_all()
            continue

        record = ChatIdempotency(
            user_id=user_id,
            key=key,
            request_hash=fingerprint,
            status="processing",
            created_at=now,
            updated_at=now,
            expires_at=now + CHAT_IDEMPOTENCY_TTL,
        )
        db.add(record)
        try:
            db.commit()
            return "new", None
        except IntegrityError:
            db.rollback()

    raise HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail="Unable to claim this chat request safely. Retry with the same idempotency key.",
    )


def _complete_chat_idempotency(
    db: Session, user_id: int, payload: ChatRequest, response: ChatResponse
) -> None:
    if not payload.idempotency_key:
        return
    record = db.scalar(
        select(ChatIdempotency).where(
            ChatIdempotency.user_id == user_id,
            ChatIdempotency.key == payload.idempotency_key,
        )
    )
    if record is None:
        return
    record.status = "completed"
    record.response_payload = response.model_dump(mode="json")
    record.updated_at = datetime.utcnow()
    record.expires_at = record.updated_at + CHAT_IDEMPOTENCY_TTL
    db.commit()
    logger.info(
        "chat_idempotency request_id=%s outcome=completed",
        current_request_id(),
    )


def _release_chat_idempotency(db: Session, user_id: int, key: str | None) -> None:
    """Release only unfinished claims so callers may retry after a failed attempt."""
    if not key:
        return
    try:
        db.execute(
            delete(ChatIdempotency).where(
                ChatIdempotency.user_id == user_id,
                ChatIdempotency.key == key,
                ChatIdempotency.status == "processing",
            )
        )
        db.commit()
    except Exception:
        db.rollback()


async def _replay_chat_response_events(response: ChatResponse):
    """Replay a cached result using the same SSE event shape as a fresh response."""
    yield f"data: {json.dumps({'type': 'status', 'status': 'Restoring completed response...'})}\n\n"
    words = (response.answer or "").split(" ")
    chunk_size = 4
    for i in range(0, len(words), chunk_size):
        chunk = " ".join(words[i:i + chunk_size])
        if i + chunk_size < len(words):
            chunk += " "
        yield f"data: {json.dumps({'type': 'token', 'token': chunk, 'chunk': chunk})}\n\n"
    if response.products:
        yield f"data: {json.dumps({'type': 'products', 'products': [p.model_dump() for p in response.products], 'product_ids': response.product_ids})}\n\n"
    if response.live_deals:
        yield f"data: {json.dumps({'type': 'live_deals', 'live_deals': [d.model_dump() for d in response.live_deals]})}\n\n"
    yield f"data: {json.dumps({'type': 'done', 'response': response.model_dump(mode='json')})}\n\n"
    yield "data: [DONE]\n\n"


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
        if user is None:
            raise HTTPException(
                status_code=401,
                detail="No account found with this email. Please switch to Create Account to register.",
            )
        if not user.hashed_password:
            raise HTTPException(
                status_code=401,
                detail="This account was registered using Google. Please click 'Continue with Google'.",
            )
        if not verify_password(payload.password, user.hashed_password):
            raise HTTPException(
                status_code=401,
                detail="Incorrect password. Please verify your password and try again.",
            )
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
    user: User = Depends(require_admin),
) -> dict[str, object]:
    """
    Admin-only legacy endpoint: update the admin's tier and invalidate old sessions.
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
def products(q: str | None = None, limit: int = 10, ids: str | None = None, db: Session = Depends(get_db)) -> list[ProductRead]:
    try:
        if ids:
            parsed_ids = [int(x.strip()) for x in ids.split(",") if x.strip().isdigit()]
            if parsed_ids:
                return [_product_read(p) for p in CatalogService(db).get_many(parsed_ids)]
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
    context: SecurityContext = Depends(get_security_context),
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

    idempotency_state, cached_response = _claim_chat_idempotency(db, user.id, payload)
    if cached_response is not None:
        return cached_response

    quota_reservation_id: str | None = None
    try:
        quota_reservation_id = _enforce_chat_quota(context)
        history = [{"role": turn.role, "content": turn.content} for turn in payload.history]
        context_plan = None

        if payload.conversation_id:
            try:
                cwm = ContextWindowManager(model_name=payload.model or "default")
                context_plan = cwm.assemble_conversation_context(
                    db=db,
                    conversation_id=payload.conversation_id,
                    current_query=payload.message,
                )
                # Use assembled messages as history (excluding current user turn)
                assembled = context_plan["assembled_messages"]
                history = [m for m in assembled if m["role"] != "user" or m["content"] != payload.message]
            except Exception as err:
                logger.warning(
                    "conversation_context request_id=%s outcome=assembly_failed error_type=%s",
                    current_request_id(),
                    type(err).__name__,
                )

        generation_succeeded = False
        try:
            response = AIOrchestrator(db).answer_via_agents(
                payload.message,
                payload.mode,
                history,
                cart=payload.cart,
                model=payload.model,
            )
            generation_succeeded = True
        except Exception as err:
            db.rollback()
            logger.warning("AI chat generation failed; returning a retryable fallback response: %s", type(err).__name__)
            response = ChatResponse(
                answer="I ran into a temporary issue retrieving product data. Please try asking again in a moment."
            )

        if generation_succeeded:
            tokens_consumed = max(50, (len(payload.message) + len(response.answer)) // 4 + 50)
            try:
                quota_engine.complete_reservation(user.id, quota_reservation_id, tokens_consumed)
                quota_reservation_id = None
            except Exception as quota_err:
                logger.warning("Unable to finalize AI token accounting: %s", type(quota_err).__name__)
        elif quota_reservation_id:
            quota_engine.release_reservation(user.id, quota_reservation_id)
            quota_reservation_id = None

        # Attach full product schemas so frontend does not need a second roundtrip
        if response.product_ids and not response.products:
            try:
                prod_entities = CatalogService(db).get_many(response.product_ids)
                response.products = [_product_read(p) for p in prod_entities]
            except Exception as e:
                logger.warning("Notice attaching product models to chat response: %s", e)

        if generation_succeeded:
            _complete_chat_idempotency(db, user.id, payload, response)
        else:
            # Do not memoize a transient provider error as a successful answer.
            _release_chat_idempotency(db, user.id, payload.idempotency_key)

        # Save chat history in an isolated transaction so history logging never crashes the response
        try:
            db.add(ChatHistory(user_id=user.id, message=payload.message, response=response.model_dump()))
            db.commit()
        except Exception as err:
            db.rollback()
            print(f"Notice: unable to save chat history: {err}")

        # Persist turns into stateful conversation management system if conversation_id provided
        if payload.conversation_id:
            try:
                ConversationService.add_message(
                    db=db,
                    conversation_id=payload.conversation_id,
                    role="user",
                    content=payload.message,
                )
                ConversationService.add_message(
                    db=db,
                    conversation_id=payload.conversation_id,
                    role="assistant",
                    content=response.answer,
                )
                if context_plan and context_plan.get("needs_summarization"):
                    SummarizationService.execute_summarization(db=db, conversation_id=payload.conversation_id)
            except Exception as err:
                logger.warning(
                    "conversation_persistence request_id=%s outcome=failed error_type=%s",
                    current_request_id(),
                    type(err).__name__,
                )

        return response
    except Exception:
        if quota_reservation_id:
            quota_engine.release_reservation(user.id, quota_reservation_id)
        _release_chat_idempotency(db, user.id, payload.idempotency_key)
        raise


@router.post("/chat/stream")
@limiter.limit("30/minute")
async def chat_stream(
    request: Request,
    payload: ChatRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    context: SecurityContext = Depends(get_security_context),
):
    """Server-Sent Events (SSE) chat streaming endpoint for fast perceived latency.
    Emits progressive status updates, token chunks, resolved products, and final metadata.
    """
    is_advanced_request = (
        payload.mode in ["advanced", "deep_research"]
        or (payload.model and any(adv in payload.model.lower() for adv in ["claude 3.7", "opus", "extended"]))
    )
    if is_advanced_request and not context.has_scope(Scope.LLM_QUERY_ADVANCED.value):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error": "Forbidden",
                "message": "Advanced reasoning models require Pro or Enterprise tier subscription.",
                "required_scope": Scope.LLM_QUERY_ADVANCED.value,
                "current_tier": context.tier.value,
            },
        )

    idempotency_state, cached_response = _claim_chat_idempotency(db, user.id, payload)
    if cached_response is not None:
        return StreamingResponse(
            _replay_chat_response_events(cached_response),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache, no-transform", "Connection": "keep-alive", "X-Accel-Buffering": "no"},
        )
    try:
        quota_reservation_id = _enforce_chat_quota(context)
    except Exception:
        _release_chat_idempotency(db, user.id, payload.idempotency_key)
        raise

    idempotency_completed = False
    history = [{"role": turn.role, "content": turn.content} for turn in payload.history]
    context_plan = None
    if payload.conversation_id:
        try:
            cwm = ContextWindowManager(model_name=payload.model or "default")
            context_plan = cwm.assemble_conversation_context(
                db=db,
                conversation_id=payload.conversation_id,
                current_query=payload.message,
            )
            assembled = context_plan["assembled_messages"]
            history = [m for m in assembled if m["role"] != "user" or m["content"] != payload.message]
        except Exception as err:
            logger.warning(
                "conversation_context request_id=%s outcome=assembly_failed error_type=%s",
                current_request_id(),
                type(err).__name__,
            )

    async def event_generator():
        nonlocal idempotency_completed, quota_reservation_id
        try:
            stream_started = time.perf_counter()
            # 1. Initial status event
            yield f"data: {json.dumps({'type': 'status', 'status': 'Analyzing query...'})}\n\n"

            # 2. Provider model discovery is non-blocking; measure setup separately.
            init_started = time.perf_counter()
            orch = AIOrchestrator(db)
            logger.info(
                "chat_stream_timing request_id=%s stage=orchestrator_init duration_ms=%.1f provider=%s model=%s",
                current_request_id(),
                (time.perf_counter() - init_started) * 1000,
                orch.provider or "none",
                orch.model or "none",
            )
            loop = asyncio.get_running_loop()
            inference_started = time.perf_counter()
            request_context = copy_context()
            response: ChatResponse = await loop.run_in_executor(
                None,
                request_context.run,
                lambda: orch.answer_via_agents(
                    payload.message,
                    payload.mode,
                    history,
                    cart=payload.cart,
                    model=payload.model,
                ),
            )
            logger.info(
                "chat_stream_timing request_id=%s stage=answer_ready duration_ms=%.1f provider=%s model=%s answer_chars=%d",
                current_request_id(),
                (time.perf_counter() - inference_started) * 1000,
                orch.provider or "none",
                orch.model or "none",
                len(response.answer or ""),
            )

            # 3. Resolve products immediately
            product_resolution_started = time.perf_counter()
            if response.product_ids and not response.products:
                prod_entities = CatalogService(db).get_many(response.product_ids)
                response.products = [_product_read(p) for p in prod_entities]
            logger.info(
                "chat_stream_timing request_id=%s stage=product_resolution duration_ms=%.1f product_count=%d",
                current_request_id(),
                (time.perf_counter() - product_resolution_started) * 1000,
                len(response.products or []),
            )

            tokens_consumed = max(50, (len(payload.message) + len(response.answer)) // 4 + 50)
            try:
                quota_engine.complete_reservation(user.id, quota_reservation_id, tokens_consumed)
                quota_reservation_id = None
            except Exception as quota_err:
                logger.warning("Unable to finalize streamed token accounting: %s", type(quota_err).__name__)

            try:
                db.add(ChatHistory(user_id=user.id, message=payload.message, response=response.model_dump()))
                db.commit()
            except Exception as e:
                db.rollback()
                logger.warning(
                    "chat_history_persistence request_id=%s outcome=failed error_type=%s",
                    current_request_id(),
                    type(e).__name__,
                )

            if payload.conversation_id:
                try:
                    ConversationService.add_message(
                        db=db,
                        conversation_id=payload.conversation_id,
                        role="user",
                        content=payload.message,
                    )
                    ConversationService.add_message(
                        db=db,
                        conversation_id=payload.conversation_id,
                        role="assistant",
                        content=response.answer,
                    )
                    if context_plan and context_plan.get("needs_summarization"):
                        SummarizationService.execute_summarization(db=db, conversation_id=payload.conversation_id)
                except Exception as e:
                    logger.warning(
                        "conversation_persistence request_id=%s outcome=failed error_type=%s",
                        current_request_id(),
                        type(e).__name__,
                    )

            # Store the final result before emitting chunks so a retry can replay it.
            _complete_chat_idempotency(db, user.id, payload, response)
            idempotency_completed = True


            # 4. The provider returns a complete answer today; do not add artificial chunk waits.
            token_delivery_started = time.perf_counter()
            full_text = response.answer or ""
            words = full_text.split(" ")
            chunk_size = 4
            for i in range(0, len(words), chunk_size):
                chunk = " ".join(words[i:i + chunk_size])
                if i + chunk_size < len(words):
                    chunk += " "
                yield f"data: {json.dumps({'type': 'token', 'token': chunk, 'chunk': chunk})}\n\n"
            logger.info(
                "chat_stream_timing request_id=%s stage=token_delivery duration_ms=%.1f word_count=%d total_ms=%.1f",
                current_request_id(),
                (time.perf_counter() - token_delivery_started) * 1000,
                len(words),
                (time.perf_counter() - stream_started) * 1000,
            )

            # 5. Send resolved products event
            if response.products:
                prods_json = [p.model_dump() for p in response.products]
                yield f"data: {json.dumps({'type': 'products', 'products': prods_json, 'product_ids': response.product_ids})}\n\n"

            # Deliver current retailer listings separately so the UI can render product cards.
            if response.live_deals:
                deals_json = [deal.model_dump() for deal in response.live_deals]
                yield f"data: {json.dumps({'type': 'live_deals', 'live_deals': deals_json})}\n\n"

            # 6. Send final completion event
            resp_dict = response.model_dump()
            resp_dict["products"] = [p.model_dump() for p in response.products]
            yield f"data: {json.dumps({'type': 'done', 'response': resp_dict})}\n\n"
            yield "data: [DONE]\n\n"


        except Exception as exc:
            if quota_reservation_id:
                try:
                    quota_engine.release_reservation(user.id, quota_reservation_id)
                    quota_reservation_id = None
                except Exception as quota_err:
                    logger.warning("Unable to release streamed token reservation: %s", type(quota_err).__name__)
            if not idempotency_completed:
                _release_chat_idempotency(db, user.id, payload.idempotency_key)
            logger.warning(
                "chat_stream_failed request_id=%s error_type=%s",
                current_request_id(),
                type(exc).__name__,
            )
            yield f"data: {json.dumps({'type': 'error', 'error': 'The chat request could not be completed.'})}\n\n"
            yield "data: [DONE]\n\n"
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        }
    )


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
    # Read at most one byte beyond the limit; never load an arbitrarily large upload into RAM.
    max_image_bytes = 8 * 1024 * 1024
    image_bytes = await file.read(max_image_bytes + 1)
    await file.close()
    if len(image_bytes) > max_image_bytes:
        raise HTTPException(status_code=413, detail="Image upload must be 8 MB or smaller.")
    if not image_bytes:
        return ChatResponse(answer="Empty image uploaded. Please upload a valid product photo.")

    try:
        from app.services.agents.photo_deal_agent import resolve_photo_mismatch_and_find_deals
        resp = resolve_photo_mismatch_and_find_deals(image_bytes, db)
        if resp.product_ids and not resp.products:
            prod_entities = CatalogService(db).get_many(resp.product_ids)
            resp.products = [_product_read(p) for p in prod_entities]
        return resp
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
    except IntegrityError:
        # A concurrent identical add may win the unique constraint race. Treat it as
        # success only when the row now exists; don't mask unrelated FK/DB failures.
        db.rollback()
        existing = db.scalar(
            select(Wishlist).where(
                Wishlist.user_id == user.id,
                Wishlist.product_id == payload.product_id,
            )
        )
        if existing is not None:
            return wishlist(db, user)
        raise HTTPException(status_code=400, detail="Unable to add this product to the wishlist.")
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


@router.get("/admin/ops/metrics")
def admin_ops_metrics(_: User = Depends(require_admin)) -> dict[str, object]:
    """Return bounded process-local operational metrics without prompts or credentials."""
    from app.core.observability import request_metrics
    from app.core.resilience import provider_breaker_stats
    from app.services.live_search import live_search_cache_stats, serpapi_breaker_stats

    return {
        "http": request_metrics.snapshot(),
        "live_search_cache": live_search_cache_stats(),
        "circuit_breakers": {
            "serpapi": serpapi_breaker_stats(),
            "ai_providers": provider_breaker_stats(),
        },
    }


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



def _require_parbad_internal_key(request: Request, settings: object) -> None:
    """Authenticate only the private ShopSense-to-Parbad service callbacks."""
    expected = str(getattr(settings, "parbad_internal_key", "") or "")
    supplied = request.headers.get("X-ShopSense-Internal-Key", "")
    if len(expected) < 32 or not hmac.compare_digest(expected, supplied):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid internal payment service credentials.")


def _parbad_sandbox_is_available(settings: object) -> bool:
    mode = str(getattr(settings, "parbad_mode", "disabled") or "disabled").lower()
    public_url = str(getattr(settings, "parbad_public_base_url", "") or "").strip()
    key = str(getattr(settings, "parbad_internal_key", "") or "")
    in_production = str(getattr(settings, "environment", "development") or "").lower() == "production"
    production_opt_in = bool(getattr(settings, "parbad_allow_virtual_in_production", False))
    return mode == "virtual" and bool(public_url) and len(key) >= 32 and (not in_production or production_opt_in)


@router.post("/payments/checkout", status_code=status.HTTP_201_CREATED)
@limiter.limit("5/minute")
def create_payment_checkout(
    request: Request,
    payload: PaymentCheckoutRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict[str, object]:
    """Create an INR order from catalog prices and return a Parbad sandbox URL."""
    settings = get_settings()
    if not _parbad_sandbox_is_available(settings):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Parbad Virtual Gateway is not enabled for this deployment. No order or payment was created.",
        )

    quantities: dict[int, int] = {}
    for item in payload.items:
        quantities[item.product_id] = quantities.get(item.product_id, 0) + item.quantity
        if quantities[item.product_id] > 20:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Maximum quantity per product is 20.")

    product_rows = list(db.scalars(select(Product).where(Product.id.in_(list(quantities)))).all())
    products = {product.id: product for product in product_rows}
    missing_ids = sorted(set(quantities) - set(products))
    if missing_ids:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="One or more cart products are no longer available.")

    item_snapshot: list[dict[str, object]] = []
    total = Decimal("0.00")
    for product_id, quantity in quantities.items():
        product = products[product_id]
        if str(product.currency or "INR").strip().upper() not in {"INR", "RS", "RS.", "₹"}:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Parbad sandbox checkout currently supports INR-priced ShopSense items only.")
        if quantity > max(0, int(product.stock or 0)):
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"Insufficient stock for {product.name}. Refresh the product before checking out.")
        try:
            unit_price = Decimal(str(product.price))
        except (InvalidOperation, TypeError, ValueError):
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="A cart item has an invalid catalog price.")
        if not unit_price.is_finite() or unit_price < 0:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="A cart item has an invalid catalog price.")
        subtotal = (unit_price * quantity).quantize(Decimal("0.01"))
        total += subtotal
        item_snapshot.append({
            "product_id": product.id,
            "name": product.name,
            "brand": product.brand,
            "unit_price": float(unit_price),
            "quantity": quantity,
            "subtotal": float(subtotal),
        })

    total = total.quantize(Decimal("0.01"))
    if total <= 0:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Checkout total must be greater than zero.")

    try:
        order = Order(user_id=user.id, total=float(total), status="pending_payment")
        db.add(order)
        db.flush()
        attempt = PaymentAttempt(
            order_id=order.id,
            user_id=user.id,
            amount=float(total),
            currency="INR",
            provider="parbad-virtual",
            status="pending",
            items=item_snapshot,
        )
        db.add(attempt)
        db.commit()
        db.refresh(order)
        db.refresh(attempt)
    except Exception as exc:
        db.rollback()
        logger.error("payment_checkout request_id=%s outcome=failed error_type=%s", current_request_id(), type(exc).__name__)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Could not create the checkout. Please try again.") from exc

    public_base = str(settings.parbad_public_base_url).rstrip("/")
    return {
        "order_id": order.id,
        "attempt_id": attempt.id,
        "amount": attempt.amount,
        "currency": attempt.currency,
        "order_status": order.status,
        "payment_mode": "sandbox",
        "payment_url": f"{public_base}/api/payments/start?attempt_id={attempt.id}",
        "notice": "Parbad Virtual Gateway only simulates a payment. No real money is charged.",
    }


@router.get("/payments/orders/{order_id}")
def get_payment_order(
    order_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict[str, object]:
    """Return payment state only to the authenticated order owner."""
    order = db.scalar(select(Order).where(Order.id == order_id, Order.user_id == user.id))
    if order is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found.")
    attempt = db.scalar(
        select(PaymentAttempt).where(
            PaymentAttempt.order_id == order.id,
            PaymentAttempt.user_id == user.id,
        ).order_by(PaymentAttempt.id.desc())
    )
    return {
        "id": order.id,
        "status": order.status,
        "total": order.total,
        "currency": attempt.currency if attempt else "INR",
        "payment_status": attempt.status if attempt else "not_started",
        "provider": attempt.provider if attempt else None,
    }


@router.get("/payments/parbad/authorize/{attempt_id}")
def authorize_parbad_payment_attempt(
    attempt_id: int,
    request: Request,
    db: Session = Depends(get_db),
) -> dict[str, object]:
    """Internal endpoint used by the .NET service to retrieve a server-priced attempt once."""
    settings = get_settings()
    _require_parbad_internal_key(request, settings)
    attempt = db.get(PaymentAttempt, attempt_id)
    if attempt is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Payment attempt not found.")
    if attempt.status != "pending":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Payment attempt is no longer available.")
    if attempt.currency != "INR" or attempt.amount <= 0:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Payment attempt has unsupported amount or currency.")
    order = db.get(Order, attempt.order_id)
    if order is None or order.user_id != attempt.user_id or order.status != "pending_payment":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Order is not payable.")
    attempt.status = "initiating"
    attempt.updated_at = datetime.utcnow()
    db.commit()
    return {
        "attempt_id": attempt.id,
        "tracking_number": attempt.id,
        "order_id": order.id,
        "amount": attempt.amount,
        "currency": attempt.currency,
    }


@router.post("/payments/parbad/events")
def receive_parbad_payment_event(
    payload: ParbadPaymentEvent,
    request: Request,
    db: Session = Depends(get_db),
) -> dict[str, object]:
    """Accept only authenticated server-to-server events after the Parbad service verifies the callback."""
    settings = get_settings()
    _require_parbad_internal_key(request, settings)
    attempt = db.get(PaymentAttempt, payload.attempt_id)
    if attempt is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Payment attempt not found.")
    order = db.get(Order, attempt.order_id)
    if order is None or order.user_id != attempt.user_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Payment order not found.")

    if attempt.status == "paid" or order.status == "paid":
        return {"ok": True, "order_id": order.id, "status": "paid"}

    if payload.status == "initiated":
        if attempt.status == "initiated":
            return {"ok": True, "order_id": order.id, "status": "initiated"}
        if attempt.status != "initiating":
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Payment attempt cannot be initiated in its current state.")
        attempt.status = "initiated"
    elif payload.status == "paid":
        if attempt.status != "initiated":
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Only an initiated payment can be marked paid.")
        attempt.status = "paid"
        attempt.transaction_code = payload.transaction_code
        attempt.verified_at = datetime.utcnow()
        order.status = "paid"
    else:
        if attempt.status not in {"pending", "initiating", "initiated"}:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Payment attempt cannot be changed in its current state.")
        attempt.status = payload.status
        order.status = "payment_cancelled" if payload.status == "cancelled" else "payment_failed"

    attempt.updated_at = datetime.utcnow()
    db.commit()
    return {"ok": True, "order_id": order.id, "status": attempt.status}


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
    Live quota dashboard: returns persisted monthly usage plus active reservations,
    rate-limit settings, and remaining allowances for the authenticated user.
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



