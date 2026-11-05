import uuid
from datetime import datetime

from fastapi import APIRouter, File, Form, HTTPException, UploadFile, status

from app.api.deps import CurrentUser, DbSession
from app.models.homework import HomeworkSubmission
from app.models.enums import HomeworkSubmissionMode, HomeworkSubmissionStatus, UserRole
from app.schemas.homework import (
    HomeworkAssignmentOut,
    HomeworkSubmissionOut,
    HomeworkSubmissionStatusUpdate,
    StudentHomeworkOut,
)
from app.services import booking_service, file_service, group_service, homework_service, tutor_service
from app.utils.time import to_utc

router = APIRouter(prefix="/homework", tags=["homework"])


def _require_tutor(user: CurrentUser) -> None:
    if user.role != UserRole.TUTOR:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Доступно только репетиторам")


def _require_student(user: CurrentUser) -> None:
    if user.role != UserRole.STUDENT:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Доступно только ученикам")


def _validate_submission_mode(submission_mode: str) -> None:
    if submission_mode not in (HomeworkSubmissionMode.MARK_DONE.value, HomeworkSubmissionMode.FILE_UPLOAD.value):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Некорректный режим сдачи задания")


def _real_uploads(files: list[UploadFile]) -> list[UploadFile]:
    # Пустое поле файла браузер присылает частью без имени - это не файл.
    return [f for f in files if f.filename]


async def _save_materials(uploads: list[UploadFile]) -> list[str]:
    return [
        await file_service.save_upload(f, "homework", file_service.ALLOWED_ATTACHMENT_TYPES) for f in uploads
    ]


async def _enrich(db: DbSession, assignments: list) -> list[HomeworkAssignmentOut]:
    """Attaches the aggregate status + recipient display name each card needs (see
    tutor/HomeworkTab.vue) - shared by every endpoint that returns assignment rows."""
    if not assignments:
        return []
    tutor_id = assignments[0].tutor_id
    status_map = await homework_service.get_assignment_status_map(db, tutor_id)
    submissions = await homework_service.list_submissions_for_assignments(db, [a.id for a in assignments])
    group_names = await group_service.get_group_names(db, [a.group_id for a in assignments])
    # Имена нужны и адресату задания, и каждому ученику в списке сдач (у группового
    # задания это разные люди).
    student_names = await booking_service.get_student_names(
        db,
        [a.student_id for a in assignments]
        + [s.student_id for rows in submissions.values() for s in rows],
    )
    return [
        HomeworkAssignmentOut.model_validate(a, from_attributes=True).model_copy(
            update={
                "status": status_map.get(a.id, "done"),
                "student_display_name": student_names.get(a.student_id) if a.student_id else None,
                "group_name": group_names.get(a.group_id) if a.group_id else None,
                "submissions": [
                    _submission_out(s, student_names.get(s.student_id))
                    for s in submissions.get(a.id, [])
                ],
            }
        )
        for a in assignments
    ]


def _submission_out(submission: HomeworkSubmission, student_name: str | None) -> HomeworkSubmissionOut:
    out = HomeworkSubmissionOut.model_validate(submission, from_attributes=True)
    out.student_display_name = student_name
    return out


@router.post("", response_model=list[HomeworkAssignmentOut], status_code=status.HTTP_201_CREATED)
async def create_homework(
    current_user: CurrentUser,
    db: DbSession,
    submission_mode: str = Form(...),
    title: str | None = Form(None),
    student_ids: list[str] = Form([]),
    group_ids: list[str] = Form([]),
    content_url: str | None = Form(None),
    due_at: str | None = Form(None),
    files: list[UploadFile] = File([]),
) -> list[HomeworkAssignmentOut]:
    _require_tutor(current_user)
    profile = await tutor_service.get_profile_by_user_id(db, current_user.id)

    if not student_ids and not group_ids:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Укажите хотя бы одного получателя")
    _validate_submission_mode(submission_mode)

    uploads = _real_uploads(files)
    content_type = homework_service.validate_content(content_url, len(uploads))
    content_file_paths = await _save_materials(uploads)

    due_at_parsed = to_utc(datetime.fromisoformat(due_at)) if due_at else None
    title = title or None

    created = []
    for student_id in student_ids:
        created.append(
            await homework_service.create_assignment_for_student(
                db, profile, uuid.UUID(student_id), title, content_type, content_url, content_file_paths,
                submission_mode, due_at_parsed,
            )
        )
    for group_id in group_ids:
        created.append(
            await homework_service.create_assignment_for_group(
                db, profile, uuid.UUID(group_id), title, content_type, content_url, content_file_paths,
                submission_mode, due_at_parsed,
            )
        )

    return await _enrich(db, created)


@router.patch("/{assignment_id}", response_model=HomeworkAssignmentOut)
async def update_homework(
    assignment_id: uuid.UUID,
    current_user: CurrentUser,
    db: DbSession,
    submission_mode: str = Form(...),
    title: str | None = Form(None),
    content_url: str | None = Form(None),
    files: list[UploadFile] = File([]),
) -> HomeworkAssignmentOut:
    _require_tutor(current_user)
    profile = await tutor_service.get_profile_by_user_id(db, current_user.id)
    assignment = await homework_service.get_assignment_or_404(db, assignment_id)
    if assignment.tutor_id != profile.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Это не ваше задание")

    _validate_submission_mode(submission_mode)

    uploads = _real_uploads(files)
    replacing_content = bool(uploads) or bool(content_url)
    content_type = None
    content_file_paths: list[str] = []
    if replacing_content:
        content_type = homework_service.validate_content(content_url, len(uploads))
        content_file_paths = await _save_materials(uploads)

    assignment = await homework_service.update_assignment(
        db, assignment, title or None, submission_mode, content_type,
        content_url if replacing_content else None, content_file_paths,
    )
    enriched = await _enrich(db, [assignment])
    return enriched[0]


@router.post("/{assignment_id}/duplicate", response_model=list[HomeworkAssignmentOut], status_code=status.HTTP_201_CREATED)
async def duplicate_homework(
    assignment_id: uuid.UUID,
    current_user: CurrentUser,
    db: DbSession,
    student_ids: list[str] = Form([]),
    group_ids: list[str] = Form([]),
) -> list[HomeworkAssignmentOut]:
    """Sends the same title/content/submission mode as an existing assignment to a
    newly chosen set of recipients (tutor/HomeworkTab.vue's "Скопировать" button) -
    reuses the source's already-uploaded files/link as-is, no re-upload needed."""
    _require_tutor(current_user)
    profile = await tutor_service.get_profile_by_user_id(db, current_user.id)
    source = await homework_service.get_assignment_or_404(db, assignment_id)
    if source.tutor_id != profile.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Это не ваше задание")

    if not student_ids and not group_ids:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Укажите хотя бы одного получателя")

    source_paths = [f.file_path for f in source.content_files]
    created = []
    for student_id in student_ids:
        created.append(
            await homework_service.create_assignment_for_student(
                db, profile, uuid.UUID(student_id), source.title, source.content_type,
                source.content_url, source_paths, source.submission_mode, source.due_at,
            )
        )
    for group_id in group_ids:
        created.append(
            await homework_service.create_assignment_for_group(
                db, profile, uuid.UUID(group_id), source.title, source.content_type,
                source.content_url, source_paths, source.submission_mode, source.due_at,
            )
        )

    return await _enrich(db, created)


@router.get("/tutor/me", response_model=list[HomeworkAssignmentOut])
async def list_my_assignments(current_user: CurrentUser, db: DbSession) -> list[HomeworkAssignmentOut]:
    _require_tutor(current_user)
    profile = await tutor_service.get_profile_by_user_id(db, current_user.id)
    rows = await homework_service.list_assignments_for_tutor(db, profile.id)
    return await _enrich(db, rows)


@router.get("/tutor/me/student-status", response_model=dict[str, str])
async def my_students_homework_status(current_user: CurrentUser, db: DbSession) -> dict[str, str]:
    _require_tutor(current_user)
    profile = await tutor_service.get_profile_by_user_id(db, current_user.id)
    status_map = await homework_service.get_student_status_map(db, profile.id)
    return {str(student_id): value for student_id, value in status_map.items()}


@router.get("/tutor/me/students/{student_id}", response_model=list[StudentHomeworkOut])
async def student_homework_for_tutor(
    student_id: uuid.UUID, current_user: CurrentUser, db: DbSession
) -> list[StudentHomeworkOut]:
    _require_tutor(current_user)
    profile = await tutor_service.get_profile_by_user_id(db, current_user.id)
    items = await homework_service.list_student_homework_for_tutor(db, profile.id, student_id)
    return [StudentHomeworkOut(**item) for item in items]


@router.get("/{assignment_id}/submissions", response_model=list[HomeworkSubmissionOut])
async def list_submissions(assignment_id: uuid.UUID, current_user: CurrentUser, db: DbSession) -> list[HomeworkSubmissionOut]:
    _require_tutor(current_user)
    profile = await tutor_service.get_profile_by_user_id(db, current_user.id)
    assignment = await homework_service.get_assignment_or_404(db, assignment_id)
    if assignment.tutor_id != profile.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Это не ваше задание")
    rows = await homework_service.list_submissions_for_assignment(db, assignment_id)
    names = await booking_service.get_student_names(db, [r.student_id for r in rows])
    return [_submission_out(row, names.get(row.student_id)) for row in rows]


@router.delete("/{assignment_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_assignment(assignment_id: uuid.UUID, current_user: CurrentUser, db: DbSession) -> None:
    _require_tutor(current_user)
    profile = await tutor_service.get_profile_by_user_id(db, current_user.id)
    assignment = await homework_service.get_assignment_or_404(db, assignment_id)
    if assignment.tutor_id != profile.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Это не ваше задание")
    await homework_service.delete_assignment(db, assignment)


@router.get("/me", response_model=list[StudentHomeworkOut])
async def my_homework(current_user: CurrentUser, db: DbSession) -> list[StudentHomeworkOut]:
    _require_student(current_user)
    items = await homework_service.list_homework_for_student(db, current_user.id)
    return [StudentHomeworkOut(**item) for item in items]


@router.post("/submissions/{submission_id}/done", response_model=HomeworkSubmissionOut)
async def mark_done(submission_id: uuid.UUID, current_user: CurrentUser, db: DbSession) -> HomeworkSubmissionOut:
    _require_student(current_user)
    submission = await homework_service.get_submission_or_404(db, submission_id)
    submission = await homework_service.mark_submission_done(db, submission, current_user)
    return HomeworkSubmissionOut.model_validate(submission, from_attributes=True)


@router.patch("/submissions/{submission_id}/status", response_model=HomeworkSubmissionOut)
async def set_submission_status(
    submission_id: uuid.UUID, payload: HomeworkSubmissionStatusUpdate, current_user: CurrentUser, db: DbSession
) -> HomeworkSubmissionOut:
    _require_tutor(current_user)
    if payload.status not in (s.value for s in HomeworkSubmissionStatus):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Некорректный статус")
    profile = await tutor_service.get_profile_by_user_id(db, current_user.id)
    submission = await homework_service.get_submission_or_404(db, submission_id)
    submission = await homework_service.set_submission_status(db, profile, submission, payload.status)
    return HomeworkSubmissionOut.model_validate(submission, from_attributes=True)


@router.delete("/submissions/{submission_id}/files/{file_id}", response_model=HomeworkSubmissionOut)
async def delete_submission_file(
    submission_id: uuid.UUID, file_id: uuid.UUID, current_user: CurrentUser, db: DbSession
) -> HomeworkSubmissionOut:
    """Убрать ошибочно приложенный файл - пока задание не проверено."""
    _require_student(current_user)
    submission = await homework_service.get_submission_or_404(db, submission_id)
    submission = await homework_service.remove_submission_file(
        db, submission, current_user, file_id
    )
    return HomeworkSubmissionOut.model_validate(submission, from_attributes=True)


@router.post("/submissions/{submission_id}/upload", response_model=HomeworkSubmissionOut)
async def upload_submission(
    submission_id: uuid.UUID,
    current_user: CurrentUser,
    db: DbSession,
    comment: str | None = Form(None),
    files: list[UploadFile] = File(...),
) -> HomeworkSubmissionOut:
    """Приложить к сдаче один или несколько файлов за раз (всего не больше
    homework_service.MAX_HOMEWORK_FILES)."""
    _require_student(current_user)
    submission = await homework_service.get_submission_or_404(db, submission_id)
    uploads = _real_uploads(files)
    if not uploads:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Выберите файл")
    await homework_service.check_can_submit_files(db, submission, current_user, len(uploads))
    file_paths = [
        await file_service.save_upload(f, "homework-submissions", file_service.ALLOWED_ATTACHMENT_TYPES)
        for f in uploads
    ]
    submission = await homework_service.submit_files(db, submission, current_user, file_paths, comment)
    return HomeworkSubmissionOut.model_validate(submission, from_attributes=True)
