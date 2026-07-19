import uuid

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import HomeworkContentType, HomeworkSubmissionMode, HomeworkSubmissionStatus
from app.models.homework import HomeworkAssignment, HomeworkSubmission
from app.models.tutor import TutorProfile
from app.models.user import User
from app.services import group_service
from app.utils.time import utcnow


async def create_assignment_for_student(
    db: AsyncSession,
    tutor: TutorProfile,
    student_id: uuid.UUID,
    title: str,
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
    return assignment


async def create_assignment_for_group(
    db: AsyncSession,
    tutor: TutorProfile,
    group_id: uuid.UUID,
    title: str,
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


async def delete_assignment(db: AsyncSession, assignment: HomeworkAssignment) -> None:
    await db.delete(assignment)
    await db.commit()


async def list_homework_for_student(db: AsyncSession, student_id: uuid.UUID) -> list[dict]:
    result = await db.execute(
        select(HomeworkSubmission, HomeworkAssignment)
        .join(HomeworkAssignment, HomeworkAssignment.id == HomeworkSubmission.assignment_id)
        .where(HomeworkSubmission.student_id == student_id)
        .order_by(HomeworkAssignment.created_at.desc())
    )
    items = []
    for submission, assignment in result.all():
        items.append(
            {
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
                "file_path": submission.file_path,
                "comment": submission.comment,
                "submitted_at": submission.submitted_at,
            }
        )
    return items


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


async def submit_file(
    db: AsyncSession, submission: HomeworkSubmission, student: User, file_path: str, comment: str | None
) -> HomeworkSubmission:
    if submission.student_id != student.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Это не ваше домашнее задание")
    assignment = await get_assignment_or_404(db, submission.assignment_id)
    if assignment.submission_mode != HomeworkSubmissionMode.FILE_UPLOAD.value:
        raise HTTPException(status.HTTP_409_CONFLICT, "Для этого задания достаточно отметки «выполнено»")

    submission.status = HomeworkSubmissionStatus.SUBMITTED.value
    submission.file_path = file_path
    submission.comment = comment
    submission.submitted_at = utcnow()
    await db.commit()
    await db.refresh(submission)
    return submission


def validate_content(content_url: str | None, has_file: bool) -> str:
    if bool(content_url) == has_file:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT, "Укажите либо ссылку, либо файл — и только один вариант"
        )
    return HomeworkContentType.FILE.value if has_file else HomeworkContentType.LINK.value
