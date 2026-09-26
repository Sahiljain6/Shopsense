import logging
from datetime import datetime
from typing import Literal
from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from sqlalchemy import desc, func, or_, select
from sqlalchemy.orm import Session

from app.core.security import get_current_user, oauth2_scheme
from app.db.session import get_db
from app.models.conversation import Conversation, ConversationSummary, Message
from app.models.entities import User
from app.schemas.conversation import (
    ConversationBranchRequest,
    ConversationCreate,
    ConversationExportResponse,
    ConversationHistoryResponse,
    ConversationListResponse,
    ConversationRead,
    ConversationSummaryRead,
    ConversationUpdate,
    MessageCreate,
    MessageRead,
    MessageUpdate,
)
from app.services.context_manager import ContextWindowManager, SummarizationService, cosine_similarity, generate_text_embedding
from app.services.conversation_service import ConcurrencyConflictError, ConversationService

logger = logging.getLogger("shopsense.api.conversation")
conv_router = APIRouter(tags=["conversations"])


def get_optional_user(
    request: Request,
    token: str | None = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> User | None:
    """Optional user dependency for guest or authenticated conversation sessions."""
    try:
        return get_current_user(request, token, db)
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Conversation Endpoints
# ---------------------------------------------------------------------------

@conv_router.post("/conversations", response_model=ConversationRead, status_code=status.HTTP_201_CREATED)
def create_conversation(
    payload: ConversationCreate,
    db: Session = Depends(get_db),
    user: User | None = Depends(get_optional_user),
) -> Conversation:
    """Create a new conversation session with state management."""
    user_id = user.id if user else None
    return ConversationService.create_conversation(
        db=db,
        user_id=user_id,
        title=payload.title,
        model_used=payload.model_used,
        system_prompt=payload.system_prompt,
        metadata=payload.metadata,
    )


@conv_router.get("/conversations", response_model=ConversationListResponse)
def list_conversations(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    include_archived: bool = Query(default=False),
    folder: str | None = Query(default=None),
    tag: str | None = Query(default=None),
    sort: Literal["updated_desc", "created_desc"] = Query(default="updated_desc"),
    db: Session = Depends(get_db),
    user: User | None = Depends(get_optional_user),
) -> dict:
    """List conversations with filtering, sorting, and pagination."""
    query = select(Conversation)

    if user:
        query = query.where(Conversation.user_id == user.id)

    if not include_archived:
        query = query.where(Conversation.archived_at.is_(None))

    if sort == "created_desc":
        query = query.order_by(Conversation.created_at.desc())
    else:
        query = query.order_by(Conversation.updated_at.desc())

    # In-memory tag / folder filter on JSON metadata if requested
    all_convs = db.scalars(query).all()
    filtered: list[Conversation] = []
    for c in all_convs:
        meta = c.metadata_json or {}
        if folder and meta.get("folder") != folder:
            continue
        if tag and tag not in meta.get("tags", []):
            continue
        filtered.append(c)

    total = len(filtered)
    page_convs = filtered[offset : offset + limit]

    return {
        "conversations": page_convs,
        "total": total,
        "limit": limit,
        "offset": offset,
    }


@conv_router.get("/conversations/search")
def search_conversations(
    q: str = Query(..., min_length=1, description="Keyword or semantic search query"),
    limit: int = Query(default=10, ge=1, le=50),
    include_archived: bool = Query(default=False),
    db: Session = Depends(get_db),
    user: User | None = Depends(get_optional_user),
) -> dict:
    """
    Hybrid Search: Combines keyword search on titles/messages with dense vector similarity.
    """
    clean_q = q.strip().lower()
    query_vec = generate_text_embedding(clean_q)

    # Base query for messages
    msg_query = (
        select(Message, Conversation)
        .join(Conversation, Message.conversation_id == Conversation.id)
        .where(Message.is_deleted == False)  # noqa: E712
    )

    if user:
        msg_query = msg_query.where(Conversation.user_id == user.id)
    if not include_archived:
        msg_query = msg_query.where(Conversation.archived_at.is_(None))

    rows = db.execute(msg_query.order_by(desc(Message.created_at)).limit(200)).all()

    scored_results: list[dict] = []
    seen_convs: set[str] = set()

    for msg, conv in rows:
        content_lower = (msg.content or "").lower()
        title_lower = (conv.title or "").lower()

        # Keyword match boost
        keyword_score = 0.0
        if clean_q in title_lower:
            keyword_score += 0.6
        if clean_q in content_lower:
            keyword_score += 0.4

        # Semantic cosine similarity score
        emb = msg.embedding or generate_text_embedding(msg.content)
        vector_score = cosine_similarity(query_vec, emb)

        # Combined reciprocal hybrid score
        hybrid_score = round((keyword_score * 0.5) + (vector_score * 0.5), 4)

        if hybrid_score > 0.15:
            scored_results.append({
                "conversation_id": conv.id,
                "conversation_title": conv.title,
                "message_id": msg.id,
                "role": msg.role,
                "sequence_number": msg.sequence_number,
                "matching_excerpt": msg.content[:200] + ("..." if len(msg.content) > 200 else ""),
                "score": hybrid_score,
                "updated_at": conv.updated_at.isoformat() if conv.updated_at else None,
            })
            seen_convs.add(conv.id)

    scored_results.sort(key=lambda x: x["score"], reverse=True)
    return {
        "query": q,
        "results_count": len(scored_results[:limit]),
        "unique_conversations": len(seen_convs),
        "results": scored_results[:limit],
    }


@conv_router.get("/conversations/{conversation_id}", response_model=ConversationRead)
def get_conversation(
    conversation_id: str,
    db: Session = Depends(get_db),
    user: User | None = Depends(get_optional_user),
) -> Conversation:
    """Retrieve conversation details by ID."""
    conv = ConversationService.get_conversation(db, conversation_id)
    if not conv:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")
    if user and conv.user_id and conv.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")
    return conv


@conv_router.patch("/conversations/{conversation_id}", response_model=ConversationRead)
def update_conversation(
    conversation_id: str,
    payload: ConversationUpdate,
    db: Session = Depends(get_db),
    user: User | None = Depends(get_optional_user),
) -> Conversation:
    """Update conversation metadata, title, system prompt, or flag."""
    conv = ConversationService.get_conversation(db, conversation_id)
    if not conv:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")
    if user and conv.user_id and conv.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")

    if payload.title is not None:
        conv.title = payload.title
    if payload.model_used is not None:
        conv.model_used = payload.model_used
    if payload.system_prompt is not None:
        conv.system_prompt = payload.system_prompt
    if payload.is_flagged is not None:
        conv.is_flagged = payload.is_flagged
    if payload.metadata is not None:
        meta = dict(conv.metadata_json or {})
        meta.update(payload.metadata)
        conv.metadata_json = meta

    conv.updated_at = datetime.utcnow()
    conv.version += 1
    db.commit()
    db.refresh(conv)
    return conv


@conv_router.get("/conversations/{conversation_id}/history", response_model=ConversationHistoryResponse)
def get_conversation_history(
    conversation_id: str,
    limit: int = Query(default=50, ge=1, le=100),
    before_seq: int | None = Query(default=None, description="Fetch turns prior to this sequence number"),
    db: Session = Depends(get_db),
    user: User | None = Depends(get_optional_user),
) -> dict:
    """Retrieve chronological message turns with cursor pagination and latest summary."""
    conv = ConversationService.get_conversation(db, conversation_id)
    if not conv:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")
    if user and conv.user_id and conv.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")

    query = (
        select(Message)
        .where(Message.conversation_id == conversation_id, Message.is_deleted == False)  # noqa: E712
    )

    if before_seq is not None:
        query = query.where(Message.sequence_number < before_seq)

    query = query.order_by(Message.sequence_number.asc()).limit(limit + 1)
    messages = list(db.scalars(query).all())

    has_more = len(messages) > limit
    if has_more:
        messages = messages[:limit]

    next_cursor = str(messages[-1].sequence_number) if messages and has_more else None

    # Fetch latest summary
    summary = db.scalar(
        select(ConversationSummary)
        .where(ConversationSummary.conversation_id == conversation_id)
        .order_by(desc(ConversationSummary.end_sequence_number))
    )

    total_count = db.scalar(
        select(func.count(Message.id))
        .where(Message.conversation_id == conversation_id, Message.is_deleted == False)  # noqa: E712
    ) or 0

    return {
        "conversation_id": conversation_id,
        "messages": messages,
        "summary": summary,
        "total_count": total_count,
        "has_more": has_more,
        "next_cursor": next_cursor,
    }


@conv_router.post("/conversations/{conversation_id}/messages", response_model=MessageRead, status_code=status.HTTP_201_CREATED)
def add_message_turn(
    conversation_id: str,
    payload: MessageCreate,
    expected_version: int | None = Query(default=None, description="Optimistic locking version number"),
    db: Session = Depends(get_db),
    user: User | None = Depends(get_optional_user),
) -> Message:
    """Add a message turn atomically with sequence ordering and OCC validation."""
    conv = ConversationService.get_conversation(db, conversation_id)
    if not conv:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")
    if user and conv.user_id and conv.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")

    try:
        return ConversationService.add_message(
            db=db,
            conversation_id=conversation_id,
            role=payload.role,
            content=payload.content,
            expected_version=expected_version,
            metadata=payload.metadata,
        )
    except ConcurrencyConflictError as err:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(err))


@conv_router.post("/conversations/{conversation_id}/branch", response_model=ConversationRead, status_code=status.HTTP_201_CREATED)
def branch_conversation(
    conversation_id: str,
    payload: ConversationBranchRequest,
    db: Session = Depends(get_db),
    user: User | None = Depends(get_optional_user),
) -> Conversation:
    """Fork conversation from a specific historical message turn."""
    conv = ConversationService.get_conversation(db, conversation_id)
    if not conv:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")
    if user and conv.user_id and conv.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")

    try:
        return ConversationService.branch_conversation(
            db=db,
            conversation_id=conversation_id,
            branch_from_message_id=payload.branch_from_message_id,
            new_title=payload.title,
            model_used=payload.model_used,
        )
    except ValueError as err:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(err))


@conv_router.post("/conversations/{conversation_id}/summarize", response_model=ConversationSummaryRead)
def trigger_summarization(
    conversation_id: str,
    preserve_recent_turns: int = Query(default=12, ge=4, le=50),
    db: Session = Depends(get_db),
    user: User | None = Depends(get_optional_user),
) -> ConversationSummary:
    """Trigger recursive compaction / summarization of older conversational turns."""
    conv = ConversationService.get_conversation(db, conversation_id)
    if not conv:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")
    if user and conv.user_id and conv.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")

    summary = SummarizationService.execute_summarization(
        db=db,
        conversation_id=conversation_id,
        preserve_recent_turns=preserve_recent_turns,
    )
    if not summary:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No eligible messages found to summarize (below threshold).",
        )
    return summary


@conv_router.get("/conversations/{conversation_id}/export", response_model=ConversationExportResponse)
def export_conversation(
    conversation_id: str,
    format: Literal["json", "markdown", "csv"] = Query(default="json"),
    db: Session = Depends(get_db),
    user: User | None = Depends(get_optional_user),
) -> dict:
    """Export complete conversation state into JSON, Markdown, or CSV."""
    conv = ConversationService.get_conversation(db, conversation_id)
    if not conv:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")
    if user and conv.user_id and conv.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")

    exported_content = ConversationService.export_conversation(db, conversation_id, export_format=format)
    return {
        "conversation_id": conversation_id,
        "format": format,
        "exported_at": datetime.utcnow(),
        "content": exported_content,
    }


@conv_router.post("/conversations/{conversation_id}/archive", response_model=ConversationRead)
def archive_conversation(
    conversation_id: str,
    db: Session = Depends(get_db),
    user: User | None = Depends(get_optional_user),
) -> Conversation:
    """Archive a conversation and compress old message turns."""
    conv = ConversationService.get_conversation(db, conversation_id)
    if not conv:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")
    if user and conv.user_id and conv.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")

    return ConversationService.archive_conversation(db, conversation_id, compress=True)


@conv_router.post("/conversations/{conversation_id}/unarchive", response_model=ConversationRead)
def unarchive_conversation(
    conversation_id: str,
    db: Session = Depends(get_db),
    user: User | None = Depends(get_optional_user),
) -> Conversation:
    """Restore an archived conversation and decompress message turns."""
    conv = ConversationService.get_conversation(db, conversation_id)
    if not conv:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")
    if user and conv.user_id and conv.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")

    return ConversationService.unarchive_conversation(db, conversation_id)


# ---------------------------------------------------------------------------
# Message Endpoints
# ---------------------------------------------------------------------------

@conv_router.get("/messages/{message_id}", response_model=MessageRead)
def get_message(
    message_id: str,
    db: Session = Depends(get_db),
) -> Message:
    """Retrieve message details by ID."""
    msg = db.scalar(select(Message).where(Message.id == message_id))
    if not msg or msg.is_deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Message not found")
    return msg


@conv_router.patch("/messages/{message_id}", response_model=MessageRead)
def edit_message(
    message_id: str,
    payload: MessageUpdate,
    db: Session = Depends(get_db),
) -> Message:
    """Edit message with revision check."""
    try:
        return ConversationService.edit_message(
            db=db,
            message_id=message_id,
            new_content=payload.content,
            expected_revision=payload.revision,
        )
    except ConcurrencyConflictError as err:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(err))
    except ValueError as err:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(err))


@conv_router.delete("/messages/{message_id}", response_model=dict)
def delete_message(
    message_id: str,
    db: Session = Depends(get_db),
) -> dict:
    """Soft-delete message."""
    try:
        ConversationService.soft_delete_message(db, message_id)
        return {"data": {"id": message_id, "status": "deleted", "deleted_at": datetime.utcnow().isoformat()}}
    except ValueError as err:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(err))
