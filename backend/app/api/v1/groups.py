import uuid

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from app.api.deps import CurrentUser, DbSession
from app.models.enums import GroupAttendanceOutcome, UserRole
from app.models.group import Group
from app.models.lesson_type import LessonType
from app.models.tutor import TutorProfile
from app.models.user import User
from app.schemas.group import (
    GroupApplicationCreate,
    GroupApplicationOut,
    GroupAttendanceEntryOut,
    GroupAttendanceReplace,
    GroupCreate,
    GroupMembershipOut,
    GroupOccurrenceCreate,
    GroupOccurrenceOut,
    GroupOccurrenceUpdate,
    GroupOut,
    GroupPublicOut,
    GroupScheduleSlotIn,
    GroupScheduleSlotOut,
    GroupUpdate,
    StudentGroupOccurrenceOut,
)
from app.services import group_service, tutor_service
from app.services.booking_service import get_student_names

router = APIRouter(prefix="/groups", tags=["groups"])
public_router = APIRouter(tags=["groups"])


def _require_tutor(user: CurrentUser) -> None:
    if user.role != UserRole.TUTOR:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Доступно только репетиторам")


def _require_student(user: CurrentUser) -> None:
    if user.role != UserRole.STUDENT:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Доступно только ученикам")


def _to_group_out(group: Group, member_count: int, duration_minutes: int) -> GroupOut:
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
        created_at=group.created_at,
        duration_minutes=duration_minutes,
    )


async def _owned_group(db: DbSession, current_user: CurrentUser, group_id: uuid.UUID) -> Group:
    profile = await tutor_service.get_profile_by_user_id(db, current_user.id)
    group = await group_service.get_group_or_404(db, group_id)
    group_service.require_owner(group, profile)
    return group


async def _group_and_tutor_names(db: DbSession, group_ids: list[uuid.UUID]) -> dict[uuid.UUID, tuple[str, str]]:
    """Batch-resolves {group_id: (group_name, tutor_display_name)} for enriching a
    student's own memberships/applications list, which otherwise only carry raw ids."""
    if not group_ids:
        return {}
    groups_result = await db.execute(select(Group).where(Group.id.in_(group_ids)))
    groups = {g.id: g for g in groups_result.scalars().all()}

    tutor_ids = {g.tutor_id for g in groups.values()}
    tutors_result = await db.execute(select(TutorProfile).where(TutorProfile.id.in_(tutor_ids)))
    tutors = {t.id: t for t in tutors_result.scalars().all()}

    user_ids = {t.user_id for t in tutors.values()}
    users_result = await db.execute(select(User).where(User.id.in_(user_ids)))
    user_names = {u.id: u.display_name for u in users_result.scalars().all()}

    out: dict[uuid.UUID, tuple[str, str]] = {}
    for group_id, group in groups.items():
        tutor = tutors.get(group.tutor_id)
        tutor_name = user_names.get(tutor.user_id, "") if tutor else ""
        out[group_id] = (group.name, tutor_name)
    return out


@router.post("", response_model=GroupOut, status_code=status.HTTP_201_CREATED)
async def create_group(payload: GroupCreate, current_user: CurrentUser, db: DbSession) -> GroupOut:
    _require_tutor(current_user)
    profile = await tutor_service.get_profile_by_user_id(db, current_user.id)
    group = await group_service.create_group(db, profile, payload)
    duration = await group_service.get_lesson_type_duration(db, group.lesson_type_id)
    return _to_group_out(group, 0, duration)


@router.get("/tutor/me", response_model=list[GroupOut])
async def list_my_groups(current_user: CurrentUser, db: DbSession) -> list[GroupOut]:
    _require_tutor(current_user)
    profile = await tutor_service.get_profile_by_user_id(db, current_user.id)
    groups = await group_service.list_groups_for_tutor(db, profile.id)
    out = []
    for group in groups:
        count = await group_service.count_active_members(db, group.id)
        duration = await group_service.get_lesson_type_duration(db, group.lesson_type_id)
        out.append(_to_group_out(group, count, duration))
    return out


# NB: these two literal "/me" routes must be registered before the "/{group_id}"
# pattern routes below - otherwise "me" gets parsed as group_id and fails UUID
# validation instead of ever reaching these handlers.
@router.get("/me", response_model=list[GroupMembershipOut])
async def my_memberships(current_user: CurrentUser, db: DbSession) -> list[GroupMembershipOut]:
    _require_student(current_user)
    rows = await group_service.list_memberships_for_student(db, current_user.id)
    names = await _group_and_tutor_names(db, [r.group_id for r in rows])
    out = []
    for r in rows:
        group_name, tutor_name = names.get(r.group_id, ("", ""))
        out.append(
            GroupMembershipOut.model_validate(r, from_attributes=True).model_copy(
                update={"group_name": group_name, "tutor_display_name": tutor_name}
            )
        )
    return out


@router.get("/me/applications", response_model=list[GroupApplicationOut])
async def my_applications(current_user: CurrentUser, db: DbSession) -> list[GroupApplicationOut]:
    _require_student(current_user)
    rows = await group_service.list_applications_for_student(db, current_user.id)
    names = await _group_and_tutor_names(db, [r.group_id for r in rows])
    out = []
    for r in rows:
        group_name, tutor_name = names.get(r.group_id, ("", ""))
        out.append(
            GroupApplicationOut.model_validate(r, from_attributes=True).model_copy(
                update={"group_name": group_name, "tutor_display_name": tutor_name}
            )
        )
    return out


async def _to_student_occurrence_out_list(
    db: DbSession, rows: list, current_user: CurrentUser
) -> list[StudentGroupOccurrenceOut]:
    names = await _group_and_tutor_names(db, [r.group_id for r in rows])
    groups_result = await db.execute(select(Group).where(Group.id.in_([r.group_id for r in rows] or [None])))
    meeting_links = {g.id: g.meeting_link for g in groups_result.scalars().all()}
    attendance = await group_service.get_own_attendance_map(db, current_user.id, [r.id for r in rows])
    out = []
    for r in rows:
        group_name, tutor_name = names.get(r.group_id, ("", ""))
        out.append(
            StudentGroupOccurrenceOut.model_validate(r, from_attributes=True).model_copy(
                update={
                    "group_name": group_name,
                    "tutor_display_name": tutor_name,
                    "meeting_link": meeting_links.get(r.group_id),
                    "my_attendance_outcome": attendance.get(r.id),
                }
            )
        )
    return out


@router.get("/me/occurrences", response_model=list[StudentGroupOccurrenceOut])
async def my_occurrences(current_user: CurrentUser, db: DbSession) -> list[StudentGroupOccurrenceOut]:
    """Every dated session of every group the student is an active member of - merged
    into the student's "Занятия" schedule alongside individual bookings (see
    student/BookingsTab.vue)."""
    _require_student(current_user)
    rows = await group_service.list_occurrences_for_student(db, current_user.id)
    return await _to_student_occurrence_out_list(db, rows, current_user)


@router.post("/me/occurrences/{occurrence_id}/no-show", response_model=StudentGroupOccurrenceOut)
async def mark_own_no_show(occurrence_id: uuid.UUID, current_user: CurrentUser, db: DbSession) -> StudentGroupOccurrenceOut:
    """Student-initiated "I won't attend this session" (the group-lesson card's
    "Отменить" button, see components/GroupOccurrenceCard.vue) - notifies the tutor,
    but unlike an individual booking cancellation the occurrence itself keeps
    happening for everyone else."""
    _require_student(current_user)
    occurrence = await group_service.get_occurrence_or_404(db, occurrence_id)
    occurrence = await group_service.mark_own_no_show(db, occurrence, current_user)
    out = await _to_student_occurrence_out_list(db, [occurrence], current_user)
    return out[0]


@router.patch("/{group_id}", response_model=GroupOut)
async def update_group(group_id: uuid.UUID, payload: GroupUpdate, current_user: CurrentUser, db: DbSession) -> GroupOut:
    _require_tutor(current_user)
    group = await _owned_group(db, current_user, group_id)
    group = await group_service.update_group(db, group, payload)
    count = await group_service.count_active_members(db, group.id)
    duration = await group_service.get_lesson_type_duration(db, group.lesson_type_id)
    return _to_group_out(group, count, duration)


@router.delete("/{group_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_group(group_id: uuid.UUID, current_user: CurrentUser, db: DbSession) -> None:
    """Only for an empty group, and the group chat survives it - see
    group_service.delete_group."""
    _require_tutor(current_user)
    group = await _owned_group(db, current_user, group_id)
    await group_service.delete_group(db, group)


@router.put("/{group_id}/schedule", response_model=GroupOut)
async def replace_group_schedule(
    group_id: uuid.UUID, payload: list[GroupScheduleSlotIn], current_user: CurrentUser, db: DbSession
) -> GroupOut:
    _require_tutor(current_user)
    group = await _owned_group(db, current_user, group_id)
    group = await group_service.replace_schedule(db, group, payload)
    count = await group_service.count_active_members(db, group.id)
    duration = await group_service.get_lesson_type_duration(db, group.lesson_type_id)
    return _to_group_out(group, count, duration)


@router.get("/{group_id}/applications", response_model=list[GroupApplicationOut])
async def list_applications(group_id: uuid.UUID, current_user: CurrentUser, db: DbSession, status_filter: str | None = None) -> list[GroupApplicationOut]:
    _require_tutor(current_user)
    await _owned_group(db, current_user, group_id)
    rows = await group_service.list_applications(db, group_id, status_filter)
    names = await get_student_names(db, [r.student_id for r in rows])
    return [
        GroupApplicationOut.model_validate(r, from_attributes=True).model_copy(
            update={"student_display_name": names.get(r.student_id, "")}
        )
        for r in rows
    ]


@router.post("/{group_id}/applications/{application_id}/accept", response_model=GroupMembershipOut)
async def accept_application(group_id: uuid.UUID, application_id: uuid.UUID, current_user: CurrentUser, db: DbSession) -> GroupMembershipOut:
    _require_tutor(current_user)
    group = await _owned_group(db, current_user, group_id)
    application = await group_service.get_application_or_404(db, application_id)
    if application.group_id != group.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Заявка не найдена")
    membership = await group_service.accept_application(db, group, application)
    return GroupMembershipOut.model_validate(membership, from_attributes=True)


@router.post("/{group_id}/applications/{application_id}/reject", response_model=GroupApplicationOut)
async def reject_application(group_id: uuid.UUID, application_id: uuid.UUID, current_user: CurrentUser, db: DbSession) -> GroupApplicationOut:
    _require_tutor(current_user)
    group = await _owned_group(db, current_user, group_id)
    application = await group_service.get_application_or_404(db, application_id)
    if application.group_id != group.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Заявка не найдена")
    application = await group_service.reject_application(db, application)
    return GroupApplicationOut.model_validate(application, from_attributes=True)


@router.get("/{group_id}/members", response_model=list[GroupMembershipOut])
async def list_members(group_id: uuid.UUID, current_user: CurrentUser, db: DbSession) -> list[GroupMembershipOut]:
    _require_tutor(current_user)
    await _owned_group(db, current_user, group_id)
    rows = await group_service.list_members(db, group_id)
    names = await get_student_names(db, [r.student_id for r in rows])
    return [
        GroupMembershipOut.model_validate(r, from_attributes=True).model_copy(
            update={"student_display_name": names.get(r.student_id, "")}
        )
        for r in rows
    ]


@router.delete("/{group_id}/members/{student_id}", response_model=GroupMembershipOut)
async def remove_member(group_id: uuid.UUID, student_id: uuid.UUID, current_user: CurrentUser, db: DbSession) -> GroupMembershipOut:
    _require_tutor(current_user)
    group = await _owned_group(db, current_user, group_id)
    membership = await group_service.remove_member_by_tutor(db, group, student_id)
    return GroupMembershipOut.model_validate(membership, from_attributes=True)


@router.get("/{group_id}/occurrences", response_model=list[GroupOccurrenceOut])
async def list_occurrences(group_id: uuid.UUID, db: DbSession) -> list[GroupOccurrenceOut]:
    await group_service.get_group_or_404(db, group_id)
    rows = await group_service.list_occurrences(db, group_id)
    return [GroupOccurrenceOut.model_validate(r, from_attributes=True) for r in rows]


@router.post("/{group_id}/occurrences", response_model=GroupOccurrenceOut, status_code=status.HTTP_201_CREATED)
async def create_occurrence(group_id: uuid.UUID, payload: GroupOccurrenceCreate, current_user: CurrentUser, db: DbSession) -> GroupOccurrenceOut:
    _require_tutor(current_user)
    group = await _owned_group(db, current_user, group_id)
    occurrence = await group_service.create_occurrence(db, group, payload.start_at, payload.end_at)
    return GroupOccurrenceOut.model_validate(occurrence, from_attributes=True)


@router.patch("/{group_id}/occurrences/{occurrence_id}", response_model=GroupOccurrenceOut)
async def update_occurrence(group_id: uuid.UUID, occurrence_id: uuid.UUID, payload: GroupOccurrenceUpdate, current_user: CurrentUser, db: DbSession) -> GroupOccurrenceOut:
    _require_tutor(current_user)
    await _owned_group(db, current_user, group_id)
    occurrence = await group_service.get_occurrence_or_404(db, occurrence_id)
    if occurrence.group_id != group_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Занятие группы не найдено")
    occurrence = await group_service.update_occurrence(db, occurrence, payload)
    return GroupOccurrenceOut.model_validate(occurrence, from_attributes=True)


@router.delete("/{group_id}/occurrences/{occurrence_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_occurrence(group_id: uuid.UUID, occurrence_id: uuid.UUID, current_user: CurrentUser, db: DbSession) -> None:
    _require_tutor(current_user)
    await _owned_group(db, current_user, group_id)
    occurrence = await group_service.get_occurrence_or_404(db, occurrence_id)
    if occurrence.group_id != group_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Занятие группы не найдено")
    await group_service.delete_occurrence(db, occurrence)


@router.get("/{group_id}/occurrences/{occurrence_id}/attendance", response_model=list[GroupAttendanceEntryOut])
async def get_occurrence_attendance(
    group_id: uuid.UUID, occurrence_id: uuid.UUID, current_user: CurrentUser, db: DbSession
) -> list[GroupAttendanceEntryOut]:
    _require_tutor(current_user)
    await _owned_group(db, current_user, group_id)
    occurrence = await group_service.get_occurrence_or_404(db, occurrence_id)
    if occurrence.group_id != group_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Занятие группы не найдено")
    rows = await group_service.get_occurrence_attendance(db, occurrence)
    return [GroupAttendanceEntryOut(**row) for row in rows]


@router.put("/{group_id}/occurrences/{occurrence_id}/attendance", response_model=list[GroupAttendanceEntryOut])
async def set_occurrence_attendance(
    group_id: uuid.UUID,
    occurrence_id: uuid.UUID,
    payload: GroupAttendanceReplace,
    current_user: CurrentUser,
    db: DbSession,
) -> list[GroupAttendanceEntryOut]:
    _require_tutor(current_user)
    await _owned_group(db, current_user, group_id)
    occurrence = await group_service.get_occurrence_or_404(db, occurrence_id)
    if occurrence.group_id != group_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Занятие группы не найдено")
    valid_outcomes = {o.value for o in GroupAttendanceOutcome}
    for entry in payload.entries:
        if entry.outcome not in valid_outcomes:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Некорректный статус посещения")
    await group_service.set_occurrence_attendance(
        db, occurrence, [(e.student_id, e.outcome) for e in payload.entries]
    )
    rows = await group_service.get_occurrence_attendance(db, occurrence)
    return [GroupAttendanceEntryOut(**row) for row in rows]


@router.post("/{group_id}/apply", response_model=GroupApplicationOut, status_code=status.HTTP_201_CREATED)
async def apply_to_group(group_id: uuid.UUID, payload: GroupApplicationCreate, current_user: CurrentUser, db: DbSession) -> GroupApplicationOut:
    _require_student(current_user)
    group = await group_service.get_group_or_404(db, group_id)
    application = await group_service.apply_to_group(db, current_user, group)
    if payload.message:
        application.message = payload.message
        await db.commit()
        await db.refresh(application)
    return GroupApplicationOut.model_validate(application, from_attributes=True)


@router.post("/{group_id}/leave", response_model=GroupMembershipOut)
async def leave_group(group_id: uuid.UUID, current_user: CurrentUser, db: DbSession) -> GroupMembershipOut:
    _require_student(current_user)
    group = await group_service.get_group_or_404(db, group_id)
    membership = await group_service.leave_group(db, current_user, group)
    return GroupMembershipOut.model_validate(membership, from_attributes=True)


@public_router.get("/tutors/{tutor_id}/groups", response_model=list[GroupPublicOut], tags=["groups"])
async def list_tutor_groups(tutor_id: uuid.UUID, db: DbSession) -> list[GroupPublicOut]:
    await tutor_service.get_profile_by_id(db, tutor_id)
    groups = await group_service.list_public_groups(db, tutor_id)
    out = []
    for group in groups:
        lesson_type = await db.get(LessonType, group.lesson_type_id)
        count = await group_service.count_active_members(db, group.id)
        out.append(
            GroupPublicOut(
                id=group.id,
                tutor_id=group.tutor_id,
                name=group.name,
                capacity=group.capacity,
                member_count=count,
                price=float(lesson_type.price) if lesson_type else 0.0,
                duration_minutes=lesson_type.duration_minutes if lesson_type else 0,
                schedule_slots=[
                    GroupScheduleSlotOut.model_validate(s, from_attributes=True) for s in group.schedule_slots
                ],
            )
        )
    return out
