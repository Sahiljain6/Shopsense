from enum import Enum
from pydantic import BaseModel, ConfigDict, EmailStr, Field


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
    email: EmailStr
    password: str = Field(min_length=8)
    full_name: str = ""


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class GoogleAuthRequest(BaseModel):
    credential: str


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    email: EmailStr
    full_name: str
    is_admin: bool


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
    role: str
    content: str


class ChatRequest(BaseModel):
    message: str
    mode: str | None = None
    history: list[ChatTurn] = Field(default_factory=list)
    cart: list[dict[str, object]] = Field(default_factory=list)
    model: str | None = "Sonnet 4.5"


class ChatResponse(BaseModel):
    answer: str
    product_ids: list[int] = Field(default_factory=list)
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
