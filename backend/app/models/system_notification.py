import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, UUIDPKMixin
from app.utils.time import utcnow


class SystemNotification(UUIDPKMixin, Base):
    """A single in-app notification from the pseudo-user "Системные уведомления"
    (see app.services.system_notification_service). Rendered by the frontend as a
    read-only chat thread - unlike ChatThread this is per-user, not per-(tutor,
    student) pair, and the recipient can never reply to it."""

    __tablename__ = "system_notifications"

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    event_type: Mapped[str] = mapped_column(String(48))
    title: Mapped[str] = mapped_column(String(255))
    body: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=None, default=utcnow, index=True
    )
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class NotificationTemplate(UUIDPKMixin, Base):
    """Admin-editable text for one (event, recipient role) combination - see
    system_notification_service.DEFAULT_TEMPLATES for the seeded defaults and
    system_notification_service.notify for how placeholders are filled in. Most
    events only ever have one role as a recipient (e.g. a student never receives
    GROUP_APPLICATION_RECEIVED), but a few - login/welcome - fire for both roles with
    different wording, so (event_type, role) rather than event_type alone is the key."""

    __tablename__ = "notification_templates"
    __table_args__ = (UniqueConstraint("event_type", "role", name="uq_notification_template_event_role"),)

    event_type: Mapped[str] = mapped_column(String(48))
    role: Mapped[str] = mapped_column(String(16))
    title: Mapped[str] = mapped_column(String(255))
    body: Mapped[str] = mapped_column(Text)
