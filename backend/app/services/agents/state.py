from typing import Any, TypedDict
from sqlalchemy.orm import Session
from app.schemas.api import ChatResponse


class ShopSenseState(TypedDict, total=False):
    message: str
    mode: str | None
    db: Session
    intent: str
    product_ids: list[int]
    response: ChatResponse
    error: str
    catalog: list[dict[str, Any]]
