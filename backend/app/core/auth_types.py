from enum import Enum
from typing import Any, Dict, List, Optional, Set
from pydantic import BaseModel, Field


class UserTier(str, Enum):
    FREE = "free"
    PRO = "pro"
    ENTERPRISE = "enterprise"
    ADMIN = "admin"


# Role Hierarchy definition: Higher roles inherit all permissions from lower roles
TIER_HIERARCHY: Dict[UserTier, int] = {
    UserTier.FREE: 1,
    UserTier.PRO: 2,
    UserTier.ENTERPRISE: 3,
    UserTier.ADMIN: 4,
}


class Scope(str, Enum):
    # Conversations / Chat
    CONVERSATIONS_CREATE = "conversations:create"
    CONVERSATIONS_READ_OWN = "conversations:read_own"
    CONVERSATIONS_DELETE_OWN = "conversations:delete_own"
    MESSAGES_CREATE = "messages:create"

    # LLM Access
    LLM_QUERY_STANDARD = "llm:query:standard_tier"
    LLM_QUERY_ADVANCED = "llm:query:advanced_tier"
    MODELS_CUSTOM_PARAMS = "models:custom_parameters"
    FILES_UPLOAD_MULTIMODAL = "files:upload_multimodal"
    DATA_EXPORT_OWN = "data:export_own"

    # Enterprise / Org
    WORKSPACE_MANAGE_MEMBERS = "workspace:manage_members"
    RAG_CUSTOM_KB = "rag:custom_knowledge_base"
    ANALYTICS_WORKSPACE = "analytics:workspace_view"
    AUDIT_LOGS_WORKSPACE = "audit_logs:workspace_view"
    SSO_ENFORCE = "sso:enforce"

    # Admin
    ADMIN_ANALYTICS_PLATFORM = "admin:analytics:platform_wide"
    ADMIN_MODERATION_REVIEW = "admin:moderation:review_flagged"
    ADMIN_USERS_MANAGE = "admin:users:manage_tiers"
    ADMIN_SYSTEM_FLAGS = "admin:system:feature_flags"
    ADMIN_QUOTAS_OVERRIDE = "admin:quotas:override"
    ADMIN_ALL = "admin:*"


ROLE_PERMISSIONS: Dict[UserTier, Set[str]] = {
    UserTier.FREE: {
        Scope.CONVERSATIONS_CREATE.value,
        Scope.CONVERSATIONS_READ_OWN.value,
        Scope.CONVERSATIONS_DELETE_OWN.value,
        Scope.MESSAGES_CREATE.value,
        Scope.LLM_QUERY_STANDARD.value,
    },
    UserTier.PRO: {
        Scope.CONVERSATIONS_CREATE.value,
        Scope.CONVERSATIONS_READ_OWN.value,
        Scope.CONVERSATIONS_DELETE_OWN.value,
        Scope.MESSAGES_CREATE.value,
        Scope.LLM_QUERY_STANDARD.value,
        Scope.LLM_QUERY_ADVANCED.value,
        Scope.MODELS_CUSTOM_PARAMS.value,
        Scope.FILES_UPLOAD_MULTIMODAL.value,
        Scope.DATA_EXPORT_OWN.value,
    },
    UserTier.ENTERPRISE: {
        Scope.CONVERSATIONS_CREATE.value,
        Scope.CONVERSATIONS_READ_OWN.value,
        Scope.CONVERSATIONS_DELETE_OWN.value,
        Scope.MESSAGES_CREATE.value,
        Scope.LLM_QUERY_STANDARD.value,
        Scope.LLM_QUERY_ADVANCED.value,
        Scope.MODELS_CUSTOM_PARAMS.value,
        Scope.FILES_UPLOAD_MULTIMODAL.value,
        Scope.DATA_EXPORT_OWN.value,
        Scope.WORKSPACE_MANAGE_MEMBERS.value,
        Scope.RAG_CUSTOM_KB.value,
        Scope.ANALYTICS_WORKSPACE.value,
        Scope.AUDIT_LOGS_WORKSPACE.value,
        Scope.SSO_ENFORCE.value,
    },
    UserTier.ADMIN: {
        Scope.CONVERSATIONS_CREATE.value,
        Scope.CONVERSATIONS_READ_OWN.value,
        Scope.CONVERSATIONS_DELETE_OWN.value,
        Scope.MESSAGES_CREATE.value,
        Scope.LLM_QUERY_STANDARD.value,
        Scope.LLM_QUERY_ADVANCED.value,
        Scope.MODELS_CUSTOM_PARAMS.value,
        Scope.FILES_UPLOAD_MULTIMODAL.value,
        Scope.DATA_EXPORT_OWN.value,
        Scope.WORKSPACE_MANAGE_MEMBERS.value,
        Scope.RAG_CUSTOM_KB.value,
        Scope.ANALYTICS_WORKSPACE.value,
        Scope.AUDIT_LOGS_WORKSPACE.value,
        Scope.SSO_ENFORCE.value,
        Scope.ADMIN_ANALYTICS_PLATFORM.value,
        Scope.ADMIN_MODERATION_REVIEW.value,
        Scope.ADMIN_USERS_MANAGE.value,
        Scope.ADMIN_SYSTEM_FLAGS.value,
        Scope.ADMIN_QUOTAS_OVERRIDE.value,
        Scope.ADMIN_ALL.value,
    },
}


class TierQuotaConfig(BaseModel):
    monthly_tokens: int
    rate_limit_rpm: int
    max_context_window: int


TIER_DEFAULT_QUOTAS: Dict[UserTier, TierQuotaConfig] = {
    UserTier.FREE: TierQuotaConfig(
        monthly_tokens=100_000,
        rate_limit_rpm=20,
        max_context_window=16_000,
    ),
    UserTier.PRO: TierQuotaConfig(
        monthly_tokens=5_000_000,
        rate_limit_rpm=120,
        max_context_window=128_000,
    ),
    UserTier.ENTERPRISE: TierQuotaConfig(
        monthly_tokens=50_000_000,
        rate_limit_rpm=600,
        max_context_window=200_000,
    ),
    UserTier.ADMIN: TierQuotaConfig(
        monthly_tokens=1_000_000_000,
        rate_limit_rpm=10_000,
        max_context_window=200_000,
    ),
}


class SecurityContext(BaseModel):
    user_id: int
    email: str
    tier: UserTier = UserTier.FREE
    org_id: Optional[str] = None
    token_version: int = 1
    scopes: Set[str] = Field(default_factory=set)
    feature_flags: Set[str] = Field(default_factory=set)
    quota: TierQuotaConfig = Field(
        default_factory=lambda: TIER_DEFAULT_QUOTAS[UserTier.FREE]
    )

    def has_scope(self, required_scope: str) -> bool:
        if Scope.ADMIN_ALL.value in self.scopes or self.tier == UserTier.ADMIN:
            return True
        return required_scope in self.scopes

    def has_feature_flag(self, flag: str) -> bool:
        if self.tier == UserTier.ADMIN:
            return True
        return flag in self.feature_flags

    def is_tier_at_least(self, required_tier: UserTier) -> bool:
        return TIER_HIERARCHY.get(self.tier, 0) >= TIER_HIERARCHY.get(required_tier, 0)
