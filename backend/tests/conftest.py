import os
import sys
from collections.abc import Generator
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["JWT_SECRET"] = "test-secret"
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from app.db.session import Base, get_db
from app.main import app
from app import models  # noqa: F401

engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=__import__("sqlalchemy.pool").pool.StaticPool)
TestingSessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)


def override_get_db() -> Generator[Session, None, None]:
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()

app.dependency_overrides[get_db] = override_get_db


def reset_db() -> None:
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)


import pytest

@pytest.fixture()
def db_session() -> Generator[Session, None, None]:
    reset_db()
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()

@pytest.fixture()
def client() -> Generator[TestClient, None, None]:
    reset_db()
    with TestClient(app) as c:
        yield c
