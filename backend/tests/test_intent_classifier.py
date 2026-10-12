import pytest

from app.services.intent_classifier import ShoppingIntent, classify_intent


@pytest.mark.parametrize(
    ("message", "expected"),
    [
        ("Recommend a laptop for programming", ShoppingIntent.PRODUCT_RECOMMENDATION),
        ("Which phone should I buy under ₹30,000?", ShoppingIntent.PRODUCT_RECOMMENDATION),
        ("Find me headphones for travelling", ShoppingIntent.PRODUCT_RECOMMENDATION),
        ("Suggest a monitor for working from home", ShoppingIntent.PRODUCT_RECOMMENDATION),
        ("Compare iPhone 15 and OnePlus 12", ShoppingIntent.PRODUCT_COMPARISON),
        ("Which is better for gaming, laptop A or laptop B?", ShoppingIntent.PRODUCT_COMPARISON),
        ("Explain the difference between OLED and LCD", ShoppingIntent.PRODUCT_COMPARISON),
        ("Compare paying upfront versus using EMI", ShoppingIntent.FINANCE_OR_EMI),
        ("Find current discounts on wireless headphones", ShoppingIntent.DEAL_SEARCH),
        ("Show me the best available offers on laptops", ShoppingIntent.DEAL_SEARCH),
        ("Is this product currently on sale?", ShoppingIntent.DEAL_SEARCH),
        ("Give me a coupon code for headphones", ShoppingIntent.DEAL_SEARCH),
        ("Summarize the reviews for this phone", ShoppingIntent.PRODUCT_REVIEW_SUMMARY),
        ("What are the most common complaints about this laptop?", ShoppingIntent.PRODUCT_REVIEW_SUMMARY),
        ("Is this laptop worth buying based on these reviews?", ShoppingIntent.PRODUCT_REVIEW_SUMMARY),
        ("Calculate EMI for ₹50,000 over 6 months at 14% annual interest", ShoppingIntent.FINANCE_OR_EMI),
        ("How much interest will I pay on this EMI?", ShoppingIntent.FINANCE_OR_EMI),
        ("Compare the total cost of these payment options", ShoppingIntent.FINANCE_OR_EMI),
        ("Suggest birthday gifts under ₹3,000 for a photographer", ShoppingIntent.GIFT_RECOMMENDATION),
        ("Find a gift for someone who enjoys gaming", ShoppingIntent.GIFT_RECOMMENDATION),
        ("Recommend an anniversary present for my partner", ShoppingIntent.GIFT_RECOMMENDATION),
        ("Can this product be delivered to PIN code 400001?", ShoppingIntent.DELIVERY_OR_LOGISTICS),
        ("When will my order arrive?", ShoppingIntent.DELIVERY_OR_LOGISTICS),
        ("Is express delivery available for this item?", ShoppingIntent.DELIVERY_OR_LOGISTICS),
        ("What are the specifications of this laptop?", ShoppingIntent.PRODUCT_INFORMATION),
        ("Does this phone support wireless charging?", ShoppingIntent.PRODUCT_INFORMATION),
        ("Explain the battery life and processor in this phone", ShoppingIntent.PRODUCT_INFORMATION),
        ("What should I consider before buying a monitor?", ShoppingIntent.GENERAL_SHOPPING_QUERY),
        ("How do I choose a good office chair?", ShoppingIntent.GENERAL_SHOPPING_QUERY),
        ("Explain how to choose between different laptop screen sizes", ShoppingIntent.GENERAL_SHOPPING_QUERY),
        ("Find the best one", ShoppingIntent.CLARIFICATION_REQUIRED),
        ("Compare it with that one", ShoppingIntent.CLARIFICATION_REQUIRED),
        ("What about battery?", ShoppingIntent.CLARIFICATION_REQUIRED),
        ("Calculate the payment", ShoppingIntent.CLARIFICATION_REQUIRED),
        ("Write a program to reverse a linked list", ShoppingIntent.OUT_OF_SCOPE),
        ("Generate Python code for a shopping website", ShoppingIntent.OUT_OF_SCOPE),
        ("Write an essay about climate change", ShoppingIntent.OUT_OF_SCOPE),
        ("Tell me the history of ancient Rome", ShoppingIntent.OUT_OF_SCOPE),
        ("Debug this JavaScript function", ShoppingIntent.OUT_OF_SCOPE),
        ("Find a phone under ₹25,000 and compare the top two options", ShoppingIntent.PRODUCT_RECOMMENDATION),
    ],
)
def test_intent_taxonomy_examples(message: str, expected: ShoppingIntent) -> None:
    result = classify_intent(message)
    assert result.intent is expected


def test_multi_intent_keeps_comparison_as_secondary_for_recommendation() -> None:
    result = classify_intent("Find a phone under ₹25,000 and compare the top two options")
    assert result.intent is ShoppingIntent.PRODUCT_RECOMMENDATION
    assert ShoppingIntent.PRODUCT_COMPARISON in result.secondary_intents


def test_finance_and_comparison_intents_are_preserved() -> None:
    result = classify_intent("Compare the EMI and upfront payment for this laptop")
    assert result.intent is ShoppingIntent.FINANCE_OR_EMI
    assert ShoppingIntent.PRODUCT_COMPARISON in result.secondary_intents


def test_follow_up_uses_available_conversation_context() -> None:
    history = [
        {"role": "user", "content": "Recommend a laptop for programming under ₹60,000"},
        {"role": "assistant", "content": "Here are two laptop recommendations."},
    ]
    result = classify_intent("What about battery life?", history=history)
    assert result.intent in {
        ShoppingIntent.PRODUCT_RECOMMENDATION,
        ShoppingIntent.PRODUCT_INFORMATION,
    }


def test_empty_message_requires_clarification() -> None:
    result = classify_intent("   ")
    assert result.intent is ShoppingIntent.CLARIFICATION_REQUIRED


def test_every_result_uses_a_declared_taxonomy_label() -> None:
    result = classify_intent("Recommend a laptop under ₹60,000")
    assert isinstance(result.intent, ShoppingIntent)
    assert all(isinstance(intent, ShoppingIntent) for intent in result.secondary_intents)
