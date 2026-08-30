import os
from collections.abc import AsyncGenerator

# Must run before `app.main` (and therefore `app.core.rate_limit`) is imported: a
# shared in-memory limiter would otherwise trip across unrelated tests hitting
# /auth/* from the same client IP, since httpx's ASGITransport doesn't vary it.
os.environ["RATE_LIMIT_ENABLED"] = "false"

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool, StaticPool

from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app import models  # noqa: F401


# Прод живёт на PostgreSQL, а тесты по умолчанию гоняются на SQLite в памяти - это
# на порядок быстрее и не требует поднятого сервера. Чтобы расхождение между
# движками не всплыло только на проде, CI прогоняет тот же набор ещё раз против
# настоящего Postgres: достаточно задать TEST_DATABASE_URL.
TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL")


@pytest_asyncio.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    if TEST_DATABASE_URL:
        engine = create_async_engine(TEST_DATABASE_URL, poolclass=NullPool)
        async with engine.begin() as conn:
            # Схема пересоздаётся на каждый тест: база одна на весь прогон, и остатки
            # предыдущего теста иначе ломали бы уникальные индексы (почты, слаги).
            await conn.run_sync(Base.metadata.drop_all)
            await conn.run_sync(Base.metadata.create_all)
    else:
        engine = create_async_engine(
            "sqlite+aiosqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(bind=engine, expire_on_commit=False, class_=AsyncSession)

    async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db

    async with session_factory() as session:
        yield session

    app.dependency_overrides.clear()
    await engine.dispose()


@pytest_asyncio.fixture
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
