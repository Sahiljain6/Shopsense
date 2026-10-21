from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.core.quota import QuotaEngine
from app.db.session import Base
from app.models.entities import MonthlyTokenUsage, QuotaReservation


def _new_quota_engine(tmp_path) -> tuple[QuotaEngine, object, object]:
    database_path = tmp_path / "quota-tests.db"
    test_engine = create_engine(
        f"sqlite:///{database_path}",
        connect_args={"check_same_thread": False, "timeout": 20},
    )
    Base.metadata.create_all(bind=test_engine)
    session_factory = sessionmaker(
        bind=test_engine,
        autoflush=False,
        autocommit=False,
        expire_on_commit=False,
    )
    return QuotaEngine(session_factory), session_factory, test_engine


def test_reservation_is_atomic_and_reconciles_to_actual_usage(tmp_path):
    quota, session_factory, db_engine = _new_quota_engine(tmp_path)
    try:
        allowed, current, reservation_id = quota.reserve(1001, estimated_tokens=60, monthly_limit=100)
        assert allowed is True
        assert current == 0
        assert reservation_id

        denied, current, denied_id = quota.reserve(1001, estimated_tokens=50, monthly_limit=100)
        assert denied is False
        assert current == 60
        assert denied_id is None
        assert quota.get_usage(1001) == 60

        assert quota.complete_reservation(1001, reservation_id, actual_tokens=25) == 25
        assert quota.get_usage(1001) == 25

        with session_factory() as db:
            assert db.scalars(select(QuotaReservation)).all() == []
            usage = db.scalar(
                select(MonthlyTokenUsage).where(MonthlyTokenUsage.user_id == 1001)
            )
            assert usage is not None
            assert usage.used_tokens == 25
            assert usage.reserved_tokens == 0
    finally:
        db_engine.dispose()


def test_concurrent_reservations_cannot_overbook_a_monthly_limit(tmp_path):
    quota, _session_factory, db_engine = _new_quota_engine(tmp_path)
    try:
        def reserve_once(_):
            return quota.reserve(1002, estimated_tokens=20, monthly_limit=100)

        with ThreadPoolExecutor(max_workers=8) as executor:
            results = list(executor.map(reserve_once, range(10)))

        allowed = [result for result in results if result[0]]
        denied = [result for result in results if not result[0]]
        assert len(allowed) == 5
        assert len(denied) == 5
        assert len({result[2] for result in allowed}) == 5
        assert quota.get_usage(1002) == 100

        for _ok, _current, reservation_id in allowed:
            assert quota.release_reservation(1002, reservation_id) is True
        assert quota.get_usage(1002) == 0
    finally:
        db_engine.dispose()


def test_expired_reservations_are_reclaimed_without_losing_used_tokens(tmp_path):
    quota, session_factory, db_engine = _new_quota_engine(tmp_path)
    try:
        quota.record_usage(1003, 15)
        allowed, _current, reservation_id = quota.reserve(1003, estimated_tokens=30, monthly_limit=100)
        assert allowed is True

        with session_factory() as db:
            reservation = db.get(QuotaReservation, reservation_id)
            assert reservation is not None
            reservation.expires_at = datetime.utcnow() - timedelta(minutes=1)
            db.commit()

        assert quota.get_usage(1003) == 15
        with session_factory() as db:
            assert db.get(QuotaReservation, reservation_id) is None
    finally:
        db_engine.dispose()
