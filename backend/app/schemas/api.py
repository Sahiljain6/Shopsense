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
class ProductOut(BaseModel):
    id: int; name: str; brand: str; price: float; currency: str; rating: float; stock: int; image_url: str; description: str
    model_config = {"from_attributes": True}
class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=2000)
class ChatResponse(BaseModel):
    answer: str; products: list[ProductOut] = []; clarification: str | None = None
class CompareRequest(BaseModel):
    product_ids: list[int] = Field(min_length=2, max_length=4)
class ReviewsRequest(BaseModel):
    product_id: int
class WishlistRequest(BaseModel):
    product_id: int
