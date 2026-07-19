import uuid

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.lesson_type import LessonType
from app.models.tutor import TutorProfile
from app.schemas.lesson_type import LessonTypeCreate, LessonTypeUpdate


async def list_lesson_types(db: AsyncSession, tutor_id: uuid.UUID, active_only: bool = False) -> list[LessonType]:
    query = select(LessonType).where(LessonType.tutor_id == tutor_id)
    if active_only:
        query = query.where(LessonType.is_active.is_(True))
    result = await db.execute(query.order_by(LessonType.created_at))
    return list(result.scalars().all())


async def get_lesson_type(db: AsyncSession, tutor_id: uuid.UUID, lesson_type_id: uuid.UUID) -> LessonType:
    result = await db.execute(
        select(LessonType).where(LessonType.id == lesson_type_id, LessonType.tutor_id == tutor_id)
    )
    lesson_type = result.scalar_one_or_none()
    if lesson_type is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Тип занятия не найден")
    return lesson_type


def _validate_granularity(tutor: TutorProfile, duration_minutes: int) -> None:
    if duration_minutes % tutor.slot_granularity_minutes != 0:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            f"Длительность должна быть кратна шагу разбивки расписания "
            f"({tutor.slot_granularity_minutes} мин)",
        )


async def create_lesson_type(db: AsyncSession, tutor: TutorProfile, payload: LessonTypeCreate) -> LessonType:
    _validate_granularity(tutor, payload.duration_minutes)
    lesson_type = LessonType(tutor_id=tutor.id, **payload.model_dump())
    db.add(lesson_type)
    await db.commit()
    await db.refresh(lesson_type)
    return lesson_type


async def update_lesson_type(
    db: AsyncSession, tutor: TutorProfile, lesson_type: LessonType, payload: LessonTypeUpdate
) -> LessonType:
    data = payload.model_dump(exclude_unset=True)
    if "duration_minutes" in data:
        _validate_granularity(tutor, data["duration_minutes"])
    for field, value in data.items():
        setattr(lesson_type, field, value)
    await db.commit()
    await db.refresh(lesson_type)
    return lesson_type


async def delete_lesson_type(db: AsyncSession, lesson_type: LessonType) -> None:
    await db.delete(lesson_type)
    await db.commit()
