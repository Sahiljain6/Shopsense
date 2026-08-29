from app.main import auto_seed_catalog
from app.models.entities import Product
from app.services.agents.graph import run_graph


def test_graph_search_phone_under_15000(db_session) -> None:
    """End-to-end LangGraph regression test for 'phone under 15000'.
    Must return only Phones <= 15000 and include seed phones (Moto G34, Realme 12x, Poco M6 Pro, Galaxy M14, CMF Phone 1, Redmi 13C).
    Must NEVER return mechanical keyboards or earbuds.
    """
    auto_seed_catalog(db_session)

    graph_output = run_graph({
        "message": "phone under 15000",
        "mode": None,
        "db": db_session
    })

    response = graph_output.get("response")
    assert response is not None
    assert response.product_ids, "Expected non-empty product_ids for 'phone under 15000'"

    for pid in response.product_ids:
        product = db_session.get(Product, pid)
        assert product is not None
        assert product.price <= 15000, f"Product {product.name} price {product.price} > 15000"
        assert product.category and product.category.name == "Phones", f"Product {product.name} category is {product.category.name if product.category else None}, expected Phones"
        assert "keyboard" not in product.name.lower()
        assert "earbuds" not in product.name.lower()


def test_graph_search_phone_under_35000(db_session) -> None:
    """End-to-end LangGraph regression test for 'phone under 35000'.
    Must include Redmi Note 13 Pro+ 5G (price 27,999) in resolved search products.
    """
    auto_seed_catalog(db_session)

    from app.services.search import resolve_products
    resolved = resolve_products("phone under 35000", db=db_session, limit=20)
    names = [p.name for p in resolved.products]
    assert len(resolved.products) >= 5, f"Expected at least 5 phones under 35000, got {len(resolved.products)}"
    assert any("Redmi Note 13 Pro+" in name for name in names), f"Expected Redmi Note 13 Pro+ 5G in results, got {names}"

    graph_output = run_graph({
        "message": "phone under 35000",
        "mode": None,
        "db": db_session
    })

    response = graph_output.get("response")
    assert response is not None
    assert response.product_ids, "Expected non-empty product_ids for 'phone under 35000'"


def test_graph_search_earbuds_laptop_keyboard_categories(db_session) -> None:
    """End-to-end LangGraph regression test for category queries:
    - 'earbuds under 5000' -> Audio category only, <= 5000
    - 'laptop under 60000' -> Laptops category only, <= 60000
    - 'keyboard under 3000' -> Peripherals category only, <= 3000
    """
    auto_seed_catalog(db_session)

    # 1. Earbuds
    out_audio = run_graph({"message": "earbuds under 5000", "mode": None, "db": db_session})
    resp_audio = out_audio.get("response")
    assert resp_audio and resp_audio.product_ids
    for pid in resp_audio.product_ids:
        p = db_session.get(Product, pid)
        assert p.price <= 5000
        assert p.category and p.category.name == "Audio"

    # 2. Laptop
    out_laptop = run_graph({"message": "laptop under 60000", "mode": None, "db": db_session})
    resp_laptop = out_laptop.get("response")
    assert resp_laptop and resp_laptop.product_ids
    for pid in resp_laptop.product_ids:
        p = db_session.get(Product, pid)
        assert p.price <= 60000
        assert p.category and p.category.name == "Laptops"

    # 3. Keyboard
    out_kb = run_graph({"message": "keyboard under 3000", "mode": None, "db": db_session})
    resp_kb = out_kb.get("response")
    assert resp_kb and resp_kb.product_ids
    for pid in resp_kb.product_ids:
        p = db_session.get(Product, pid)
        assert p.price <= 3000
        assert p.category and p.category.name == "Peripherals"


def test_graph_search_keyboard_alone_returns_zero_phones_or_earbuds(db_session) -> None:
    """End-to-end LangGraph regression test: 'keyboard' alone.
    Must return ZERO phones or earbuds in product_ids.
    """
    auto_seed_catalog(db_session)

    graph_output = run_graph({
        "message": "keyboard",
        "mode": None,
        "db": db_session
    })

    response = graph_output.get("response")
    assert response is not None

    for pid in response.product_ids:
        p = db_session.get(Product, pid)
        assert p is not None
        assert p.category and p.category.name == "Peripherals"
        assert "phone" not in p.name.lower()
        assert "earbuds" not in p.name.lower()


def test_spacing_variants_category_resolution(db_session) -> None:
    """Ensure natural spacing variants resolve to the correct category."""
    from app.services.search import resolve_category
    assert resolve_category("mac book m5") == "Laptops"
    assert resolve_category("macbook m5") == "Laptops"
    assert resolve_category("one plus 12") == "Phones"
    assert resolve_category("i phone 15") == "Phones"
    assert resolve_category("air dopes") == "Audio"
    assert resolve_category("smart watch") == "Peripherals"


def test_resolve_products_spacing_and_empty_catalog_signaling(db_session) -> None:
    """Ensure existing items match with spacing variants, but non-existent items
    (like mac book m5) return products=[] instead of dumping unrelated products.
    """
    auto_seed_catalog(db_session)
    from app.services.search import resolve_products

    # 1. "one plus 12" exists -> must resolve OnePlus 12
    res_oneplus = resolve_products("one plus 12", db=db_session)
    assert len(res_oneplus.products) >= 1
    assert any("OnePlus 12" in p.name for p in res_oneplus.products)

    # 2. "i phone 15" exists -> must resolve Apple iPhone 15
    res_iphone = resolve_products("i phone 15", db=db_session)
    assert len(res_iphone.products) >= 1
    assert any("iPhone 15" in p.name for p in res_iphone.products)

    # 3. "mac book m3" exists -> must resolve Apple MacBook Air M3
    res_m3 = resolve_products("mac book m3", db=db_session)
    assert len(res_m3.products) >= 1
    assert any("M3" in p.name for p in res_m3.products)

    # 4. "mac book m5" does NOT exist in catalog -> must return products=[]
    # MUST NOT return MacBook Air M3 or unrelated laptops!
    res_m5 = resolve_products("mac book m5", db=db_session)
    assert res_m5.category_name == "Laptops"
    assert len(res_m5.products) == 0, f"Expected 0 products for 'mac book m5', got {[p.name for p in res_m5.products]}"


def test_execute_search_catalog_signals_live_search_when_empty(db_session) -> None:
    """Ensure _execute_search_catalog returns guidance to use search_live_web when catalog has 0 matches."""
    auto_seed_catalog(db_session)
    from app.services.ai import AIOrchestrator
    import json

    orchestrator = AIOrchestrator(db_session)
    result_str = orchestrator._execute_search_catalog(category="Laptops", keywords="mac book m5")
    data = json.loads(result_str)
    assert data["count"] == 0
    assert "search_live_web" in data.get("message", "")
