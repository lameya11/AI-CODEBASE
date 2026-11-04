"""Test fixtures and shared configuration."""
import asyncio
import os
import pytest
import pytest_asyncio

# Set test database
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
os.environ.setdefault("DATA_DIR", "/tmp/ci_test_data")

from app.db.session import engine, Base, init_db
from app.db import SessionLocal


@pytest_asyncio.fixture(scope="session")
async def db_engine():
    """Create tables once per test session."""
    await init_db()
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def db(db_engine):
    """Provide a clean DB session per test."""
    async with SessionLocal() as session:
        yield session
        await session.rollback()
