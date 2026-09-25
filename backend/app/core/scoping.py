from functools import wraps
from typing import Callable, Optional, Set
from fastapi import Depends, HTTPException, Request, status

from app.core.auth_types import SecurityContext, UserTier, TIER_HIERARCHY, Scope
from app.core.security import get_security_context


class ScopeChecker:
    """FastAPI Dependency for declarative scope checking with 0 DB overhead."""

    def __init__(self, required_scope: str):
        self.required_scope = required_scope

    def __call__(self, context: SecurityContext = Depends(get_security_context)) -> SecurityContext:
        if context.has_scope(self.required_scope):
            return context

        # Import audit dynamically to avoid circular dependencies
        try:
            from app.core.audit import audit_logger
            audit_logger.log_denied_access(
                user_id=context.user_id,
                email=context.email,
                tier=context.tier.value,
                required_scope=self.required_scope,
                assigned_scopes=list(context.scopes),
                reason="insufficient_scope",
            )
        except Exception:
            pass

        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error": "Forbidden",
                "message": f"Requires scope '{self.required_scope}'",
                "required_scope": self.required_scope,
                "current_tier": context.tier.value,
            },
        )


class FeatureFlagChecker:
    """FastAPI Dependency for checking user feature flags (gradual rollout)."""

    def __init__(self, required_flag: str):
        self.required_flag = required_flag

    def __call__(self, context: SecurityContext = Depends(get_security_context)) -> SecurityContext:
        if context.has_feature_flag(self.required_flag):
            return context

        try:
            from app.core.audit import audit_logger
            audit_logger.log_denied_access(
                user_id=context.user_id,
                email=context.email,
                tier=context.tier.value,
                required_scope=f"feature:{self.required_flag}",
                assigned_scopes=list(context.scopes),
                reason="feature_flag_disabled",
            )
        except Exception:
            pass

        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error": "Forbidden",
                "message": f"Feature '{self.required_flag}' is not active on your tier or account",
                "feature_flag": self.required_flag,
            },
        )


class TierChecker:
    """FastAPI Dependency for enforcing role hierarchy (e.g., admin > enterprise > pro > free)."""

    def __init__(self, minimum_tier: UserTier):
        self.minimum_tier = minimum_tier

    def __call__(self, context: SecurityContext = Depends(get_security_context)) -> SecurityContext:
        if context.is_tier_at_least(self.minimum_tier):
            return context

        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error": "Forbidden",
                "message": f"Requires at least '{self.minimum_tier.value}' tier subscription",
                "required_tier": self.minimum_tier.value,
                "current_tier": context.tier.value,
            },
        )


def require_scope(required_scope: str):
    """Convenience helper to declare scope requirement as a dependency."""
    return Depends(ScopeChecker(required_scope))


def require_feature_flag(required_flag: str):
    """Convenience helper to declare feature flag requirement as a dependency."""
    return Depends(FeatureFlagChecker(required_flag))


def require_tier(minimum_tier: UserTier):
    """Convenience helper to declare tier hierarchy requirement as a dependency."""
    return Depends(TierChecker(minimum_tier))
