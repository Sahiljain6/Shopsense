from datetime import datetime
from pydantic import BaseModel, EmailStr, Field


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)
    full_name: str


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserOut(BaseModel):
    id: int
    email: EmailStr
    full_name: str
    is_admin: bool
    created_at: datetime
    model_config = {"from_attributes": True}


class ProductBase(BaseModel):
    category_id: int = 1
    name: str
    brand: str
    description: str
    price: float
    currency: str = "USD"
    rating: float = 0
    stock: int = 0
    image_url: str
    attributes: dict = {}


class ProductOut(ProductBase):
    id: int
    model_config = {"from_attributes": True}


class ProductWrite(ProductBase):
    pass


class ReviewOut(BaseModel):
    id: int
    product_id: int
    user_id: int | None = None
    rating: float
    title: str
    body: str
    sentiment: str
    model_config = {"from_attributes": True}


class ReviewWrite(BaseModel):
    product_id: int
    rating: float
    title: str
    body: str
    sentiment: str = "neutral"


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=2000)


class ChatResponse(BaseModel):
    answer: str
    products: list[ProductOut] = []
    clarification: str | None = None


class CompareRequest(BaseModel):
    product_ids: list[int] = Field(min_length=2, max_length=4)


class ReviewsRequest(BaseModel):
    product_id: int


class WishlistRequest(BaseModel):
    product_id: int


class OrderOut(BaseModel):
    id: int
    user_id: int
    status: str
    total: float
    model_config = {"from_attributes": True}
