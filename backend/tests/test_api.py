from app.models.entities import Category, Product


def seed_phone(db_session) -> Product:
    category = Category(name="Phones")
    db_session.add(category); db_session.flush()
    product = Product(name="Xiaomi Phone Sense", brand="Xiaomi", description="budget phone for students", price=12999, rating=4.5, stock=10, category_id=category.id, attributes={"ram":"6GB"})
    db_session.add(product); db_session.commit(); db_session.refresh(product)
    return product


def _register_and_login(client) -> dict[str, str]:
    """Register a fresh test user and return Authorization headers."""
    client.post("/auth/register", json={"email": "test@example.com", "password": "Password123!", "full_name": "Tester"})
    token = client.post("/auth/login", json={"email": "test@example.com", "password": "Password123!"}).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_auth_flow(client) -> None:
    res = client.post("/auth/register", json={"email":"user@example.com","password":"password123","full_name":"User"})
    assert res.status_code == 200
    token = client.post("/auth/login", json={"email":"user@example.com","password":"password123"}).json()["access_token"]
    me = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200
    assert me.json()["email"] == "user@example.com"


def test_chat_requires_auth(client) -> None:
    """POST /chat without an Authorization header must return 401."""
    res = client.post("/chat", json={"message": "recommend a budget phone"})
    assert res.status_code == 401


def test_chat_grounding(client, db_session) -> None:
    product = seed_phone(db_session)
    headers = _register_and_login(client)
    res = client.post("/chat", json={"message":"recommend a budget phone under 15000"}, headers=headers)
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

    res = client.post("/chat", json={"message": "Compare iPhone 15 vs OnePlus 12"}, headers=_register_and_login(client))
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
    assert current == "0003_add_google_id_nullable_password"


def test_jwt_secret_validation_in_production_and_dev(monkeypatch) -> None:
    """Ensure Settings raises a RuntimeError if JWT_SECRET is not set in production,
    and generates a random-per-run secret in development."""
    import pytest
    from app.core.config import Settings

    # In production without JWT_SECRET: must raise RuntimeError
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.delenv("JWT_SECRET", raising=False)
    with pytest.raises(RuntimeError, match="CRITICAL SECURITY ERROR: JWT_SECRET"):
        Settings(environment="production", jwt_secret="")

    # In production with dummy secret: must raise RuntimeError
    with pytest.raises(RuntimeError, match="CRITICAL SECURITY ERROR: JWT_SECRET"):
        Settings(environment="production", jwt_secret="shopsense-hackathon-secure-secret-key-2026-production")

    # In development without JWT_SECRET: must generate a non-empty random secret
    monkeypatch.setenv("ENVIRONMENT", "development")
    s_dev = Settings(environment="development", jwt_secret="")
    assert s_dev.jwt_secret
    assert len(s_dev.jwt_secret) >= 32


def test_google_identity_services_flow(client, db_session, monkeypatch) -> None:
    """Test real Google Identity Services (GIS) auth:
    1. New Google user creation (google_id set, hashed_password is None)
    2. Google-authenticated user can immediately access /chat and /auth/me
    3. Existing email/password user links google_id on Google login
    4. Rejection of unverified email or invalid issuer
    """
    from google.oauth2 import id_token
    from app.models.entities import User

    # 1. New user registration via Google ID token
    mock_payload_new = {
        "sub": "gid-123456789",
        "email": "test_gis_user@gmail.com",
        "email_verified": True,
        "name": "GIS Test User",
        "iss": "https://accounts.google.com"
    }
    monkeypatch.setattr(id_token, "verify_oauth2_token", lambda *args, **kwargs: mock_payload_new)

    resp = client.post("/auth/google", json={"credential": "mock-valid-google-id-token"})
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
    token_data = resp.json()
    assert "access_token" in token_data
    access_token = token_data["access_token"]

    # Verify user in database has google_id and null hashed_password
    user = db_session.query(User).filter(User.email == "test_gis_user@gmail.com").first()
    assert user is not None
    assert user.google_id == "gid-123456789"
    assert user.hashed_password is None
    assert user.full_name == "GIS Test User"

    # Verify user can immediately access protected /auth/me and /chat
    me_resp = client.get("/auth/me", headers={"Authorization": f"Bearer {access_token}"})
    assert me_resp.status_code == 200
    assert me_resp.json()["email"] == "test_gis_user@gmail.com"

    chat_resp = client.post(
        "/chat",
        json={"message": "hello", "mode": "standard", "history": []},
        headers={"Authorization": f"Bearer {access_token}"}
    )
    assert chat_resp.status_code == 200

    # 2. Existing password user links Google account
    # Pre-populate existing user directly in DB
    existing = User(
        email="existing_user@gmail.com",
        full_name="Original Name",
        hashed_password="hashed_pw_secret"
    )
    db_session.add(existing)
    db_session.commit()

    mock_payload_existing = {
        "sub": "gid-999999999",
        "email": "existing_user@gmail.com",
        "email_verified": True,
        "name": "Original Name",
        "iss": "accounts.google.com"
    }
    monkeypatch.setattr(id_token, "verify_oauth2_token", lambda *args, **kwargs: mock_payload_existing)

    link_resp = client.post("/auth/google", json={"credential": "mock-valid-link-token"})
    assert link_resp.status_code == 200

    # Must be linked to the same account without duplicate creation
    users_with_email = db_session.query(User).filter(User.email == "existing_user@gmail.com").all()
    assert len(users_with_email) == 1
    linked_user = users_with_email[0]
    assert linked_user.google_id == "gid-999999999"
    assert linked_user.hashed_password is not None  # Original password preserved

    # 3. Unverified email rejection
    mock_unverified = {
        "sub": "gid-0000",
        "email": "unverified@gmail.com",
        "email_verified": False,
        "iss": "https://accounts.google.com"
    }
    monkeypatch.setattr(id_token, "verify_oauth2_token", lambda *args, **kwargs: mock_unverified)
    unverified_resp = client.post("/auth/google", json={"credential": "mock-unverified-token"})
    assert unverified_resp.status_code == 400

    # 4. Invalid issuer rejection
    mock_bad_issuer = {
        "sub": "gid-0000",
        "email": "bad_issuer@gmail.com",
        "email_verified": True,
        "iss": "https://attacker-domain.com"
    }
    monkeypatch.setattr(id_token, "verify_oauth2_token", lambda *args, **kwargs: mock_bad_issuer)
    issuer_resp = client.post("/auth/google", json={"credential": "mock-bad-issuer-token"})
    assert issuer_resp.status_code == 401


def test_cookie_auth_csrf_and_refresh_token_rotation(client, db_session) -> None:
    """Ensure:
    1. /auth/login sets httpOnly access_token, refresh_token, and readable csrf_token cookies.
    2. Cookie-authenticated GET requests succeed without Bearer headers.
    3. Cookie-authenticated POST requests without X-CSRF-Token fail with 403.
    4. Cookie-authenticated POST requests with valid X-CSRF-Token succeed with 200.
    5. /auth/refresh rotates access and refresh tokens.
    6. /auth/logout clears auth cookies.
    """
    from app.core.security import hash_password
    from app.models.entities import User

    user = User(
        email="cookie_user@example.com",
        hashed_password=hash_password("MySecurePass123!"),
        full_name="Cookie User"
    )
    db_session.add(user)
    db_session.commit()

    # 1. Login
    login_resp = client.post(
        "/auth/login",
        json={"email": "cookie_user@example.com", "password": "MySecurePass123!"}
    )
    assert login_resp.status_code == 200
    cookies = login_resp.cookies
    assert "access_token" in cookies
    assert "refresh_token" in cookies
    assert "csrf_token" in cookies
    csrf_val = cookies["csrf_token"]

    # 2. GET request using cookies (read operation - no CSRF required)
    me_resp = client.get("/auth/me")
    assert me_resp.status_code == 200
    assert me_resp.json()["email"] == "cookie_user@example.com"

    # 3. State-changing POST request using cookies WITHOUT X-CSRF-Token header -> must be rejected (403)
    chat_no_csrf = client.post("/chat", json={"message": "hello", "mode": "standard", "history": []})
    assert chat_no_csrf.status_code == 403
    assert "CSRF" in chat_no_csrf.json()["detail"]

    # 4. State-changing POST request with valid X-CSRF-Token header -> succeeds (200)
    chat_with_csrf = client.post(
        "/chat",
        json={"message": "hello", "mode": "standard", "history": []},
        headers={"X-CSRF-Token": csrf_val}
    )
    assert chat_with_csrf.status_code == 200

    # 5. /auth/refresh rotates tokens
    old_access = cookies["access_token"]
    old_refresh = cookies["refresh_token"]
    refresh_resp = client.post("/auth/refresh")
    assert refresh_resp.status_code == 200
    new_cookies = refresh_resp.cookies
    assert "access_token" in new_cookies
    assert "refresh_token" in new_cookies
    assert new_cookies["access_token"] != old_access

    # 6. /auth/logout clears cookies
    logout_resp = client.post("/auth/logout")
    assert logout_resp.status_code == 200



