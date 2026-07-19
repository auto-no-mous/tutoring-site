from fastapi import APIRouter, HTTPException, status

from app.api.deps import CurrentUser, DbSession
from app.models.enums import UserRole
from app.schemas.stats import StudentStatsOut, TutorStatsOut
from app.services import stats_service, tutor_service

router = APIRouter(prefix="/stats", tags=["stats"])


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
