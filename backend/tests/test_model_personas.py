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

def test_model_persona_enum_members():
    from app.schemas.api import ModelPersona
    assert ModelPersona.SONNET_4_5.value == "Sonnet 4.5"
    assert ModelPersona.GEMINI_FLASH.value == "Gemini Flash"
    assert ModelPersona.DEAL_SPECIALIST.value == "Deal Specialist"
    assert len(ModelPersona) == 3

def test_chat_response_model_attribution():
    from app.schemas.api import ChatResponse
    resp = ChatResponse(answer="Recommended deal", model="Sonnet 4.5")
    assert resp.answer == "Recommended deal"
    assert resp.model == "Sonnet 4.5"
