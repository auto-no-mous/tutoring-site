"""Разбор занятий групп, оставшихся от снятых дней расписания.

Пока group_service.replace_schedule не чистил за собой, снятый из расписания день
продолжал занимать время репетитора: занятия остались в базе со статусом scheduled,
и запись на это время отбивалась сообщением «пересекается с группой». Новый код так
больше не делает, но уже накопившиеся строки надо разобрать разово - этим скриптом.

По умолчанию только показывает, что нашёл:

    python -m app.scripts.cleanup_orphan_occurrences
    python -m app.scripts.cleanup_orphan_occurrences --apply

Осиротевшим считается будущее занятие группы, которое: ещё не отменено, не
перенесено вручную (original_start_at), без отметок посещаемости и не попадает ни в
один день текущего расписания своей группы. Разовые занятия, добавленные репетитором
вне расписания, под это описание тоже подходят - поэтому скрипт сначала печатает
список и требует явного --apply.
"""

import argparse
import asyncio

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.db.session import AsyncSessionLocal
from app.models.enums import GroupOccurrenceStatus
from app.models.group import Group, GroupAttendance, GroupOccurrence
from app.services.schedule_service import MSK
from app.utils.time import ensure_aware, utcnow


async def find_orphans() -> list[tuple[Group, GroupOccurrence]]:
    async with AsyncSessionLocal() as db:
        groups = (
            (await db.execute(select(Group).options(selectinload(Group.schedule_slots))))
            .scalars()
            .all()
        )
        occurrences = (
            (
                await db.execute(
                    select(GroupOccurrence).where(
                        GroupOccurrence.start_at >= utcnow(),
                        GroupOccurrence.status == GroupOccurrenceStatus.SCHEDULED.value,
                        GroupOccurrence.original_start_at.is_(None),
                    )
                )
            )
            .scalars()
            .all()
        )
        marked = set(
            (await db.execute(select(GroupAttendance.occurrence_id))).scalars().all()
        )

        by_id = {group.id: group for group in groups}
        orphans = []
        for occurrence in occurrences:
            group = by_id.get(occurrence.group_id)
            if group is None or occurrence.id in marked:
                continue
            slots = {(slot.weekday, slot.start_time) for slot in group.schedule_slots}
            local = ensure_aware(occurrence.start_at).astimezone(MSK)
            if (local.weekday(), local.time()) not in slots:
                orphans.append((group, occurrence))
        return orphans


async def delete(orphan_ids: list) -> None:
    async with AsyncSessionLocal() as db:
        for occurrence_id in orphan_ids:
            occurrence = await db.get(GroupOccurrence, occurrence_id)
            if occurrence is not None:
                await db.delete(occurrence)
        await db.commit()


async def main() -> None:
    parser = argparse.ArgumentParser(description="Разбор осиротевших занятий групп")
    parser.add_argument("--apply", action="store_true", help="действительно удалить найденное")
    args = parser.parse_args()

    orphans = await find_orphans()
    if not orphans:
        print("Осиротевших занятий нет")
        return

    print(f"Найдено занятий вне расписания своей группы: {len(orphans)}")
    for group, occurrence in orphans:
        local = ensure_aware(occurrence.start_at).astimezone(MSK)
        print(f"  {local:%d.%m.%Y %H:%M} (МСК) — группа «{group.name}»")

    if not args.apply:
        print("\nЭто предпросмотр. Чтобы удалить, повторите запуск с --apply")
        return

    await delete([occurrence.id for _, occurrence in orphans])
    print(f"\nУдалено: {len(orphans)}")


if __name__ == "__main__":
    asyncio.run(main())
