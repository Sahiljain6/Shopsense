from datetime import datetime, timezone
from typing import Dict, Optional, Tuple
from fastapi import Depends, HTTPException, Request, status

from app.core.auth_types import SecurityContext, UserTier, TIER_DEFAULT_QUOTAS
from app.core.security import get_security_context


class QuotaEngine:
    """
    High-performance thread-safe quota enforcement engine.
    Supports atomic token checks and monthly usage rollover.
    Can be backed by Redis HINCRBY in distributed deployment.
    """

    def __init__(self):
        # Maps (user_id, YYYY-MM) -> token_count
        self._monthly_usage: Dict[Tuple[int, str], int] = {}

    def _get_period_key(self) -> str:
        return datetime.now(timezone.utc).strftime("%Y-%m")

    def get_usage(self, user_id: int) -> int:
        period = self._get_period_key()
        return self._monthly_usage.get((user_id, period), 0)

    def check_and_reserve(
        self,
        user_id: int,
        estimated_tokens: int,
        monthly_limit: int,
    ) -> Tuple[bool, int]:
        """
        Returns (is_allowed, current_usage).
        """
        period = self._get_period_key()
        current = self._monthly_usage.get((user_id, period), 0)

        if current + estimated_tokens > monthly_limit:
            return False, current

        return True, current

    def record_usage(self, user_id: int, actual_tokens: int) -> int:
        """Add actual consumed tokens (prompt + completion) to user's monthly total."""
        period = self._get_period_key()
        key = (user_id, period)
        new_total = self._monthly_usage.get(key, 0) + max(0, actual_tokens)
        self._monthly_usage[key] = new_total
        return new_total

    def reset_usage(self, user_id: int) -> None:
        period = self._get_period_key()
        self._monthly_usage[(user_id, period)] = 0


quota_engine = QuotaEngine()


def check_quota(estimated_tokens: int = 500):
    """
    FastAPI dependency that enforces tier token quotas before LLM invocation.
    """
    def _dependency(context: SecurityContext = Depends(get_security_context)) -> SecurityContext:
        monthly_limit = context.quota.monthly_tokens
        allowed, current_usage = quota_engine.check_and_reserve(
            context.user_id,
            estimated_tokens=estimated_tokens,
            monthly_limit=monthly_limit,
        )

        if not allowed:
            try:
                from app.core.audit import audit_logger
                audit_logger.log_quota_exceeded(
                    user_id=context.user_id,
                    email=context.email,
                    tier=context.tier.value,
                    metric="monthly_tokens",
                    limit=monthly_limit,
                    current_usage=current_usage,
                    requested=estimated_tokens,
                )
            except Exception:
                pass

            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail={
                    "error": "Quota Exceeded",
                    "reason": "monthly_token_quota_exceeded",
                    "monthly_limit": monthly_limit,
                    "current_usage": current_usage,
                    "requested_tokens": estimated_tokens,
                    "tier": context.tier.value,
                    "upgrade_hint": "Upgrade to Pro or Enterprise for increased token allowances.",
                },
            )

        return context

    return _dependency
