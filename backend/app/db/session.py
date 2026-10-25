from collections.abc import Generator
from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker
from sqlalchemy.pool import StaticPool
from app.core.config import get_settings


class Base(DeclarativeBase):
    pass


def _connect_args(url: str, lock_timeout_ms: int) -> dict[str, object]:
    if url.startswith("sqlite"):
        return {"check_same_thread": False, "timeout": max(0.1, lock_timeout_ms / 1000)}
    return {}


settings = get_settings()
_engine_options: dict[str, object] = {
    "connect_args": _connect_args(settings.database_url, settings.db_lock_timeout_ms),
    "pool_pre_ping": True,
}

# Share one in-memory SQLite database across the app's worker/test threads.
if settings.database_url in {"sqlite://", "sqlite:///:memory:"}:
    _engine_options["poolclass"] = StaticPool

# QueuePool settings are supported for the production PostgreSQL deployment.
# SQLite retains its dialect-appropriate defaults, including the in-memory test setup.
if not settings.database_url.startswith("sqlite"):
    _engine_options.update(
        pool_size=settings.db_pool_size,
        max_overflow=settings.db_max_overflow,
        pool_timeout=settings.db_pool_timeout_seconds,
        pool_recycle=settings.db_pool_recycle_seconds,
    )

engine = create_engine(settings.database_url, **_engine_options)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()



def _configure_connection_limits(dbapi_connection: object, _connection_record: object) -> None:
    """Apply bounded DB lock/query waits once per pooled connection."""
    cursor = dbapi_connection.cursor()
    try:
        if engine.dialect.name == "sqlite":
            cursor.execute(f"PRAGMA busy_timeout = {settings.db_lock_timeout_ms}")
        elif engine.dialect.name == "postgresql":
            cursor.execute(f"SET lock_timeout = '{settings.db_lock_timeout_ms}ms'")
            cursor.execute(f"SET statement_timeout = '{settings.db_statement_timeout_ms}ms'")
            # Persist session defaults across pool checkouts; a rolled-back setup
            # transaction would otherwise discard these SET values.
            dbapi_connection.commit()
    finally:
        cursor.close()


event.listen(engine, "connect", _configure_connection_limits)
