import uuid

from pydantic import BaseModel, ConfigDict

from app.schemas.common import UTCDateTime


class HomeworkAssignmentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tutor_id: uuid.UUID
    student_id: uuid.UUID | None
    group_id: uuid.UUID | None
    title: str
    content_type: str
    content_url: str | None
    content_file_path: str | None
    submission_mode: str
    due_at: UTCDateTime | None
    created_at: UTCDateTime


class HomeworkSubmissionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    assignment_id: uuid.UUID
    student_id: uuid.UUID
    status: str
    file_path: str | None
    comment: str | None
    submitted_at: UTCDateTime | None


class StudentHomeworkOut(BaseModel):
    submission_id: uuid.UUID
    assignment_id: uuid.UUID
    tutor_id: uuid.UUID
    group_id: uuid.UUID | None
    title: str
    content_type: str
    content_url: str | None
    content_file_path: str | None
    submission_mode: str
    due_at: UTCDateTime | None
    status: str
    file_path: str | None
    comment: str | None
    submitted_at: UTCDateTime | None
