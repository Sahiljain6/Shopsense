import pytest
from pydantic import ValidationError

from app.schemas.api import CHAT_MESSAGE_MAX_LENGTH, ChatRequest


def test_chat_request_accepts_message_at_character_limit():
    request = ChatRequest(message="x" * CHAT_MESSAGE_MAX_LENGTH)
    assert len(request.message) == CHAT_MESSAGE_MAX_LENGTH


def test_chat_request_rejects_message_over_character_limit():
    with pytest.raises(ValidationError):
        ChatRequest(message="x" * (CHAT_MESSAGE_MAX_LENGTH + 1))


def test_chat_request_preserves_other_fields_with_valid_message():
    request = ChatRequest(
        message="Compare phones under ₹40,000",
        mode="compare",
        history=[{"role": "user", "content": "I prefer Samsung"}],
        cart=[{"id": 1, "name": "Galaxy"}],
        model="Sonnet 4.5",
    )
    assert request.mode == "compare"
    assert request.history[0].content == "I prefer Samsung"
    assert request.cart[0]["name"] == "Galaxy"
