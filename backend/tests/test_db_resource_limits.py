import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError

from app.core.config import Settings, get_settings
from app.db.session import engine
from app.models.entities import Category, Product, User, Wishlist


def test_sqlite_busy_timeout_is_configured_for_bounded_lock_waits():
    if engine.dialect.name != "sqlite":
        pytest.skip("SQLite-specific connection timeout assertion")
    with engine.connect() as connection:
        timeout_ms = connection.scalar(text("PRAGMA busy_timeout"))
    assert timeout_ms >= 100


def test_duplicate_wishlist_rows_are_rejected_by_database(db_session):
    user = User(email="wishlist-unique@example.com", hashed_password="not-a-real-password")
    category = Category(name="Wishlist Test")
    db_session.add_all([user, category])
    db_session.flush()
    product = Product(
        name="Test Headphones",
        brand="Test",
        description="test",
        price=100.0,
        category_id=category.id,
    )
    db_session.add(product)
    db_session.commit()

    db_session.add(Wishlist(user_id=user.id, product_id=product.id))
    db_session.commit()
    db_session.add(Wishlist(user_id=user.id, product_id=product.id))
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()

    rows = db_session.scalars(
        select(Wishlist).where(Wishlist.user_id == user.id, Wishlist.product_id == product.id)
    ).all()
    assert len(rows) == 1


def test_database_timeout_settings_are_bounded():
    settings = Settings(
        _env_file=None,
        jwt_secret="test-secret",
        environment="development",
        db_lock_timeout_ms=500,
        db_statement_timeout_ms=1000,
    )
    assert settings.db_lock_timeout_ms == 500
    assert settings.db_statement_timeout_ms == 1000
