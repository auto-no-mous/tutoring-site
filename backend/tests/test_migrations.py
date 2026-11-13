"""Схема после миграций должна совпадать с моделями там, где на это рассчитывает код.

Тесты поднимают базу из моделей (metadata.create_all), а прод - миграциями, и
расхождение между ними тестам не видно. Так статьи блога перестали сохраняться:
модель ждёт, что дату создания подставит база (server_default), а миграция таблицы
этого значения не задала - на проде INSERT падал с NOT NULL.
"""

from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect

from app.core.config import settings
from app.db.base import Base

BACKEND_DIR = Path(__file__).resolve().parent.parent


def test_columns_with_db_defaults_get_them_from_migrations(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    db_file = tmp_path / "migrated.sqlite3"
    monkeypatch.setattr(settings, "database_url", f"sqlite+aiosqlite:///{db_file.as_posix()}")
    # Без файла alembic.ini: иначе env.py перенастроит логирование всего процесса.
    config = Config()
    config.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    command.upgrade(config, "head")

    engine = create_engine(f"sqlite:///{db_file.as_posix()}")
    try:
        inspector = inspect(engine)
        missing = []
        for table in Base.metadata.sorted_tables:
            migrated = {c["name"]: c for c in inspector.get_columns(table.name)}
            for column in table.columns:
                if column.server_default is None:
                    continue
                if migrated.get(column.name, {}).get("default") is None:
                    missing.append(f"{table.name}.{column.name}")
        assert missing == [], f"модель ждёт значение по умолчанию от базы, а миграции его не задают: {missing}"
    finally:
        engine.dispose()
