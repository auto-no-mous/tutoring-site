import uuid

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import LessonFormat
from app.models.lesson_type import LessonType
from app.models.subject import TutorSubject
from app.models.tutor import TutorProfile
from app.models.user import User
from app.schemas.tutor import TutorProfileUpdate
from app.services import review_service, subject_service


async def get_profile_by_user_id(db: AsyncSession, user_id: uuid.UUID) -> TutorProfile:
    result = await db.execute(select(TutorProfile).where(TutorProfile.user_id == user_id))
    profile = result.scalar_one_or_none()
    if profile is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Анкета репетитора не найдена")
    return profile


async def get_profile_by_id(db: AsyncSession, tutor_id: uuid.UUID) -> TutorProfile:
    profile = await db.get(TutorProfile, tutor_id)
    if profile is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Анкета репетитора не найдена")
    return profile


async def update_profile(db: AsyncSession, profile: TutorProfile, payload: TutorProfileUpdate) -> TutorProfile:
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(profile, field, value)
    await db.commit()
    await db.refresh(profile)
    return profile


async def set_photo(db: AsyncSession, profile: TutorProfile, photo_url: str) -> TutorProfile:
    profile.photo_url = photo_url
    await db.commit()
    await db.refresh(profile)
    return profile


async def search_catalog(
    db: AsyncSession,
    subject_id: uuid.UUID | None = None,
    price_min: float | None = None,
    price_max: float | None = None,
) -> list[dict]:
    """Public catalog: hidden profiles are excluded (section 2.1); direct-link access
    to a hidden profile is handled separately by get_profile_by_id.

    Price is normalized to a per-hour rate (price / duration_minutes * 60) over
    individual-format lesson types only, so tutors with different lesson lengths (or
    group offerings, priced per seat) are still comparable on a single number."""
    hourly_price_expr = LessonType.price / LessonType.duration_minutes * 60.0
    price_agg = (
        select(
            LessonType.tutor_id.label("tutor_id"),
            func.min(hourly_price_expr).label("hourly_price"),
        )
        .where(LessonType.is_active.is_(True), LessonType.format == LessonFormat.INDIVIDUAL.value)
        .group_by(LessonType.tutor_id)
        .subquery()
    )

    query = (
        select(TutorProfile, User.display_name, User.first_name, User.patronymic, price_agg.c.hourly_price)
        .join(User, User.id == TutorProfile.user_id)
        .outerjoin(price_agg, price_agg.c.tutor_id == TutorProfile.id)
        .where(TutorProfile.is_hidden.is_(False))
    )
    if subject_id is not None:
        query = query.where(
            TutorProfile.id.in_(select(TutorSubject.tutor_id).where(TutorSubject.subject_id == subject_id))
        )
    if price_min is not None:
        query = query.where(price_agg.c.hourly_price >= price_min)
    if price_max is not None:
        query = query.where(price_agg.c.hourly_price <= price_max)

    result = await db.execute(query)
    rows = result.all()
    tutor_ids = [profile.id for profile, *_ in rows]
    ratings = await review_service.get_rating_summaries(db, tutor_ids)
    subjects_by_tutor = await subject_service.get_subject_names_for_tutors(db, tutor_ids)

    items = []
    for profile, display_name, first_name, patronymic, hourly_price in rows:
        avg_rating, reviews_count = ratings.get(profile.id, (None, 0))
        items.append(
            {
                "id": profile.id,
                "user_id": profile.user_id,
                "display_name": display_name,
                "name_patronymic": f"{first_name} {patronymic}" if patronymic else first_name,
                "photo_url": profile.photo_url,
                "subjects": subjects_by_tutor.get(profile.id, []),
                "hourly_price": float(hourly_price) if hourly_price is not None else None,
                "avg_rating": avg_rating,
                "reviews_count": reviews_count,
            }
        )
    return items
