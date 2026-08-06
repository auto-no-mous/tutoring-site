import datetime as dt
import uuid

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.enums import (
    BookedBy,
    GroupApplicationStatus,
    GroupAttendanceOutcome,
    GroupMembershipStatus,
    GroupOccurrenceStatus,
    NotificationEvent,
    UserRole,
)
from app.models.group import Group, GroupApplication, GroupAttendance, GroupMembership, GroupOccurrence, GroupSchedule
from app.models.lesson_type import LessonType
from app.models.tutor import TutorProfile
from app.models.user import User
from app.schemas.group import GroupCreate, GroupOccurrenceUpdate, GroupScheduleSlotIn, GroupUpdate
from app.services import chat_service, notification_service, schedule_service
from app.services.booking_service import get_student_names
from app.services.schedule_service import MSK
from app.utils.time import ensure_aware, utcnow

OCCURRENCE_WEEKS_AHEAD = 8


async def _get_group_lesson_type(db: AsyncSession, tutor_id: uuid.UUID, lesson_type_id: uuid.UUID) -> LessonType:
    result = await db.execute(
        select(LessonType).where(LessonType.id == lesson_type_id, LessonType.tutor_id == tutor_id)
    )
    lesson_type = result.scalar_one_or_none()
    if lesson_type is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Тип занятия не найден")
    if lesson_type.format != "group":
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Тип занятия не является групповым")
    return lesson_type


async def get_lesson_type_duration(db: AsyncSession, lesson_type_id: uuid.UUID) -> int:
    """Powers GroupOut.duration_minutes, so the frontend can render periodicity like
    "Среда 14:00, 90 мин" without a second round-trip per group."""
    lesson_type = await db.get(LessonType, lesson_type_id)
    return lesson_type.duration_minutes if lesson_type else 0


async def get_group_or_404(db: AsyncSession, group_id: uuid.UUID) -> Group:
    result = await db.execute(
        select(Group).options(selectinload(Group.schedule_slots)).where(Group.id == group_id)
    )
    group = result.scalar_one_or_none()
    if group is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Группа не найдена")
    return group


def require_owner(group: Group, tutor: TutorProfile) -> None:
    if group.tutor_id != tutor.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Это не ваша группа")


async def count_active_members(db: AsyncSession, group_id: uuid.UUID) -> int:
    result = await db.execute(
        select(GroupMembership).where(
            GroupMembership.group_id == group_id, GroupMembership.status == GroupMembershipStatus.ACTIVE.value
        )
    )
    return len(result.scalars().all())


async def create_group(db: AsyncSession, tutor: TutorProfile, payload: GroupCreate) -> Group:
    await _get_group_lesson_type(db, tutor.id, payload.lesson_type_id)

    group = Group(
        tutor_id=tutor.id,
        lesson_type_id=payload.lesson_type_id,
        name=payload.name,
        capacity=payload.capacity,
        meeting_link=payload.meeting_link,
    )
    db.add(group)
    await db.flush()

    for slot in payload.schedule_slots:
        db.add(GroupSchedule(group_id=group.id, weekday=slot.weekday, start_time=slot.start_time))

    await db.commit()
    await db.refresh(group)
    group = await get_group_or_404(db, group.id)

    await generate_occurrences(db, group)
    # Group chat is shared by all current/future members and the tutor (section 2.11) -
    # create it up front rather than lazily, since there's exactly one per group.
    await chat_service.create_group_thread(db, group.tutor_id, group.id)
    return group


async def update_group(db: AsyncSession, group: Group, payload: GroupUpdate) -> Group:
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(group, field, value)
    await db.commit()
    await db.refresh(group)
    return group


async def replace_schedule(db: AsyncSession, group: Group, slots: list[GroupScheduleSlotIn]) -> Group:
    for existing in list(group.schedule_slots):
        await db.delete(existing)
    await db.flush()

    for slot in slots:
        db.add(GroupSchedule(group_id=group.id, weekday=slot.weekday, start_time=slot.start_time))
    await db.commit()

    # populate_existing is required here: the session's identity map still holds
    # `group` (and its now-stale schedule_slots collection) from before this
    # function ran, and a plain selectinload query would otherwise silently return
    # that cached state instead of the rows just committed above.
    result = await db.execute(
        select(Group)
        .options(selectinload(Group.schedule_slots))
        .where(Group.id == group.id)
        .execution_options(populate_existing=True)
    )
    group = result.scalar_one()
    await generate_occurrences(db, group)
    return group


async def list_groups_for_tutor(db: AsyncSession, tutor_id: uuid.UUID) -> list[Group]:
    result = await db.execute(
        select(Group)
        .options(selectinload(Group.schedule_slots))
        .where(Group.tutor_id == tutor_id)
        .order_by(Group.created_at.desc())
    )
    return list(result.scalars().all())


async def list_all_groups(db: AsyncSession) -> list[Group]:
    result = await db.execute(select(Group).options(selectinload(Group.schedule_slots)))
    return list(result.scalars().all())


async def list_public_groups(db: AsyncSession, tutor_id: uuid.UUID) -> list[Group]:
    result = await db.execute(
        select(Group)
        .options(selectinload(Group.schedule_slots))
        .where(Group.tutor_id == tutor_id, Group.is_active.is_(True))
    )
    return list(result.scalars().all())


async def generate_occurrences(db: AsyncSession, group: Group, weeks_ahead: int = OCCURRENCE_WEEKS_AHEAD) -> list[GroupOccurrence]:
    """Generates upcoming dated sessions from the group's weekly schedule (section
    2.11). Anchored to "today" (unlike individual recurring bookings, a group's
    schedule isn't tied to one student's chosen first date - see
    booking_service.generate_recurring_occurrences for why that distinction matters).
    Skips weeks where an occurrence already exists or the tutor already has something
    else on at that time; leaves a gap rather than failing outright."""
    if not group.is_active:
        return []

    lesson_type = await db.get(LessonType, group.lesson_type_id)
    if lesson_type is None:
        return []

    tutor_profile = await db.get(TutorProfile, group.tutor_id)
    break_minutes = tutor_profile.break_between_lessons_minutes if tutor_profile else 0

    today_msk = utcnow().astimezone(MSK).date()
    now = utcnow()
    duration = dt.timedelta(minutes=lesson_type.duration_minutes)

    created: list[GroupOccurrence] = []
    for slot in group.schedule_slots:
        days_to_weekday = (slot.weekday - today_msk.weekday()) % 7
        base_date = today_msk + dt.timedelta(days=days_to_weekday)
        first_candidate_msk = dt.datetime.combine(base_date, slot.start_time, tzinfo=MSK)
        if first_candidate_msk.astimezone(dt.timezone.utc) <= now:
            base_date += dt.timedelta(days=7)

        for i in range(weeks_ahead):
            candidate_date = base_date + dt.timedelta(weeks=i)
            candidate_start_msk = dt.datetime.combine(candidate_date, slot.start_time, tzinfo=MSK)
            candidate_start_utc = candidate_start_msk.astimezone(dt.timezone.utc)
            candidate_end_utc = candidate_start_utc + duration

            existing = await db.execute(
                select(GroupOccurrence).where(
                    GroupOccurrence.group_id == group.id, GroupOccurrence.start_at == candidate_start_utc
                )
            )
            if existing.scalar_one_or_none() is not None:
                continue

            reserved_zones = await schedule_service.get_reserved_zones(
                db,
                group.tutor_id,
                candidate_start_utc - dt.timedelta(days=1),
                candidate_end_utc + dt.timedelta(days=1),
                break_minutes,
            )
            if schedule_service.slot_conflicts(candidate_start_utc, candidate_end_utc, break_minutes, reserved_zones):
                continue

            occurrence = GroupOccurrence(
                group_id=group.id,
                start_at=candidate_start_utc,
                end_at=candidate_end_utc,
                status=GroupOccurrenceStatus.SCHEDULED.value,
            )
            db.add(occurrence)
            created.append(occurrence)

    if created:
        await db.commit()
        for occurrence in created:
            await db.refresh(occurrence)
    return created


async def list_occurrences(db: AsyncSession, group_id: uuid.UUID) -> list[GroupOccurrence]:
    result = await db.execute(
        select(GroupOccurrence).where(GroupOccurrence.group_id == group_id).order_by(GroupOccurrence.start_at)
    )
    return list(result.scalars().all())


async def get_occurrence_or_404(db: AsyncSession, occurrence_id: uuid.UUID) -> GroupOccurrence:
    occurrence = await db.get(GroupOccurrence, occurrence_id)
    if occurrence is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Занятие группы не найдено")
    return occurrence


async def create_occurrence(db: AsyncSession, group: Group, start_at: dt.datetime, end_at: dt.datetime) -> GroupOccurrence:
    occurrence = GroupOccurrence(
        group_id=group.id, start_at=start_at, end_at=end_at, status=GroupOccurrenceStatus.SCHEDULED.value
    )
    db.add(occurrence)
    await db.commit()
    await db.refresh(occurrence)
    return occurrence


async def update_occurrence(db: AsyncSession, occurrence: GroupOccurrence, payload: GroupOccurrenceUpdate) -> GroupOccurrence:
    data = payload.model_dump(exclude_unset=True)
    if ("start_at" in data or "end_at" in data) and occurrence.original_start_at is None:
        occurrence.original_start_at = occurrence.start_at
        data.setdefault("status", GroupOccurrenceStatus.RESCHEDULED.value)
    for field, value in data.items():
        setattr(occurrence, field, value)
    await db.commit()
    await db.refresh(occurrence)
    return occurrence


async def delete_occurrence(db: AsyncSession, occurrence: GroupOccurrence) -> None:
    await db.delete(occurrence)
    await db.commit()


async def apply_to_group(db: AsyncSession, student: User, group: Group) -> GroupApplication:
    if not group.is_active:
        raise HTTPException(status.HTTP_409_CONFLICT, "Группа неактивна")

    existing_membership = await db.execute(
        select(GroupMembership).where(
            GroupMembership.group_id == group.id,
            GroupMembership.student_id == student.id,
            GroupMembership.status == GroupMembershipStatus.ACTIVE.value,
        )
    )
    if existing_membership.scalar_one_or_none() is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "Вы уже участвуете в этой группе")

    existing_application = await db.execute(
        select(GroupApplication).where(
            GroupApplication.group_id == group.id,
            GroupApplication.student_id == student.id,
            GroupApplication.status == GroupApplicationStatus.PENDING.value,
        )
    )
    if existing_application.scalar_one_or_none() is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "Заявка уже подана и ожидает решения")

    application = GroupApplication(group_id=group.id, student_id=student.id)
    db.add(application)
    await db.commit()
    await db.refresh(application)

    await notification_service.notify_tutor(
        db,
        group.tutor_id,
        NotificationEvent.GROUP_APPLICATION,
        "Новая заявка в группу",
        f"{student.display_name} подал(а) заявку на участие в группе «{group.name}».",
    )
    return application


async def list_applications(db: AsyncSession, group_id: uuid.UUID, status_filter: str | None = None) -> list[GroupApplication]:
    query = select(GroupApplication).where(GroupApplication.group_id == group_id)
    if status_filter is not None:
        query = query.where(GroupApplication.status == status_filter)
    result = await db.execute(query.order_by(GroupApplication.created_at))
    return list(result.scalars().all())


async def get_application_or_404(db: AsyncSession, application_id: uuid.UUID) -> GroupApplication:
    application = await db.get(GroupApplication, application_id)
    if application is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Заявка не найдена")
    return application


async def accept_application(db: AsyncSession, group: Group, application: GroupApplication) -> GroupMembership:
    if application.status != GroupApplicationStatus.PENDING.value:
        raise HTTPException(status.HTTP_409_CONFLICT, "Заявка уже обработана")

    active_count = await count_active_members(db, group.id)
    if active_count >= group.capacity:
        raise HTTPException(status.HTTP_409_CONFLICT, "В группе нет свободных мест")

    application.status = GroupApplicationStatus.ACCEPTED.value
    application.decided_at = utcnow()

    result = await db.execute(
        select(GroupMembership).where(
            GroupMembership.group_id == group.id, GroupMembership.student_id == application.student_id
        )
    )
    membership = result.scalar_one_or_none()
    if membership is not None:
        membership.status = GroupMembershipStatus.ACTIVE.value
        membership.joined_at = utcnow()
        membership.left_at = None
    else:
        membership = GroupMembership(group_id=group.id, student_id=application.student_id)
        db.add(membership)

    await db.commit()
    await db.refresh(membership)
    return membership


async def reject_application(db: AsyncSession, application: GroupApplication) -> GroupApplication:
    if application.status != GroupApplicationStatus.PENDING.value:
        raise HTTPException(status.HTTP_409_CONFLICT, "Заявка уже обработана")
    application.status = GroupApplicationStatus.REJECTED.value
    application.decided_at = utcnow()
    await db.commit()
    await db.refresh(application)
    return application


async def list_members(db: AsyncSession, group_id: uuid.UUID, active_only: bool = True) -> list[GroupMembership]:
    query = select(GroupMembership).where(GroupMembership.group_id == group_id)
    if active_only:
        query = query.where(GroupMembership.status == GroupMembershipStatus.ACTIVE.value)
    result = await db.execute(query)
    return list(result.scalars().all())


async def _leave(db: AsyncSession, membership: GroupMembership, actor: str) -> GroupMembership:
    membership.status = GroupMembershipStatus.LEFT.value
    membership.left_at = utcnow()
    membership.left_by = actor
    await db.commit()
    await db.refresh(membership)
    return membership


async def leave_group(db: AsyncSession, student: User, group: Group) -> GroupMembership:
    result = await db.execute(
        select(GroupMembership).where(
            GroupMembership.group_id == group.id,
            GroupMembership.student_id == student.id,
            GroupMembership.status == GroupMembershipStatus.ACTIVE.value,
        )
    )
    membership = result.scalar_one_or_none()
    if membership is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Вы не состоите в этой группе")
    membership = await _leave(db, membership, BookedBy.STUDENT.value)

    await notification_service.notify_tutor(
        db,
        group.tutor_id,
        NotificationEvent.GROUP_WITHDRAWAL,
        "Ученик покинул группу",
        f"{student.display_name} отказался(-ась) от участия в группе «{group.name}».",
    )
    return membership


async def remove_member_by_tutor(db: AsyncSession, group: Group, student_id: uuid.UUID) -> GroupMembership:
    result = await db.execute(
        select(GroupMembership).where(
            GroupMembership.group_id == group.id,
            GroupMembership.student_id == student_id,
            GroupMembership.status == GroupMembershipStatus.ACTIVE.value,
        )
    )
    membership = result.scalar_one_or_none()
    if membership is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Ученик не состоит в этой группе")
    return await _leave(db, membership, BookedBy.TUTOR.value)


async def admin_remove_member(db: AsyncSession, group: Group, student_id: uuid.UUID) -> GroupMembership:
    result = await db.execute(
        select(GroupMembership).where(
            GroupMembership.group_id == group.id,
            GroupMembership.student_id == student_id,
            GroupMembership.status == GroupMembershipStatus.ACTIVE.value,
        )
    )
    membership = result.scalar_one_or_none()
    if membership is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Ученик не состоит в этой группе")
    return await _leave(db, membership, BookedBy.ADMIN.value)


async def admin_reassign_tutor(db: AsyncSession, group: Group, tutor_id: uuid.UUID, lesson_type_id: uuid.UUID) -> Group:
    """Admin override: moves a group to a different tutor, along with a group-format
    lesson type belonging to that tutor (a group's lesson type must belong to its own
    tutor - see _get_group_lesson_type). Existing schedule slots/occurrences and
    memberships are left untouched; only future occurrence generation will use the new
    tutor's calendar."""
    await _get_group_lesson_type(db, tutor_id, lesson_type_id)
    group.tutor_id = tutor_id
    group.lesson_type_id = lesson_type_id
    await db.commit()
    await db.refresh(group)
    return group


async def admin_add_member(db: AsyncSession, group: Group, student_id: uuid.UUID) -> GroupMembership:
    """Admin override: enrolls a student directly, bypassing the apply/accept flow
    (section 2.11 normally requires one) - still respects group capacity."""
    student = await db.get(User, student_id)
    if student is None or student.role != UserRole.STUDENT.value:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Ученик не найден")

    result = await db.execute(
        select(GroupMembership).where(GroupMembership.group_id == group.id, GroupMembership.student_id == student_id)
    )
    membership = result.scalar_one_or_none()
    if membership is not None and membership.status == GroupMembershipStatus.ACTIVE.value:
        raise HTTPException(status.HTTP_409_CONFLICT, "Ученик уже состоит в этой группе")

    active_count = await count_active_members(db, group.id)
    if active_count >= group.capacity:
        raise HTTPException(status.HTTP_409_CONFLICT, "В группе нет свободных мест")

    if membership is not None:
        membership.status = GroupMembershipStatus.ACTIVE.value
        membership.joined_at = utcnow()
        membership.left_at = None
        membership.left_by = None
    else:
        membership = GroupMembership(group_id=group.id, student_id=student_id)
        db.add(membership)

    await db.commit()
    await db.refresh(membership)
    return membership


async def list_memberships_for_student(db: AsyncSession, student_id: uuid.UUID) -> list[GroupMembership]:
    """All of a student's memberships regardless of status - the frontend filters to
    active-only for the "my groups" display, but also uses the unfiltered list to
    decide whether the "Группы" cabinet tab should show at all (visible if the
    student is or ever was a member of some group, not just currently active)."""
    result = await db.execute(select(GroupMembership).where(GroupMembership.student_id == student_id))
    return list(result.scalars().all())


async def list_applications_for_student(db: AsyncSession, student_id: uuid.UUID) -> list[GroupApplication]:
    result = await db.execute(select(GroupApplication).where(GroupApplication.student_id == student_id))
    return list(result.scalars().all())


async def has_group_membership_with_tutor(db: AsyncSession, tutor_id: uuid.UUID, student_id: uuid.UUID) -> bool:
    """One half of the access check for GET /tutors/me/students/{id} (see
    api/v1/tutors.py::get_my_student) - a tutor may view a student's detail page if
    they share (or shared) a group, regardless of booking history."""
    result = await db.execute(
        select(GroupMembership.id)
        .join(Group, Group.id == GroupMembership.group_id)
        .where(Group.tutor_id == tutor_id, GroupMembership.student_id == student_id)
        .limit(1)
    )
    return result.scalar_one_or_none() is not None


async def list_student_group_memberships_for_tutor(
    db: AsyncSession, tutor_id: uuid.UUID, student_id: uuid.UUID
) -> list[tuple[Group, GroupMembership]]:
    """This student's memberships (any status) across the given tutor's own groups -
    powers the "groups" section of GET /tutors/me/students/{id}."""
    result = await db.execute(
        select(Group, GroupMembership)
        .join(GroupMembership, GroupMembership.group_id == Group.id)
        .where(Group.tutor_id == tutor_id, GroupMembership.student_id == student_id)
        .order_by(GroupMembership.joined_at.desc())
    )
    return [(row[0], row[1]) for row in result.all()]


async def list_active_member_ids_at(db: AsyncSession, group_id: uuid.UUID, at: dt.datetime) -> list[uuid.UUID]:
    """Students whose membership covered a given moment - same "were they actually
    in the group at the time" logic stats_service uses for monthly student counts."""
    result = await db.execute(
        select(GroupMembership.student_id).where(
            GroupMembership.group_id == group_id,
            GroupMembership.joined_at <= at,
            (GroupMembership.left_at.is_(None)) | (GroupMembership.left_at > at),
        )
    )
    return [row[0] for row in result.all()]


async def get_occurrence_attendance(db: AsyncSession, occurrence: GroupOccurrence) -> list[dict]:
    """Per-student outcome for a past occurrence, one entry per student who was an
    active member at occurrence.start_at. Students with no GroupAttendance row yet
    default to CONDUCTED (see GroupAttendance docstring)."""
    student_ids = await list_active_member_ids_at(db, occurrence.group_id, ensure_aware(occurrence.start_at))
    if not student_ids:
        return []

    result = await db.execute(
        select(GroupAttendance).where(
            GroupAttendance.occurrence_id == occurrence.id, GroupAttendance.student_id.in_(student_ids)
        )
    )
    outcomes = {row.student_id: row.outcome for row in result.scalars().all()}

    names = await get_student_names(db, student_ids)
    return [
        {
            "student_id": student_id,
            "student_display_name": names.get(student_id, ""),
            "outcome": outcomes.get(student_id, GroupAttendanceOutcome.CONDUCTED.value),
        }
        for student_id in student_ids
    ]


async def set_occurrence_attendance(
    db: AsyncSession, occurrence: GroupOccurrence, entries: list[tuple[uuid.UUID, str]]
) -> None:
    active_ids = set(await list_active_member_ids_at(db, occurrence.group_id, ensure_aware(occurrence.start_at)))

    result = await db.execute(
        select(GroupAttendance).where(GroupAttendance.occurrence_id == occurrence.id)
    )
    existing = {row.student_id: row for row in result.scalars().all()}

    for student_id, outcome in entries:
        if student_id not in active_ids:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Ученик не был участником группы на момент занятия")
        row = existing.get(student_id)
        if row is not None:
            row.outcome = outcome
        else:
            db.add(GroupAttendance(occurrence_id=occurrence.id, student_id=student_id, outcome=outcome))

    await db.commit()
