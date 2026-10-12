from app.services.constraint_extractor import ShoppingConstraints, extract_constraints


def test_extracts_category_budget_and_use_case():
    result = extract_constraints("Recommend a gaming laptop under ₹80,000")

    assert result.category == "Laptops"
    assert result.budget_max == 80000
    assert result.budget_currency == "INR"
    assert "gaming" in result.use_cases


def test_extracts_between_budget_range_without_currency_markers():
    result = extract_constraints("Find phones between 10000 and 20000")

    assert result.category == "Phones"
    assert result.budget_min == 10000
    assert result.budget_max == 20000
    assert result.budget_currency == "INR"


def test_extracts_from_to_budget_range_with_shorthand():
    result = extract_constraints("Find earbuds from ₹10k to ₹20k")

    assert result.category == "Audio"
    assert result.budget_min == 10000
    assert result.budget_max == 20000
    assert result.budget_currency == "INR"


def test_extracts_target_budget():
    result = extract_constraints("Suggest a phone around ₹30,000")

    assert result.budget_target == 30000
    assert result.budget_min is None
    assert result.budget_max is None


def test_does_not_convert_usd_to_inr():
    result = extract_constraints("Find headphones with a budget of $500")

    assert result.budget_max == 500
    assert result.budget_currency == "USD"


def test_extracts_shorthand_budget_and_ignores_model_number():
    result = extract_constraints("Compare iPhone 16 and Galaxy S24, under 15k")

    assert result.budget_max == 15000
    assert result.budget_currency == "INR"


def test_does_not_treat_model_numbers_as_budget():
    result = extract_constraints("Compare iPhone 16 and Galaxy S24")

    assert result.budget_min is None
    assert result.budget_max is None
    assert result.budget_target is None


def test_extracts_required_preferred_and_excluded_features():
    result = extract_constraints(
        "Find a laptop with 16GB RAM and SSD, preferably a backlit keyboard, "
        "no RGB lighting"
    )

    assert "16gb ram" in result.required_features
    assert "ssd" in result.required_features
    assert "a backlit keyboard" in result.preferred_features or "backlit keyboard" in result.preferred_features
    assert "rgb lighting" in result.excluded_features


def test_extracts_explicit_must_have_features():
    result = extract_constraints("I need a phone; must have 5G and AMOLED")

    assert "5g" in result.required_features
    assert "amoled" in result.required_features


def test_extracts_preferred_and_excluded_brands():
    result = extract_constraints("I prefer Samsung phones, avoid Xiaomi")

    assert result.preferred_brands == ("Samsung",)
    assert result.excluded_brands == ("Xiaomi",)
    assert result.preferred_features == ()
    assert result.excluded_features == ()


def test_extracts_required_features_label():
    result = extract_constraints("Required features: 5G, NFC and AMOLED")

    assert result.required_features == ("5g", "nfc", "amoled")


def test_extracts_delivery_postal_code():
    result = extract_constraints("Can you find a phone deliverable to PIN code 400001?")

    assert result.delivery_postal_code == "400001"


def test_extracts_delivery_location():
    result = extract_constraints("Find earbuds available in Mumbai")

    assert result.delivery_location == "Mumbai"


def test_empty_or_missing_message_returns_empty_constraints():
    assert extract_constraints(None) == ShoppingConstraints()
    assert extract_constraints("   ") == ShoppingConstraints()


def test_to_dict_converts_tuples_to_json_friendly_lists():
    result = extract_constraints("Recommend gaming headphones with ANC")
    value = result.to_dict()

    assert value["category"] == "Audio"
    assert value["use_cases"] == ["gaming"]
    assert isinstance(value["required_features"], list)


def test_handles_indian_comma_grouping_and_lakh_decimal():
    indian_grouping = extract_constraints("Find a laptop under ₹1,50,000")
    lakh_decimal = extract_constraints("Find a laptop with a budget of 1.5 lakh")

    assert indian_grouping.budget_max == 150000
    assert lakh_decimal.budget_max == 150000
    assert indian_grouping.budget_currency == "INR"
    assert lakh_decimal.budget_currency == "INR"
