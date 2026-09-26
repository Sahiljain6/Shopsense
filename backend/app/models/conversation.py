import uuid
from datetime import datetime
from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Index, Integer, JSON, LargeBinary, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.session import Base


class Conversation(Base):
    __tablename__ = "conversations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True)
    title: Mapped[str] = mapped_column(String(255), default="New Conversation")
    model_used: Mapped[str] = mapped_column(String(64), default="default")
    system_prompt: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, index=True)
    archived_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, default=None, index=True)
    total_messages: Mapped[int] = mapped_column(Integer, default=0)
    total_tokens_used: Mapped[int] = mapped_column(Integer, default=0)
    total_cost_usd: Mapped[float] = mapped_column(Float, default=0.0)
    version: Mapped[int] = mapped_column(Integer, default=1)
    is_flagged: Mapped[bool] = mapped_column(Boolean, default=False)
    parent_conversation_id: Mapped[str | None] = mapped_column(ForeignKey("conversations.id", ondelete="SET NULL"), nullable=True)
    branch_point_message_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    metadata_json: Mapped[dict[str, object]] = mapped_column(JSON, default=lambda: {"tags": [], "folder": "default", "custom_fields": {}})

    messages: Mapped[list["Message"]] = relationship(
        "Message",
        back_populates="conversation",
        cascade="all, delete-orphan",
        order_by="Message.sequence_number"
    )
    summaries: Mapped[list["ConversationSummary"]] = relationship(
        "ConversationSummary",
        back_populates="conversation",
        cascade="all, delete-orphan",
        order_by="ConversationSummary.end_sequence_number"
    )


class Message(Base):
    __tablename__ = "messages"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    conversation_id: Mapped[str] = mapped_column(ForeignKey("conversations.id", ondelete="CASCADE"), index=True)
    parent_message_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    sequence_number: Mapped[int] = mapped_column(Integer, default=1, index=True)
    role: Mapped[str] = mapped_column(String(20), default="user")  # 'user', 'assistant', 'system', 'tool'
    content: Mapped[str] = mapped_column(Text, default="")
    content_compressed: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    tokens_prompt: Mapped[int] = mapped_column(Integer, default=0)
    tokens_completion: Mapped[int] = mapped_column(Integer, default=0)
    tokens_total: Mapped[int] = mapped_column(Integer, default=0)
    embedding: Mapped[list[float] | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    edited_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False)
    metadata_json: Mapped[dict[str, object]] = mapped_column(JSON, default=lambda: {"annotations": [], "sources": [], "tool_calls": [], "revision": 1})

    conversation: Mapped[Conversation] = relationship("Conversation", back_populates="messages")

    __table_args__ = (
        Index("ix_messages_conv_seq", "conversation_id", "sequence_number"),
    )


class ConversationSummary(Base):
    __tablename__ = "conversation_summaries"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    conversation_id: Mapped[str] = mapped_column(ForeignKey("conversations.id", ondelete="CASCADE"), index=True)
    summary_text: Mapped[str] = mapped_column(Text)
    summary_version: Mapped[int] = mapped_column(Integer, default=1)
    message_range: Mapped[dict[str, object]] = mapped_column(JSON, default=dict)
    start_sequence_number: Mapped[int] = mapped_column(Integer, default=1)
    end_sequence_number: Mapped[int] = mapped_column(Integer, default=1)
    source_token_count: Mapped[int] = mapped_column(Integer, default=0)
    summary_token_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    conversation: Mapped[Conversation] = relationship("Conversation", back_populates="summaries")
