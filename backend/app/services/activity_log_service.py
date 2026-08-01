import datetime as dt
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.booking import Booking
from app.models.enums import (
    ActivityEventType,
    BookedBy,
    BookingOutcome,
    BookingStatus,
    GroupApplicationStatus,
    GroupAttendanceOutcome,
    GroupMembershipStatus,
    GroupOccurrenceStatus,
)
from app.models.group import Group, GroupApplication, GroupAttendance, GroupMembership, GroupOccurrence
from app.models.user import User
from app.services.booking_service import get_tutor_name_patronymic_map
from app.services.group_service import list_active_member_ids_at
from app.utils.time import ensure_aware, utcnow

_STATUS_LABELS: dict[str, str] = {
    ActivityEventType.LESSON_CONDUCTED.value: "Проведено успешно",
    ActivityEventType.LESSON_STUDENT_NO_SHOW.value: "Ученик не явился",
    ActivityEventType.LESSON_TUTOR_NO_SHOW.value: "Репетитор не явился",
    ActivityEventType.LESSON_CANCELLED_BY_STUDENT.value: "Отменено учеником",
    ActivityEventType.LESSON_CANCELLED_BY_TUTOR.value: "Отменено репетитором",
    ActivityEventType.LESSON_RESCHEDULED.value: "Перенесено учеником",
    ActivityEventType.GROUP_LESSON_CONDUCTED.value: "Проведено успешно",
    ActivityEventType.GROUP_LESSON_STUDENT_NO_SHOW.value: "Ученик не явился",
    ActivityEventType.GROUP_LESSON_CANCELLED.value: "Отменено репетитором",
    ActivityEventType.GROUP_LESSON_RESCHEDULED.value: "Перенесено репетитором",
    ActivityEventType.GROUP_APPLICATION_ACCEPTED.value: "Заявка принята",
    ActivityEventType.GROUP_APPLICATION_REJECTED.value: "Заявка отклонена",
    ActivityEventType.GROUP_MEMBERSHIP_LEFT.value: "Покинул группу",
    ActivityEventType.GROUP_MEMBERSHIP_REMOVED.value: "Исключён репетитором",
}

_INDIVIDUAL_LABEL = "Индивидуальное занятие"

# LESSON_RESCHEDULED covers all three actors (student/tutor/admin can each reschedule
# a booking, see booking_service.reschedule_booking / admin_reschedule_booking) - the
# fixed entry in _STATUS_LABELS is only the student-initiated default; the actual
# label is picked from here via booking.cancelled_by, see _individual_lesson_entries.
_RESCHEDULE_LABELS: dict[str, str] = {
    BookedBy.STUDENT.value: "Перенесено учеником",
    BookedBy.TUTOR.value: "Перенесено репетитором",
    BookedBy.ADMIN.value: "Перенесено администратором",
}


def _entry(
    entry_id: str,
    event_type: str,
    occurred_at: dt.datetime,
    *,
    lesson_at: dt.datetime | None = None,
    format_label: str,
    counterpart_label: str,
    counterpart_name: str,
    duration_minutes: int | None = None,
    status_label: str | None = None,
) -> dict:
    return {
        "id": entry_id,
        "event_type": event_type,
        "occurred_at": ensure_aware(occurred_at),
        "lesson_at": ensure_aware(lesson_at) if lesson_at is not None else None,
        "format_label": format_label,
        "counterpart_label": counterpart_label,
        "counterpart_name": counterpart_name,
        "duration_minutes": duration_minutes,
        "status_label": status_label or _STATUS_LABELS[event_type],
    }


async def _last_first_names(db: AsyncSession, student_ids: list[uuid.UUID]) -> dict[uuid.UUID, str]:
    ids = {sid for sid in student_ids if sid is not None}
    if not ids:
        return {}
    result = await db.execute(select(User.id, User.first_name, User.last_name).where(User.id.in_(ids)))
    return {row.id: f"{row.last_name} {row.first_name}".strip() for row in result.all()}


async def _individual_lesson_entries(
    db: AsyncSession,
    *,
    tutor_id: uuid.UUID | None,
    student_id: uuid.UUID | None,
    date_from: dt.datetime | None,
    date_to: dt.datetime | None,
) -> list[dict]:
    query = select(Booking).where(Booking.student_id.is_not(None), Booking.is_manual_block.is_(False))
    if tutor_id is not None:
        query = query.where(Booking.tutor_id == tutor_id)
    if student_id is not None:
        query = query.where(Booking.student_id == student_id)
    if date_from is not None:
        query = query.where(Booking.start_at >= date_from)
    if date_to is not None:
        query = query.where(Booking.start_at < date_to)

    rows = list((await db.execute(query)).scalars().all())
    if not rows:
        return []

    now = utcnow()
    is_tutor_view = tutor_id is not None
    if is_tutor_view:
        names = await _last_first_names(db, [r.student_id for r in rows])
    else:
        names = await get_tutor_name_patronymic_map(db, [r.tutor_id for r in rows])
    counterpart_label = "Ученик" if is_tutor_view else "Репетитор"

    entries: list[dict] = []
    for booking in rows:
        counterpart_name = names.get(booking.student_id if is_tutor_view else booking.tutor_id, "")
        duration = round((booking.end_at - booking.start_at).total_seconds() / 60)
        common = {
            "lesson_at": booking.start_at,
            "format_label": _INDIVIDUAL_LABEL,
            "counterpart_label": counterpart_label,
            "counterpart_name": counterpart_name,
            "duration_minutes": duration,
        }

        if booking.status == BookingStatus.CANCELLED_BY_STUDENT.value:
            entries.append(_entry(f"booking:{booking.id}", ActivityEventType.LESSON_CANCELLED_BY_STUDENT.value, booking.cancelled_at or booking.start_at, **common))
        elif booking.status == BookingStatus.CANCELLED_BY_TUTOR.value:
            entries.append(_entry(f"booking:{booking.id}", ActivityEventType.LESSON_CANCELLED_BY_TUTOR.value, booking.cancelled_at or booking.start_at, **common))
        elif booking.status == BookingStatus.RESCHEDULED.value:
            reschedule_label = _RESCHEDULE_LABELS.get(booking.cancelled_by, _RESCHEDULE_LABELS[BookedBy.STUDENT.value])
            entries.append(
                _entry(
                    f"booking:{booking.id}",
                    ActivityEventType.LESSON_RESCHEDULED.value,
                    booking.cancelled_at or booking.start_at,
                    status_label=reschedule_label,
                    **common,
                )
            )
        elif booking.status in (BookingStatus.SCHEDULED.value, BookingStatus.COMPLETED.value) and ensure_aware(booking.end_at) < now:
            outcome = booking.outcome or BookingOutcome.CONDUCTED.value
            event_type = {
                BookingOutcome.CONDUCTED.value: ActivityEventType.LESSON_CONDUCTED.value,
                BookingOutcome.STUDENT_NO_SHOW.value: ActivityEventType.LESSON_STUDENT_NO_SHOW.value,
                BookingOutcome.TUTOR_NO_SHOW.value: ActivityEventType.LESSON_TUTOR_NO_SHOW.value,
            }[outcome]
            entries.append(_entry(f"booking:{booking.id}", event_type, booking.end_at, **common))
    return entries


async def _group_lesson_and_application_entries(
    db: AsyncSession,
    *,
    tutor_id: uuid.UUID | None,
    student_id: uuid.UUID | None,
    date_from: dt.datetime | None,
    date_to: dt.datetime | None,
) -> list[dict]:
    group_query = select(Group)
    if tutor_id is not None:
        group_query = group_query.where(Group.tutor_id == tutor_id)
    elif student_id is not None:
        member_group_ids = select(GroupMembership.group_id).where(GroupMembership.student_id == student_id)
        applied_group_ids = select(GroupApplication.group_id).where(GroupApplication.student_id == student_id)
        group_query = group_query.where(Group.id.in_(member_group_ids) | Group.id.in_(applied_group_ids))
    groups = {g.id: g for g in (await db.execute(group_query)).scalars().all()}
    if not groups:
        return []
    group_ids = list(groups.keys())

    tutor_names = await get_tutor_name_patronymic_map(db, [g.tutor_id for g in groups.values()])
    is_tutor_view = tutor_id is not None
    counterpart_label = "Ученик" if is_tutor_view else "Репетитор"

    entries: list[dict] = []

    # --- group occurrences (whole-session cancel/reschedule + per-student attendance) ---
    occ_query = select(GroupOccurrence).where(GroupOccurrence.group_id.in_(group_ids))
    if date_from is not None:
        occ_query = occ_query.where(GroupOccurrence.start_at >= date_from)
    if date_to is not None:
        occ_query = occ_query.where(GroupOccurrence.start_at < date_to)
    occurrences = list((await db.execute(occ_query)).scalars().all())

    now = utcnow()
    past_live_occurrences = [
        o
        for o in occurrences
        if o.status in (GroupOccurrenceStatus.SCHEDULED.value, GroupOccurrenceStatus.COMPLETED.value)
        and ensure_aware(o.end_at) < now
    ]
    attendance_by_occurrence: dict[uuid.UUID, dict[uuid.UUID, str]] = {}
    if past_live_occurrences:
        occ_ids = [o.id for o in past_live_occurrences]
        rows = (
            await db.execute(select(GroupAttendance).where(GroupAttendance.occurrence_id.in_(occ_ids)))
        ).scalars().all()
        for row in rows:
            attendance_by_occurrence.setdefault(row.occurrence_id, {})[row.student_id] = row.outcome

    student_names: dict[uuid.UUID, str] = {}
    if is_tutor_view:
        all_active: set[uuid.UUID] = set()
        members_per_occurrence: dict[uuid.UUID, list[uuid.UUID]] = {}
        for occ in past_live_occurrences:
            active = await list_active_member_ids_at(db, occ.group_id, ensure_aware(occ.start_at))
            members_per_occurrence[occ.id] = active
            all_active.update(active)
        student_names = await _last_first_names(db, list(all_active))
    else:
        members_per_occurrence = {}

    for occ in occurrences:
        group = groups.get(occ.group_id)
        if group is None:
            continue
        format_label = f"Групповое занятие «{group.name}»"
        tutor_name = tutor_names.get(group.tutor_id, "")
        duration = round((occ.end_at - occ.start_at).total_seconds() / 60)

        if occ.status == GroupOccurrenceStatus.CANCELLED.value:
            # The tutor initiated this themselves via the Groups tab - it isn't news
            # to them, so only students who were actually enrolled at the time see it.
            if is_tutor_view or student_id not in await list_active_member_ids_at(db, occ.group_id, ensure_aware(occ.start_at)):
                continue
            entries.append(
                _entry(
                    f"occurrence:{occ.id}:cancelled",
                    ActivityEventType.GROUP_LESSON_CANCELLED.value,
                    occ.updated_at,
                    lesson_at=occ.start_at,
                    format_label=format_label,
                    counterpart_label=counterpart_label,
                    counterpart_name=tutor_name,
                    duration_minutes=duration,
                )
            )
        elif occ.status == GroupOccurrenceStatus.RESCHEDULED.value:
            if is_tutor_view or student_id not in await list_active_member_ids_at(db, occ.group_id, ensure_aware(occ.start_at)):
                continue
            entries.append(
                _entry(
                    f"occurrence:{occ.id}:rescheduled",
                    ActivityEventType.GROUP_LESSON_RESCHEDULED.value,
                    occ.updated_at,
                    lesson_at=occ.original_start_at or occ.start_at,
                    format_label=format_label,
                    counterpart_label=counterpart_label,
                    counterpart_name=tutor_name,
                    duration_minutes=duration,
                )
            )
        elif occ in past_live_occurrences:
            if is_tutor_view:
                for sid in members_per_occurrence.get(occ.id, []):
                    outcome = attendance_by_occurrence.get(occ.id, {}).get(sid, GroupAttendanceOutcome.CONDUCTED.value)
                    event_type = (
                        ActivityEventType.GROUP_LESSON_CONDUCTED.value
                        if outcome == GroupAttendanceOutcome.CONDUCTED.value
                        else ActivityEventType.GROUP_LESSON_STUDENT_NO_SHOW.value
                    )
                    entries.append(
                        _entry(
                            f"occurrence:{occ.id}:attendance:{sid}",
                            event_type,
                            occ.end_at,
                            lesson_at=occ.start_at,
                            format_label=format_label,
                            counterpart_label=counterpart_label,
                            counterpart_name=student_names.get(sid, ""),
                            duration_minutes=duration,
                        )
                    )
            elif student_id is not None:
                active = await list_active_member_ids_at(db, occ.group_id, ensure_aware(occ.start_at))
                if student_id not in active:
                    continue
                outcome = attendance_by_occurrence.get(occ.id, {}).get(student_id, GroupAttendanceOutcome.CONDUCTED.value)
                event_type = (
                    ActivityEventType.GROUP_LESSON_CONDUCTED.value
                    if outcome == GroupAttendanceOutcome.CONDUCTED.value
                    else ActivityEventType.GROUP_LESSON_STUDENT_NO_SHOW.value
                )
                entries.append(
                    _entry(
                        f"occurrence:{occ.id}:attendance:{student_id}",
                        event_type,
                        occ.end_at,
                        lesson_at=occ.start_at,
                        format_label=format_label,
                        counterpart_label=counterpart_label,
                        counterpart_name=tutor_name,
                        duration_minutes=duration,
                    )
                )

    # --- applications (accepted/rejected) ---
    app_query = select(GroupApplication).where(
        GroupApplication.group_id.in_(group_ids), GroupApplication.status != GroupApplicationStatus.PENDING.value
    )
    if student_id is not None:
        app_query = app_query.where(GroupApplication.student_id == student_id)
    if date_from is not None:
        app_query = app_query.where(GroupApplication.decided_at >= date_from)
    if date_to is not None:
        app_query = app_query.where(GroupApplication.decided_at < date_to)
    applications = list((await db.execute(app_query)).scalars().all())
    if applications:
        app_student_names = await _last_first_names(db, [a.student_id for a in applications]) if is_tutor_view else {}
        for app in applications:
            group = groups[app.group_id]
            counterpart_name = app_student_names.get(app.student_id, "") if is_tutor_view else tutor_names.get(group.tutor_id, "")
            event_type = (
                ActivityEventType.GROUP_APPLICATION_ACCEPTED.value
                if app.status == GroupApplicationStatus.ACCEPTED.value
                else ActivityEventType.GROUP_APPLICATION_REJECTED.value
            )
            entries.append(
                _entry(
                    f"application:{app.id}",
                    event_type,
                    app.decided_at or app.created_at,
                    format_label=f"Заявка в группу «{group.name}»",
                    counterpart_label=counterpart_label,
                    counterpart_name=counterpart_name,
                    duration_minutes=None,
                )
            )

    # --- memberships that ended (left / removed) ---
    mem_query = select(GroupMembership).where(
        GroupMembership.group_id.in_(group_ids), GroupMembership.status == GroupMembershipStatus.LEFT.value
    )
    if student_id is not None:
        mem_query = mem_query.where(GroupMembership.student_id == student_id)
    if date_from is not None:
        mem_query = mem_query.where(GroupMembership.left_at >= date_from)
    if date_to is not None:
        mem_query = mem_query.where(GroupMembership.left_at < date_to)
    memberships = list((await db.execute(mem_query)).scalars().all())
    if memberships:
        mem_student_names = await _last_first_names(db, [m.student_id for m in memberships]) if is_tutor_view else {}
        for membership in memberships:
            group = groups[membership.group_id]
            counterpart_name = mem_student_names.get(membership.student_id, "") if is_tutor_view else tutor_names.get(group.tutor_id, "")
            event_type = (
                ActivityEventType.GROUP_MEMBERSHIP_REMOVED.value
                if membership.left_by == BookedBy.TUTOR.value
                else ActivityEventType.GROUP_MEMBERSHIP_LEFT.value
            )
            entries.append(
                _entry(
                    f"membership:{membership.id}",
                    event_type,
                    membership.left_at,
                    format_label=f"Участие в группе «{group.name}»",
                    counterpart_label=counterpart_label,
                    counterpart_name=counterpart_name,
                    duration_minutes=None,
                )
            )

    return entries


async def list_activity_log(
    db: AsyncSession,
    *,
    tutor_id: uuid.UUID | None = None,
    student_id: uuid.UUID | None = None,
    event_types: list[str] | None = None,
    date_from: dt.datetime | None = None,
    date_to: dt.datetime | None = None,
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[dict], int]:
    """Returns (page of entries newest-first, total matching count). Exactly one of
    tutor_id/student_id should be given - the log is always scoped to one viewer."""
    individual = await _individual_lesson_entries(
        db, tutor_id=tutor_id, student_id=student_id, date_from=date_from, date_to=date_to
    )
    group = await _group_lesson_and_application_entries(
        db, tutor_id=tutor_id, student_id=student_id, date_from=date_from, date_to=date_to
    )
    entries = individual + group

    if event_types:
        wanted = set(event_types)
        entries = [e for e in entries if e["event_type"] in wanted]

    entries.sort(key=lambda e: e["occurred_at"], reverse=True)

    total = len(entries)
    start = (page - 1) * page_size
    return entries[start : start + page_size], total
