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
