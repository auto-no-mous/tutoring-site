import datetime as dt
import uuid

from fastapi import HTTPException, status
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.booking import Booking, RecurringSeries
from app.models.enums import (
    BookedBy,
    BookingStatus,
    GroupOccurrenceStatus,
    NotificationEvent,
    SystemNotificationEvent,
    UserRole,
)
from app.models.group import Group, GroupOccurrence
from app.models.lesson_type import LessonType
from app.models.subject import TutorSubject, TutorSubjectDirection
from app.models.tutor import TutorProfile
from app.models.user import User
from app.schemas.booking import BookingTutorUpdate, ManualBookingCreate
from app.services import notification_service, schedule_service, system_notification_service, tutor_service
from app.services.schedule_service import MSK
from app.utils.time import ensure_aware, utcnow

RECURRING_WEEKS_AHEAD = 8


def _fmt_date_time(moment: dt.datetime) -> tuple[str, str]:
    """Splits a moment into (date, time) strings in MSK for system-notification
    template placeholders {date}/{time}/{old_date}/{old_time}/{new_date}/{new_time} -
    see system_notification_service.DEFAULT_TEMPLATES."""
    local = ensure_aware(moment).astimezone(MSK)
    return f"{local:%d.%m.%Y}", f"{local:%H:%M}"


async def _get_active_lesson_type(db: AsyncSession, tutor_id: uuid.UUID, lesson_type_id: uuid.UUID) -> LessonType:
    result = await db.execute(
        select(LessonType).where(
            LessonType.id == lesson_type_id, LessonType.tutor_id == tutor_id, LessonType.is_active.is_(True)
        )
    )
    lesson_type = result.scalar_one_or_none()
    if lesson_type is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Тип занятия не найден")
    if lesson_type.format != "individual":
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Тип занятия не является индивидуальным")
    return lesson_type


async def get_booking_or_404(db: AsyncSession, booking_id: uuid.UUID) -> Booking:
    booking = await db.get(Booking, booking_id)
    if booking is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Занятие не найдено")
    return booking


async def list_bookings_for_student(db: AsyncSession, student_id: uuid.UUID) -> list[Booking]:
    result = await db.execute(
        select(Booking).where(Booking.student_id == student_id).order_by(Booking.start_at)
    )
    return list(result.scalars().all())


async def list_bookings_for_tutor(db: AsyncSession, tutor_id: uuid.UUID) -> list[Booking]:
    result = await db.execute(
        select(Booking).where(Booking.tutor_id == tutor_id).order_by(Booking.start_at)
    )
    return list(result.scalars().all())


async def has_had_booking(db: AsyncSession, tutor_id: uuid.UUID, student_id: uuid.UUID) -> bool:
    """One half of the access check for GET /tutors/me/students/{id} (see
    app/services/group_service.has_group_membership_with_tutor for the other half) -
    a tutor may view a student's detail page if they've ever had a booking together,
    regardless of current group membership."""
    result = await db.execute(
        select(Booking.id).where(Booking.tutor_id == tutor_id, Booking.student_id == student_id).limit(1)
    )
    return result.scalar_one_or_none() is not None


async def get_student_names(db: AsyncSession, student_ids: list[uuid.UUID]) -> dict[uuid.UUID, str]:
    ids = {sid for sid in student_ids if sid is not None}
    if not ids:
        return {}
    result = await db.execute(select(User.id, User.display_name).where(User.id.in_(ids)))
    return dict(result.all())


async def list_students_for_tutor(db: AsyncSession, tutor_id: uuid.UUID) -> list[dict]:
    """Ученики репетитора для выпадающих списков (запись вручную, выдача домашки):
    все, с кем есть или были занятия, плюс заведённые им вручную - последних надо
    выбирать ещё до первой записи, иначе их незачем было бы заводить.

    Сначала те, с кем занимались недавно; ученики без единого занятия - в конце.
    """
    last_lesson = (
        select(Booking.student_id, func.max(Booking.start_at).label("last_start_at"))
        .where(Booking.tutor_id == tutor_id, Booking.student_id.is_not(None))
        .group_by(Booking.student_id)
        .subquery()
    )
    result = await db.execute(
        select(User.id, User.first_name, User.last_name, User.grade, last_lesson.c.last_start_at)
        .outerjoin(last_lesson, last_lesson.c.student_id == User.id)
        .where(
            or_(
                last_lesson.c.last_start_at.is_not(None),
                User.managed_by_tutor_id == tutor_id,
            )
        )
        .order_by(last_lesson.c.last_start_at.desc().nulls_last())
    )
    return [
        {
            "id": student_id,
            "first_name": first_name,
            "last_name": last_name,
            "grade": grade,
            "last_lesson_at": last_start_at,
        }
        for student_id, first_name, last_name, grade, last_start_at in result.all()
    ]


async def get_series_active_map(db: AsyncSession, series_ids: list[uuid.UUID | None]) -> dict[uuid.UUID, bool]:
    ids = {sid for sid in series_ids if sid is not None}
    if not ids:
        return {}
    result = await db.execute(select(RecurringSeries.id, RecurringSeries.is_active).where(RecurringSeries.id.in_(ids)))
    return dict(result.all())


async def get_lesson_type_names(db: AsyncSession, lesson_type_ids: list[uuid.UUID | None]) -> dict[uuid.UUID, str]:
    ids = {i for i in lesson_type_ids if i is not None}
    if not ids:
        return {}
    result = await db.execute(select(LessonType.id, LessonType.name).where(LessonType.id.in_(ids)))
    return dict(result.all())


async def get_lesson_type_formats(db: AsyncSession, lesson_type_ids: list[uuid.UUID | None]) -> dict[uuid.UUID, str]:
    """"individual" / "group" per lesson type - lets every booking card show what kind
    of lesson it is (see BookingOut.lesson_type_format)."""
    ids = {i for i in lesson_type_ids if i is not None}
    if not ids:
        return {}
    result = await db.execute(select(LessonType.id, LessonType.format).where(LessonType.id.in_(ids)))
    return dict(result.all())


async def get_tutor_name_patronymic_map(db: AsyncSession, tutor_ids: list[uuid.UUID | None]) -> dict[uuid.UUID, str]:
    """"Имя Отчество" only (no surname) - the format used on student-facing booking
    cards, see api/v1/bookings.py::_to_booking_out."""
    ids = {i for i in tutor_ids if i is not None}
    if not ids:
        return {}
    result = await db.execute(
        select(TutorProfile.id, User.first_name, User.patronymic)
        .join(User, User.id == TutorProfile.user_id)
        .where(TutorProfile.id.in_(ids))
    )
    return {
        tutor_id: f"{first_name} {patronymic}" if patronymic else first_name
        for tutor_id, first_name, patronymic in result.all()
    }


async def list_all_bookings(
    db: AsyncSession,
    tutor_id: uuid.UUID | None = None,
    student_id: uuid.UUID | None = None,
    date_from: dt.datetime | None = None,
    date_to: dt.datetime | None = None,
    subject_id: uuid.UUID | None = None,
    direction_id: uuid.UUID | None = None,
    grade: int | None = None,
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[Booking], int]:
    """Admin bookings list (see api/v1/admin.py). subject_id/direction_id/grade filter
    by attributes of the tutor/student rather than the booking itself - a booking
    doesn't record which subject was taught, so this narrows to "tutor teaches this
    subject/direction" and "student is in this grade" respectively, mirroring the
    subquery-based filtering tutor_service.search_catalog already uses for the public
    catalog's subject filter."""
    query = select(Booking)
    if tutor_id is not None:
        query = query.where(Booking.tutor_id == tutor_id)
    if student_id is not None:
        query = query.where(Booking.student_id == student_id)
    if date_from is not None:
        query = query.where(Booking.start_at >= date_from)
    if date_to is not None:
        query = query.where(Booking.start_at < date_to)
    if subject_id is not None:
        query = query.where(
            Booking.tutor_id.in_(select(TutorSubject.tutor_id).where(TutorSubject.subject_id == subject_id))
        )
    if direction_id is not None:
        query = query.where(
            Booking.tutor_id.in_(
                select(TutorSubject.tutor_id)
                .join(TutorSubjectDirection, TutorSubjectDirection.tutor_subject_id == TutorSubject.id)
                .where(TutorSubjectDirection.direction_id == direction_id)
            )
        )
    if grade is not None:
        query = query.where(Booking.student_id.in_(select(User.id).where(User.grade == grade)))

    total = (await db.execute(select(func.count()).select_from(query.subquery()))).scalar_one()
    query = query.order_by(Booking.start_at).offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(query)
    return list(result.scalars().all()), total


async def get_tutor_display_names(db: AsyncSession, tutor_ids: list[uuid.UUID]) -> dict[uuid.UUID, str]:
    """Full "Фамилия Имя Отчество" tutor names, keyed by TutorProfile.id - used by the
    admin bookings list (unlike get_tutor_name_patronymic_map's "Имя Отчество"-only
    student-facing format)."""
    ids = {i for i in tutor_ids if i is not None}
    if not ids:
        return {}
    result = await db.execute(
        select(TutorProfile.id, User.display_name).join(User, User.id == TutorProfile.user_id).where(TutorProfile.id.in_(ids))
    )
    return dict(result.all())


async def generate_recurring_occurrences(
    db: AsyncSession,
    series: RecurringSeries,
    initiated_by: str,
    anchor_date: dt.date,
    weeks_ahead: int = RECURRING_WEEKS_AHEAD,
    start_offset: int = 1,
    enforce_schedule: bool = True,
) -> list[Booking]:
    """Creates upcoming occurrences for an active series (section 2.4), weekly from
    `anchor_date` (the date of the booking the series was created from - NOT "today":
    anchoring to today would drift the whole series if the first booking was made
    further out than a week, and could even generate a date earlier than the one the
    student actually picked). Weeks where a booking already exists or the slot is no
    longer available are silently skipped - the series has a gap rather than the whole
    generation failing.

    A future periodic top-up job should anchor from the series' latest existing
    occurrence instead of a fixed anchor_date, to keep extending the rolling window."""
    if not series.is_active:
        return []

    tutor = await db.get(TutorProfile, series.tutor_id)
    lesson_type = await db.get(LessonType, series.lesson_type_id)
    if tutor is None or lesson_type is None:
        return []

    created: list[Booking] = []
    for i in range(start_offset, start_offset + weeks_ahead):
        candidate_date = anchor_date + dt.timedelta(weeks=i)
        candidate_start_msk = dt.datetime.combine(candidate_date, series.start_time, tzinfo=MSK)
        candidate_start_utc = candidate_start_msk.astimezone(dt.timezone.utc)
        candidate_end_utc = candidate_start_utc + dt.timedelta(minutes=lesson_type.duration_minutes)

        existing = await db.execute(
            select(Booking).where(
                Booking.recurring_series_id == series.id, Booking.start_at == candidate_start_utc
            )
        )
        if existing.scalar_one_or_none() is not None:
            continue

        # Серию, назначенную репетитором, недельная сетка не ограничивает: он ставит
        # занятие там, где считает нужным, ровно как в ручной записи. Иначе
        # "каждый вторник в 18:00" вне его расписания молча породило бы одно занятие
        # вместо серии. Пересечения с занятым временем пропускаем в любом случае.
        if enforce_schedule:
            if not await schedule_service.is_slot_available(db, tutor, lesson_type, candidate_start_utc):
                continue
        elif await schedule_service.has_conflict(db, tutor, lesson_type, candidate_start_utc):
            continue

        booking = Booking(
            tutor_id=series.tutor_id,
            student_id=series.student_id,
            lesson_type_id=series.lesson_type_id,
            start_at=candidate_start_utc,
            end_at=candidate_end_utc,
            status=BookingStatus.SCHEDULED.value,
            booked_by=initiated_by,
            recurring_series_id=series.id,
        )
        db.add(booking)
        created.append(booking)

    if created:
        await db.commit()
        for booking in created:
            await db.refresh(booking)
    return created


async def create_student_booking(
    db: AsyncSession, student: User, tutor_id: uuid.UUID, lesson_type_id: uuid.UUID, start_at: dt.datetime, repeat_weekly: bool
) -> Booking:
    tutor = await db.get(TutorProfile, tutor_id)
    if tutor is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Репетитор не найден")
    lesson_type = await _get_active_lesson_type(db, tutor_id, lesson_type_id)

    if not await schedule_service.is_slot_available(db, tutor, lesson_type, start_at):
        raise HTTPException(status.HTTP_409_CONFLICT, "Выбранное время уже недоступно")

    # Проверяем ДО вставки: сразу после неё "первая запись" перестала бы быть первой.
    is_first_with_tutor = not await has_had_booking(db, tutor_id, student.id)

    end_at = start_at + dt.timedelta(minutes=lesson_type.duration_minutes)
    booking = Booking(
        tutor_id=tutor_id,
        student_id=student.id,
        lesson_type_id=lesson_type_id,
        start_at=start_at,
        end_at=end_at,
        status=BookingStatus.SCHEDULED.value,
        booked_by=BookedBy.STUDENT.value,
    )
    db.add(booking)
    await db.commit()
    await db.refresh(booking)

    tutor_user = await db.get(User, tutor.user_id)
    if is_first_with_tutor and tutor_user is not None:
        # Первое занятие пары - развёрнутое письмо обоим (см. notify_first_booking).
        await notification_service.notify_first_booking(
            db,
            student=student,
            tutor_user=tutor_user,
            start_at=start_at,
            lesson_name=lesson_type.name,
        )
    else:
        await notification_service.notify_tutor(
            db,
            tutor_id,
            NotificationEvent.NEW_BOOKING,
            "Новая запись на занятие",
            f"{student.display_name} записался(-ась) на {start_at.astimezone(MSK):%d.%m.%Y %H:%M} (МСК).",
        )

    if repeat_weekly:
        start_msk = start_at.astimezone(MSK)
        series = RecurringSeries(
            tutor_id=tutor_id,
            student_id=student.id,
            lesson_type_id=lesson_type_id,
            weekday=start_msk.weekday(),
            start_time=start_msk.time(),
        )
        db.add(series)
        await db.commit()
        await db.refresh(series)

        booking.recurring_series_id = series.id
        await db.commit()
        await db.refresh(booking)

        await generate_recurring_occurrences(
            db, series, initiated_by=BookedBy.STUDENT.value, anchor_date=start_msk.date()
        )

    return booking


async def describe_conflicts(
    db: AsyncSession, tutor: TutorProfile, start_at: dt.datetime, end_at: dt.datetime
) -> list[str]:
    """Человеческое описание того, с чем пересекается предполагаемое время.

    Нужно, чтобы отказ был не «время занято», а «занято вот этим»: репетитор решает,
    ставить ли занятие внахлёст, и для этого должен видеть, поверх чего оно ляжет.
    Окно расширено на перерыв между занятиями - в него упирается та же проверка, что
    и в create_manual_booking, и «пересечение» может означать just нарушенный перерыв.
    """
    gap = dt.timedelta(minutes=tutor.break_between_lessons_minutes)
    window_start = start_at - gap
    window_end = end_at + gap

    bookings = await db.execute(
        select(Booking).where(
            Booking.tutor_id == tutor.id,
            Booking.status == BookingStatus.SCHEDULED.value,
            Booking.start_at < window_end,
            Booking.end_at > window_start,
        )
    )
    rows = list(bookings.scalars().all())
    student_names = await get_student_names(db, [b.student_id for b in rows if b.student_id])

    described: list[tuple[dt.datetime, str]] = []
    for booking in rows:
        who = student_names.get(booking.student_id, "занятие") if booking.student_id else "блок времени"
        described.append((ensure_aware(booking.start_at), _format_conflict(booking.start_at, booking.end_at, who)))

    occurrences = await db.execute(
        select(GroupOccurrence, Group.name)
        .join(Group, Group.id == GroupOccurrence.group_id)
        .where(
            Group.tutor_id == tutor.id,
            GroupOccurrence.status == GroupOccurrenceStatus.SCHEDULED.value,
            GroupOccurrence.start_at < window_end,
            GroupOccurrence.end_at > window_start,
        )
    )
    for occurrence, group_name in occurrences.all():
        described.append(
            (
                ensure_aware(occurrence.start_at),
                _format_conflict(occurrence.start_at, occurrence.end_at, f"группа «{group_name}»"),
            )
        )

    described.sort(key=lambda item: item[0])
    return [text for _, text in described]


def _format_conflict(start_at: dt.datetime, end_at: dt.datetime, who: str) -> str:
    start_msk = ensure_aware(start_at).astimezone(MSK)
    end_msk = ensure_aware(end_at).astimezone(MSK)
    return f"{start_msk:%d.%m %H:%M}-{end_msk:%H:%M} ({who})"


async def create_manual_booking(db: AsyncSession, tutor: TutorProfile, payload: ManualBookingCreate) -> Booking:
    student = None
    is_first_with_tutor = False
    if payload.student_id is not None:
        student = await db.get(User, payload.student_id)
        if student is None or student.role != "student":
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Ученик не найден")
        # Как и в записи ученика: считаем до вставки самой записи.
        is_first_with_tutor = not await has_had_booking(db, tutor.id, student.id)

    lesson_type = None
    if payload.lesson_type_id is not None:
        result = await db.execute(
            select(LessonType).where(LessonType.id == payload.lesson_type_id, LessonType.tutor_id == tutor.id)
        )
        lesson_type = result.scalar_one_or_none()
        if lesson_type is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Тип занятия не найден")

    if payload.end_at <= payload.start_at:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Время окончания должно быть позже начала")

    reserved_zones = await schedule_service.get_reserved_zones(
        db,
        tutor.id,
        payload.start_at - dt.timedelta(days=1),
        payload.end_at + dt.timedelta(days=1),
        tutor.break_between_lessons_minutes,
    )
    if schedule_service.slot_conflicts(
        payload.start_at, payload.end_at, tutor.break_between_lessons_minutes, reserved_zones
    ) and not payload.allow_overlap:
        # Не запрет, а вопрос: интерфейс показывает, с чем пересекается, и повторяет
        # запрос с allow_overlap, если репетитор всё же настаивает. Сознательный
        # нахлёст - его право: он один знает, что в это время действительно возможно.
        conflicts = await describe_conflicts(db, tutor, payload.start_at, payload.end_at)
        listed = "; ".join(conflicts) if conflicts else "существующей записью"
        raise HTTPException(status.HTTP_409_CONFLICT, f"Время пересекается с: {listed}")

    booking = Booking(
        tutor_id=tutor.id,
        student_id=payload.student_id,
        lesson_type_id=payload.lesson_type_id,
        start_at=payload.start_at,
        end_at=payload.end_at,
        status=BookingStatus.SCHEDULED.value,
        is_manual_block=payload.student_id is None,
        booked_by=BookedBy.TUTOR.value,
        meeting_link=payload.meeting_link,
        notes=payload.notes,
    )
    db.add(booking)
    await db.commit()
    await db.refresh(booking)

    # Занятие, назначенное репетитором вручную, для ученика такая же новость, как
    # и своя запись - если это их первое занятие, письмо получают оба.
    if is_first_with_tutor and student is not None:
        tutor_user = await db.get(User, tutor.user_id)
        if tutor_user is not None:
            await notification_service.notify_first_booking(
                db,
                student=student,
                tutor_user=tutor_user,
                start_at=payload.start_at,
                lesson_name=lesson_type.name if lesson_type else None,
            )

    if payload.repeat_weekly and payload.student_id is not None and lesson_type is not None:
        start_msk = payload.start_at.astimezone(MSK)
        series = RecurringSeries(
            tutor_id=tutor.id,
            student_id=payload.student_id,
            lesson_type_id=lesson_type.id,
            weekday=start_msk.weekday(),
            start_time=start_msk.time(),
        )
        db.add(series)
        await db.commit()
        await db.refresh(series)

        booking.recurring_series_id = series.id
        await db.commit()
        await db.refresh(booking)

        await generate_recurring_occurrences(
            db,
            series,
            initiated_by=BookedBy.TUTOR.value,
            anchor_date=start_msk.date(),
            enforce_schedule=False,
        )

    return booking


async def update_booking_by_tutor(db: AsyncSession, booking: Booking, payload: BookingTutorUpdate) -> Booking:
    data = payload.model_dump(exclude_unset=True, exclude={"apply_link_to_student"})
    for field, value in data.items():
        setattr(booking, field, value)
    if booking.student_id is not None:
        booking.is_manual_block = False
    await db.commit()
    await db.refresh(booking)

    if payload.apply_link_to_student and booking.student_id is not None and "meeting_link" in data:
        result = await db.execute(
            select(Booking).where(
                Booking.tutor_id == booking.tutor_id,
                Booking.student_id == booking.student_id,
                Booking.status == BookingStatus.SCHEDULED.value,
                Booking.id != booking.id,
            )
        )
        for other in result.scalars().all():
            other.meeting_link = booking.meeting_link
        await db.commit()

    return booking


async def delete_booking(db: AsyncSession, booking: Booking) -> None:
    await db.delete(booking)
    await db.commit()


async def set_booking_outcome(db: AsyncSession, tutor: TutorProfile, booking: Booking, outcome: str) -> Booking:
    """Tutor-recorded result of a past individual lesson (activity log). Only valid
    for a booking that actually took place as scheduled - a cancelled/rescheduled
    booking never "happens", so it has no outcome to record."""
    if booking.tutor_id != tutor.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Это не ваше занятие")
    if booking.status != BookingStatus.SCHEDULED.value:
        raise HTTPException(status.HTTP_409_CONFLICT, "У отменённого или перенесённого занятия нет результата")
    if ensure_aware(booking.end_at) > utcnow():
        raise HTTPException(status.HTTP_409_CONFLICT, "Занятие ещё не состоялось")

    booking.outcome = outcome
    await db.commit()
    await db.refresh(booking)
    return booking


async def _count_since(db: AsyncSession, tutor_id: uuid.UUID, student_id: uuid.UUID, status_value: str, since: dt.datetime) -> int:
    result = await db.execute(
        select(Booking).where(
            Booking.tutor_id == tutor_id,
            Booking.student_id == student_id,
            Booking.status == status_value,
            Booking.cancelled_at.is_not(None),
            Booking.cancelled_at >= since,
        )
    )
    return len(result.scalars().all())


def _start_of_month(now: dt.datetime) -> dt.datetime:
    return now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)


async def _check_booking_actor(db: AsyncSession, booking: Booking, actor: User) -> bool:
    """Ownership check shared by cancel/reschedule - `actor` may be either the
    student on the booking or the tutor who owns it. Returns whether the actor is
    the tutor, which callers use to decide whether the cancellation/reschedule
    policy (hours-before/per-month limits) applies - that policy only exists to
    bound student-initiated changes; a tutor managing their own schedule isn't
    subject to it - and who to notify afterwards."""
    if actor.role == UserRole.TUTOR.value:
        profile = await tutor_service.get_profile_by_user_id(db, actor.id)
        if booking.tutor_id != profile.id:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Это не ваше занятие")
        return True
    if booking.student_id != actor.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Это не ваше занятие")
    return False


async def cancel_booking(db: AsyncSession, booking: Booking, actor: User, reason: str | None) -> Booking:
    is_tutor = await _check_booking_actor(db, booking, actor)
    if booking.status != BookingStatus.SCHEDULED.value:
        raise HTTPException(status.HTTP_409_CONFLICT, "Занятие уже отменено, перенесено или завершено")

    now = utcnow()
    start_at = ensure_aware(booking.start_at)

    if not is_tutor:
        tutor = await db.get(TutorProfile, booking.tutor_id)
        if start_at - now < dt.timedelta(hours=tutor.cancel_min_hours_before):
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                f"Отменить можно не позднее чем за {tutor.cancel_min_hours_before} ч. до занятия",
            )

        cancels_this_month = await _count_since(
            db, booking.tutor_id, actor.id, BookingStatus.CANCELLED_BY_STUDENT.value, _start_of_month(now)
        )
        if cancels_this_month >= tutor.cancel_max_per_month:
            raise HTTPException(status.HTTP_409_CONFLICT, "Превышен лимит отмен занятий в этом месяце")

    booking.status = BookingStatus.CANCELLED_BY_TUTOR.value if is_tutor else BookingStatus.CANCELLED_BY_STUDENT.value
    booking.cancelled_by = BookedBy.TUTOR.value if is_tutor else BookedBy.STUDENT.value
    booking.cancelled_at = now
    booking.cancel_reason = reason
    await db.commit()
    await db.refresh(booking)

    date_str, time_str = _fmt_date_time(start_at)
    if is_tutor:
        if booking.student_id is not None:
            await notification_service.notify(
                db,
                booking.student_id,
                NotificationEvent.SCHEDULE_CHANGE,
                "Репетитор отменил занятие",
                f"Занятие {start_at.astimezone(MSK):%d.%m.%Y %H:%M} (МСК) отменено репетитором.",
            )
            await system_notification_service.notify(
                db, booking.student_id, SystemNotificationEvent.BOOKING_CANCELLED_BY_TUTOR,
                date=date_str, time=time_str,
            )
    else:
        await notification_service.notify_tutor(
            db,
            booking.tutor_id,
            NotificationEvent.SCHEDULE_CHANGE,
            "Ученик отменил занятие",
            f"{actor.display_name} отменил(а) занятие {start_at.astimezone(MSK):%d.%m.%Y %H:%M} (МСК).",
        )
        await system_notification_service.notify(
            db, tutor.user_id, SystemNotificationEvent.BOOKING_CANCELLED_BY_STUDENT,
            student_name=actor.display_name, date=date_str, time=time_str,
        )
    return booking


async def get_reschedule_context(db: AsyncSession, booking: Booking, actor: User) -> tuple[TutorProfile, LessonType]:
    """Ownership/eligibility checks shared by the reschedule-availability browsing
    endpoints and the actual reschedule action - see api/v1/bookings.py. `actor` may
    be either the student on the booking or the tutor who owns it."""
    await _check_booking_actor(db, booking, actor)
    if booking.status != BookingStatus.SCHEDULED.value:
        raise HTTPException(status.HTTP_409_CONFLICT, "Занятие уже отменено, перенесено или завершено")
    if booking.lesson_type_id is None:
        raise HTTPException(status.HTTP_409_CONFLICT, "Занятие без типа нельзя перенести")

    tutor = await db.get(TutorProfile, booking.tutor_id)
    lesson_type = await db.get(LessonType, booking.lesson_type_id)
    if tutor is None or lesson_type is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Репетитор или тип занятия не найден")
    return tutor, lesson_type


async def reschedule_booking(
    db: AsyncSession,
    booking: Booking,
    actor: User,
    new_start_at: dt.datetime,
    lesson_type_id: uuid.UUID | None = None,
    duration_minutes: int | None = None,
) -> Booking:
    tutor, lesson_type = await get_reschedule_context(db, booking, actor)
    is_tutor = actor.role == UserRole.TUTOR.value
    now = utcnow()
    start_at = ensure_aware(booking.start_at)

    if not is_tutor and (lesson_type_id is not None or duration_minutes is not None):
        raise HTTPException(
            status.HTTP_403_FORBIDDEN, "Менять тип и длительность занятия может только репетитор"
        )

    if lesson_type_id is not None and lesson_type_id != booking.lesson_type_id:
        new_type = await db.get(LessonType, lesson_type_id)
        if new_type is None or new_type.tutor_id != booking.tutor_id:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Тип занятия не найден")
        lesson_type = new_type

    if not is_tutor:
        if start_at - now < dt.timedelta(hours=tutor.reschedule_min_hours_before):
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                f"Перенести можно не позднее чем за {tutor.reschedule_min_hours_before} ч. до занятия",
            )

        reschedules_this_month = await _count_since(
            db, booking.tutor_id, actor.id, BookingStatus.RESCHEDULED.value, _start_of_month(now)
        )
        if reschedules_this_month >= tutor.reschedule_max_per_month:
            raise HTTPException(status.HTTP_409_CONFLICT, "Превышен лимит переносов занятий в этом месяце")

    # Проверка доступности слота - это свод правил для ученика: рабочие часы, запас по
    # времени, отсутствие пересечений, не в прошлом. К репетитору она не применяется
    # вовсе: у него бывает необходимость перенести занятие и на вчера (записать уже
    # проведённое), и внакладку с другим - это его календарь и его ответственность.
    if not is_tutor and not await schedule_service.is_slot_available(
        db, tutor, lesson_type, new_start_at, exclude_booking_id=booking.id
    ):
        raise HTTPException(status.HTTP_409_CONFLICT, "Выбранное время уже недоступно")

    new_duration = duration_minutes or lesson_type.duration_minutes
    new_end_at = new_start_at + dt.timedelta(minutes=new_duration)
    new_booking = Booking(
        tutor_id=booking.tutor_id,
        student_id=booking.student_id,
        lesson_type_id=lesson_type.id,
        start_at=new_start_at,
        end_at=new_end_at,
        status=BookingStatus.SCHEDULED.value,
        booked_by=BookedBy.TUTOR.value if is_tutor else BookedBy.STUDENT.value,
        meeting_link=booking.meeting_link,
        recurring_series_id=booking.recurring_series_id,
        rescheduled_from_id=booking.id,
    )
    db.add(new_booking)

    booking.status = BookingStatus.RESCHEDULED.value
    booking.cancelled_by = BookedBy.TUTOR.value if is_tutor else BookedBy.STUDENT.value
    booking.cancelled_at = now

    await db.commit()
    await db.refresh(new_booking)

    old_date_str, old_time_str = _fmt_date_time(start_at)
    new_date_str, new_time_str = _fmt_date_time(new_start_at)
    if is_tutor:
        if booking.student_id is not None:
            await notification_service.notify(
                db,
                booking.student_id,
                NotificationEvent.SCHEDULE_CHANGE,
                "Репетитор перенёс занятие",
                f"Занятие {start_at.astimezone(MSK):%d.%m.%Y %H:%M} (МСК) перенесено репетитором "
                f"на {new_start_at.astimezone(MSK):%d.%m.%Y %H:%M} (МСК).",
            )
            await system_notification_service.notify(
                db, booking.student_id, SystemNotificationEvent.BOOKING_RESCHEDULED_BY_TUTOR,
                old_date=old_date_str, old_time=old_time_str, new_date=new_date_str, new_time=new_time_str,
            )
    else:
        await notification_service.notify_tutor(
            db,
            booking.tutor_id,
            NotificationEvent.SCHEDULE_CHANGE,
            "Ученик перенёс занятие",
            f"{actor.display_name} перенёс(ла) занятие {start_at.astimezone(MSK):%d.%m.%Y %H:%M} "
            f"на {new_start_at.astimezone(MSK):%d.%m.%Y %H:%M} (МСК).",
        )
        if tutor.user_id is not None:
            await system_notification_service.notify(
                db, tutor.user_id, SystemNotificationEvent.BOOKING_RESCHEDULED_BY_STUDENT,
                student_name=actor.display_name,
                old_date=old_date_str, old_time=old_time_str, new_date=new_date_str, new_time=new_time_str,
            )
    return new_booking


async def get_admin_reschedule_context(db: AsyncSession, booking: Booking) -> tuple[TutorProfile, int]:
    """Like get_reschedule_context, but for the admin path: no ownership check, and
    works for bookings without a lesson_type (manual blocks) by deriving a default
    duration from the booking itself instead of requiring a LessonType row."""
    if booking.status != BookingStatus.SCHEDULED.value:
        raise HTTPException(status.HTTP_409_CONFLICT, "Занятие уже отменено, перенесено или завершено")
    tutor = await db.get(TutorProfile, booking.tutor_id)
    if tutor is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Репетитор не найден")
    duration_minutes = int((ensure_aware(booking.end_at) - ensure_aware(booking.start_at)).total_seconds() // 60)
    return tutor, duration_minutes


async def admin_reschedule_booking(
    db: AsyncSession, booking: Booking, new_start_at: dt.datetime, duration_minutes: int | None = None
) -> Booking:
    """Admin override: moves any scheduled booking (typed or a manual block) to a
    new time, by default preserving its original duration (or a caller-supplied
    override). Unlike the tutor/student paths this has no policy limits and doesn't
    require a lesson_type - only a basic double-booking check, since admin has full
    override authority (AdminView's own "Полный доступ ко всей системе")."""
    if booking.status != BookingStatus.SCHEDULED.value:
        raise HTTPException(status.HTTP_409_CONFLICT, "Занятие уже отменено, перенесено или завершено")

    tutor = await db.get(TutorProfile, booking.tutor_id)
    if tutor is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Репетитор не найден")

    now = utcnow()
    start_at = ensure_aware(booking.start_at)
    duration = (
        dt.timedelta(minutes=duration_minutes) if duration_minutes else ensure_aware(booking.end_at) - start_at
    )
    new_end_at = new_start_at + duration

    reserved_zones = await schedule_service.get_reserved_zones(
        db,
        tutor.id,
        new_start_at - dt.timedelta(days=1),
        new_end_at + dt.timedelta(days=1),
        tutor.break_between_lessons_minutes,
        exclude_booking_id=booking.id,
    )
    if schedule_service.slot_conflicts(new_start_at, new_end_at, tutor.break_between_lessons_minutes, reserved_zones):
        raise HTTPException(status.HTTP_409_CONFLICT, "Выбранное время уже недоступно")

    new_booking = Booking(
        tutor_id=booking.tutor_id,
        student_id=booking.student_id,
        lesson_type_id=booking.lesson_type_id,
        start_at=new_start_at,
        end_at=new_end_at,
        status=BookingStatus.SCHEDULED.value,
        booked_by=BookedBy.ADMIN.value,
        is_manual_block=booking.is_manual_block,
        meeting_link=booking.meeting_link,
        notes=booking.notes,
        recurring_series_id=booking.recurring_series_id,
        rescheduled_from_id=booking.id,
    )
    db.add(new_booking)

    booking.status = BookingStatus.RESCHEDULED.value
    booking.cancelled_by = BookedBy.ADMIN.value
    booking.cancelled_at = now

    await db.commit()
    await db.refresh(new_booking)

    if booking.student_id is not None:
        await notification_service.notify(
            db,
            booking.student_id,
            NotificationEvent.SCHEDULE_CHANGE,
            "Занятие перенесено администрацией",
            f"Занятие {start_at.astimezone(MSK):%d.%m.%Y %H:%M} (МСК) перенесено "
            f"на {new_start_at.astimezone(MSK):%d.%m.%Y %H:%M} (МСК).",
        )
        old_date_str, old_time_str = _fmt_date_time(start_at)
        new_date_str, new_time_str = _fmt_date_time(new_start_at)
        await system_notification_service.notify(
            db, booking.student_id, SystemNotificationEvent.BOOKING_RESCHEDULED_BY_TUTOR,
            old_date=old_date_str, old_time=old_time_str, new_date=new_date_str, new_time=new_time_str,
        )
    await notification_service.notify_tutor(
        db,
        booking.tutor_id,
        NotificationEvent.SCHEDULE_CHANGE,
        "Занятие перенесено администрацией",
        f"Занятие {start_at.astimezone(MSK):%d.%m.%Y %H:%M} (МСК) перенесено "
        f"на {new_start_at.astimezone(MSK):%d.%m.%Y %H:%M} (МСК).",
    )
    return new_booking


async def stop_recurring_series(db: AsyncSession, series: RecurringSeries, actor: User) -> RecurringSeries:
    """Останавливает серию. Останавливать может и ученик, и репетитор, который её ведёт:
    ученик, заведённый вручную, сам этого сделать не может - в аккаунт никто не входит."""
    if actor.role == UserRole.TUTOR.value:
        profile = await tutor_service.get_profile_by_user_id(db, actor.id)
        if series.tutor_id != profile.id:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Это не ваша серия занятий")
    elif series.student_id != actor.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Это не ваша серия занятий")
    series.is_active = False
    series.stopped_at = utcnow()
    await db.commit()
    await db.refresh(series)
    return series


async def list_active_series_for_tutor(db: AsyncSession, tutor_id: uuid.UUID) -> list[dict]:
    """Действующие еженедельные серии репетитора - для блока «Ученики» в статистике."""
    result = await db.execute(
        select(RecurringSeries, LessonType.name, User.display_name)
        .join(LessonType, LessonType.id == RecurringSeries.lesson_type_id)
        .join(User, User.id == RecurringSeries.student_id)
        .where(RecurringSeries.tutor_id == tutor_id, RecurringSeries.is_active.is_(True))
        .order_by(RecurringSeries.weekday, RecurringSeries.start_time)
    )
    return [
        {
            "id": series.id,
            "tutor_id": series.tutor_id,
            "student_id": series.student_id,
            "lesson_type_id": series.lesson_type_id,
            "weekday": series.weekday,
            "start_time": series.start_time,
            "is_active": series.is_active,
            "lesson_type_name": lesson_type_name,
            "student_display_name": student_display_name,
        }
        for series, lesson_type_name, student_display_name in result.all()
    ]


async def list_active_series_for_student(db: AsyncSession, student_id: uuid.UUID) -> list[dict]:
    """Enriched for display (section 3.1's stop-recurring flow lives in student
    settings, not next to every generated booking row)."""
    result = await db.execute(
        select(RecurringSeries, LessonType.name, User.display_name)
        .join(LessonType, LessonType.id == RecurringSeries.lesson_type_id)
        .join(TutorProfile, TutorProfile.id == RecurringSeries.tutor_id)
        .join(User, User.id == TutorProfile.user_id)
        .where(RecurringSeries.student_id == student_id, RecurringSeries.is_active.is_(True))
        .order_by(RecurringSeries.weekday, RecurringSeries.start_time)
    )
    return [
        {
            "id": series.id,
            "tutor_id": series.tutor_id,
            "student_id": series.student_id,
            "lesson_type_id": series.lesson_type_id,
            "weekday": series.weekday,
            "start_time": series.start_time,
            "is_active": series.is_active,
            "lesson_type_name": lesson_type_name,
            "tutor_display_name": tutor_display_name,
        }
        for series, lesson_type_name, tutor_display_name in result.all()
    ]
