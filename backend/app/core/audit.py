import logging
import secrets
import time
from collections import deque
from datetime import datetime, timezone
from typing import Any, Deque, Dict, List, Optional
from pydantic import BaseModel, Field

logger = logging.getLogger("security.audit")


class AuditEvent(BaseModel):
    event_id: str = Field(default_factory=lambda: f"evt_{secrets.token_hex(12)}")
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    event_type: str
    user_id: Optional[int] = None
    email: Optional[str] = None
    tier: Optional[str] = None
    endpoint: Optional[str] = None
    http_method: Optional[str] = None
    required_scope: Optional[str] = None
    assigned_scopes: Optional[List[str]] = None
    reason: str
    details: Dict[str, Any] = Field(default_factory=dict)


class SecurityAuditLogger:
    """
    Structured security audit logger with an in-memory buffer for real-time
    monitoring and forensic scenario testing.
    """

    def __init__(self, max_buffer_size: int = 1000):
        self._buffer: Deque[AuditEvent] = deque(maxlen=max_buffer_size)

    def log(self, event: AuditEvent) -> None:
        self._buffer.append(event)
        logger.warning(
            f"[SECURITY AUDIT] {event.event_type.upper()} | user_id={event.user_id} "
            f"tier={event.tier} reason={event.reason} details={event.details}"
        )

    def log_denied_access(
        self,
        user_id: Optional[int],
        email: Optional[str],
        tier: Optional[str],
        required_scope: str,
        assigned_scopes: List[str],
        reason: str,
        endpoint: Optional[str] = None,
    ) -> AuditEvent:
        event = AuditEvent(
            event_type="denied_access",
            user_id=user_id,
            email=email,
            tier=tier,
            endpoint=endpoint,
            required_scope=required_scope,
            assigned_scopes=assigned_scopes,
            reason=reason,
        )
        self.log(event)
        return event

    def log_quota_exceeded(
        self,
        user_id: int,
        email: str,
        tier: str,
        metric: str,
        limit: int,
        current_usage: int,
        requested: int,
    ) -> AuditEvent:
        event = AuditEvent(
            event_type="quota_exceeded",
            user_id=user_id,
            email=email,
            tier=tier,
            reason=f"{metric}_exceeded",
            details={
                "metric": metric,
                "limit": limit,
                "current_usage": current_usage,
                "requested": requested,
            },
        )
        self.log(event)
        return event

    def get_events(
        self,
        event_type: Optional[str] = None,
        user_id: Optional[int] = None,
    ) -> List[AuditEvent]:
        events = list(self._buffer)
        if event_type:
            events = [e for e in events if e.event_type == event_type]
        if user_id is not None:
            events = [e for e in events if e.user_id == user_id]
        return events

    def clear(self) -> None:
        self._buffer.clear()


audit_logger = SecurityAuditLogger()
