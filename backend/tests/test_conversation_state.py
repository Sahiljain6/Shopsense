import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.session import Base, get_db
from app.main import app
from app.models.conversation import Conversation, ConversationSummary, Message
from app.services.context_manager import ContextWindowManager, SummarizationService, estimate_tokens
from app.services.conversation_service import ConcurrencyConflictError, ConversationService

from sqlalchemy.pool import StaticPool

# In-memory SQLite engine with StaticPool to retain tables across connections
SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"
test_engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


@pytest.fixture(scope="function")
def db_session():
    Base.metadata.create_all(bind=test_engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=test_engine)


@pytest.fixture(scope="function")
def client(db_session):
    # Ensure all registered models (incl. Conversation, Message, etc.) exist in test_engine
    Base.metadata.create_all(bind=test_engine)

    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def test_conversation_creation_and_metadata(db_session):
    conv = ConversationService.create_conversation(
        db=db_session,
        title="Shopping Research",
        model_used="gpt-4o",
        metadata={"tags": ["electronics", "phones"], "folder": "tech"},
    )
    assert conv.id is not None
    assert conv.title == "Shopping Research"
    assert conv.version == 1
    assert conv.metadata_json["tags"] == ["electronics", "phones"]
    assert conv.total_messages == 0


def test_message_turn_accounting_and_auto_title(db_session):
    conv = ConversationService.create_conversation(db=db_session)
    assert conv.title == "New Conversation"

    # Add user message
    msg1 = ConversationService.add_message(
        db=db_session,
        conversation_id=conv.id,
        role="user",
        content="I need a recommendation for Sony headphones under 20000",
    )
    assert msg1.sequence_number == 1
    assert msg1.tokens_prompt > 0
    assert conv.total_messages == 1
    assert conv.version == 2
    # Verify auto-title generated
    assert conv.title != "New Conversation"
    assert "Sony" in conv.title or "Headphones" in conv.title or "Recommendation" in conv.title

    # Add assistant response
    msg2 = ConversationService.add_message(
        db=db_session,
        conversation_id=conv.id,
        role="assistant",
        content="I recommend the Sony WH-1000XM4 which is currently on sale.",
    )
    assert msg2.sequence_number == 2
    assert msg2.tokens_completion > 0
    assert conv.total_messages == 2
    assert conv.version == 3
    assert conv.total_cost_usd > 0.0


def test_optimistic_concurrency_control(db_session):
    conv = ConversationService.create_conversation(db=db_session)
    current_ver = conv.version  # 1

    # Successful turn with expected version
    ConversationService.add_message(
        db=db_session,
        conversation_id=conv.id,
        role="user",
        content="Turn 1",
        expected_version=current_ver,
    )
    assert conv.version == 2

    # Conflicting turn with stale version (expected 1, but current is 2)
    with pytest.raises(ConcurrencyConflictError):
        ConversationService.add_message(
            db=db_session,
            conversation_id=conv.id,
            role="user",
            content="Conflicting turn",
            expected_version=current_ver,
        )


def test_context_window_manager_and_100_turns_scaling(db_session):
    conv = ConversationService.create_conversation(db=db_session, model_used="gpt-4o")

    # Simulate 100 turns
    for i in range(1, 101):
        role = "user" if i % 2 == 1 else "assistant"
        content = f"Turn {i}: Discussing laptop battery life and memory configurations."
        ConversationService.add_message(
            db=db_session,
            conversation_id=conv.id,
            role=role,
            content=content,
        )

    assert conv.total_messages == 100

    cwm = ContextWindowManager(model_name="gpt-4o", sliding_window_size=15)
    context_plan = cwm.assemble_conversation_context(
        db=db_session,
        conversation_id=conv.id,
        current_query="What was the best laptop battery recommendation?",
    )

    assert context_plan["sliding_window_message_count"] == 15
    # Token usage must stay well bounded within working budget
    metrics = context_plan["metrics"]
    assert metrics["total_estimated_tokens"] < metrics["working_budget"]
    assert context_plan["needs_summarization"] is True


def test_recursive_summarization(db_session):
    conv = ConversationService.create_conversation(db=db_session)

    # Add 25 turns with content long enough to make summarization meaningful
    long_content = (
        "I am looking for wireless ANC earbuds with a budget constraint of 15000 INR. "
        "The key requirements are: active noise cancellation of at least 30dB, "
        "minimum 30 hours total battery life, IPX5 water resistance rating, "
        "low latency Bluetooth 5.3 for gaming, and preferably LDAC Hi-Res Audio support."
    )
    for i in range(1, 26):
        ConversationService.add_message(
            db=db_session,
            conversation_id=conv.id,
            role="user" if i % 2 == 1 else "assistant",
            content=f"Message {i}: {long_content}",
        )

    # Run summarization
    summary = SummarizationService.execute_summarization(
        db=db_session,
        conversation_id=conv.id,
        preserve_recent_turns=10,
    )

    assert summary is not None
    assert summary.summary_version == 1
    assert summary.end_sequence_number == 15  # 25 - 10 = 15
    assert "Historical Context" in summary.summary_text
    # Summary compresses 15 turns: source must be > summary (meaningful ratio)
    assert summary.source_token_count > summary.summary_token_count


def test_conversation_branching(db_session):
    conv = ConversationService.create_conversation(db=db_session, title="Main Thread")

    # Add 6 turns
    msg_ids = []
    for i in range(1, 7):
        m = ConversationService.add_message(
            db=db_session,
            conversation_id=conv.id,
            role="user" if i % 2 == 1 else "assistant",
            content=f"Thread turn #{i}",
        )
        msg_ids.append(m.id)

    # Branch from message #3
    branch_from_id = msg_ids[2]  # index 2 is turn #3
    branch = ConversationService.branch_conversation(
        db=db_session,
        conversation_id=conv.id,
        branch_from_message_id=branch_from_id,
        new_title="Alternate Branch",
    )

    assert branch.id != conv.id
    assert branch.parent_conversation_id == conv.id
    assert branch.branch_point_message_id == branch_from_id
    assert branch.total_messages == 3

    # Add turn to branch
    branch_m4 = ConversationService.add_message(
        db=db_session,
        conversation_id=branch.id,
        role="user",
        content="Alternate path turn 4",
    )
    assert branch_m4.sequence_number == 4
    assert branch.total_messages == 4
    # Ensure original conversation remains unaffected
    assert conv.total_messages == 6


def test_archiving_and_lossless_decompression(db_session):
    conv = ConversationService.create_conversation(db=db_session, title="To Archive")
    original_text = "This is a detailed shopping specification with product IDs and price breakdown."
    msg = ConversationService.add_message(
        db=db_session,
        conversation_id=conv.id,
        role="user",
        content=original_text,
    )

    # Archive with compression
    ConversationService.archive_conversation(db=db_session, conversation_id=conv.id, compress=True)
    assert conv.archived_at is not None
    assert msg.content_compressed is not None

    # Unarchive and verify lossless restoration
    ConversationService.unarchive_conversation(db=db_session, conversation_id=conv.id)
    assert conv.archived_at is None
    assert msg.content == original_text


def test_conversation_export_formats(db_session):
    conv = ConversationService.create_conversation(db=db_session, title="Export Test")
    ConversationService.add_message(
        db=db_session,
        conversation_id=conv.id,
        role="user",
        content="Hello, what are good deals?",
    )
    ConversationService.add_message(
        db=db_session,
        conversation_id=conv.id,
        role="assistant",
        content="Here are today's top deals.",
    )

    # JSON export
    json_out = ConversationService.export_conversation(db_session, conv.id, export_format="json")
    assert '"title": "Export Test"' in json_out
    assert '"Hello, what are good deals?"' in json_out

    # Markdown export
    md_out = ConversationService.export_conversation(db_session, conv.id, export_format="markdown")
    assert "# Conversation: Export Test" in md_out
    assert "### [#1] USER" in md_out

    # CSV export
    csv_out = ConversationService.export_conversation(db_session, conv.id, export_format="csv")
    assert "sequence_number,role,content,tokens_total" in csv_out


def test_rest_api_conversation_flow(client):
    # 1. Create conversation via REST
    resp = client.post("/conversations", json={"title": "API Test Conv", "model_used": "gpt-4o"})
    assert resp.status_code == 201
    conv_data = resp.json()
    conv_id = conv_data["id"]

    # 2. Add message turn
    resp = client.post(f"/conversations/{conv_id}/messages", json={"content": "Suggest a high refresh monitor", "role": "user"})
    assert resp.status_code == 201
    msg_id = resp.json()["id"]

    # 3. Get history
    resp = client.get(f"/conversations/{conv_id}/history")
    assert resp.status_code == 200
    assert len(resp.json()["messages"]) == 1

    # 4. Search conversations
    resp = client.get("/conversations/search?q=monitor")
    assert resp.status_code == 200
    assert resp.json()["results_count"] >= 1

    # 5. Edit message
    resp = client.patch(f"/messages/{msg_id}", json={"content": "Suggest a 240Hz monitor", "revision": 1})
    assert resp.status_code == 200
    assert resp.json()["content"] == "Suggest a 240Hz monitor"

    # 6. Branch conversation
    resp = client.post(f"/conversations/{conv_id}/branch", json={"branch_from_message_id": msg_id, "title": "Branched Path"})
    assert resp.status_code == 201
    assert resp.json()["title"] == "Branched Path"

    # 7. Export conversation
    resp = client.get(f"/conversations/{conv_id}/export?format=markdown")
    assert resp.status_code == 200
    assert "240Hz monitor" in resp.json()["content"]

    # 8. Archive & Unarchive
    resp = client.post(f"/conversations/{conv_id}/archive")
    assert resp.status_code == 200
    assert resp.json()["archived_at"] is not None

    resp = client.post(f"/conversations/{conv_id}/unarchive")
    assert resp.status_code == 200
    assert resp.json()["archived_at"] is None
