"""Seeds a starter set of subjects/directions (project_description.md section 10
redesign - controlled vocabulary the admin can extend later via the admin API/UI).
Idempotent: skips any subject/direction that already exists by name.

Usage:
    poetry run python -m app.scripts.seed_subjects
"""

import asyncio

from sqlalchemy import select

from app.db.session import AsyncSessionLocal
from app.models.subject import Direction, Subject

SCHOOL_DIRECTIONS = ["5-9 класс", "10-11 класс", "Подготовка к ОГЭ", "Подготовка к ЕГЭ", "Подготовка к олимпиаде"]

SUBJECTS: dict[str, list[str]] = {
    "Математика": SCHOOL_DIRECTIONS,
    "Информатика": SCHOOL_DIRECTIONS,
    "Русский язык": SCHOOL_DIRECTIONS,
    "Английский язык": ["Начальный уровень", "Разговорный клуб", "Подготовка к ЕГЭ", "Подготовка к международным экзаменам"],
    "Физика": SCHOOL_DIRECTIONS,
    "Химия": SCHOOL_DIRECTIONS,
    "Биология": SCHOOL_DIRECTIONS,
    "Обществознание": ["5-9 класс", "10-11 класс", "Подготовка к ОГЭ", "Подготовка к ЕГЭ"],
    "История": ["5-9 класс", "10-11 класс", "Подготовка к ОГЭ", "Подготовка к ЕГЭ"],
}


async def seed() -> None:
    async with AsyncSessionLocal() as db:
        for subject_name, direction_names in SUBJECTS.items():
            result = await db.execute(select(Subject).where(Subject.name == subject_name))
            subject = result.scalar_one_or_none()
            if subject is None:
                subject = Subject(name=subject_name)
                db.add(subject)
                await db.flush()
                print(f"Created subject: {subject_name}")

            for direction_name in direction_names:
                existing = await db.execute(
                    select(Direction).where(Direction.subject_id == subject.id, Direction.name == direction_name)
                )
                if existing.scalar_one_or_none() is None:
                    db.add(Direction(subject_id=subject.id, name=direction_name))
                    print(f"  + {direction_name}")

        await db.commit()


def main() -> None:
    asyncio.run(seed())


if __name__ == "__main__":
    main()
