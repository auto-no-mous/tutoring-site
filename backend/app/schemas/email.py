import uuid

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.schemas.common import UTCDateTime


class EmailLogOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    direction: str
    kind: str
    status: str
    address_from: str
    address_to: str
    subject: str
    body_preview: str
    user_id: uuid.UUID | None
    sent_by_id: uuid.UUID | None
    error: str | None
    created_at: UTCDateTime


class EmailLogPageOut(BaseModel):
    entries: list[EmailLogOut]
    total: int
    page: int
    page_size: int


class EmailStatsOut(BaseModel):
    sent_24h: int
    failed_24h: int
    sent_30d: int
    failed_30d: int
    received_30d: int
    # Разбивка отправленных за 30 дней по типам писем (verification/password_reset/admin).
    by_kind: dict[str, int]
    last_sent_at: UTCDateTime | None


class AdminEmailSend(BaseModel):
    """Ручное письмо из админки. Получатели задаются пользователями сайта и/или
    произвольными адресами; каждому уходит отдельное письмо, чтобы адреса
    получателей не видели друг друга."""

    user_ids: list[uuid.UUID] = Field(default_factory=list)
    emails: list[EmailStr] = Field(default_factory=list)
    subject: str = Field(min_length=1, max_length=200)
    body: str = Field(min_length=1, max_length=5000)


class AdminEmailSendResult(BaseModel):
    sent: int
    failed: int
    # Пользователи без почты или с неподтверждённым адресом - им не отправляли.
    skipped: list[str]
