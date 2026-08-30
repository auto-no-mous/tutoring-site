"""Разовый перенос данных из SQLite в PostgreSQL.

Запускается один раз при переезде (раздел 9 project_description.md), после того как
на пустой базе PostgreSQL уже накатаны миграции:

    python -m app.scripts.sqlite_to_postgres \\
        --source sqlite:///storage/db.sqlite3 \\
        --target postgresql+psycopg://user:pass@postgres:5432/mytutor

Копирует таблицы в порядке внешних ключей (Base.metadata.sorted_tables), читая и
записывая через типы самих моделей: SQLAlchemy сама превращает CHAR(32) в uuid,
0/1 в boolean, а JSON-текст в структуру. Отдельно чинится только то, что типами не
описывается - наивные даты: SQLite отдаёт их без часового пояса, а в PostgreSQL
колонки timestamptz, и наивное значение он трактовал бы по часовому поясу сессии.

Скрипт синхронный намеренно: это операция обслуживания, а не часть приложения, и
одноразовый psycopg проще, чем поднимать асинхронный стек ради одного прогона.
"""

import argparse
import sys
from datetime import datetime, timezone

from sqlalchemy import DateTime, create_engine, func, select
from sqlalchemy.schema import Table

from app import models  # noqa: F401  (регистрирует все модели на Base.metadata)
from app.db.base import Base


def _normalize(table: Table, row: dict) -> dict:
    """Проставляет UTC там, где SQLite вернул дату без часового пояса."""
    for column in table.columns:
        value = row.get(column.name)
        if isinstance(value, datetime) and value.tzinfo is None and isinstance(column.type, DateTime):
            row[column.name] = value.replace(tzinfo=timezone.utc)
    return row


def check_source_integrity(source_url: str) -> list[tuple[str, str, int]]:
    """Ищет в SQLite строки, ссылающиеся на несуществующие записи.

    SQLite по умолчанию не исполняет внешние ключи (PRAGMA foreign_keys=0), поэтому
    удаления оставляют висячие ссылки, и база годами живёт с ними без единой жалобы.
    PostgreSQL так не умеет: он отвергнет такие строки, и перенос свалится посреди
    работы с невнятной ошибкой драйвера. Лучше сказать об этом до начала.
    """
    if not source_url.startswith("sqlite"):
        return []

    engine = create_engine(source_url)
    with engine.connect() as conn:
        rows = conn.exec_driver_sql("PRAGMA foreign_key_check").fetchall()

    counts: dict[tuple[str, str], int] = {}
    for table, _rowid, parent, _fkid in rows:
        counts[(table, parent)] = counts.get((table, parent), 0) + 1
    return [(table, parent, count) for (table, parent), count in sorted(counts.items())]


def transfer(source_url: str, target_url: str, batch_size: int = 500) -> int:
    source = create_engine(source_url)
    target = create_engine(target_url)

    total = 0
    with source.connect() as src, target.begin() as dst:
        for table in Base.metadata.sorted_tables:
            existing = dst.execute(select(func.count()).select_from(table)).scalar_one()
            if existing:
                # Переносим только в пустую базу: дописывать поверх - верный способ
                # получить половину данных дважды, а половину не получить вовсе.
                raise SystemExit(
                    f"Таблица {table.name} в целевой базе не пуста ({existing} строк). "
                    "Перенос рассчитан на чистую базу со свежими миграциями."
                )

            rows = [_normalize(table, dict(row)) for row in src.execute(select(table)).mappings()]
            if not rows:
                print(f"{table.name}: пусто")
                continue

            for start in range(0, len(rows), batch_size):
                dst.execute(table.insert(), rows[start : start + batch_size])
            total += len(rows)
            print(f"{table.name}: {len(rows)}")

    return total


def verify(source_url: str, target_url: str) -> bool:
    """Сверяет число строк по каждой таблице - дешёвая проверка, что ничего не потерялось."""
    source = create_engine(source_url)
    target = create_engine(target_url)
    ok = True
    with source.connect() as src, target.connect() as dst:
        for table in Base.metadata.sorted_tables:
            in_source = src.execute(select(func.count()).select_from(table)).scalar_one()
            in_target = dst.execute(select(func.count()).select_from(table)).scalar_one()
            if in_source != in_target:
                print(f"РАСХОЖДЕНИЕ {table.name}: было {in_source}, стало {in_target}")
                ok = False
    return ok


def main() -> None:
    parser = argparse.ArgumentParser(description="Перенос данных SQLite -> PostgreSQL")
    parser.add_argument("--source", required=True, help="sqlite:///storage/db.sqlite3")
    parser.add_argument("--target", required=True, help="postgresql+psycopg://...")
    parser.add_argument(
        "--verify-only", action="store_true", help="только сверить количество строк"
    )
    args = parser.parse_args()

    if args.verify_only:
        sys.exit(0 if verify(args.source, args.target) else 1)

    orphans = check_source_integrity(args.source)
    if orphans:
        print("В исходной базе есть строки со ссылками на удалённые записи:")
        for table, parent, count in orphans:
            print(f"  {table} -> {parent}: {count}")
        print(
            "PostgreSQL такие строки не примет. Удалите их или перенесите в базу, "
            "где внешние ключи не проверяются, а затем почините."
        )
        sys.exit(2)

    total = transfer(args.source, args.target)
    print(f"Перенесено строк: {total}")
    if not verify(args.source, args.target):
        sys.exit(1)
    print("Сверка по количеству строк прошла")


if __name__ == "__main__":
    main()
