import asyncio

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from app.api.routes import identify_image_route
from app.core.config import Settings
from app.core.observability import RequestMetrics
from app.schemas.api import ChatRequest, ChatTurn


def test_development_secret_is_random_when_not_configured():
    first = Settings(_env_file=None, jwt_secret="", environment="development")
    second = Settings(_env_file=None, jwt_secret="", environment="development")
    assert len(first.jwt_secret) >= 32
    assert first.jwt_secret != second.jwt_secret
    assert "development" not in first.jwt_secret


def test_production_rejects_placeholder_jwt_secret():
    with pytest.raises(RuntimeError, match="JWT_SECRET"):
        Settings(
            _env_file=None,
            jwt_secret="replace-with-a-random-32-byte-or-longer-secret",
            environment="production",
        )


def test_chat_payload_history_cart_and_turn_text_are_bounded():
    with pytest.raises(ValidationError):
        ChatRequest(message="Find headphones", history=[ChatTurn(role="user", content="x")] * 21)
    with pytest.raises(ValidationError):
        ChatRequest(message="Find headphones", cart=[{"id": i} for i in range(51)])
    with pytest.raises(ValidationError):
        ChatTurn(role="user", content="x" * 4001)


def test_image_upload_is_rejected_before_image_processing(db_session):
    class OversizedUpload:
        closed = False

        async def read(self, size):
            assert size == 8 * 1024 * 1024 + 1
            return b"x" * size

        async def close(self):
            self.closed = True

    upload = OversizedUpload()
    with pytest.raises(HTTPException) as error:
        asyncio.run(identify_image_route(upload, db_session))
    assert error.value.status_code == 413
    assert upload.closed is True


def test_request_metrics_retains_only_bounded_route_keys_and_samples():
    metrics = RequestMetrics(max_routes=10, samples_per_route=10)
    for i in range(30):
        metrics.record("GET", f"/products/{i}", 200, i)
    metrics.record("GET", "/products/{product_id}", 500, 42)

    snapshot = metrics.snapshot()
    assert snapshot["request_count"] == 31
    assert snapshot["server_error_count"] == 1
    assert len(snapshot["routes"]) <= 10
    assert snapshot["samples_per_route"] == 10


def test_declared_oversized_request_is_rejected_before_route_body_parsing():
    from app.core.observability import RequestBodyLimitMiddleware

    sent = []
    app_called = {"value": False}

    async def inner_app(_scope, _receive, _send):
        app_called["value"] = True

    scope = {
        "type": "http",
        "method": "POST",
        "path": "/chat",
        "headers": [(b"content-length", b"10485761")],
    }

    async def receive():
        return {"type": "http.request", "body": b"", "more_body": False}

    async def send(message):
        sent.append(message)

    asyncio.run(RequestBodyLimitMiddleware(inner_app)(scope, receive, send))

    assert app_called["value"] is False
    assert sent[0]["type"] == "http.response.start"
    assert sent[0]["status"] == 413
