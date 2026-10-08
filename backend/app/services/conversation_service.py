import csv
import io
import json
import logging
import uuid
import zlib
from datetime import datetime, timedelta
from typing import Any, Literal
from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session

from app.models.conversation import Conversation, ConversationSummary, Message
from app.services.context_manager import estimate_tokens, generate_text_embedding

logger = logging.getLogger("shopsense.conversation_service")

# Approximate pricing per 1K tokens for cost tracking ($/1K tokens)
MODEL_PRICING: dict[str, dict[str, float]] = {
    "default": {"prompt": 0.0015, "completion": 0.002},
    "gpt-4o": {"prompt": 0.0025, "completion": 0.010},
    "gpt-4o-mini": {"prompt": 0.00015, "completion": 0.0006},
    "claude-3-5-sonnet": {"prompt": 0.003, "completion": 0.015},
    "claude-3-haiku": {"prompt": 0.00025, "completion": 0.00125},
}


class ConcurrencyConflictError(Exception):
    """Raised when an optimistic concurrency check fails."""
    pass


class ConversationService:
    @staticmethod
    def create_conversation(
        db: Session,
        user_id: int | None = None,
        title: str | None = None,
        model_used: str = "gpt-4o",
        system_prompt: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> Conversation:
        """Create a new stateful conversation session."""
        conv_title = title or "New Conversation"
        meta = metadata or {"tags": [], "folder": "default", "custom_fields": {}}
        conv = Conversation(
            user_id=user_id,
            title=conv_title,
            model_used=model_used,
            system_prompt=system_prompt,
            metadata_json=meta,
            version=1,
        )
        db.add(conv)
        db.commit()
        db.refresh(conv)
        return conv

    @staticmethod
    def get_conversation(db: Session, conversation_id: str) -> Conversation | None:
        """Retrieve conversation by ID."""
        return db.scalar(select(Conversation).where(Conversation.id == conversation_id))

    @staticmethod
    def add_message(
        db: Session,
        conversation_id: str,
        role: Literal["user", "assistant", "system", "tool"],
        content: str,
        expected_version: int | None = None,
        tokens_prompt: int = 0,
        tokens_completion: int = 0,
        metadata: dict[str, Any] | None = None,
    ) -> Message:
        """
        Add a message turn atomically with sequence numbers, token accounting,
        and optimistic concurrency validation.
        """
        conv = db.scalar(select(Conversation).where(Conversation.id == conversation_id))
        if not conv:
            raise ValueError(f"Conversation {conversation_id} not found")

        # Concurrency verification (Optimistic Concurrency Control)
        if expected_version is not None and conv.version != expected_version:
            raise ConcurrencyConflictError(
                f"Conversation version conflict: current={conv.version}, expected={expected_version}"
            )

        # Atomic sequence number calculation
        current_max_seq = db.scalar(
            select(func.max(Message.sequence_number)).where(Message.conversation_id == conversation_id)
        ) or 0
        next_seq = current_max_seq + 1

        # Token calculation
        calculated_tokens = estimate_tokens(content)
        t_prompt = tokens_prompt or (calculated_tokens if role == "user" else 0)
        t_completion = tokens_completion or (calculated_tokens if role == "assistant" else 0)
        t_total = t_prompt + t_completion

        # Embedding generation
        embedding_vec = generate_text_embedding(content)

        msg_meta = metadata or {}
        msg_meta.setdefault("revision", 1)
        msg_meta.setdefault("status", "completed")

        message = Message(
            conversation_id=conversation_id,
            sequence_number=next_seq,
            role=role,
            content=content,
            tokens_prompt=t_prompt,
            tokens_completion=t_completion,
            tokens_total=t_total,
            embedding=embedding_vec,
            metadata_json=msg_meta,
        )
        db.add(message)

        # Update conversation rollups
        pricing = MODEL_PRICING.get(conv.model_used, MODEL_PRICING["default"])
        cost = (t_prompt / 1000.0 * pricing["prompt"]) + (t_completion / 1000.0 * pricing["completion"])

        conv.total_messages += 1
        conv.total_tokens_used += t_total
        conv.total_cost_usd += cost
        conv.version += 1
        conv.updated_at = datetime.utcnow()

        # Auto-title generation trigger if title is default and turn count is reached
        if conv.title == "New Conversation" and role == "user" and next_seq in (1, 2, 3):
            ConversationService._auto_generate_title(conv, content)

        db.commit()
        db.refresh(message)
        db.refresh(conv)
        return message

    @staticmethod
    def _auto_generate_title(conv: Conversation, user_message: str) -> None:
        """Lightweight heuristic title generation — retains all meaningful words."""
        stop = {"i", "a", "an", "the", "for", "to", "do", "of", "is", "in", "at", "on", "and", "or", "am", "are"}
        words = user_message.strip().split()
        meaningful = [w for w in words if w.lower() not in stop]
        candidates = meaningful[:8] if meaningful else words[:6]
        candidate = " ".join(candidates)
        if len(candidate) > 50:
            candidate = candidate[:47] + "..."
        conv.title = candidate.title()  # Title Case for readability

    @staticmethod
    def branch_conversation(
        db: Session,
        conversation_id: str,
        branch_from_message_id: str,
        new_title: str | None = None,
        model_used: str | None = None,
    ) -> Conversation:
        """
        Create a new branch (fork) stemming from a specific historical message.
        Copies history up to branch point for seamless DAG continuity.
        """
        source_conv = db.scalar(select(Conversation).where(Conversation.id == conversation_id))
        if not source_conv:
            raise ValueError(f"Source conversation {conversation_id} not found")

        branch_msg = db.scalar(select(Message).where(Message.id == branch_from_message_id))
        if not branch_msg or branch_msg.conversation_id != conversation_id:
            raise ValueError(f"Branch message {branch_from_message_id} not found in conversation {conversation_id}")

        cutoff_seq = branch_msg.sequence_number

        # Create child branched conversation
        fork_title = new_title or f"{source_conv.title} (Branch @ #{cutoff_seq})"
        new_conv = Conversation(
            user_id=source_conv.user_id,
            title=fork_title,
            model_used=model_used or source_conv.model_used,
            system_prompt=source_conv.system_prompt,
            parent_conversation_id=source_conv.id,
            branch_point_message_id=branch_from_message_id,
            metadata_json={"tags": ["branch"], "forked_from": conversation_id, "branch_sequence": cutoff_seq},
            version=1,
        )
        db.add(new_conv)
        db.flush()

        # Copy ancestor turns up to cutoff sequence into the new branch
        ancestor_messages: list[Message] = db.scalars(
            select(Message)
            .where(
                Message.conversation_id == conversation_id,
                Message.sequence_number <= cutoff_seq,
                Message.is_deleted == False,  # noqa: E712
            )
            .order_by(Message.sequence_number.asc())
        ).all()

        total_tokens = 0
        for orig in ancestor_messages:
            cloned = Message(
                conversation_id=new_conv.id,
                parent_message_id=orig.id,
                sequence_number=orig.sequence_number,
                role=orig.role,
                content=orig.content,
                tokens_prompt=orig.tokens_prompt,
                tokens_completion=orig.tokens_completion,
                tokens_total=orig.tokens_total,
                embedding=orig.embedding,
                metadata_json=orig.metadata_json,
            )
            db.add(cloned)
            total_tokens += orig.tokens_total

        new_conv.total_messages = len(ancestor_messages)
        new_conv.total_tokens_used = total_tokens
        db.commit()
        db.refresh(new_conv)
        return new_conv

    @staticmethod
    def archive_conversation(db: Session, conversation_id: str, compress: bool = True) -> Conversation:
        """
        Archive a conversation and optionally compress old message content with zlib
        to minimize storage overhead.
        """
        conv = db.scalar(select(Conversation).where(Conversation.id == conversation_id))
        if not conv:
            raise ValueError(f"Conversation {conversation_id} not found")

        conv.archived_at = datetime.utcnow()
        conv.version += 1

        if compress:
            messages: list[Message] = db.scalars(
                select(Message).where(Message.conversation_id == conversation_id)
            ).all()
            for msg in messages:
                if msg.content and not msg.content_compressed:
                    # Compress UTF-8 content with zlib
                    msg.content_compressed = zlib.compress(msg.content.encode("utf-8"))

        db.commit()
        db.refresh(conv)
        return conv

    @staticmethod
    def unarchive_conversation(db: Session, conversation_id: str) -> Conversation:
        """Restore an archived conversation and decompress content."""
        conv = db.scalar(select(Conversation).where(Conversation.id == conversation_id))
        if not conv:
            raise ValueError(f"Conversation {conversation_id} not found")

        conv.archived_at = None
        conv.version += 1

        messages: list[Message] = db.scalars(
            select(Message).where(Message.conversation_id == conversation_id)
        ).all()
        for msg in messages:
            if msg.content_compressed:
                try:
                    decompressed = zlib.decompress(msg.content_compressed).decode("utf-8")
                    msg.content = decompressed
                except Exception as err:
                    logger.warning(f"Error decompressing message {msg.id}: {err}")

        db.commit()
        db.refresh(conv)
        return conv

    @staticmethod
    def auto_archive_inactive(db: Session, inactive_days: int = 90) -> int:
        """Scan and automatically archive conversations inactive for > N days."""
        cutoff_date = datetime.utcnow() - timedelta(days=inactive_days)
        candidates: list[Conversation] = db.scalars(
            select(Conversation).where(
                Conversation.archived_at.is_(None),
                Conversation.updated_at < cutoff_date,
            )
        ).all()

        archived_count = 0
        for conv in candidates:
            ConversationService.archive_conversation(db, conv.id, compress=True)
            archived_count += 1

        return archived_count

    @staticmethod
    def edit_message(
        db: Session,
        message_id: str,
        new_content: str,
        expected_revision: int,
    ) -> Message:
        """Edit message with revision check."""
        msg = db.scalar(select(Message).where(Message.id == message_id))
        if not msg:
            raise ValueError(f"Message {message_id} not found")

        current_rev = msg.metadata_json.get("revision", 1)
        if expected_revision != current_rev:
            raise ConcurrencyConflictError(
                f"Message revision conflict: current={current_rev}, expected={expected_revision}"
            )

        msg.content = new_content
        msg.edited_at = datetime.utcnow()
        meta = dict(msg.metadata_json)
        meta["revision"] = current_rev + 1
        meta["dependent_responses"] = "stale"
        msg.metadata_json = meta
        msg.tokens_prompt = estimate_tokens(new_content) if msg.role == "user" else 0
        msg.tokens_completion = estimate_tokens(new_content) if msg.role == "assistant" else 0
        msg.tokens_total = msg.tokens_prompt + msg.tokens_completion
        msg.embedding = generate_text_embedding(new_content)

        db.commit()
        db.refresh(msg)
        return msg

    @staticmethod
    def soft_delete_message(db: Session, message_id: str) -> Message:
        """Soft delete a message while retaining sequence ordering."""
        msg = db.scalar(select(Message).where(Message.id == message_id))
        if not msg:
            raise ValueError(f"Message {message_id} not found")

        msg.is_deleted = True
        meta = dict(msg.metadata_json)
        meta["status"] = "deleted"
        msg.metadata_json = meta
        db.commit()
        db.refresh(msg)
        return msg

    @staticmethod
    def export_conversation(
        db: Session,
        conversation_id: str,
        export_format: Literal["json", "markdown", "csv"] = "json",
    ) -> str:
        """Export conversation history into requested format."""
        conv = db.scalar(select(Conversation).where(Conversation.id == conversation_id))
        if not conv:
            raise ValueError(f"Conversation {conversation_id} not found")

        messages: list[Message] = db.scalars(
            select(Message)
            .where(Message.conversation_id == conversation_id)
            .order_by(Message.sequence_number.asc())
        ).all()

        # Ensure content is uncompressed
        for m in messages:
            if not m.content and m.content_compressed:
                m.content = zlib.decompress(m.content_compressed).decode("utf-8")

        summary = db.scalar(
            select(ConversationSummary)
            .where(ConversationSummary.conversation_id == conversation_id)
            .order_by(desc(ConversationSummary.end_sequence_number))
        )

        if export_format == "json":
            export_obj = {
                "id": conv.id,
                "title": conv.title,
                "model_used": conv.model_used,
                "system_prompt": conv.system_prompt,
                "created_at": conv.created_at.isoformat() if conv.created_at else None,
                "updated_at": conv.updated_at.isoformat() if conv.updated_at else None,
                "total_messages": conv.total_messages,
                "total_tokens_used": conv.total_tokens_used,
                "total_cost_usd": conv.total_cost_usd,
                "summary": summary.summary_text if summary else None,
                "messages": [
                    {
                        "id": m.id,
                        "sequence_number": m.sequence_number,
                        "role": m.role,
                        "content": m.content,
                        "tokens": m.tokens_total,
                        "created_at": m.created_at.isoformat() if m.created_at else None,
                        "edited_at": m.edited_at.isoformat() if m.edited_at else None,
                        "is_deleted": m.is_deleted,
                    }
                    for m in messages
                ],
            }
            return json.dumps(export_obj, indent=2)

        elif export_format == "markdown":
            md_lines = [
                f"# Conversation: {conv.title}",
                f"- **Model**: {conv.model_used}",
                f"- **Created At**: {conv.created_at}",
                f"- **Total Turns**: {conv.total_messages}",
                f"- **Total Tokens**: {conv.total_tokens_used}",
                f"- **Estimated Cost**: ${conv.total_cost_usd:.4f}",
                "",
            ]
            if summary:
                md_lines.extend([
                    "## Running Summary",
                    summary.summary_text,
                    "",
                ])
            md_lines.append("## Transcript\n")
            for m in messages:
                if m.is_deleted:
                    continue
                role_label = m.role.upper()
                md_lines.append(f"### [#{m.sequence_number}] {role_label} ({m.created_at})")
                md_lines.append(m.content)
                md_lines.append("")
            return "\n".join(md_lines)

        elif export_format == "csv":
            output = io.StringIO()
            writer = csv.writer(output)
            writer.writerow(["sequence_number", "role", "content", "tokens_total", "created_at", "is_deleted"])
            for m in messages:
                writer.writerow([m.sequence_number, m.role, m.content, m.tokens_total, m.created_at, m.is_deleted])
            return output.getvalue()

        else:
            raise ValueError(f"Unsupported format: {export_format}")
