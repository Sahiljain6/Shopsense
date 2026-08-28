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
