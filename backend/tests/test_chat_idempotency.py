from datetime import datetime, timedelta

import pytest
from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import select

from app.api.routes import _claim_chat_idempotency, _complete_chat_idempotency
from app.models.entities import ChatIdempotency, User
from app.schemas.api import ChatRequest, ChatResponse


def _user(db_session, email: str) -> User:
    user = User(email=email, full_name="Test User")
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


def test_completed_chat_retry_replays_response_without_creating_another_record(db_session):
    user = _user(db_session, "idempotency-replay@example.com")
    payload = ChatRequest(message="Find wireless headphones under 5000", idempotency_key="chat-run-0001")

    state, cached = _claim_chat_idempotency(db_session, user.id, payload)
    assert state == "new"
    assert cached is None

    response = ChatResponse(answer="Here are three headphone options.")
    _complete_chat_idempotency(db_session, user.id, payload, response)

    retry_state, replayed = _claim_chat_idempotency(db_session, user.id, payload)

    assert retry_state == "replay"
    assert replayed is not None
    assert replayed.answer == response.answer
    rows = db_session.scalars(
        select(ChatIdempotency).where(
            ChatIdempotency.user_id == user.id,
            ChatIdempotency.key == payload.idempotency_key,
        )
    ).all()
    assert len(rows) == 1
    assert rows[0].status == "completed"


def test_reusing_key_for_different_payload_returns_conflict(db_session):
    user = _user(db_session, "idempotency-conflict@example.com")
    first = ChatRequest(message="Find a laptop", idempotency_key="chat-run-0002")
    second = ChatRequest(message="Find a phone", idempotency_key="chat-run-0002")

    _claim_chat_idempotency(db_session, user.id, first)

    with pytest.raises(HTTPException) as exc_info:
        _claim_chat_idempotency(db_session, user.id, second)

    assert exc_info.value.status_code == 409


def test_duplicate_while_processing_is_rejected_without_second_claim(db_session):
    user = _user(db_session, "idempotency-processing@example.com")
    payload = ChatRequest(message="Compare two phones", idempotency_key="chat-run-0003")

    state, cached = _claim_chat_idempotency(db_session, user.id, payload)
    assert state == "new"
    assert cached is None

    with pytest.raises(HTTPException) as exc_info:
        _claim_chat_idempotency(db_session, user.id, payload)

    assert exc_info.value.status_code == 409
    count = len(db_session.scalars(select(ChatIdempotency)).all())
    assert count == 1


def test_idempotency_keys_are_scoped_to_authenticated_user(db_session):
    first_user = _user(db_session, "idempotency-user-a@example.com")
    second_user = _user(db_session, "idempotency-user-b@example.com")
    payload = ChatRequest(message="Recommend a smartwatch", idempotency_key="chat-run-0004")

    first_state, _ = _claim_chat_idempotency(db_session, first_user.id, payload)
    second_state, _ = _claim_chat_idempotency(db_session, second_user.id, payload)

    assert first_state == "new"
    assert second_state == "new"
    assert len(db_session.scalars(select(ChatIdempotency)).all()) == 2


def test_stale_in_progress_claim_can_be_recovered(db_session):
    user = _user(db_session, "idempotency-stale@example.com")
    payload = ChatRequest(message="Find a good monitor", idempotency_key="chat-run-0005")
    _claim_chat_idempotency(db_session, user.id, payload)

    record = db_session.scalar(
        select(ChatIdempotency).where(
            ChatIdempotency.user_id == user.id,
            ChatIdempotency.key == payload.idempotency_key,
        )
    )
    assert record is not None
    record.updated_at = datetime.utcnow() - timedelta(minutes=5)
    db_session.commit()

    state, cached = _claim_chat_idempotency(db_session, user.id, payload)

    assert state == "new"
    assert cached is None
    db_session.refresh(record)
    assert record.status == "processing"
    assert record.updated_at > datetime.utcnow() - timedelta(minutes=1)


def test_request_accepts_uuid_style_idempotency_key():
    payload = ChatRequest(message="Find running shoes", idempotency_key="7a9f2c30-7d4a-4f61-962f-c7a8bb7a1f11")
    assert payload.idempotency_key == "7a9f2c30-7d4a-4f61-962f-c7a8bb7a1f11"


@pytest.mark.parametrize("invalid_key", ["short", "contains spaces", "bad/key", "x" * 129])
def test_request_rejects_malformed_idempotency_key(invalid_key):
    with pytest.raises(ValidationError):
        ChatRequest(message="Find running shoes", idempotency_key=invalid_key)


def test_legacy_request_without_key_remains_supported(db_session):
    user = _user(db_session, "idempotency-legacy@example.com")
    payload = ChatRequest(message="Recommend a backpack")

    state, cached = _claim_chat_idempotency(db_session, user.id, payload)

    assert state == "new"
    assert cached is None
    assert db_session.scalars(select(ChatIdempotency)).all() == []
