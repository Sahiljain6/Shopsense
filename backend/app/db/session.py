from collections.abc import Generator
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker
from sqlalchemy.pool import StaticPool
from app.core.config import get_settings


class Base(DeclarativeBase):
    pass


def _connect_args(url: str) -> dict[str, object]:
    return {"check_same_thread": False} if url.startswith("sqlite") else {}


settings = get_settings()
_engine_options: dict[str, object] = {
    "connect_args": _connect_args(settings.database_url),
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
