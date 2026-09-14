"""Продлевает еженедельные занятия: индивидуальные серии и занятия групп.

Зачем нужен отдельный запуск: и серия занятий с учеником, и расписание группы
разворачиваются в конкретные занятия один раз - когда их включают, - на восемь недель
вперёд. Недели проходят, занятия остаются в прошлом, а новых никто не создаёт: через
два месяца у ученика впереди пусто, хотя еженедельные занятия никто не отменял.

Если серия не может создать ни одной недели (время занято или выпало из расписания),
репетитор получает уведомление - один раз, пока серия не оживёт: иначе она умирала
молча, а ежедневная задача слала бы одно и то же письмо каждые сутки.

Запускается внешним планировщиком раз в сутки (systemd-таймер
my-tutor-extend-schedules.timer, см. ops/README.md) - своего планировщика в проекте
нет. Безопасен при любой частоте запуска: уже существующие недели пропускаются, в
прошлое занятия не создаются.

Usage:
    poetry run python -m app.scripts.extend_schedules
"""

import asyncio

from app.db.session import AsyncSessionLocal
from app.services import booking_service, group_service


async def main() -> None:
    async with AsyncSessionLocal() as db:
        series_stats = await booking_service.top_up_active_series(db)
        group_stats = await group_service.top_up_occurrences(db)

    print(
        f"Серий проверено: {series_stats['series']}, занятий создано: {series_stats['created']}, "
        f"не продлеваются: {series_stats['stalled']}; "
        f"групп проверено: {group_stats['groups']}, занятий создано: {group_stats['created']}"
    )


if __name__ == "__main__":
    asyncio.run(main())
