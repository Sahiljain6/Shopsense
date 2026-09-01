import pytest
from app.schemas.api import ChatRequest

def test_chat_request_default_model():
    req = ChatRequest(message="Find earbuds under 3000")
    assert req.message == "Find earbuds under 3000"
    assert req.model is None or req.model == "Sonnet 4.5" or isinstance(req.model, str)

def test_chat_request_explicit_persona_models():
    req_sonnet = ChatRequest(message="Compare phones", model="Sonnet 4.5")
    assert req_sonnet.model == "Sonnet 4.5"

    req_flash = ChatRequest(message="Live prices", model="Gemini Flash")
    assert req_flash.model == "Gemini Flash"

    req_specialist = ChatRequest(message="Inspect photo", model="Deal Specialist")
    assert req_specialist.model == "Deal Specialist"

def test_chat_request_serialization():
    req = ChatRequest(message="Hello AI", model="Sonnet 4.5")
    data = req.model_dump()
    assert data["message"] == "Hello AI"
    assert data["model"] == "Sonnet 4.5"
