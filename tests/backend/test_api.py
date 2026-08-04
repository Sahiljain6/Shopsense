from uuid import uuid4

from fastapi.testclient import TestClient
from backend.app.main import app

client = TestClient(app)


def token():
    client.post(
        "/register",
        json={
            "email": "test@example.com",
            "password": "Password123",
            "full_name": "Test User",
        },
    )
    return client.post(
        "/login", json={"email": "test@example.com", "password": "Password123"}
    ).json()["access_token"]


def test_health():
    assert client.get("/health").json() == {"status": "ok"}


def test_auth_and_short_chat_clarifies():
    t = token()
    data = client.post(
        "/chat", headers={"Authorization": f"Bearer {t}"}, json={"message": "laptop"}
    ).json()
    assert data["clarification"] == "What is your budget and primary use case?"


def test_auth_accepts_long_password():
    long_password = "correct horse battery staple " * 8
    email = f"long-password-{uuid4()}@example.com"

    register_response = client.post(
        "/register",
        json={
            "email": email,
            "password": long_password,
            "full_name": "Long Password",
        },
    )
    assert register_response.status_code == 200

    login_response = client.post(
        "/login", json={"email": email, "password": long_password}
    )
    assert login_response.status_code == 200
    assert login_response.json()["access_token"]
