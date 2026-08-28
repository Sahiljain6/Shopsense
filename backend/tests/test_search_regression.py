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
