import uuid

from fastapi import HTTPException, status
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.schedule import WeeklyAvailability
from app.models.tutor import TutorProfile
from app.schemas.schedule import AvailabilityIntervalIn


async def list_availability(db: AsyncSession, tutor_id: uuid.UUID) -> list[WeeklyAvailability]:
    result = await db.execute(
        select(WeeklyAvailability)
        .where(WeeklyAvailability.tutor_id == tutor_id)
        .order_by(WeeklyAvailability.weekday, WeeklyAvailability.start_time)
    )
    return list(result.scalars().all())


def _validate_granularity(tutor: TutorProfile, intervals: list[AvailabilityIntervalIn]) -> None:
    step = tutor.slot_granularity_minutes
    for interval in intervals:
        start_minutes = interval.start_time.hour * 60 + interval.start_time.minute
        end_minutes = interval.end_time.hour * 60 + interval.end_time.minute
        if start_minutes % step != 0 or end_minutes % step != 0:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_CONTENT,
                f"Границы интервалов должны быть кратны шагу разбивки расписания ({step} мин)",
            )


async def replace_availability(
    db: AsyncSession, tutor: TutorProfile, intervals: list[AvailabilityIntervalIn]
) -> list[WeeklyAvailability]:
    _validate_granularity(tutor, intervals)

    await db.execute(delete(WeeklyAvailability).where(WeeklyAvailability.tutor_id == tutor.id))
    rows = [
        WeeklyAvailability(
            tutor_id=tutor.id,
            weekday=interval.weekday,
            start_time=interval.start_time,
            end_time=interval.end_time,
        )
        for interval in intervals
    ]
    db.add_all(rows)
    await db.commit()
    for row in rows:
        await db.refresh(row)
    return rows
