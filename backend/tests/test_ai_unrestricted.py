from app.models.entities import Category, Product
from app.services.ai import AIOrchestrator, needs_clarification, parse_budget


def test_needs_clarification_does_not_gate_common_prompts() -> None:
    assert needs_clarification("mobile under 15000") is None
    assert needs_clarification("hello") is None
    assert needs_clarification("recommend something good") is None
    assert needs_clarification("I need a gift") is None


def test_parse_budget_common_indian_formats() -> None:
    assert parse_budget("under 1 lakh") == 100000
    assert parse_budget("under 1.5 lakh") == 150000
    assert parse_budget("under 15k") == 15000
    assert parse_budget("below Rs 15000") == 15000


def test_general_prompts_return_useful_answers_without_clarification(db_session) -> None:
    category = Category(name="Phones")
    db_session.add(category)
    db_session.flush()
    product = Product(name="Xiaomi Phone Sense", brand="Xiaomi", description="budget phone for students", price=12999, rating=4.5, stock=10, category_id=category.id, attributes={"ram": "6GB"})
    db_session.add(product)
    db_session.commit()

    for prompt in ["hello", "recommend something good", "I need a gift for my brother", "what can I buy with 20000?"]:
        response = AIOrchestrator(db_session).answer(prompt)
        assert response is not None, f"Response was None for prompt '{prompt}'"
        assert response.clarification is None
        assert "Which product category should I search in?" not in response.answer
        assert response.answer


def test_gemini_provider_preserves_conversation_history(monkeypatch, db_session) -> None:
    """Regression test: verify Gemini REST payload builds multi-turn contents array containing all history turns."""
    from app.services.ai import _build_gemini_contents, AIOrchestrator

    history = [
        {"role": "user", "content": "phone under 15000"},
        {"role": "assistant", "content": "I recommend Motorola Moto G34 5G."}
    ]
    user_msg = "tell me some offer going on this"

    contents = _build_gemini_contents(user_msg, history)
    assert len(contents) == 3
    assert contents[0] == {"role": "user", "parts": [{"text": "phone under 15000"}]}
    assert contents[1] == {"role": "model", "parts": [{"text": "I recommend Motorola Moto G34 5G."}]}
    assert contents[2] == {"role": "user", "parts": [{"text": "tell me some offer going on this"}]}

    # Mock HTTP request to Gemini API and assert payload
    captured_payloads = []

    class MockResponse:
        status_code = 200
        text = "{}"
        def json(self):
            return {"candidates": [{"content": {"parts": [{"text": "Offers response"}]}}]}

    class MockClient:
        def __init__(self, timeout=15):
            pass
        def __enter__(self):
            return self
        def __exit__(self, *args):
            pass
        def post(self, url, json=None, **kwargs):
            captured_payloads.append(json)
            return MockResponse()

    monkeypatch.setattr("httpx.Client", MockClient)

    orchestrator = AIOrchestrator(db_session)
    orchestrator.provider = "gemini"
    orchestrator.gemini_api_key = "test_key"

    ans = orchestrator._chat("system prompt", user_msg, history=history)
    assert ans == "Offers response"
    assert len(captured_payloads) == 1
    assert captured_payloads[0]["contents"] == contents


def test_offer_followup_resolves_last_product(db_session) -> None:
    """Regression test: asking 'tell me some offer going on this' resolves against the last discussed phone."""
    from app.main import auto_seed_catalog
    auto_seed_catalog(db_session)

    history = [{"role": "assistant", "content": "I recommend the Motorola Moto G34 5G (₹11,999)."}]

    orchestrator = AIOrchestrator(db_session)
    response = orchestrator.answer("tell me some offer going on this", history=history)

    assert response is not None
    assert "Motorola Moto G34" in response.answer or "Bank Discount" in response.answer or "Offers" in response.answer
    assert response.product_ids


def test_unmatched_query_with_failed_llm_returns_honest_clarification(monkeypatch, db_session) -> None:
    """Regression test for random catalog product dump:
    When query is 'fetch me some offer on flipkart' and _chat() returns None (LLM provider failed),
    the system must NOT return top-rated random catalog products (MacBook Air / Sony earbuds / Keychron).
    Instead, it must ask an honest clarifying question.
    """
    from app.main import auto_seed_catalog
    auto_seed_catalog(db_session)

    orchestrator = AIOrchestrator(db_session)
    monkeypatch.setattr(orchestrator, "_chat", lambda *args, **kwargs: None)

    response = orchestrator.answer("fetch me some offer on flipkart")

    assert response is not None
    # Must NOT return random product_ids
    assert not response.product_ids or len(response.product_ids) == 0, f"Expected zero product_ids, got {response.product_ids}"
    assert "Flipkart" in response.answer or "category" in response.answer
    assert "Here are top verified options" not in response.answer


def test_seed_version_upsert(db_session) -> None:
    """Regression test: seed versioning upserts products by SKU and updates on version bump."""
    from app.main import auto_seed_catalog, SEED_VERSION, SEED_DATA
    from app.models.entities import SeedVersion

    # First seed — fresh database
    auto_seed_catalog(db_session)

    product_count = db_session.query(Product).count()
    assert product_count == len(SEED_DATA), f"Expected {len(SEED_DATA)} products, got {product_count}"

    stored = db_session.query(SeedVersion).first()
    assert stored is not None
    assert stored.version == SEED_VERSION

    # Calling again should be a no-op (version already current)
    auto_seed_catalog(db_session)
    assert db_session.query(Product).count() == len(SEED_DATA), "Duplicate products inserted on re-seed"

    # Simulate a version bump: reset version, change a price in seed_data
    stored.version = 0
    db_session.commit()

    original_moto = db_session.query(Product).filter(Product.sku == "moto-g34-5g").first()
    assert original_moto is not None
    original_price = original_moto.price

    # Force a re-seed (version was reset)
    auto_seed_catalog(db_session)

    # Product count should NOT increase (upsert, not duplicate insert)
    assert db_session.query(Product).count() == len(SEED_DATA), "Duplicate products inserted after version bump re-seed"

    # Version should be updated
    stored = db_session.query(SeedVersion).first()
    assert stored.version == SEED_VERSION

    # SKU-based product should still exist
    moto = db_session.query(Product).filter(Product.sku == "moto-g34-5g").first()
    assert moto is not None
    assert moto.name == "Motorola Moto G34 5G (8GB RAM, 128GB)"


def test_tool_calling_search_catalog(monkeypatch, db_session) -> None:
    """Test that tool-calling executes search_catalog and attaches product_ids."""
    from app.main import auto_seed_catalog
    auto_seed_catalog(db_session)

    orchestrator = AIOrchestrator(db_session)

    # Mock _chat_with_tools to simulate LLM invoking search_catalog tool
    def mock_chat_with_tools(system, user, history=None):
        orchestrator._execute_tool("search_catalog", {"category": "Phones", "budget": 15000})
        return "I found great phone options under ₹15,000 for you!"

    monkeypatch.setattr(orchestrator, "_chat_with_tools", mock_chat_with_tools)

    response = orchestrator._tool_calling_answer("find me a phone under 15000")
    assert response is not None
    assert "phone" in response.answer.lower()
    assert len(response.product_ids) > 0
    assert all(pid in response.reasons for pid in [str(p) for p in response.product_ids])
