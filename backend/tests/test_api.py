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


def test_duplicate_catalog_cleanup_and_unique_sku(db_session) -> None:
    """Ensure cleanup_duplicate_products removes duplicates and preserves correct sku."""
    from app.main import cleanup_duplicate_products
    cat = Category(name="Phones")
    db_session.add(cat)
    db_session.flush()

    p1 = Product(name="Duplicate Phone", sku=None, brand="BrandA", description="first", price=10000, category_id=cat.id)
    p2 = Product(name="Duplicate Phone", sku="dup-phone-sku", brand="BrandA", description="second", price=10000, category_id=cat.id)
    db_session.add_all([p1, p2])
    db_session.commit()

    deleted = cleanup_duplicate_products(db_session)
    assert deleted == 1

    remaining = db_session.query(Product).filter(Product.name == "Duplicate Phone").all()
    assert len(remaining) == 1
    assert remaining[0].sku == "dup-phone-sku"


def test_comparison_pre_check_resolves_two_distinct_products(client, db_session) -> None:
    """Ensure 'X vs Y' comparison resolves both items without duplicate cards."""
    cat = Category(name="Phones")
    db_session.add(cat)
    db_session.flush()

    p1 = Product(name="Apple iPhone 15", sku="iphone-15", brand="Apple", description="A16 Bionic phone", price=69900, rating=4.8, category_id=cat.id)
    p2 = Product(name="OnePlus 12", sku="oneplus-12", brand="OnePlus", description="Snapdragon 8 Gen 3 phone", price=64999, rating=4.7, category_id=cat.id)
    db_session.add_all([p1, p2])
    db_session.commit()

    res = client.post("/chat", json={"message": "Compare iPhone 15 vs OnePlus 12"})
    assert res.status_code == 200
    body = res.json()
    assert p1.id in body["product_ids"]
    assert p2.id in body["product_ids"]
    assert len(body["product_ids"]) == len(set(body["product_ids"]))


def test_tool_products_deduplication(db_session) -> None:
    """Ensure _execute_search_catalog deduplicates products across calls."""
    from app.services.ai import AIOrchestrator
    cat = Category(name="Phones")
    db_session.add(cat)
    db_session.flush()

    p1 = Product(name="Test Phone", sku="test-phone-1", brand="TestBrand", description="test phone", price=12000, rating=4.5, category_id=cat.id)
    db_session.add(p1)
    db_session.commit()

    orchestrator = AIOrchestrator(db_session)
    orchestrator._execute_search_catalog(category="Phones")
    orchestrator._execute_search_catalog(category="Phones")

    assert len(orchestrator._tool_products) == 1
    assert orchestrator._tool_products[0].id == p1.id


def test_cors_restricted_origins(client) -> None:
    """Ensure unauthorized origins do not receive allow-origin header."""
    res = client.options(
        "/auth/login",
        headers={
            "Origin": "https://malicious-phishing-site.com",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        },
    )
    assert res.headers.get("access-control-allow-origin") != "https://malicious-phishing-site.com"


def test_rate_limiting_flood_returns_429(client) -> None:
    """Ensure flooding /auth/register triggers 429 Too Many Requests."""
    statuses = []
    for i in range(10):
        r = client.post("/auth/register", json={
            "email": f"flood{i}@example.com",
            "password": "Password123!",
            "full_name": f"Flooder {i}"
        })
        statuses.append(r.status_code)
    assert 429 in statuses


def test_entrypoint_script_has_lf_and_migration_command() -> None:
    """Ensure container entrypoint script exists, uses LF line endings, and invokes alembic."""
    from pathlib import Path
    entrypoint = Path(__file__).resolve().parent.parent / "entrypoint.sh"
    assert entrypoint.exists(), "backend/entrypoint.sh must exist"
    content = entrypoint.read_bytes()
    assert b"\r" not in content, "entrypoint.sh must have unix LF line endings to run in Linux container"
    assert b"alembic upgrade head" in content
    assert b'--port "${PORT:-8000}"' in content
    assert b'PORT=""' not in content
    assert b"exec uvicorn app.main:app" in content


def test_alembic_self_healing_orphaned_revision(db_session) -> None:
    """Ensure an orphaned/unknown alembic revision is self-healed to baseline without crash."""
    from sqlalchemy import text
    from alembic.config import Config
    from alembic import command
    from pathlib import Path

    backend_dir = Path(__file__).resolve().parent.parent
    alembic_ini = backend_dir / "alembic.ini"

    # Simulate an orphaned revision in alembic_version table
    db_session.execute(text("CREATE TABLE IF NOT EXISTS alembic_version (version_num VARCHAR(32) NOT NULL PRIMARY KEY);"))
    db_session.execute(text("DELETE FROM alembic_version;"))
    db_session.execute(text("INSERT INTO alembic_version (version_num) VALUES ('stale_orphaned_9999');"))
    db_session.commit()

    cfg = Config(str(alembic_ini))
    cfg.set_main_option("script_location", str(backend_dir / "alembic"))
    cfg.attributes["connection"] = db_session.connection()
    # Run alembic upgrade head using the test engine connection
    command.upgrade(cfg, "head")

    # Verify that alembic healed to the actual head
    current = db_session.execute(text("SELECT version_num FROM alembic_version")).scalar()
    assert current == "0002_dedupe_and_unique_sku"
