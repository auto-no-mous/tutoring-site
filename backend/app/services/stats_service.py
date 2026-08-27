import calendar
import datetime as dt
import uuid

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.booking import Booking
from app.models.enums import (
    BookingOutcome,
    BookingStatus,
    GroupAttendanceOutcome,
    HomeworkSubmissionStatus,
)
from app.models.group import Group, GroupAttendance, GroupMembership, GroupOccurrence
from app.models.homework import HomeworkAssignment, HomeworkSubmission
from app.utils.time import utcnow

_ACTIVE_BOOKING_STATUSES = (BookingStatus.SCHEDULED.value, BookingStatus.COMPLETED.value)
_DONE_SUBMISSION_STATUSES = (HomeworkSubmissionStatus.SUBMITTED.value, HomeworkSubmissionStatus.DONE.value)
_NO_SHOW_OUTCOMES = (BookingOutcome.STUDENT_NO_SHOW.value, BookingOutcome.TUTOR_NO_SHOW.value)


def _held_individual_lesson(now: dt.datetime) -> tuple:
    """Условия, при которых индивидуальная запись считается проведённым занятием.

    Ровно тот же набор, по которому журнал активности рисует «Проведено успешно»
    (activity_log_service._individual_lesson_entries): две витрины одних и тех же
    данных расходиться не должны, а раньше расходились - счётчик учитывал всё, у чего
    прошло время и не снят статус, и потому засчитывал:

    - ручные блокировки времени в календаре репетитора (is_manual_block, ученика у них
      нет вовсе) - в журнале они не показываются как занятия;
    - записи, которые репетитор отметил как неявку - в журнале это отдельные
      «Ученик не явился» / «Репетитор не явился», а не проведённое занятие.

    Отменённые и перенесённые записи отсеиваются статусом: у переноса старая строка
    получает RESCHEDULED, а живой остаётся только новая (booking_service).
    Незаполненный outcome у прошедшей записи по-прежнему означает «проведено» - это
    осознанное умолчание модели, репетитор отмечает только исключения.
    """
    return (
        Booking.status.in_(_ACTIVE_BOOKING_STATUSES),
        Booking.end_at < now,
        Booking.is_manual_block.is_(False),
        Booking.student_id.is_not(None),
        or_(Booking.outcome.is_(None), Booking.outcome.not_in(_NO_SHOW_OUTCOMES)),
    )


def _month_bounds(now: dt.datetime) -> tuple[dt.datetime, dt.datetime]:
    start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    last_day = calendar.monthrange(now.year, now.month)[1]
    end = start.replace(day=last_day) + dt.timedelta(days=1)
    return start, end


async def get_tutor_stats(db: AsyncSession, tutor_id: uuid.UUID) -> dict:
    now = utcnow()
    month_start, month_end = _month_bounds(now)

    individual_held = await db.execute(
        select(func.count(Booking.id)).where(Booking.tutor_id == tutor_id, *_held_individual_lesson(now))
    )
    group_held = await db.execute(
        select(func.count(GroupOccurrence.id))
        .join(Group, Group.id == GroupOccurrence.group_id)
        .where(
            Group.tutor_id == tutor_id,
            GroupOccurrence.status.in_(("scheduled", "completed")),
            GroupOccurrence.end_at < now,
        )
    )
    total_lessons_held = (individual_held.scalar() or 0) + (group_held.scalar() or 0)

    homeworks_done = await db.execute(
        select(func.count(HomeworkSubmission.id))
        .join(HomeworkAssignment, HomeworkAssignment.id == HomeworkSubmission.assignment_id)
        .where(HomeworkAssignment.tutor_id == tutor_id, HomeworkSubmission.status.in_(_DONE_SUBMISSION_STATUSES))
    )

    individual_students = await db.execute(
        select(Booking.student_id.distinct()).where(
            Booking.tutor_id == tutor_id,
            Booking.student_id.is_not(None),
            Booking.status.in_(_ACTIVE_BOOKING_STATUSES),
            Booking.start_at >= month_start,
            Booking.start_at < month_end,
        )
    )
    group_students = await db.execute(
        select(GroupMembership.student_id.distinct())
        .join(Group, Group.id == GroupMembership.group_id)
        .join(GroupOccurrence, GroupOccurrence.group_id == Group.id)
        .where(
            Group.tutor_id == tutor_id,
            GroupOccurrence.start_at >= month_start,
            GroupOccurrence.start_at < month_end,
            GroupOccurrence.start_at >= GroupMembership.joined_at,
            or_(GroupMembership.left_at.is_(None), GroupOccurrence.start_at < GroupMembership.left_at),
        )
    )
    unique_students = {row[0] for row in individual_students.all()} | {row[0] for row in group_students.all()}

    return {
        "total_lessons_held": total_lessons_held,
        "homeworks_done": homeworks_done.scalar() or 0,
        "unique_students_this_month": len(unique_students),
    }


async def get_student_stats(db: AsyncSession, student_id: uuid.UUID) -> dict:
    now = utcnow()

    individual_completed = await db.execute(
        select(func.count(Booking.id)).where(Booking.student_id == student_id, *_held_individual_lesson(now))
    )
    group_completed = await db.execute(
        select(func.count(GroupOccurrence.id))
        .join(GroupMembership, GroupMembership.group_id == GroupOccurrence.group_id)
        .where(
            GroupMembership.student_id == student_id,
            GroupOccurrence.status.in_(("scheduled", "completed")),
            GroupOccurrence.end_at < now,
            GroupOccurrence.start_at >= GroupMembership.joined_at,
            or_(GroupMembership.left_at.is_(None), GroupOccurrence.start_at < GroupMembership.left_at),
            # Занятие группы состоялось, но конкретно этот ученик на нём не был -
            # в его личном счётчике «занятий пройдено» ему не место. Для счётчика
            # репетитора выше такое занятие, наоборот, остаётся проведённым.
            ~select(GroupAttendance.id)
            .where(
                GroupAttendance.occurrence_id == GroupOccurrence.id,
                GroupAttendance.student_id == student_id,
                GroupAttendance.outcome == GroupAttendanceOutcome.STUDENT_NO_SHOW.value,
            )
            .exists(),
        )
    )
    lessons_completed = (individual_completed.scalar() or 0) + (group_completed.scalar() or 0)

    total_result = await db.execute(
        select(func.count(HomeworkSubmission.id)).where(HomeworkSubmission.student_id == student_id)
    )
    done_result = await db.execute(
        select(func.count(HomeworkSubmission.id)).where(
            HomeworkSubmission.student_id == student_id,
            HomeworkSubmission.status.in_(_DONE_SUBMISSION_STATUSES),
        )
    )
    homework_total = total_result.scalar() or 0
    homework_done = done_result.scalar() or 0
    rate = (homework_done / homework_total) if homework_total > 0 else 0.0

    return {
        "lessons_completed": lessons_completed,
        "homework_total": homework_total,
        "homework_done": homework_done,
        "homework_completion_rate": rate,
    }
