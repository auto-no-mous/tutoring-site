import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, UUIDPKMixin
from app.models.enums import NotificationChannel, NotificationEvent, NotificationStatus
from app.utils.time import utcnow


class NotificationLog(UUIDPKMixin, Base):
    """Audit log of notifications dispatched via Telegram/email (section 2.7)."""

    __tablename__ = "notification_log"

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    channel: Mapped[str] = mapped_column(String(16), default=NotificationChannel.EMAIL.value)
    event_type: Mapped[str] = mapped_column(String(32), default=NotificationEvent.OTHER.value)
    payload: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(16), default=NotificationStatus.PENDING.value)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=None, default=utcnow, index=True
    )
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
