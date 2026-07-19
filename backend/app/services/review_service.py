import uuid

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.booking import Booking
from app.models.enums import BookingStatus
from app.models.group import Group, GroupMembership, GroupOccurrence
from app.models.review import Review
from app.models.user import User
from app.schemas.review import ReviewCreate
from app.utils.time import utcnow


async def has_had_lesson_with(db: AsyncSession, tutor_id: uuid.UUID, student_id: uuid.UUID) -> bool:
    now = utcnow()

    individual = await db.execute(
        select(Booking.id).where(
            Booking.tutor_id == tutor_id,
            Booking.student_id == student_id,
            Booking.status != BookingStatus.CANCELLED_BY_STUDENT.value,
            Booking.status != BookingStatus.CANCELLED_BY_TUTOR.value,
            Booking.start_at < now,
        )
    )
    if individual.first() is not None:
        return True

    group_lesson = await db.execute(
        select(GroupOccurrence.id)
        .join(Group, Group.id == GroupOccurrence.group_id)
        .join(GroupMembership, GroupMembership.group_id == Group.id)
        .where(
            Group.tutor_id == tutor_id,
            GroupMembership.student_id == student_id,
            GroupOccurrence.start_at < now,
            GroupOccurrence.start_at >= GroupMembership.joined_at,
        )
    )
    return group_lesson.first() is not None


async def upsert_review(db: AsyncSession, student: User, tutor_id: uuid.UUID, payload: ReviewCreate) -> Review:
    if not await has_had_lesson_with(db, tutor_id, student.id):
        raise HTTPException(
            status.HTTP_403_FORBIDDEN, "Оставить отзыв можно только после занятия с этим репетитором"
        )

    result = await db.execute(
        select(Review).where(Review.tutor_id == tutor_id, Review.student_id == student.id)
    )
    review = result.scalar_one_or_none()
    if review is None:
        review = Review(tutor_id=tutor_id, student_id=student.id, rating=payload.rating, text=payload.text)
        db.add(review)
    else:
        review.rating = payload.rating
        review.text = payload.text

    await db.commit()
    await db.refresh(review)
    return review


async def list_reviews_for_tutor(db: AsyncSession, tutor_id: uuid.UUID) -> list[dict]:
    result = await db.execute(
        select(Review, User.display_name)
        .join(User, User.id == Review.student_id)
        .where(Review.tutor_id == tutor_id)
        .order_by(Review.created_at.desc())
    )
    items = []
    for review, display_name in result.all():
        items.append(
            {
                "id": review.id,
                "tutor_id": review.tutor_id,
                "student_id": review.student_id,
                "rating": review.rating,
                "text": review.text,
                "created_at": review.created_at,
                "updated_at": review.updated_at,
                "student_display_name": display_name,
            }
        )
    return items


async def get_rating_summary(db: AsyncSession, tutor_id: uuid.UUID) -> tuple[float | None, int]:
    result = await db.execute(
        select(func.avg(Review.rating), func.count(Review.id)).where(Review.tutor_id == tutor_id)
    )
    avg_rating, count = result.one()
    return (float(avg_rating) if avg_rating is not None else None, count)


async def get_rating_summaries(db: AsyncSession, tutor_ids: list[uuid.UUID]) -> dict[uuid.UUID, tuple[float | None, int]]:
    if not tutor_ids:
        return {}
    result = await db.execute(
        select(Review.tutor_id, func.avg(Review.rating), func.count(Review.id))
        .where(Review.tutor_id.in_(tutor_ids))
        .group_by(Review.tutor_id)
    )
    return {row[0]: (float(row[1]) if row[1] is not None else None, row[2]) for row in result.all()}
