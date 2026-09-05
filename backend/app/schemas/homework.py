import uuid

from pydantic import BaseModel, ConfigDict

from app.schemas.common import UTCDateTime


class HomeworkAssignmentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tutor_id: uuid.UUID
    student_id: uuid.UUID | None
    group_id: uuid.UUID | None
    title: str | None
    content_type: str
    content_url: str | None
    content_file_path: str | None
    submission_mode: str
    due_at: UTCDateTime | None
    created_at: UTCDateTime
    # Populated by list_my_assignments (api/v1/homework.py) - not meaningful right
    # after create/update, which return before there's anything to aggregate/name.
    status: str = "pending"
    student_display_name: str | None = None
    group_name: str | None = None


class HomeworkSubmissionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    assignment_id: uuid.UUID
    student_id: uuid.UUID
    status: str
    file_path: str | None
    comment: str | None
    submitted_at: UTCDateTime | None


class HomeworkSubmissionStatusUpdate(BaseModel):
    status: str


class StudentHomeworkOut(BaseModel):
    submission_id: uuid.UUID
    assignment_id: uuid.UUID
    tutor_id: uuid.UUID
    group_id: uuid.UUID | None
    # Название необязательно с миграции afc6a11a104d: репетитор может задать домашку
    # одной ссылкой. Здесь оно оставалось обязательным, и список домашних заданий у
    # такого ученика падал с 500 вместо того, чтобы показать задание без заголовка.
    title: str | None
    content_type: str
    content_url: str | None
    content_file_path: str | None
    submission_mode: str
    due_at: UTCDateTime | None
    status: str
    file_path: str | None
    comment: str | None
    submitted_at: UTCDateTime | None
