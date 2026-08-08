from pydantic import BaseModel, ConfigDict, EmailStr, Field


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)
    full_name: str = ""


class UserLogin(BaseModel):
    email: EmailStr
    password: str


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


class ChatRequest(BaseModel):
    message: str
    mode: str | None = None


class ChatResponse(BaseModel):
    answer: str
    product_ids: list[int] = Field(default_factory=list)
    reasons: dict[str, str] = Field(default_factory=dict)
    pros: dict[str, list[str]] = Field(default_factory=dict)
    cons: dict[str, list[str]] = Field(default_factory=dict)
    clarification: str | None = None


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
