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
from app.utils.html_sanitize import strip_html_to_text


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


# "me" is already a reserved path segment for the tutor's own /tutors/me/* routes -
# a tutor with this slug would make /tutors/me resolve to the self-service endpoint
# instead of their public profile.
RESERVED_SLUGS = {"me"}


async def get_profile_by_id_or_slug(db: AsyncSession, id_or_slug: str) -> TutorProfile:
    """Public-profile lookup (see api/v1/tutors.py::get_public_profile): accepts
    either the tutor's real UUID or their custom slug, so /tutors/<slug> and
    /tutors/<uuid> both work."""
    try:
        tutor_id = uuid.UUID(id_or_slug)
    except ValueError:
        result = await db.execute(select(TutorProfile).where(TutorProfile.slug == id_or_slug))
        profile = result.scalar_one_or_none()
    else:
        profile = await db.get(TutorProfile, tutor_id)
    if profile is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Анкета репетитора не найдена")
    return profile


async def _apply_slug_change(db: AsyncSession, profile: TutorProfile, slug: str) -> None:
    if slug in RESERVED_SLUGS:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Этот ник зарезервирован, выберите другой")
    result = await db.execute(select(TutorProfile.id).where(TutorProfile.slug == slug, TutorProfile.id != profile.id))
    if result.scalar_one_or_none() is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "Этот ник уже занят другим репетитором")
    profile.slug = slug


async def update_profile(db: AsyncSession, profile: TutorProfile, payload: TutorProfileUpdate) -> TutorProfile:
    data = payload.model_dump(exclude_unset=True)
    if "slug" in data:
        slug = data.pop("slug")
        if slug is None:
            profile.slug = None
        else:
            await _apply_slug_change(db, profile, slug)
    for field, value in data.items():
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
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[dict], int]:
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

    total = (await db.execute(select(func.count()).select_from(query.subquery()))).scalar_one()

    query = query.order_by(User.display_name).offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(query)
    rows = result.all()
    tutor_ids = [profile.id for profile, *_ in rows]
    ratings = await review_service.get_rating_summaries(db, tutor_ids)
    subjects_by_tutor = await subject_service.get_subject_names_for_tutors(db, tutor_ids)
    # Group lesson types aren't part of price_agg (it covers individual formats only,
    # since group seats aren't comparable per hour), so whether to show the group
    # booking button needs its own lookup - one query for the whole page.
    tutors_with_group_type = set(
        (
            await db.execute(
                select(LessonType.tutor_id)
                .where(
                    LessonType.tutor_id.in_(tutor_ids),
                    LessonType.is_active.is_(True),
                    LessonType.format == LessonFormat.GROUP.value,
                )
                .distinct()
            )
        )
        .scalars()
        .all()
    )

    about_snippet_length = 140

    items = []
    for profile, display_name, first_name, patronymic, hourly_price in rows:
        avg_rating, reviews_count = ratings.get(profile.id, (None, 0))
        about_snippet = None
        if profile.about:
            about_text = strip_html_to_text(profile.about)
            if about_text:
                about_snippet = (
                    about_text[:about_snippet_length] + "…"
                    if len(about_text) > about_snippet_length
                    else about_text
                )
        items.append(
            {
                "id": profile.id,
                "user_id": profile.user_id,
                "display_name": display_name,
                "name_patronymic": f"{first_name} {patronymic}" if patronymic else first_name,
                "photo_url": profile.photo_url,
                "slug": profile.slug,
                "subjects": subjects_by_tutor.get(profile.id, []),
                "hourly_price": float(hourly_price) if hourly_price is not None else None,
                "avg_rating": avg_rating,
                "reviews_count": reviews_count,
                "about_snippet": about_snippet,
                # hourly_price is only computed from active individual-format lesson
                # types (see the price_agg subquery above), so its presence already
                # tells us whether the tutor has one - same rule as the public
                # profile's show_individual_booking.
                "show_individual_booking": bool(profile.allow_individual_bookings) and hourly_price is not None,
                "show_group_booking": bool(profile.allow_group_bookings)
                and profile.id in tutors_with_group_type,
            }
        )
    return items, total
