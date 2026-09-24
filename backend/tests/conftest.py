import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

# Point the app at a dedicated test database BEFORE importing app modules,
# so we never run tests against the dev database by accident.
os.environ["DB_NAME"] = "smartcare_ai_test"

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import settings
from app.core.database import Base, get_db
from app.main import app

# Ensure the test database exists (created once, outside SQLAlchemy, via root conn)
import pymysql

_admin_conn = pymysql.connect(
    host=settings.DB_HOST, port=settings.DB_PORT, user=settings.DB_USER, password=settings.DB_PASSWORD
)
with _admin_conn.cursor() as cur:
    cur.execute(
        f"CREATE DATABASE IF NOT EXISTS {settings.DB_NAME} CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
    )
_admin_conn.commit()
_admin_conn.close()

test_engine = create_engine(settings.DATABASE_URL, pool_pre_ping=True)
TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


@pytest.fixture(scope="function", autouse=True)
def db_session():
    """Fresh schema for every test function — slower but fully isolated."""
    Base.metadata.drop_all(bind=test_engine)
    Base.metadata.create_all(bind=test_engine)

    def override_get_db():
        db = TestSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    yield
    app.dependency_overrides.clear()


@pytest.fixture()
def client():
    return TestClient(app)


@pytest.fixture()
def db(db_session):
    """A raw SQLAlchemy session bound to the same test database/schema that
    db_session (autouse) just created — for tests that need to set up model
    rows directly (doctors, specializations, ...) rather than only going
    through the HTTP API."""
    session = TestSessionLocal()
    try:
        yield session
    finally:
        session.close()
