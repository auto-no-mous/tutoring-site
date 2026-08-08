import uuid

from pydantic import BaseModel, ConfigDict

from app.schemas.common import UTCDateTime


class SystemNotificationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    event_type: str
    title: str
    body: str
    created_at: UTCDateTime
    read_at: UTCDateTime | None


class NotificationTemplateOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    event_type: str
    role: str
    title: str
    body: str


class NotificationTemplateUpdate(BaseModel):
    title: str
    body: str


class UnreadSummaryOut(BaseModel):
    chat_unread: int
    system_unread: int
    total: int
