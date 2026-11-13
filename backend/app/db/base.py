import uuid
from datetime import datetime

from sqlalchemy import DateTime, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from app.utils.time import utcnow


class Base(DeclarativeBase):
    pass


class UUIDPKMixin:
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)


class TimestampMixin:
    # Дату ставит и база (server_default), и сам код (default): если миграция
    # таблицы забудет значение по умолчанию, запись всё равно сохранится. Так
    # однажды сломалось сохранение статей блога - см. миграцию e5f0b3c8a2d4 и
    # tests/test_migrations.py, который такое расхождение теперь ловит.
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), default=utcnow, onupdate=func.now()
    )
