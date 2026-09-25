from typing import Any, Type, TypeVar
from sqlalchemy import Select, select
from sqlalchemy.orm import Session

from app.core.auth_types import SecurityContext, UserTier

T = TypeVar("T")


class ScopedQueryFilter:
    """
    Ensures database queries are strictly isolated to the authenticated user's scope.
    Admins can query across all tenants; non-admins are restricted to their own rows.
    """

    @staticmethod
    def apply_user_scope(
        stmt: Select[Any],
        model: Any,
        context: SecurityContext,
        user_id_column_name: str = "user_id",
    ) -> Select[Any]:
        # Admins bypass row-level ownership filtering
        if context.tier == UserTier.ADMIN:
            return stmt

        col = getattr(model, user_id_column_name, None)
        if col is not None:
            return stmt.where(col == context.user_id)

        return stmt

    @staticmethod
    def assert_ownership(
        instance: Any,
        context: SecurityContext,
        user_id_attr: str = "user_id",
    ) -> bool:
        """
        Validates whether the user owns the model instance.
        Returns True if authorized, False otherwise.
        """
        if context.tier == UserTier.ADMIN:
            return True
        return getattr(instance, user_id_attr, None) == context.user_id
