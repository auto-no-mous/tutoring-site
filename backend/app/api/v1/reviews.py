import uuid

from fastapi import APIRouter, HTTPException, status

from app.api.deps import CurrentUser, DbSession
from app.models.enums import UserRole
from app.schemas.review import RatingSummary, ReviewCreate, ReviewOut
from app.services import review_service, tutor_service

router = APIRouter(tags=["reviews"])


@router.post("/tutors/{tutor_id}/reviews", response_model=ReviewOut)
async def create_or_update_review(tutor_id: uuid.UUID, payload: ReviewCreate, current_user: CurrentUser, db: DbSession) -> ReviewOut:
    if current_user.role != UserRole.STUDENT:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Доступно только ученикам")
    await tutor_service.get_profile_by_id(db, tutor_id)
    review = await review_service.upsert_review(db, current_user, tutor_id, payload)
    return ReviewOut.model_validate(review, from_attributes=True).model_copy(
        update={"student_display_name": current_user.display_name}
    )


@router.get("/tutors/{tutor_id}/reviews", response_model=list[ReviewOut])
async def list_reviews(tutor_id: uuid.UUID, db: DbSession) -> list[ReviewOut]:
    await tutor_service.get_profile_by_id(db, tutor_id)
    rows = await review_service.list_reviews_for_tutor(db, tutor_id)
    return [ReviewOut(**row) for row in rows]


@router.get("/tutors/{tutor_id}/rating", response_model=RatingSummary)
async def get_rating(tutor_id: uuid.UUID, db: DbSession) -> RatingSummary:
    await tutor_service.get_profile_by_id(db, tutor_id)
    average, count = await review_service.get_rating_summary(db, tutor_id)
    return RatingSummary(average=average, count=count)
