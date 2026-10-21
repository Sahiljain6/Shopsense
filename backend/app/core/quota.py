from datetime import datetime, timedelta, timezone
from uuid import uuid4

from fastapi import Depends, HTTPException, status
from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert as postgresql_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session

from app.core.auth_types import SecurityContext
from app.core.security import get_security_context
from app.db.session import SessionLocal
from app.models.entities import MonthlyTokenUsage, QuotaReservation


RESERVATION_TTL = timedelta(minutes=15)


def _utc_period() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m")


def _utc_now_naive() -> datetime:
    # The existing SQLAlchemy DateTime columns use UTC-naive timestamps.
    return datetime.now(timezone.utc).replace(tzinfo=None)


class QuotaEngine:
    """Database-backed token accounting with atomic reservations.

    The unique (user_id, period) row is shared across app workers/replicas. SQLite and
    PostgreSQL use native conditional upserts so concurrent requests cannot all pass
    the same preflight check. Token usage persists across application restarts.
    """

    def __init__(self, session_factory=SessionLocal):
        self._session_factory = session_factory

    @staticmethod
    def _current_total(db: Session, user_id: int, period: str) -> int:
        row = db.scalar(
            select(MonthlyTokenUsage).where(
                MonthlyTokenUsage.user_id == user_id,
                MonthlyTokenUsage.period == period,
            )
        )
        if row is None:
            return 0
        return max(0, row.used_tokens) + max(0, row.reserved_tokens)

    @staticmethod
    def _cleanup_expired_reservations(db: Session, now: datetime) -> None:
        expired = db.scalars(
            select(QuotaReservation)
            .where(QuotaReservation.expires_at <= now)
            .with_for_update()
        ).all()
        if not expired:
            return

        for reservation in expired:
            usage = db.scalar(
                select(MonthlyTokenUsage)
                .where(
                    MonthlyTokenUsage.user_id == reservation.user_id,
                    MonthlyTokenUsage.period == reservation.period,
                )
                .with_for_update()
            )
            if usage is not None:
                usage.reserved_tokens = max(0, usage.reserved_tokens - reservation.reserved_tokens)
                usage.updated_at = now
            db.delete(reservation)

    def get_usage(self, user_id: int) -> int:
        period = _utc_period()
        now = _utc_now_naive()
        with self._session_factory() as db:
            self._cleanup_expired_reservations(db, now)
            total = self._current_total(db, user_id, period)
            db.commit()
            return total

    def reserve(
        self,
        user_id: int,
        estimated_tokens: int,
        monthly_limit: int,
    ) -> tuple[bool, int, str | None]:
        """Atomically reserve capacity before calling an expensive upstream provider.

        Returns (allowed, current_usage_before_reservation, reservation_id).
        A denied attempt has no durable reservation. The reservation expires after a
        bounded lease if a worker disappears before finalizing it.
        """
        estimate = max(0, int(estimated_tokens))
        period = _utc_period()
        now = _utc_now_naive()
        reservation_id = str(uuid4())

        if estimate > monthly_limit:
            return False, self.get_usage(user_id), None

        with self._session_factory() as db:
            self._cleanup_expired_reservations(db, now)
            dialect = db.get_bind().dialect.name
            values = {
                "user_id": user_id,
                "period": period,
                "used_tokens": 0,
                "reserved_tokens": estimate,
                "updated_at": now,
            }

            if dialect == "sqlite":
                insert_fn = sqlite_insert
            elif dialect == "postgresql":
                insert_fn = postgresql_insert
            else:
                db.rollback()
                raise RuntimeError(
                    f"Atomic token reservations are not implemented for database dialect '{dialect}'."
                )

            insert_stmt = insert_fn(MonthlyTokenUsage).values(**values)
            statement = insert_stmt.on_conflict_do_update(
                index_elements=[MonthlyTokenUsage.user_id, MonthlyTokenUsage.period],
                set_={
                    "reserved_tokens": MonthlyTokenUsage.reserved_tokens + estimate,
                    "updated_at": now,
                },
                where=(
                    MonthlyTokenUsage.used_tokens
                    + MonthlyTokenUsage.reserved_tokens
                    + estimate
                    <= monthly_limit
                ),
            ).returning(MonthlyTokenUsage.used_tokens, MonthlyTokenUsage.reserved_tokens)

            result = db.execute(statement).first()
            if result is None:
                current = self._current_total(db, user_id, period)
                db.rollback()
                return False, current, None

            reserved_usage = db.add(
                QuotaReservation(
                    reservation_id=reservation_id,
                    user_id=user_id,
                    period=period,
                    reserved_tokens=estimate,
                    created_at=now,
                    expires_at=now + RESERVATION_TTL,
                )
            )
            db.commit()
            current_before_reservation = max(0, int(result.used_tokens)) + max(
                0, int(result.reserved_tokens) - estimate
            )
            return True, current_before_reservation, reservation_id

    def complete_reservation(self, user_id: int, reservation_id: str | None, actual_tokens: int) -> int | None:
        """Replace a pending estimate with measured/estimated consumed tokens."""
        if not reservation_id:
            return None
        now = _utc_now_naive()
        with self._session_factory() as db:
            reservation = db.scalar(
                select(QuotaReservation)
                .where(
                    QuotaReservation.reservation_id == reservation_id,
                    QuotaReservation.user_id == user_id,
                )
                .with_for_update()
            )
            if reservation is None:
                return None
            usage = db.scalar(
                select(MonthlyTokenUsage)
                .where(
                    MonthlyTokenUsage.user_id == user_id,
                    MonthlyTokenUsage.period == reservation.period,
                )
                .with_for_update()
            )
            if usage is None:
                usage = MonthlyTokenUsage(
                    user_id=user_id,
                    period=reservation.period,
                    used_tokens=0,
                    reserved_tokens=0,
                    updated_at=now,
                )
                db.add(usage)
                db.flush()

            usage.reserved_tokens = max(0, usage.reserved_tokens - reservation.reserved_tokens)
            usage.used_tokens = max(0, usage.used_tokens) + max(0, int(actual_tokens))
            usage.updated_at = now
            db.delete(reservation)
            db.commit()
            return usage.used_tokens

    def release_reservation(self, user_id: int, reservation_id: str | None) -> bool:
        """Release capacity when a request is rejected or fails before a result is usable."""
        if not reservation_id:
            return False
        now = _utc_now_naive()
        with self._session_factory() as db:
            reservation = db.scalar(
                select(QuotaReservation)
                .where(
                    QuotaReservation.reservation_id == reservation_id,
                    QuotaReservation.user_id == user_id,
                )
                .with_for_update()
            )
            if reservation is None:
                return False
            usage = db.scalar(
                select(MonthlyTokenUsage)
                .where(
                    MonthlyTokenUsage.user_id == user_id,
                    MonthlyTokenUsage.period == reservation.period,
                )
                .with_for_update()
            )
            if usage is not None:
                usage.reserved_tokens = max(0, usage.reserved_tokens - reservation.reserved_tokens)
                usage.updated_at = now
            db.delete(reservation)
            db.commit()
            return True

    def check_and_reserve(
        self,
        user_id: int,
        estimated_tokens: int,
        monthly_limit: int,
    ) -> tuple[bool, int]:
        """Compatibility preflight check; use reserve() for an enforced request."""
        current = self.get_usage(user_id)
        return current + max(0, estimated_tokens) <= monthly_limit, current

    def record_usage(self, user_id: int, actual_tokens: int) -> int:
        """Record usage not associated with a prior reservation (e.g. admin/test adjustment)."""
        period = _utc_period()
        now = _utc_now_naive()
        increment = max(0, int(actual_tokens))
        with self._session_factory() as db:
            dialect = db.get_bind().dialect.name
            values = {
                "user_id": user_id,
                "period": period,
                "used_tokens": increment,
                "reserved_tokens": 0,
                "updated_at": now,
            }
            if dialect == "sqlite":
                insert_fn = sqlite_insert
            elif dialect == "postgresql":
                insert_fn = postgresql_insert
            else:
                raise RuntimeError(
                    f"Token accounting is not implemented for database dialect '{dialect}'."
                )

            stmt = insert_fn(MonthlyTokenUsage).values(**values)
            stmt = stmt.on_conflict_do_update(
                index_elements=[MonthlyTokenUsage.user_id, MonthlyTokenUsage.period],
                set_={
                    "used_tokens": MonthlyTokenUsage.used_tokens + increment,
                    "updated_at": now,
                },
            )
            db.execute(stmt)
            db.commit()
        return self.get_usage(user_id)

    def reset_usage(self, user_id: int) -> None:
        """Reset the current UTC month for this user; intended for admin/test workflows."""
        period = _utc_period()
        now = _utc_now_naive()
        with self._session_factory() as db:
            usage = db.scalar(
                select(MonthlyTokenUsage).where(
                    MonthlyTokenUsage.user_id == user_id,
                    MonthlyTokenUsage.period == period,
                )
            )
            if usage is None:
                db.add(
                    MonthlyTokenUsage(
                        user_id=user_id,
                        period=period,
                        used_tokens=0,
                        reserved_tokens=0,
                        updated_at=now,
                    )
                )
            else:
                usage.used_tokens = 0
                usage.reserved_tokens = 0
                usage.updated_at = now
            db.execute(
                delete(QuotaReservation).where(
                    QuotaReservation.user_id == user_id,
                    QuotaReservation.period == period,
                )
            )
            db.commit()

    def reset_all(self) -> None:
        """Clear quota state for isolated test runs."""
        with self._session_factory() as db:
            db.execute(delete(QuotaReservation))
            db.execute(delete(MonthlyTokenUsage))
            db.commit()


quota_engine = QuotaEngine()


def check_quota(estimated_tokens: int = 500):
    """Compatibility dependency for endpoints that only need a quota preflight check."""
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
