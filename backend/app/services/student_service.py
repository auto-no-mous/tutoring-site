"""Ученики репетитора: заведённые вручную, их статистика и приватные примечания.

Зачем это есть: часть учеников не хочет ни регистрироваться, ни заходить на сайт, но
репетитору всё равно нужно вести их расписание, группы и домашку. Такой ученик - это
обычная строка в users с role=student, без почты и пароля, помеченная
managed_by_tutor_id. Отдельной сущности нет намеренно: bookings, group_memberships,
homework_* и посещаемость ссылаются на users.id, и любая параллельная таблица
"виртуальных учеников" потребовала бы раздваивать каждый из этих внешних ключей.

Забрать такой аккаунт себе человек может по ссылке-приглашению - см.
app.services.claim_service.
"""

import uuid

from fastapi import HTTPException, status
from sqlalchemy import false, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.booking import Booking
from app.models.enums import BookingOutcome, BookingStatus, HomeworkSubmissionStatus, UserRole
from app.models.homework import HomeworkAssignment, HomeworkSubmission
from app.models.student_note import TutorStudentNote
from app.models.tutor import TutorProfile
from app.models.user import User
from app.schemas.student import ManagedStudentCreate, ManagedStudentUpdate
from app.utils.names import compose_display_name
from app.utils.time import ensure_aware, utcnow

# Больше на одного репетитора в обозримой практике не бывает, а без предела запрос
# в форму записи может однажды притащить тысячи строк.
MAX_MANAGED_STUDENTS = 500


async def create_managed_student(
    db: AsyncSession, tutor: TutorProfile, payload: ManagedStudentCreate
) -> User:
    count = await db.scalar(
        select(func.count()).select_from(User).where(User.managed_by_tutor_id == tutor.id)
    )
    if (count or 0) >= MAX_MANAGED_STUDENTS:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"Достигнут предел в {MAX_MANAGED_STUDENTS} учеников, заведённых вручную",
        )

    student = User(
        role=UserRole.STUDENT.value,
        managed_by_tutor_id=tutor.id,
        first_name=payload.first_name,
        last_name=payload.last_name,
        patronymic=payload.patronymic,
        display_name=compose_display_name(payload.first_name, payload.last_name, payload.patronymic),
        grade=payload.grade,
        # Ни почты, ни пароля: войти в такой аккаунт нельзя, пока ученик сам не
        # привяжет способ входа по ссылке-приглашению.
        email=None,
        password_hash=None,
        email_verified=False,
        # Согласие на обработку ПД даёт человек, а не репетитор за него. Ставится в
        # момент, когда ученик забирает аккаунт (claim_service), - до тех пор в
        # профиле только ФИО и класс, которые репетитор и так вёл бы в тетради.
        pd_consent_given=False,
    )
    db.add(student)
    await db.commit()
    await db.refresh(student)

    if payload.note:
        await set_note(db, tutor, student.id, payload.note)
        await db.refresh(student)
    return student


async def get_managed_student(db: AsyncSession, tutor: TutorProfile, student_id: uuid.UUID) -> User:
    student = await db.get(User, student_id)
    if student is None or student.managed_by_tutor_id != tutor.id:
        # Один и тот же ответ и для чужого ученика, и для несуществующего: иначе по
        # коду ответа можно было бы перебирать чужие id.
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Ученик не найден")
    return student


async def update_managed_student(
    db: AsyncSession, tutor: TutorProfile, student_id: uuid.UUID, payload: ManagedStudentUpdate
) -> User:
    student = await get_managed_student(db, tutor, student_id)
    data = payload.model_dump(exclude_unset=True)
    for field, value in data.items():
        setattr(student, field, value)
    if {"first_name", "last_name", "patronymic"} & data.keys():
        student.display_name = compose_display_name(
            student.first_name, student.last_name, student.patronymic
        )
    await db.commit()
    await db.refresh(student)
    return student


async def delete_managed_student(db: AsyncSession, tutor: TutorProfile, student_id: uuid.UUID) -> None:
    student = await get_managed_student(db, tutor, student_id)
    await db.delete(student)
    await db.commit()


async def set_note(
    db: AsyncSession, tutor: TutorProfile, student_id: uuid.UUID, text: str | None
) -> None:
    """Заводит, меняет или (пустым текстом) убирает примечание об ученике."""
    result = await db.execute(
        select(TutorStudentNote).where(
            TutorStudentNote.tutor_id == tutor.id, TutorStudentNote.student_id == student_id
        )
    )
    note = result.scalar_one_or_none()
    cleaned = (text or "").strip()

    if not cleaned:
        if note is not None:
            await db.delete(note)
            await db.commit()
        return

    if note is None:
        db.add(TutorStudentNote(tutor_id=tutor.id, student_id=student_id, text=cleaned))
    else:
        note.text = cleaned
        note.updated_at = utcnow()
    await db.commit()


async def _notes_map(db: AsyncSession, tutor_id: uuid.UUID) -> dict[uuid.UUID, str]:
    result = await db.execute(
        select(TutorStudentNote.student_id, TutorStudentNote.text).where(
            TutorStudentNote.tutor_id == tutor_id
        )
    )
    return {student_id: text for student_id, text in result.all()}


async def list_students_with_stats(db: AsyncSession, tutor: TutorProfile) -> list[dict]:
    """Ученики репетитора для блока «Ученики»: все, с кем есть или были занятия, плюс
    заведённые вручную (даже если записей ещё нет).

    Считается пятью запросами на весь список, а не по запросу на ученика: список
    открывается целиком, и N+1 здесь превратился бы в десятки запросов.
    """
    lessons = (
        select(
            Booking.student_id,
            func.count().label("held"),
            func.max(Booking.start_at).label("last_at"),
        )
        .where(
            Booking.tutor_id == tutor.id,
            Booking.student_id.is_not(None),
            Booking.start_at < utcnow(),
            Booking.status.in_([BookingStatus.SCHEDULED.value, BookingStatus.COMPLETED.value]),
            or_(Booking.outcome.is_(None), Booking.outcome == BookingOutcome.CONDUCTED.value),
        )
        .group_by(Booking.student_id)
    )
    no_shows = (
        select(Booking.student_id, func.count().label("no_shows"))
        .where(
            Booking.tutor_id == tutor.id,
            Booking.student_id.is_not(None),
            Booking.outcome == BookingOutcome.STUDENT_NO_SHOW.value,
        )
        .group_by(Booking.student_id)
    )
    upcoming = (
        select(Booking.student_id, func.min(Booking.start_at).label("next_at"))
        .where(
            Booking.tutor_id == tutor.id,
            Booking.student_id.is_not(None),
            Booking.start_at >= utcnow(),
            Booking.status == BookingStatus.SCHEDULED.value,
        )
        .group_by(Booking.student_id)
    )
    homework = (
        select(
            HomeworkSubmission.student_id,
            func.count().filter(HomeworkSubmission.status == HomeworkSubmissionStatus.DONE.value).label("done"),
            func.count().filter(HomeworkSubmission.status != HomeworkSubmissionStatus.DONE.value).label("pending"),
        )
        .join(HomeworkAssignment, HomeworkAssignment.id == HomeworkSubmission.assignment_id)
        .where(HomeworkAssignment.tutor_id == tutor.id)
        .group_by(HomeworkSubmission.student_id)
    )

    held_map = {row.student_id: (row.held, row.last_at) for row in (await db.execute(lessons)).all()}
    no_show_map = {row.student_id: row.no_shows for row in (await db.execute(no_shows)).all()}
    next_map = {row.student_id: row.next_at for row in (await db.execute(upcoming)).all()}
    homework_map = {row.student_id: (row.done, row.pending) for row in (await db.execute(homework)).all()}
    notes = await _notes_map(db, tutor.id)

    student_ids = set(held_map) | set(no_show_map) | set(next_map) | set(homework_map)
    result = await db.execute(
        select(User).where(
            or_(
                User.id.in_(student_ids) if student_ids else false(),
                User.managed_by_tutor_id == tutor.id,
            )
        )
    )

    rows = []
    for student in result.scalars().all():
        held, last_at = held_map.get(student.id, (0, None))
        done, pending = homework_map.get(student.id, (0, 0))
        rows.append(
            {
                "id": student.id,
                "first_name": student.first_name,
                "last_name": student.last_name,
                "patronymic": student.patronymic,
                "grade": student.grade,
                "photo_url": student.photo_url,
                "is_managed": student.is_managed,
                # Ученик, заведённый вручную, но уже забравший аккаунт, выглядит как
                # обычный - показываем только сам факт наличия входа.
                "has_login": bool(student.auth_providers),
                "note": notes.get(student.id),
                "lessons_held": held,
                "no_shows": no_show_map.get(student.id, 0),
                "last_lesson_at": last_at,
                "next_lesson_at": next_map.get(student.id),
                "homework_done": done,
                "homework_pending": pending,
            }
        )

    # Сверху те, с кем занимаешься сейчас: сначала по ближайшему занятию (скорое -
    # выше), затем по последнему прошедшему (недавнее - выше), в конце заведённые
    # вручную, у которых записей ещё нет.
    def sort_key(row: dict) -> tuple[int, float]:
        if row["next_lesson_at"] is not None:
            return (0, ensure_aware(row["next_lesson_at"]).timestamp())
        if row["last_lesson_at"] is not None:
            return (1, -ensure_aware(row["last_lesson_at"]).timestamp())
        return (2, 0.0)

    rows.sort(key=sort_key)
    return rows
