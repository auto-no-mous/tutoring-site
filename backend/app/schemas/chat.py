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
    # Populated by list_threads (api/v1/chat.py) - not meaningful on the single-thread
    # open/get endpoints, which return before any messages necessarily exist yet.
    unread_count: int = 0
    last_message_preview: str | None = None
    last_message_at: UTCDateTime | None = None


class ChatMessageCreate(BaseModel):
    content: str | None = None


class ChatMessageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    thread_id: uuid.UUID
    sender_id: uuid.UUID
    # Populated by the endpoints (api/v1/chat.py) - lets the group chat view show who
    # said what without a separate lookup per sender_id.
    sender_display_name: str = ""
    content: str | None
    file_path: str | None
    created_at: UTCDateTime
