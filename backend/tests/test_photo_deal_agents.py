import io
import pytest
from fastapi.testclient import TestClient

from app.main import app, auto_seed_catalog
from app.models.entities import Product
from app.services.agents.graph import run_graph
from app.services.agents.photo_deal_agent import (
    DealOfferSpecialistAgent,
    VisualInspectorAgent,
    resolve_photo_mismatch_and_find_deals,
)


@pytest.fixture(autouse=True)
def seed_db(db_session):
    auto_seed_catalog(db_session)


def test_visual_inspector_detects_mismatch(monkeypatch, db_session) -> None:
    # Mock identify_image to return vague / mismatched gadget tags
    monkeypatch.setattr(
        "app.services.agents.photo_deal_agent.identify_image",
        lambda _bytes, _key: ["gadget", "screen", "portable device"]
    )

    agent_1 = VisualInspectorAgent()
    findings = agent_1.inspect(b"fake_image_bytes", db_session)

    assert "labels" in findings
    assert findings["is_mismatch"] is True
    assert "Agent 1 (Visual Inspector) ➡️ Agent 2" in findings["handoff_prompt"]
    assert findings["detected_category"] in ["Phones", "Peripherals", "General"]


def test_deal_specialist_resolves_optimal_option_and_offers(db_session) -> None:
    agent_2 = DealOfferSpecialistAgent(db_session)

    # Simulated visual data from Agent 1 indicating a phone
    visual_data = {
        "labels": ["smartphone", "mobile phone", "camera"],
        "detected_category": "Phones",
        "is_mismatch": True,
        "mismatch_reason": "Exact photo model not found in catalog.",
        "direct_matches": []
    }

    result = agent_2.resolve_and_scout(visual_data)
    assert len(result["candidate_products"]) > 0
    assert result["optimal_product"] is not None

    optimal = result["optimal_product"]
    # Should resolve to a Phone
    assert optimal.category.name == "Phones" or "phone" in optimal.name.lower() or "oneplus" in optimal.name.lower() or "iphone" in optimal.name.lower()

    # Verify ongoing offers attached
    offers = result["offers"]
    assert "emi" in offers
    assert "best_monthly" in offers
    assert "timing_verdict" in offers
    assert len(offers["bank_discounts"]) > 0


def test_resolve_photo_mismatch_collaborative_pipeline(monkeypatch, db_session) -> None:
    monkeypatch.setattr(
        "app.services.agents.photo_deal_agent.identify_image",
        lambda _bytes, _key: ["headphones", "audio", "earphones"]
    )

    response = resolve_photo_mismatch_and_find_deals(b"fake_audio_bytes", db_session)
    assert response is not None
    assert "Multi-Agent Visual Shopping & Deal Finder" in response.answer
    assert "Agent 1 (Visual Inspector)" in response.answer
    assert "Agent 2 (Deal & Offer Specialist)" in response.answer
    assert "⭐ Optimal Option" in response.answer
    assert "No-Cost EMI" in response.answer
    assert len(response.product_ids) > 0


def test_multi_agent_graph_photo_deal_routing(monkeypatch, db_session) -> None:
    monkeypatch.setattr(
        "app.services.agents.photo_deal_agent.identify_image",
        lambda _bytes, _key: ["laptop", "computer", "notebook"]
    )

    state = {
        "message": "check this photo mismatch and find me the deal",
        "image_bytes": b"mock_laptop_bytes",
        "db": db_session,
    }

    output = run_graph(state)
    assert output.get("response") is not None
    assert "Multi-Agent Visual Shopping & Deal Finder" in output["response"].answer
    assert output["response"].product_ids


def test_api_identify_image_endpoint(client: TestClient, db_session, monkeypatch) -> None:
    auto_seed_catalog(db_session)
    monkeypatch.setattr(
        "app.services.agents.photo_deal_agent.identify_image",
        lambda _bytes, _key: ["mobile", "smartphone"]
    )

    # Upload mock image file
    file_content = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01"
    response = client.post(
        "/identify-image",
        files={"file": ("test.png", io.BytesIO(file_content), "image/png")}
    )

    assert response.status_code == 200
    data = response.json()
    assert "Multi-Agent Visual Shopping & Deal Finder" in data["answer"]
    assert "Agent 1 (Visual Inspector)" in data["answer"]
    assert "Agent 2 (Deal & Offer Specialist)" in data["answer"]
    assert len(data["product_ids"]) > 0
