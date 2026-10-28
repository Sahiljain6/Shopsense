import re
from enum import Enum
from typing import Literal
from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


class ModelPersona(str, Enum):
    SONNET_4_5 = "Sonnet 4.5"
    GEMINI_FLASH = "Gemini Flash"
    DEAL_SPECIALIST = "Deal Specialist"


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    refresh_token: str | None = None
    csrf_token: str | None = None


class RefreshTokenRequest(BaseModel):
    refresh_token: str | None = None


class UserCreate(BaseModel):
    email: EmailStr = Field(description="Valid email address")
    password: str = Field(
        min_length=8,
        description="Password must be at least 8 characters long",
    )
    full_name: str = Field(default="", description="Optional display name")

    @field_validator("password")
    @classmethod
    def password_not_blank(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("Password cannot be blank.")
        return v

    @field_validator("email")
    @classmethod
    def email_lowercase(cls, v: str) -> str:
        return v.strip().lower()


class UserLogin(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, description="Account password")

    @field_validator("email")
    @classmethod
    def email_lowercase(cls, v: str) -> str:
        return v.strip().lower()


class GoogleAuthRequest(BaseModel):
    credential: str | None = None
    access_token: str | None = None


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    email: EmailStr
    full_name: str = ""
    is_admin: bool
    tier: str = "free"
    org_id: str | None = None
    feature_flags: list[str] = []
    google_id: str | None = None


class ProductBase(BaseModel):
    name: str
    brand: str
    description: str
    price: float
    currency: str = "INR"
    rating: float = 0
    stock: int = 0
    image_url: str = ""
    attributes: dict[str, object] = Field(default_factory=dict)
    category_id: int


class ProductCreate(ProductBase):
    pass


class ProductRead(ProductBase):
    model_config = ConfigDict(from_attributes=True)
    id: int
    category_name: str | None = None


class ChatTurn(BaseModel):
    role: str = Field(max_length=16)
    content: str = Field(max_length=4000)


CHAT_MESSAGE_MAX_LENGTH = 4000


class ChatRequest(BaseModel):
    message: str = Field(max_length=CHAT_MESSAGE_MAX_LENGTH, description="Shopping prompt, up to 4,000 characters")
    mode: str | None = None
    history: list[ChatTurn] = Field(default_factory=list, max_length=20)
    cart: list[dict[str, object]] = Field(default_factory=list, max_length=50)
    model: str | None = "Sonnet 4.5"
    conversation_id: str | None = None
    idempotency_key: str | None = Field(
        default=None,
        min_length=8,
        max_length=128,
        description="Optional key reused only for retries of the same chat submission",
    )

    @field_validator("idempotency_key")
    @classmethod
    def validate_idempotency_key(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        if not re.fullmatch(r"[A-Za-z0-9._:-]{8,128}", value):
            raise ValueError("idempotency_key must be 8-128 characters using letters, digits, '.', '_', ':', or '-'.")
        return value


class LiveDeal(BaseModel):
    """A current retailer listing returned by a shopping-search provider."""

    title: str
    price: float | None = None
    old_price: float | None = None
    currency: str = "INR"
    source: str = "Google Shopping"
    url: str
    image_url: str | None = None
    rating: float | None = None
    reviews: int | None = None
    discount_percentage: float | None = None
    snippet: str = ""
    retrieved_at: str | None = None
    provider: str = "SerpApi Google Shopping"
    is_live: bool = True
    trust_score: int | None = None
    badge: str | None = None
    is_verified: bool = False
    warning: str | None = None


class ChatResponse(BaseModel):
    answer: str
    product_ids: list[int] = Field(default_factory=list)
    products: list[ProductRead] = Field(default_factory=list)
    live_deals: list[LiveDeal] = Field(default_factory=list)
    reasons: dict[str, str] = Field(default_factory=dict)
    pros: dict[str, list[str]] = Field(default_factory=dict)
    cons: dict[str, list[str]] = Field(default_factory=dict)
    clarification: str | None = None
    model: str | None = None


class CompareRequest(BaseModel):
    product_ids: list[int] = Field(min_length=2, max_length=4)


class ReviewSummaryRequest(BaseModel):
    product_id: int


class ReviewRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    product_id: int
    user_name: str
    rating: float
    title: str
    body: str


class WishlistRequest(BaseModel):
    product_id: int


class PaymentCheckoutItem(BaseModel):
    product_id: int = Field(ge=1)
    quantity: int = Field(default=1, ge=1, le=20)


class PaymentCheckoutRequest(BaseModel):
    items: list[PaymentCheckoutItem] = Field(min_length=1, max_length=30)


class ParbadPaymentEvent(BaseModel):
    attempt_id: int = Field(ge=1)
    status: Literal["initiated", "paid", "failed", "cancelled"]
    transaction_code: str | None = Field(default=None, max_length=200)


class FetchLinkRequest(BaseModel):
    url: str


class FetchLinkResponse(BaseModel):
    product: ProductRead
    created: bool


class PriceHistoryEntry(BaseModel):
    price: float
    currency: str
    captured_at: str


class PriceHistoryResponse(BaseModel):
    product_id: int
    source_url: str | None = None
    history: list[PriceHistoryEntry]
