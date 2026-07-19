import uuid

from pydantic import BaseModel, ConfigDict

from app.schemas.common import UTCDateTime


class ChatThreadOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    type: str
    tutor_id: uuid.UUID
    student_id: uuid.UUID | None
    group_id: uuid.UUID | None
    display_title: str = ""


class ChatMessageCreate(BaseModel):
    content: str | None = None


class ChatMessageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    thread_id: uuid.UUID
    sender_id: uuid.UUID
    content: str | None
    file_path: str | None
    created_at: UTCDateTime
