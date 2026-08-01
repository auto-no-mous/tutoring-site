import datetime as dt

from fastapi import APIRouter, HTTPException, Query, status

from app.api.deps import CurrentUser, DbSession
from app.models.enums import ActivityEventType, UserRole
from app.schemas.stats import ActivityLogPageOut, StudentStatsOut, TutorStatsOut
from app.services import activity_log_service, stats_service, tutor_service

router = APIRouter(prefix="/stats", tags=["stats"])

_VALID_EVENT_TYPES = {e.value for e in ActivityEventType}


async def _log_page(
    *,
    tutor_id=None,
    student_id=None,
    event_types: list[str] | None,
    date_from: dt.date | None,
    date_to: dt.date | None,
    page: int,
    page_size: int,
    db: DbSession,
) -> ActivityLogPageOut:
    if event_types:
        unknown = set(event_types) - _VALID_EVENT_TYPES
        if unknown:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, f"Неизвестные типы событий: {sorted(unknown)}")
    if page < 1 or not (1 <= page_size <= 100):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Некорректные параметры страницы")

    from_dt = dt.datetime.combine(date_from, dt.time.min, tzinfo=dt.timezone.utc) if date_from else None
    to_dt = dt.datetime.combine(date_to + dt.timedelta(days=1), dt.time.min, tzinfo=dt.timezone.utc) if date_to else None

    entries, total = await activity_log_service.list_activity_log(
        db,
        tutor_id=tutor_id,
        student_id=student_id,
        event_types=event_types,
        date_from=from_dt,
        date_to=to_dt,
        page=page,
        page_size=page_size,
    )
    return ActivityLogPageOut(entries=entries, total=total, page=page, page_size=page_size)


@router.get("/tutor/me", response_model=TutorStatsOut)
async def my_tutor_stats(current_user: CurrentUser, db: DbSession) -> TutorStatsOut:
    if current_user.role != UserRole.TUTOR:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Доступно только репетиторам")
    profile = await tutor_service.get_profile_by_user_id(db, current_user.id)
    data = await stats_service.get_tutor_stats(db, profile.id)
    return TutorStatsOut(**data)


@router.get("/student/me", response_model=StudentStatsOut)
async def my_student_stats(current_user: CurrentUser, db: DbSession) -> StudentStatsOut:
    if current_user.role != UserRole.STUDENT:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Доступно только ученикам")
    data = await stats_service.get_student_stats(db, current_user.id)
    return StudentStatsOut(**data)


@router.get("/tutor/me/log", response_model=ActivityLogPageOut)
async def my_tutor_log(
    current_user: CurrentUser,
    db: DbSession,
    event_types: list[str] | None = Query(default=None),
    date_from: dt.date | None = None,
    date_to: dt.date | None = None,
    page: int = 1,
    page_size: int = 20,
) -> ActivityLogPageOut:
    if current_user.role != UserRole.TUTOR:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Доступно только репетиторам")
    profile = await tutor_service.get_profile_by_user_id(db, current_user.id)
    return await _log_page(
        tutor_id=profile.id,
        event_types=event_types,
        date_from=date_from,
        date_to=date_to,
        page=page,
        page_size=page_size,
        db=db,
    )


@router.get("/student/me/log", response_model=ActivityLogPageOut)
async def my_student_log(
    current_user: CurrentUser,
    db: DbSession,
    event_types: list[str] | None = Query(default=None),
    date_from: dt.date | None = None,
    date_to: dt.date | None = None,
    page: int = 1,
    page_size: int = 20,
) -> ActivityLogPageOut:
    if current_user.role != UserRole.STUDENT:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Доступно только ученикам")
    return await _log_page(
        student_id=current_user.id,
        event_types=event_types,
        date_from=date_from,
        date_to=date_to,
        page=page,
        page_size=page_size,
        db=db,
    )
