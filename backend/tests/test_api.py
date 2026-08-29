from app.models.entities import Category, Product


def seed_phone(db_session) -> Product:
    category = Category(name="Phones")
    db_session.add(category); db_session.flush()
    product = Product(name="Xiaomi Phone Sense", brand="Xiaomi", description="budget phone for students", price=12999, rating=4.5, stock=10, category_id=category.id, attributes={"ram":"6GB"})
    db_session.add(product); db_session.commit(); db_session.refresh(product)
    return product


def test_auth_flow(client) -> None:
    res = client.post("/auth/register", json={"email":"user@example.com","password":"password123","full_name":"User"})
    assert res.status_code == 200
    token = client.post("/auth/login", json={"email":"user@example.com","password":"password123"}).json()["access_token"]
    me = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200
    assert me.json()["email"] == "user@example.com"


def test_cors_allows_vercel_preview_origin(client) -> None:
    res = client.options(
        "/auth/login",
        headers={
            "Origin": "https://shopsense-4a45rlij8-sahil-jain-s-projects.vercel.app",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        },
    )
    assert res.status_code == 200
    assert res.headers["access-control-allow-origin"] in ["*", "https://shopsense-4a45rlij8-sahil-jain-s-projects.vercel.app"]


def test_chat_grounding(client, db_session) -> None:
    product = seed_phone(db_session)
    res = client.post("/chat", json={"message":"recommend a budget phone under 15000"})
    assert res.status_code == 200
    body = res.json()
    assert body["product_ids"] == [product.id]
    assert 999999 not in body["product_ids"]


def test_transaction_rollback_resilience(client, db_session) -> None:
    """Regression test for Bug 2: ensure failed statements do not poison subsequent queries."""
    from sqlalchemy import text
    # 1. Simulate an intentional error in the session
    try:
        db_session.execute(text("SELECT * FROM non_existent_table_for_test;"))
    except Exception:
        db_session.rollback()

    # 2. Subsequent queries must execute cleanly without InFailedSqlTransaction
    cat = Category(name="Phones")
    db_session.add(cat)
    db_session.commit()
    assert cat.id is not None


def test_gemini_live_model_discovery() -> None:
    """Regression test for Bug 3: get_active_gemini_models returns live 2.5 models and filters dead 1.0/1.5."""
    from app.services.ai import get_active_gemini_models
    # When api key is invalid/offline, it must fall back to live 2026 models, not dead 1.5
    models = get_active_gemini_models("test-invalid-key")
    assert "gemini-2.5-flash" in models
    assert not any("1.5" in m for m in models)
    assert not any("1.0" in m for m in models)


def test_ensure_schema_upgrades_idempotent() -> None:
    """Regression test for Bug 1: ensure_schema_upgrades runs without error repeatedly."""
    from app.main import ensure_schema_upgrades
    ensure_schema_upgrades()
    ensure_schema_upgrades()
