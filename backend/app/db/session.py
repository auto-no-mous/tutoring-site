from collections.abc import AsyncGenerator

from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings

connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}



def use_unicode_lower_on_sqlite(async_engine: AsyncEngine) -> None:
    """Встроенный lower() в SQLite меняет регистр только у латиницы, и поиск
    репетитора «петров» не находил бы «Петров». На PostgreSQL (прод) lower() и так
    понимает кириллицу; здесь - для локального запуска и тестов, которые живут на
    SQLite."""
    if async_engine.dialect.name != "sqlite":
        return

    @event.listens_for(async_engine.sync_engine, "connect")
    def _register(dbapi_connection, _record) -> None:  # type: ignore[no-untyped-def]
        dbapi_connection.create_function(
            "lower", 1, lambda value: value.lower() if isinstance(value, str) else value, deterministic=True
        )


engine = create_async_engine(settings.database_url, echo=settings.debug, connect_args=connect_args)
use_unicode_lower_on_sqlite(engine)

AsyncSessionLocal = async_sessionmaker(bind=engine, expire_on_commit=False, class_=AsyncSession)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        yield session
