import hashlib
import json
import logging
import math
import re
from typing import Any
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.models.conversation import Conversation, ConversationSummary, Message

logger = logging.getLogger("shopsense.context_manager")

# Model default context window capacities
MODEL_CONTEXT_LIMITS: dict[str, int] = {
    "default": 8192,
    "gpt-3.5-turbo": 16385,
    "gpt-4": 8192,
    "gpt-4-turbo": 128000,
    "gpt-4o": 128000,
    "gpt-4o-mini": 128000,
    "claude-3-haiku": 100000,
    "claude-3-sonnet": 100000,
    "claude-3-5-sonnet": 200000,
    "claude-3-opus": 200000,
    "mistral-7b": 32768,
    "llama-3-8b": 8192,
    "llama-3-70b": 8192,
}


def estimate_tokens(text: str | None) -> int:
    """Fast, reliable token estimation across languages and code blocks (~3.8 chars/token)."""
    if not text:
        return 0
    # Words + punctuation heuristics
    words = len(text.split())
    chars = len(text)
    token_est = int(math.ceil(max(words * 1.3, chars / 3.8)))
    return max(1, token_est)


def cosine_similarity(vec_a: list[float], vec_b: list[float]) -> float:
    """Compute cosine similarity between two float vectors."""
    if not vec_a or not vec_b or len(vec_a) != len(vec_b):
        return 0.0
    dot_product = sum(a * b for a, b in zip(vec_a, vec_b))
    norm_a = math.sqrt(sum(a * a for a in vec_a))
    norm_b = math.sqrt(sum(b * b for b in vec_b))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return dot_product / (norm_a * norm_b)


def generate_text_embedding(text: str, dimensions: int = 128) -> list[float]:
    """Deterministic hash-based dense embedding fallback for local/test vector search."""
    tokens = re.findall(r"\w+", text.lower())
    if not tokens:
        return [0.0] * dimensions

    vec = [0.0] * dimensions
    for token in tokens:
        digest = hashlib.sha256(token.encode("utf-8")).digest()
        for idx in range(dimensions):
            byte_val = digest[idx % len(digest)]
            vec[idx] += (byte_val / 128.0) - 1.0

    # L2 normalize
    norm = math.sqrt(sum(v * v for v in vec))
    if norm > 0:
        vec = [round(v / norm, 5) for v in vec]
    return vec


class ContextWindowManager:
    def __init__(
        self,
        model_name: str = "default",
        max_context_tokens: int | None = None,
        sliding_window_size: int = 15,
        summarization_threshold: float = 0.70,
        response_reserve_tokens: int = 1500,
    ):
        self.model_name = model_name
        self.max_tokens = max_context_tokens or MODEL_CONTEXT_LIMITS.get(model_name, 8192)
        self.sliding_window_size = sliding_window_size
        self.summarization_threshold = summarization_threshold
        self.response_reserve_tokens = response_reserve_tokens
        # Working budget for inputs (history, summary, system prompt, current turn)
        self.working_budget = max(1000, self.max_tokens - self.response_reserve_tokens)

    def assemble_conversation_context(
        self,
        db: Session,
        conversation_id: str,
        current_query: str,
        system_prompt: str | None = None,
        include_semantic_search: bool = True,
    ) -> dict[str, Any]:
        """
        Assemble the optimal LLM context window using:
        1. Base system prompt
        2. Latest incremental summary (if any)
        3. Relevant past turns outside window (via vector similarity)
        4. Contiguous recent sliding window turns
        5. Current user query
        """
        conversation = db.scalar(select(Conversation).where(Conversation.id == conversation_id))
        if not conversation:
            raise ValueError(f"Conversation {conversation_id} not found")

        sys_prompt = system_prompt or conversation.system_prompt or "You are a helpful AI assistant."
        sys_tokens = estimate_tokens(sys_prompt)
        query_tokens = estimate_tokens(current_query)

        # 1. Fetch latest summary
        latest_summary = db.scalar(
            select(ConversationSummary)
            .where(ConversationSummary.conversation_id == conversation_id)
            .order_by(desc(ConversationSummary.end_sequence_number))
        )
        summary_text = latest_summary.summary_text if latest_summary else ""
        summary_tokens = latest_summary.summary_token_count if latest_summary else 0
        summary_end_seq = latest_summary.end_sequence_number if latest_summary else 0

        # 2. Fetch all active messages in chronological order
        all_messages: list[Message] = db.scalars(
            select(Message)
            .where(Message.conversation_id == conversation_id, Message.is_deleted == False)  # noqa: E712
            .order_by(Message.sequence_number.asc())
        ).all()

        total_message_count = len(all_messages)

        # 3. Partition into sliding window (most recent turns) and older turns
        if total_message_count <= self.sliding_window_size:
            sliding_messages = all_messages
            older_messages = []
        else:
            sliding_messages = all_messages[-self.sliding_window_size:]
            older_messages = all_messages[:-self.sliding_window_size]

        sliding_seq_start = sliding_messages[0].sequence_number if sliding_messages else 1
        sliding_tokens = sum(m.tokens_total or estimate_tokens(m.content) for m in sliding_messages)

        # 4. Semantic search for relevant past messages from older messages
        semantic_retrieved: list[dict[str, Any]] = []
        semantic_tokens = 0
        if include_semantic_search and older_messages and len(current_query.strip()) > 8:
            query_embedding = generate_text_embedding(current_query)
            scored_candidates: list[tuple[float, Message]] = []
            for msg in older_messages:
                # Exclude turns already covered in the active sliding window
                if msg.sequence_number >= sliding_seq_start:
                    continue
                if not msg.embedding:
                    msg.embedding = generate_text_embedding(msg.content)
                    db.add(msg)
                score = cosine_similarity(query_embedding, msg.embedding)
                if score > 0.45:  # Relevance threshold
                    scored_candidates.append((score, msg))

            scored_candidates.sort(key=lambda x: x[0], reverse=True)
            for score, msg in scored_candidates[:3]:
                msg_tokens = msg.tokens_total or estimate_tokens(msg.content)
                semantic_retrieved.append({
                    "id": msg.id,
                    "sequence_number": msg.sequence_number,
                    "role": msg.role,
                    "content": msg.content,
                    "similarity": round(score, 4),
                    "tokens": msg_tokens,
                })
                semantic_tokens += msg_tokens

        # 5. Check if summarization is needed for older messages
        needs_summarization = False
        unsummarized_older = [
            m for m in older_messages if m.sequence_number > summary_end_seq
        ]
        total_estimated = sys_tokens + summary_tokens + semantic_tokens + sliding_tokens + query_tokens

        if total_estimated > (self.working_budget * self.summarization_threshold) or len(unsummarized_older) >= 10:
            needs_summarization = True

        # 6. Assemble LLM prompt messages payload
        assembled_messages: list[dict[str, str]] = []

        # System prompt with summary and relevant context injections
        enriched_system_prompt = sys_prompt
        if summary_text:
            enriched_system_prompt += f"\n\n[CONVERSATION RUNNING SUMMARY OF EARLIER TURNS]:\n{summary_text}"
        if semantic_retrieved:
            relevant_excerpts = "\n".join(
                f"- [Turn #{item['sequence_number']} - {item['role']}]: {item['content']}"
                for item in semantic_retrieved
            )
            enriched_system_prompt += f"\n\n[RELEVANT HISTORICAL EXCERPTS]:\n{relevant_excerpts}"

        assembled_messages.append({"role": "system", "content": enriched_system_prompt})

        # Append recent sliding window messages
        for msg in sliding_messages:
            assembled_messages.append({"role": msg.role, "content": msg.content})

        # Append current user query
        assembled_messages.append({"role": "user", "content": current_query})

        # Emergency trim if assembled payload still exceeds working budget
        final_tokens = estimate_tokens(json.dumps(assembled_messages))
        if final_tokens > self.working_budget:
            logger.warning(
                f"Context budget exceeded ({final_tokens} > {self.working_budget}). Trimming oldest sliding messages."
            )
            while len(sliding_messages) > 4 and final_tokens > self.working_budget:
                sliding_messages.pop(0)
                assembled_messages = [{"role": "system", "content": enriched_system_prompt}]
                for msg in sliding_messages:
                    assembled_messages.append({"role": msg.role, "content": msg.content})
                assembled_messages.append({"role": "user", "content": current_query})
                final_tokens = estimate_tokens(json.dumps(assembled_messages))

        return {
            "conversation_id": conversation_id,
            "assembled_messages": assembled_messages,
            "metrics": {
                "system_tokens": sys_tokens,
                "summary_tokens": summary_tokens,
                "semantic_tokens": semantic_tokens,
                "sliding_tokens": sliding_tokens,
                "query_tokens": query_tokens,
                "total_estimated_tokens": final_tokens,
                "max_context_tokens": self.max_tokens,
                "working_budget": self.working_budget,
                "utilization_pct": round((final_tokens / self.max_tokens) * 100, 2),
            },
            "sliding_window_message_count": len(sliding_messages),
            "older_unsummarized_count": len(unsummarized_older),
            "needs_summarization": needs_summarization,
            "latest_summary": {
                "id": latest_summary.id,
                "end_sequence_number": latest_summary.end_sequence_number,
                "text": latest_summary.summary_text,
            } if latest_summary else None,
        }


class SummarizationService:
    @staticmethod
    def compress_turns_into_summary(
        previous_summary: str | None,
        messages_to_compress: list[Message],
    ) -> str:
        """
        Compress conversational turns into high-density state points.
        Extracts: Key decisions, user profile attributes, preferences, tasks, and constraints.
        """
        if not messages_to_compress:
            return previous_summary or ""

        # Distill points from candidate messages
        distilled_points: list[str] = []
        for msg in messages_to_compress:
            content_clean = msg.content.strip().replace("\n", " ")
            if len(content_clean) > 120:
                content_clean = content_clean[:117] + "..."
            distilled_points.append(f"Turn #{msg.sequence_number} ({msg.role}): {content_clean}")

        batch_notes = " | ".join(distilled_points)

        if previous_summary:
            updated_summary = f"{previous_summary}\n- [Updates]: {batch_notes}"
        else:
            updated_summary = f"- [Historical Context]: {batch_notes}"

        # Bound summary length to prevent unbounded summary growth
        if len(updated_summary) > 3000:
            lines = updated_summary.split("\n")
            # Keep header and most recent distilled updates
            updated_summary = lines[0] + "\n" + "\n".join(lines[-15:])

        return updated_summary

    @classmethod
    def execute_summarization(
        cls,
        db: Session,
        conversation_id: str,
        preserve_recent_turns: int = 12,
    ) -> ConversationSummary | None:
        """
        Compress non-summarized older turns into a new ConversationSummary record.
        """
        conversation = db.scalar(select(Conversation).where(Conversation.id == conversation_id))
        if not conversation:
            return None

        # Fetch latest summary
        latest_summary = db.scalar(
            select(ConversationSummary)
            .where(ConversationSummary.conversation_id == conversation_id)
            .order_by(desc(ConversationSummary.end_sequence_number))
        )
        last_end_seq = latest_summary.end_sequence_number if latest_summary else 0
        current_version = latest_summary.summary_version if latest_summary else 0

        # Fetch candidate messages to summarize
        max_seq = db.scalar(
            select(Message.sequence_number)
            .where(Message.conversation_id == conversation_id)
            .order_by(desc(Message.sequence_number))
        ) or 0

        cutoff_seq = max(0, max_seq - preserve_recent_turns)
        if cutoff_seq <= last_end_seq:
            # Nothing new to summarize
            return latest_summary

        candidates: list[Message] = db.scalars(
            select(Message)
            .where(
                Message.conversation_id == conversation_id,
                Message.sequence_number > last_end_seq,
                Message.sequence_number <= cutoff_seq,
                Message.is_deleted == False,  # noqa: E712
            )
            .order_by(Message.sequence_number.asc())
        ).all()

        if not candidates:
            return latest_summary

        previous_text = latest_summary.summary_text if latest_summary else None
        new_summary_text = cls.compress_turns_into_summary(previous_text, candidates)

        source_tokens = sum(m.tokens_total or estimate_tokens(m.content) for m in candidates)
        if latest_summary:
            source_tokens += latest_summary.summary_token_count

        summary_tokens = estimate_tokens(new_summary_text)

        first_seq = candidates[0].sequence_number
        last_seq = candidates[-1].sequence_number

        new_summary = ConversationSummary(
            conversation_id=conversation_id,
            summary_text=new_summary_text,
            summary_version=current_version + 1,
            message_range={"first_msg_id": candidates[0].id, "last_msg_id": candidates[-1].id},
            start_sequence_number=latest_summary.start_sequence_number if latest_summary else first_seq,
            end_sequence_number=last_seq,
            source_token_count=source_tokens,
            summary_token_count=summary_tokens,
        )
        db.add(new_summary)
        db.commit()
        db.refresh(new_summary)

        logger.info(
            f"Created summary for conv {conversation_id}: turns {first_seq}..{last_seq}, "
            f"compressed {source_tokens} tokens into {summary_tokens} tokens."
        )
        return new_summary
