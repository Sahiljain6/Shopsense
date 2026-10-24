from app.core.security import create_access_token
from app.models.entities import User
from conftest import TestingSessionLocal


def test_request_id_is_returned_and_untrusted_ids_are_replaced(client):
    response = client.get("/health", headers={"X-Request-ID": "test-request-0001"})
    assert response.status_code == 200
    assert response.headers["X-Request-ID"] == "test-request-0001"

    invalid = client.get("/health", headers={"X-Request-ID": "bad request\nforged"})
    assert invalid.status_code == 200
    assert invalid.headers["X-Request-ID"] != "bad request\nforged"
    assert len(invalid.headers["X-Request-ID"]) <= 64


def test_cors_allows_shop_sense_project_preview_but_not_unrelated_origins(client):
    allowed_origin = "https://shopsense-4444-l2msp2txf-sahil-jain-s-projects.vercel.app"
    allowed = client.options(
        "/health",
        headers={
            "Origin": allowed_origin,
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "authorization,content-type",
        },
    )
    assert allowed.status_code == 200
    assert allowed.headers.get("access-control-allow-origin") == allowed_origin

    untrusted = client.options(
        "/health",
        headers={
            "Origin": "https://shopsense-fake-team.vercel.app",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert "access-control-allow-origin" not in untrusted.headers


def test_admin_metrics_endpoint_is_protected_and_returns_bounded_aggregate_data(client):
    with TestingSessionLocal() as db:
        admin = User(
            email="ops-admin@example.com",
            hashed_password="not-a-real-password",
            is_admin=True,
        )
        db.add(admin)
        db.commit()
        db.refresh(admin)
        token = create_access_token(admin.email, user=admin)

    unauthorized = client.get("/admin/ops/metrics")
    assert unauthorized.status_code in (401, 403)

    response = client.get(
        "/admin/ops/metrics",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["http"]["scope"] == "process-local"
    assert "request_count" in data["http"]
    assert data["live_search_cache"]["scope"] == "process-local"
    assert data["circuit_breakers"]["serpapi"]["state"] in {"closed", "open", "half_open"}
    assert "routes" in data["http"]
