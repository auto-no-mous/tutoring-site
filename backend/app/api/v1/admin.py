import uuid

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import DbSession, require_roles
from app.models.enums import UserRole
from app.models.group import Group
from app.models.user import User
from app.schemas.admin import AdminBookingCreate, AdminStudentUpdate, AdminTutorUpdate
from app.schemas.booking import BookingOut, BookingTutorUpdate, ManualBookingCreate
from app.schemas.group import (
    GroupApplicationOut,
    GroupMembershipOut,
    GroupOut,
    GroupScheduleSlotOut,
    GroupUpdate,
)
from app.schemas.subject import (
    DirectionCreate,
    DirectionOut,
    DirectionUpdate,
    SubjectCreate,
    SubjectOut,
    SubjectUpdate,
)
from app.schemas.tutor import TutorProfileOut
from app.schemas.user import UserOut
from app.services import admin_service, booking_service, group_service, subject_service

router = APIRouter(
    prefix="/admin", tags=["admin"], dependencies=[Depends(require_roles(UserRole.ADMIN.value))]
)


def _to_group_out(group: Group, member_count: int) -> GroupOut:
    return GroupOut(
        id=group.id,
        tutor_id=group.tutor_id,
        lesson_type_id=group.lesson_type_id,
        name=group.name,
        capacity=group.capacity,
        meeting_link=group.meeting_link,
        is_active=group.is_active,
        schedule_slots=[GroupScheduleSlotOut.model_validate(s, from_attributes=True) for s in group.schedule_slots],
        member_count=member_count,
    )


# --- Tutors -------------------------------------------------------------------


def _to_profile_out(profile, user: User | None) -> TutorProfileOut:
    return TutorProfileOut.model_validate(profile, from_attributes=True).model_copy(
        update={
            "display_name": user.display_name if user else None,
            "is_active": user.is_active if user else None,
        }
    )


@router.get("/tutors", response_model=list[TutorProfileOut])
async def list_tutors(db: DbSession) -> list[TutorProfileOut]:
    profiles = await admin_service.list_tutors(db)
    out = []
    for profile in profiles:
        user = await db.get(User, profile.user_id)
        out.append(_to_profile_out(profile, user))
    return out


@router.get("/tutors/{tutor_id}", response_model=TutorProfileOut)
async def get_tutor(tutor_id: uuid.UUID, db: DbSession) -> TutorProfileOut:
    profile = await admin_service.get_tutor_or_404(db, tutor_id)
    user = await db.get(User, profile.user_id)
    return _to_profile_out(profile, user)


@router.patch("/tutors/{tutor_id}", response_model=TutorProfileOut)
async def update_tutor(tutor_id: uuid.UUID, payload: AdminTutorUpdate, db: DbSession) -> TutorProfileOut:
    profile = await admin_service.get_tutor_or_404(db, tutor_id)
    profile = await admin_service.update_tutor(db, profile, payload)
    user = await db.get(User, profile.user_id)
    return _to_profile_out(profile, user)


@router.delete("/tutors/{tutor_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_tutor(tutor_id: uuid.UUID, db: DbSession) -> None:
    profile = await admin_service.get_tutor_or_404(db, tutor_id)
    await admin_service.delete_tutor(db, profile)


# --- Students -------------------------------------------------------------------


@router.get("/students", response_model=list[UserOut])
async def list_students(db: DbSession) -> list[UserOut]:
    users = await admin_service.list_students(db)
    return [UserOut.model_validate(u, from_attributes=True) for u in users]


@router.get("/students/{student_id}", response_model=UserOut)
async def get_student(student_id: uuid.UUID, db: DbSession) -> UserOut:
    user = await admin_service.get_student_or_404(db, student_id)
    return UserOut.model_validate(user, from_attributes=True)


@router.patch("/students/{student_id}", response_model=UserOut)
async def update_student(student_id: uuid.UUID, payload: AdminStudentUpdate, db: DbSession) -> UserOut:
    user = await admin_service.get_student_or_404(db, student_id)
    user = await admin_service.update_student(db, user, payload)
    return UserOut.model_validate(user, from_attributes=True)


@router.delete("/students/{student_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_student(student_id: uuid.UUID, db: DbSession) -> None:
    user = await admin_service.get_student_or_404(db, student_id)
    await admin_service.delete_student(db, user)


# --- Bookings (individual lessons) -----------------------------------------------


@router.get("/bookings", response_model=list[BookingOut])
async def list_bookings(
    db: DbSession, tutor_id: uuid.UUID | None = None, student_id: uuid.UUID | None = None
) -> list[BookingOut]:
    rows = await booking_service.list_all_bookings(db, tutor_id, student_id)
    names = await booking_service.get_student_names(db, [r.student_id for r in rows if r.student_id])
    return [
        BookingOut.model_validate(r, from_attributes=True).model_copy(
            update={"student_display_name": names.get(r.student_id) if r.student_id else None}
        )
        for r in rows
    ]


@router.post("/bookings", response_model=BookingOut, status_code=status.HTTP_201_CREATED)
async def create_booking(payload: AdminBookingCreate, db: DbSession) -> BookingOut:
    tutor = await admin_service.get_tutor_or_404(db, payload.tutor_id)
    manual_payload = ManualBookingCreate(
        student_id=payload.student_id,
        lesson_type_id=payload.lesson_type_id,
        start_at=payload.start_at,
        end_at=payload.end_at,
        meeting_link=payload.meeting_link,
        notes=payload.notes,
        repeat_weekly=False,
    )
    booking = await booking_service.create_manual_booking(db, tutor, manual_payload)
    return BookingOut.model_validate(booking, from_attributes=True)


@router.patch("/bookings/{booking_id}", response_model=BookingOut)
async def update_booking(booking_id: uuid.UUID, payload: BookingTutorUpdate, db: DbSession) -> BookingOut:
    booking = await booking_service.get_booking_or_404(db, booking_id)
    booking = await booking_service.update_booking_by_tutor(db, booking, payload)
    return BookingOut.model_validate(booking, from_attributes=True)


@router.delete("/bookings/{booking_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_booking(booking_id: uuid.UUID, db: DbSession) -> None:
    booking = await booking_service.get_booking_or_404(db, booking_id)
    await booking_service.delete_booking(db, booking)


# --- Groups, applications, membership --------------------------------------------


@router.get("/groups", response_model=list[GroupOut])
async def list_groups(db: DbSession) -> list[GroupOut]:
    groups = await group_service.list_all_groups(db)
    out = []
    for group in groups:
        count = await group_service.count_active_members(db, group.id)
        out.append(_to_group_out(group, count))
    return out


@router.patch("/groups/{group_id}", response_model=GroupOut)
async def update_group(group_id: uuid.UUID, payload: GroupUpdate, db: DbSession) -> GroupOut:
    group = await group_service.get_group_or_404(db, group_id)
    group = await group_service.update_group(db, group, payload)
    count = await group_service.count_active_members(db, group.id)
    return _to_group_out(group, count)


@router.delete("/groups/{group_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_group(group_id: uuid.UUID, db: DbSession) -> None:
    group = await group_service.get_group_or_404(db, group_id)
    await db.delete(group)
    await db.commit()


@router.get("/groups/{group_id}/applications", response_model=list[GroupApplicationOut])
async def list_applications(group_id: uuid.UUID, db: DbSession) -> list[GroupApplicationOut]:
    await group_service.get_group_or_404(db, group_id)
    rows = await group_service.list_applications(db, group_id)
    return [GroupApplicationOut.model_validate(r, from_attributes=True) for r in rows]


@router.post("/groups/{group_id}/applications/{application_id}/accept", response_model=GroupMembershipOut)
async def accept_application(group_id: uuid.UUID, application_id: uuid.UUID, db: DbSession) -> GroupMembershipOut:
    group = await group_service.get_group_or_404(db, group_id)
    application = await group_service.get_application_or_404(db, application_id)
    if application.group_id != group.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Заявка не найдена")
    membership = await group_service.accept_application(db, group, application)
    return GroupMembershipOut.model_validate(membership, from_attributes=True)


@router.post("/groups/{group_id}/applications/{application_id}/reject", response_model=GroupApplicationOut)
async def reject_application(group_id: uuid.UUID, application_id: uuid.UUID, db: DbSession) -> GroupApplicationOut:
    group = await group_service.get_group_or_404(db, group_id)
    application = await group_service.get_application_or_404(db, application_id)
    if application.group_id != group.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Заявка не найдена")
    application = await group_service.reject_application(db, application)
    return GroupApplicationOut.model_validate(application, from_attributes=True)


@router.get("/groups/{group_id}/members", response_model=list[GroupMembershipOut])
async def list_members(group_id: uuid.UUID, db: DbSession) -> list[GroupMembershipOut]:
    await group_service.get_group_or_404(db, group_id)
    rows = await group_service.list_members(db, group_id)
    return [GroupMembershipOut.model_validate(r, from_attributes=True) for r in rows]


@router.delete("/groups/{group_id}/members/{student_id}", response_model=GroupMembershipOut)
async def remove_member(group_id: uuid.UUID, student_id: uuid.UUID, db: DbSession) -> GroupMembershipOut:
    group = await group_service.get_group_or_404(db, group_id)
    membership = await group_service.remove_member_by_tutor(db, group, student_id)
    return GroupMembershipOut.model_validate(membership, from_attributes=True)


# --- Subjects/directions (controlled vocabulary, section 10 redesign) -------------


@router.get("/subjects", response_model=list[SubjectOut])
async def list_subjects(db: DbSession) -> list[SubjectOut]:
    rows = await subject_service.list_subjects(db)
    return [SubjectOut.model_validate(s, from_attributes=True) for s in rows]


@router.post("/subjects", response_model=SubjectOut, status_code=status.HTTP_201_CREATED)
async def create_subject(payload: SubjectCreate, db: DbSession) -> SubjectOut:
    subject = await subject_service.create_subject(db, payload)
    return SubjectOut.model_validate(subject, from_attributes=True)


@router.patch("/subjects/{subject_id}", response_model=SubjectOut)
async def update_subject(subject_id: uuid.UUID, payload: SubjectUpdate, db: DbSession) -> SubjectOut:
    subject = await subject_service.get_subject_or_404(db, subject_id)
    subject = await subject_service.update_subject(db, subject, payload)
    return SubjectOut.model_validate(subject, from_attributes=True)


@router.delete("/subjects/{subject_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_subject(subject_id: uuid.UUID, db: DbSession) -> None:
    subject = await subject_service.get_subject_or_404(db, subject_id)
    await subject_service.delete_subject(db, subject)


@router.post("/subjects/{subject_id}/directions", response_model=DirectionOut, status_code=status.HTTP_201_CREATED)
async def create_direction(subject_id: uuid.UUID, payload: DirectionCreate, db: DbSession) -> DirectionOut:
    subject = await subject_service.get_subject_or_404(db, subject_id)
    direction = await subject_service.create_direction(db, subject, payload.name)
    return DirectionOut.model_validate(direction, from_attributes=True)


@router.patch("/directions/{direction_id}", response_model=DirectionOut)
async def update_direction(direction_id: uuid.UUID, payload: DirectionUpdate, db: DbSession) -> DirectionOut:
    direction = await subject_service.get_direction_or_404(db, direction_id)
    direction = await subject_service.update_direction(db, direction, payload.name)
    return DirectionOut.model_validate(direction, from_attributes=True)


@router.delete("/directions/{direction_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_direction(direction_id: uuid.UUID, db: DbSession) -> None:
    direction = await subject_service.get_direction_or_404(db, direction_id)
    await subject_service.delete_direction(db, direction)
