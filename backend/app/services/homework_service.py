import uuid
from collections.abc import Sequence

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.enums import (
    HomeworkContentType,
    HomeworkSubmissionMode,
    HomeworkSubmissionStatus,
    SystemNotificationEvent,
    UserRole,
)
from app.models.homework import HomeworkAssignment, HomeworkSubmission, HomeworkSubmissionFile
from app.models.tutor import TutorProfile
from app.models.user import User
from app.services import group_service, system_notification_service
from app.utils.time import utcnow


async def create_assignment_for_student(
    db: AsyncSession,
    tutor: TutorProfile,
    student_id: uuid.UUID,
    title: str | None,
    content_type: str,
    content_url: str | None,
    content_file_path: str | None,
    submission_mode: str,
    due_at,
) -> HomeworkAssignment:
    student = await db.get(User, student_id)
    if student is None or student.role != "student":
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Ученик не найден")

    assignment = HomeworkAssignment(
        tutor_id=tutor.id,
        student_id=student_id,
        title=title,
        content_type=content_type,
        content_url=content_url,
        content_file_path=content_file_path,
        submission_mode=submission_mode,
        due_at=due_at,
    )
    db.add(assignment)
    await db.flush()

    db.add(HomeworkSubmission(assignment_id=assignment.id, student_id=student_id))
    await db.commit()
    await db.refresh(assignment)

    await system_notification_service.notify(
        db,
        student_id,
        SystemNotificationEvent.HOMEWORK_ASSIGNED,
        homework_title=title or "Без названия",
        homework_url=_homework_tab_url(),
    )
    return assignment


async def create_assignment_for_group(
    db: AsyncSession,
    tutor: TutorProfile,
    group_id: uuid.UUID,
    title: str | None,
    content_type: str,
    content_url: str | None,
    content_file_path: str | None,
    submission_mode: str,
    due_at,
) -> HomeworkAssignment:
    group = await group_service.get_group_or_404(db, group_id)
    group_service.require_owner(group, tutor)

    members = await group_service.list_members(db, group_id, active_only=True)
    if not members:
        raise HTTPException(status.HTTP_409_CONFLICT, "В группе нет активных участников")

    assignment = HomeworkAssignment(
        tutor_id=tutor.id,
        group_id=group_id,
        title=title,
        content_type=content_type,
        content_url=content_url,
        content_file_path=content_file_path,
        submission_mode=submission_mode,
        due_at=due_at,
    )
    db.add(assignment)
    await db.flush()

    for member in members:
        db.add(HomeworkSubmission(assignment_id=assignment.id, student_id=member.student_id))

    await db.commit()
    await db.refresh(assignment)

    for member in members:
        await system_notification_service.notify(
            db,
            member.student_id,
            SystemNotificationEvent.HOMEWORK_ASSIGNED,
            homework_title=title or "Без названия",
            homework_url=_homework_tab_url(),
        )
    return assignment


async def get_assignment_or_404(db: AsyncSession, assignment_id: uuid.UUID) -> HomeworkAssignment:
    assignment = await db.get(HomeworkAssignment, assignment_id)
    if assignment is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Домашнее задание не найдено")
    return assignment


async def list_assignments_for_tutor(db: AsyncSession, tutor_id: uuid.UUID) -> list[HomeworkAssignment]:
    result = await db.execute(
        select(HomeworkAssignment)
        .where(HomeworkAssignment.tutor_id == tutor_id)
        .order_by(HomeworkAssignment.created_at.desc())
    )
    return list(result.scalars().all())


async def list_submissions_for_assignment(db: AsyncSession, assignment_id: uuid.UUID) -> list[HomeworkSubmission]:
    result = await db.execute(
        select(HomeworkSubmission).where(HomeworkSubmission.assignment_id == assignment_id)
    )
    return list(result.scalars().all())


async def list_submissions_for_assignments(
    db: AsyncSession, assignment_ids: Sequence[uuid.UUID]
) -> dict[uuid.UUID, list[HomeworkSubmission]]:
    """Сдачи сразу по всем заданиям репетитора.

    Карточка задания во вкладке «ДЗ» показывает сдачи учеников без раскрытия, так что
    запрос на каждое задание превратился бы в десятки запросов на один список.
    """
    if not assignment_ids:
        return {}
    result = await db.execute(
        select(HomeworkSubmission)
        .where(HomeworkSubmission.assignment_id.in_(assignment_ids))
        .order_by(HomeworkSubmission.created_at)
    )
    by_assignment: dict[uuid.UUID, list[HomeworkSubmission]] = {}
    for submission in result.scalars().all():
        by_assignment.setdefault(submission.assignment_id, []).append(submission)
    return by_assignment


async def delete_assignment(db: AsyncSession, assignment: HomeworkAssignment) -> None:
    await db.delete(assignment)
    await db.commit()


def _to_student_homework_dict(submission: HomeworkSubmission, assignment: HomeworkAssignment) -> dict:
    return {
        "submission_id": submission.id,
        "assignment_id": assignment.id,
        "tutor_id": assignment.tutor_id,
        "group_id": assignment.group_id,
        "title": assignment.title,
        "content_type": assignment.content_type,
        "content_url": assignment.content_url,
        "content_file_path": assignment.content_file_path,
        "submission_mode": assignment.submission_mode,
        "due_at": assignment.due_at,
        "status": submission.status,
        "files": [
            {"id": f.id, "file_path": f.file_path, "uploaded_at": f.uploaded_at}
            for f in submission.files
        ],
        "comment": submission.comment,
        "submitted_at": submission.submitted_at,
    }


async def pending_count_for_user(db: AsyncSession, user: User) -> int:
    """Сколько домашних заданий ждёт действия именно этого человека.

    У ученика это невыполненные задания, у репетитора - сданные, но ещё не
    проверенные: именно их он и ищет, открывая вкладку. Число показывается бейджем
    рядом с «ДЗ», как непрочитанные в чате.
    """
    if user.role == UserRole.TUTOR.value:
        profile = await db.execute(select(TutorProfile).where(TutorProfile.user_id == user.id))
        tutor = profile.scalar_one_or_none()
        if tutor is None:
            return 0
        query = (
            select(func.count())
            .select_from(HomeworkSubmission)
            .join(HomeworkAssignment, HomeworkAssignment.id == HomeworkSubmission.assignment_id)
            .where(
                HomeworkAssignment.tutor_id == tutor.id,
                HomeworkSubmission.status == HomeworkSubmissionStatus.SUBMITTED.value,
            )
        )
    elif user.role == UserRole.STUDENT.value:
        query = (
            select(func.count())
            .select_from(HomeworkSubmission)
            .where(
                HomeworkSubmission.student_id == user.id,
                HomeworkSubmission.status == HomeworkSubmissionStatus.PENDING.value,
            )
        )
    else:
        return 0

    return (await db.scalar(query)) or 0


async def list_homework_for_student(db: AsyncSession, student_id: uuid.UUID) -> list[dict]:
    result = await db.execute(
        select(HomeworkSubmission, HomeworkAssignment)
        .join(HomeworkAssignment, HomeworkAssignment.id == HomeworkSubmission.assignment_id)
        .where(HomeworkSubmission.student_id == student_id)
        .order_by(HomeworkAssignment.created_at.desc())
    )
    return [_to_student_homework_dict(submission, assignment) for submission, assignment in result.all()]


async def list_student_homework_for_tutor(
    db: AsyncSession, tutor_id: uuid.UUID, student_id: uuid.UUID
) -> list[dict]:
    """One tutor's view of a specific student's homework - powers the "ДЗ" button on
    a booking card (section: tutor cabinet lesson cards)."""
    result = await db.execute(
        select(HomeworkSubmission, HomeworkAssignment)
        .join(HomeworkAssignment, HomeworkAssignment.id == HomeworkSubmission.assignment_id)
        .where(HomeworkSubmission.student_id == student_id, HomeworkAssignment.tutor_id == tutor_id)
        .order_by(HomeworkAssignment.created_at.desc())
    )
    return [_to_student_homework_dict(submission, assignment) for submission, assignment in result.all()]


async def get_student_status_map(db: AsyncSession, tutor_id: uuid.UUID) -> dict[uuid.UUID, str]:
    """Per-student aggregate homework status for this tutor, used to color the "ДЗ"
    button on each booking card: "pending" if any submission is still outstanding,
    else "done". Students with no submissions at all from this tutor are simply
    absent from the map (the card falls back to "none")."""
    result = await db.execute(
        select(HomeworkSubmission.student_id, HomeworkSubmission.status)
        .join(HomeworkAssignment, HomeworkAssignment.id == HomeworkSubmission.assignment_id)
        .where(HomeworkAssignment.tutor_id == tutor_id)
    )
    by_student: dict[uuid.UUID, list[str]] = {}
    for student_id, submission_status in result.all():
        by_student.setdefault(student_id, []).append(submission_status)

    return {
        student_id: "pending" if HomeworkSubmissionStatus.PENDING.value in statuses else "done"
        for student_id, statuses in by_student.items()
    }


async def get_assignment_status_map(db: AsyncSession, tutor_id: uuid.UUID) -> dict[uuid.UUID, str]:
    """Статус задания целиком: "pending", если хоть кто-то ещё не сдал, иначе
    "submitted", если что-то прислано и ждёт проверки, иначе "done".

    Раньше присланное считалось выполненным, и работа, которую репетитор ещё не
    смотрел, ничем не отличалась от проверенной - а именно её и надо заметить первой.
    Красит и фильтрует карточки во вкладке «ДЗ» (tutor/HomeworkTab.vue).
    """
    result = await db.execute(
        select(HomeworkSubmission.assignment_id, HomeworkSubmission.status)
        .join(HomeworkAssignment, HomeworkAssignment.id == HomeworkSubmission.assignment_id)
        .where(HomeworkAssignment.tutor_id == tutor_id)
    )
    by_assignment: dict[uuid.UUID, list[str]] = {}
    for assignment_id, submission_status in result.all():
        by_assignment.setdefault(assignment_id, []).append(submission_status)

    def aggregate(statuses: list[str]) -> str:
        if HomeworkSubmissionStatus.PENDING.value in statuses:
            return HomeworkSubmissionStatus.PENDING.value
        if HomeworkSubmissionStatus.SUBMITTED.value in statuses:
            return HomeworkSubmissionStatus.SUBMITTED.value
        return HomeworkSubmissionStatus.DONE.value

    return {
        assignment_id: aggregate(statuses) for assignment_id, statuses in by_assignment.items()
    }


async def update_assignment(
    db: AsyncSession,
    assignment: HomeworkAssignment,
    title: str | None,
    submission_mode: str,
    content_type: str | None,
    content_url: str | None,
    content_file_path: str | None,
) -> HomeworkAssignment:
    """`content_type` is None when the tutor didn't touch the material (edit form's
    "Заменить материал" left unchecked) - the existing link/file is kept as-is;
    otherwise it fully replaces content_url/content_file_path together, since exactly
    one of the two is ever meaningful (see homework_service.validate_content)."""
    assignment.title = title
    assignment.submission_mode = submission_mode
    if content_type is not None:
        assignment.content_type = content_type
        assignment.content_url = content_url
        assignment.content_file_path = content_file_path
    await db.commit()
    await db.refresh(assignment)
    return assignment


async def get_submission_or_404(db: AsyncSession, submission_id: uuid.UUID) -> HomeworkSubmission:
    submission = await db.get(HomeworkSubmission, submission_id)
    if submission is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Домашнее задание не найдено")
    return submission


async def mark_submission_done(db: AsyncSession, submission: HomeworkSubmission, student: User) -> HomeworkSubmission:
    if submission.student_id != student.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Это не ваше домашнее задание")
    assignment = await get_assignment_or_404(db, submission.assignment_id)
    if assignment.submission_mode != HomeworkSubmissionMode.MARK_DONE.value:
        raise HTTPException(status.HTTP_409_CONFLICT, "Для этого задания требуется отправить файл")

    submission.status = HomeworkSubmissionStatus.DONE.value
    submission.submitted_at = utcnow()
    await db.commit()
    await db.refresh(submission)
    return submission


# Больше одного-двух скриншотов к заданию не прикладывают; предел нужен, чтобы
# случайный цикл загрузки не превратил сдачу в файлопомойку.
MAX_SUBMISSION_FILES = 10


def _homework_tab_url() -> str:
    """Адрес вкладки с домашними заданиями. Собирается здесь, а не зашит в шаблон:
    он отличается между локальной разработкой и продом."""
    return f"{settings.frontend_base_url.rstrip('/')}/cabinet?tab=homework"


async def submit_file(
    db: AsyncSession, submission: HomeworkSubmission, student: User, file_path: str, comment: str | None
) -> HomeworkSubmission:
    """Добавляет файл к сдаче. Файлы копятся: ученик может приложить второй скриншот,
    а ошибочный убрать отдельно (remove_submission_file) - раньше файл был один, и
    приложенный по ошибке оставался единственным свидетельством выполнения."""
    if submission.student_id != student.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Это не ваше домашнее задание")
    assignment = await get_assignment_or_404(db, submission.assignment_id)
    if assignment.submission_mode != HomeworkSubmissionMode.FILE_UPLOAD.value:
        raise HTTPException(status.HTTP_409_CONFLICT, "Для этого задания достаточно отметки «выполнено»")
    if len(submission.files) >= MAX_SUBMISSION_FILES:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"К одному заданию можно приложить не больше {MAX_SUBMISSION_FILES} файлов",
        )

    db.add(HomeworkSubmissionFile(submission_id=submission.id, file_path=file_path))
    submission.status = HomeworkSubmissionStatus.SUBMITTED.value
    if comment:
        submission.comment = comment
    submission.submitted_at = utcnow()
    await db.commit()
    await db.refresh(submission)
    return submission


async def remove_submission_file(
    db: AsyncSession, submission: HomeworkSubmission, student: User, file_id: uuid.UUID
) -> HomeworkSubmission:
    """Убирает ошибочно приложенный файл.

    Пока задание не проверено, ученик распоряжается своими вложениями сам. Проверенное
    (done) не трогаем: репетитор уже смотрел именно эти файлы.
    """
    if submission.student_id != student.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Это не ваше домашнее задание")
    if submission.status == HomeworkSubmissionStatus.DONE.value:
        raise HTTPException(
            status.HTTP_409_CONFLICT, "Задание уже проверено - файлы менять нельзя"
        )

    target = next((f for f in submission.files if f.id == file_id), None)
    if target is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Файл не найден")

    await db.delete(target)
    await db.flush()
    await db.refresh(submission)

    # Убрали последний файл - задание снова не выполнено: показывать «отправлено»
    # без единого вложения было бы неправдой.
    if not submission.files:
        submission.status = HomeworkSubmissionStatus.PENDING.value
        submission.submitted_at = None
    await db.commit()
    await db.refresh(submission)
    return submission


async def set_submission_status(
    db: AsyncSession, tutor: TutorProfile, submission: HomeworkSubmission, new_status: str
) -> HomeworkSubmission:
    """Lets the tutor manually override a submission's status - e.g. to close out a
    month-old "pending" debt that's no longer relevant but the student never
    completed. Only touches status; doesn't fabricate file_path/submitted_at, since
    the tutor is asserting an outcome, not pretending the student actually submitted
    something."""
    assignment = await get_assignment_or_404(db, submission.assignment_id)
    if assignment.tutor_id != tutor.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Это не ваше задание")

    submission.status = new_status
    await db.commit()
    await db.refresh(submission)
    return submission


def validate_content(content_url: str | None, has_file: bool) -> str:
    if bool(content_url) == has_file:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT, "Укажите либо ссылку, либо файл — и только один вариант"
        )
    return HomeworkContentType.FILE.value if has_file else HomeworkContentType.LINK.value
