import datetime as dt
import uuid

from fastapi import APIRouter, File, HTTPException, UploadFile, status

from app.api.deps import CurrentUser, DbSession
from app.models.enums import UserRole
from app.models.user import User
from app.schemas.lesson_type import LessonTypeCreate, LessonTypeOut, LessonTypeUpdate
from app.schemas.schedule import AvailabilityIntervalOut, SlotOut, WeeklyAvailabilityReplace
from app.schemas.subject import TutorSubjectOut, TutorSubjectsReplace
from app.schemas.tutor import (
    TutorCatalogItem,
    TutorCatalogPageOut,
    TutorProfileOut,
    TutorProfileUpdate,
    TutorPublicProfile,
    TutorStudentOut,
    UploadedImageOut,
)
from app.services import (
    availability_service,
    booking_service,
    file_service,
    lesson_type_service,
    review_service,
    schedule_service,
    subject_service,
    tutor_service,
)

router = APIRouter(prefix="/tutors", tags=["tutors"])


def _require_tutor(user: CurrentUser) -> None:
    if user.role != UserRole.TUTOR:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Доступно только репетиторам")


def _to_profile_out(profile, user: User) -> TutorProfileOut:
    return TutorProfileOut.model_validate(profile, from_attributes=True).model_copy(
        update={
            "display_name": user.display_name,
            "is_active": user.is_active,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "patronymic": user.patronymic,
            "email": user.email,
        }
    )


@router.get("", response_model=TutorCatalogPageOut)
async def catalog(
    db: DbSession,
    subject_id: uuid.UUID | None = None,
    price_min: float | None = None,
    price_max: float | None = None,
    page: int = 1,
    page_size: int = 20,
) -> TutorCatalogPageOut:
    if page < 1 or not (1 <= page_size <= 100):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Некорректные параметры страницы")
    items, total = await tutor_service.search_catalog(
        db, subject_id=subject_id, price_min=price_min, price_max=price_max, page=page, page_size=page_size
    )
    return TutorCatalogPageOut(
        items=[TutorCatalogItem(**item) for item in items], total=total, page=page, page_size=page_size
    )


@router.get("/me", response_model=TutorProfileOut)
async def get_my_profile(current_user: CurrentUser, db: DbSession) -> TutorProfileOut:
    _require_tutor(current_user)
    profile = await tutor_service.get_profile_by_user_id(db, current_user.id)
    return _to_profile_out(profile, current_user)


@router.patch("/me", response_model=TutorProfileOut)
async def update_my_profile(
    payload: TutorProfileUpdate, current_user: CurrentUser, db: DbSession
) -> TutorProfileOut:
    _require_tutor(current_user)
    profile = await tutor_service.get_profile_by_user_id(db, current_user.id)
    profile = await tutor_service.update_profile(db, profile, payload)
    return _to_profile_out(profile, current_user)


@router.post("/me/photo", response_model=TutorProfileOut)
async def upload_my_photo(current_user: CurrentUser, db: DbSession, file: UploadFile = File(...)) -> TutorProfileOut:
    _require_tutor(current_user)
    profile = await tutor_service.get_profile_by_user_id(db, current_user.id)
    photo_url = await file_service.save_upload(file, "tutor-photos", file_service.ALLOWED_IMAGE_TYPES)
    profile = await tutor_service.set_photo(db, profile, photo_url)
    return _to_profile_out(profile, current_user)


@router.post("/me/about-image", response_model=UploadedImageOut)
async def upload_about_image(current_user: CurrentUser, db: DbSession, file: UploadFile = File(...)) -> UploadedImageOut:
    """Uploads an image for insertion into the "about" rich text field (see
    components/RichTextEditor.vue) - a separate endpoint from /me/photo since it
    doesn't touch the profile row, just returns a URL for the editor to embed."""
    _require_tutor(current_user)
    await tutor_service.get_profile_by_user_id(db, current_user.id)
    url = await file_service.save_upload(file, "tutor-about-images", file_service.ALLOWED_IMAGE_TYPES)
    return UploadedImageOut(url=url)


@router.get("/me/availability", response_model=list[AvailabilityIntervalOut])
async def get_my_availability(current_user: CurrentUser, db: DbSession) -> list[AvailabilityIntervalOut]:
    _require_tutor(current_user)
    profile = await tutor_service.get_profile_by_user_id(db, current_user.id)
    rows = await availability_service.list_availability(db, profile.id)
    return [AvailabilityIntervalOut.model_validate(r, from_attributes=True) for r in rows]


@router.put("/me/availability", response_model=list[AvailabilityIntervalOut])
async def replace_my_availability(
    payload: WeeklyAvailabilityReplace, current_user: CurrentUser, db: DbSession
) -> list[AvailabilityIntervalOut]:
    _require_tutor(current_user)
    profile = await tutor_service.get_profile_by_user_id(db, current_user.id)
    rows = await availability_service.replace_availability(db, profile, payload.intervals)
    return [AvailabilityIntervalOut.model_validate(r, from_attributes=True) for r in rows]


@router.get("/me/lesson-types", response_model=list[LessonTypeOut])
async def list_my_lesson_types(current_user: CurrentUser, db: DbSession) -> list[LessonTypeOut]:
    _require_tutor(current_user)
    profile = await tutor_service.get_profile_by_user_id(db, current_user.id)
    rows = await lesson_type_service.list_lesson_types(db, profile.id)
    return [LessonTypeOut.model_validate(r, from_attributes=True) for r in rows]


@router.post("/me/lesson-types", response_model=LessonTypeOut, status_code=status.HTTP_201_CREATED)
async def create_my_lesson_type(
    payload: LessonTypeCreate, current_user: CurrentUser, db: DbSession
) -> LessonTypeOut:
    _require_tutor(current_user)
    profile = await tutor_service.get_profile_by_user_id(db, current_user.id)
    lesson_type = await lesson_type_service.create_lesson_type(db, profile, payload)
    return LessonTypeOut.model_validate(lesson_type, from_attributes=True)


@router.patch("/me/lesson-types/{lesson_type_id}", response_model=LessonTypeOut)
async def update_my_lesson_type(
    lesson_type_id: uuid.UUID, payload: LessonTypeUpdate, current_user: CurrentUser, db: DbSession
) -> LessonTypeOut:
    _require_tutor(current_user)
    profile = await tutor_service.get_profile_by_user_id(db, current_user.id)
    lesson_type = await lesson_type_service.get_lesson_type(db, profile.id, lesson_type_id)
    lesson_type = await lesson_type_service.update_lesson_type(db, profile, lesson_type, payload)
    return LessonTypeOut.model_validate(lesson_type, from_attributes=True)


@router.delete("/me/lesson-types/{lesson_type_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_my_lesson_type(lesson_type_id: uuid.UUID, current_user: CurrentUser, db: DbSession) -> None:
    _require_tutor(current_user)
    profile = await tutor_service.get_profile_by_user_id(db, current_user.id)
    lesson_type = await lesson_type_service.get_lesson_type(db, profile.id, lesson_type_id)
    await lesson_type_service.delete_lesson_type(db, lesson_type)


@router.get("/me/subjects", response_model=list[TutorSubjectOut])
async def get_my_subjects(current_user: CurrentUser, db: DbSession) -> list[TutorSubjectOut]:
    _require_tutor(current_user)
    profile = await tutor_service.get_profile_by_user_id(db, current_user.id)
    rows = await subject_service.get_tutor_subjects(db, profile.id)
    return subject_service.to_tutor_subject_out(rows)


@router.put("/me/subjects", response_model=list[TutorSubjectOut])
async def replace_my_subjects(
    payload: TutorSubjectsReplace, current_user: CurrentUser, db: DbSession
) -> list[TutorSubjectOut]:
    _require_tutor(current_user)
    profile = await tutor_service.get_profile_by_user_id(db, current_user.id)
    rows = await subject_service.replace_tutor_subjects(db, profile, payload.selections)
    return subject_service.to_tutor_subject_out(rows)


@router.get("/me/students", response_model=list[TutorStudentOut])
async def get_my_students(current_user: CurrentUser, db: DbSession) -> list[TutorStudentOut]:
    _require_tutor(current_user)
    profile = await tutor_service.get_profile_by_user_id(db, current_user.id)
    rows = await booking_service.list_students_for_tutor(db, profile.id)
    return [TutorStudentOut(**row) for row in rows]


@router.get("/{tutor_id}", response_model=TutorPublicProfile)
async def get_public_profile(tutor_id: str, db: DbSession) -> TutorPublicProfile:
    profile = await tutor_service.get_profile_by_id_or_slug(db, tutor_id)
    user = await db.get(User, profile.user_id)
    avg_rating, reviews_count = await review_service.get_rating_summary(db, profile.id)
    subject_rows = await subject_service.get_tutor_subjects(db, profile.id)
    return TutorPublicProfile(
        id=profile.id,
        user_id=profile.user_id,
        display_name=user.display_name if user else "",
        photo_url=profile.photo_url,
        about=profile.about,
        subjects=subject_service.to_tutor_subject_out(subject_rows),
        avg_rating=avg_rating,
        reviews_count=reviews_count,
    )


@router.get("/{tutor_id}/lesson-types", response_model=list[LessonTypeOut])
async def list_public_lesson_types(tutor_id: uuid.UUID, db: DbSession) -> list[LessonTypeOut]:
    await tutor_service.get_profile_by_id(db, tutor_id)
    rows = await lesson_type_service.list_lesson_types(db, tutor_id, active_only=True)
    return [LessonTypeOut.model_validate(r, from_attributes=True) for r in rows]


@router.get("/{tutor_id}/availability/dates", response_model=list[dt.date])
async def get_available_dates(
    tutor_id: uuid.UUID,
    lesson_type_id: uuid.UUID,
    date_from: dt.date,
    date_to: dt.date,
    db: DbSession,
) -> list[dt.date]:
    if (date_to - date_from).days > 60:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Слишком большой диапазон дат")
    profile = await tutor_service.get_profile_by_id(db, tutor_id)
    lesson_type = await lesson_type_service.get_lesson_type(db, tutor_id, lesson_type_id)
    return await schedule_service.compute_available_dates(db, profile, lesson_type, date_from, date_to)


@router.get("/{tutor_id}/availability/slots", response_model=list[SlotOut])
async def get_day_slots(
    tutor_id: uuid.UUID,
    lesson_type_id: uuid.UUID,
    date: dt.date,
    db: DbSession,
) -> list[SlotOut]:
    profile = await tutor_service.get_profile_by_id(db, tutor_id)
    lesson_type = await lesson_type_service.get_lesson_type(db, tutor_id, lesson_type_id)
    return await schedule_service.compute_day_slots(db, profile, lesson_type, date)
